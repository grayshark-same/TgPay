# Архитектура tgpay — целевой дизайн и план миграции

Документ описывает целевую архитектуру платёжного Telegram-бота tgpay,
спроектированную начисто, без обязательств обратной совместимости с текущим
кодом, — и реалистичный план перехода с работающего прода на эту архитектуру
без потери денег, балансов и истории.

Контекст: это действующий бизнес с реальными деньгами. Один VPS, Python;
целевая упаковка — Docker Compose, код и деплой — через GitHub.
Целевая архитектура обязана решать by design те проблемы, которые
сегодня приходится чинить руками: двойные начисления, потерю users.db при
деплое, сброс счётчика заявок, падение polling-потока из-за одного хэндлера,
рассинхрон цен, бэкап «на честном слове».

---

## 1. Текущее состояние (as-is), честно

### 1.1. Процессы

| Процесс | Файл | Что делает |
|---|---|---|
| Основной бот | `bot.py` (~7700 строк) | все хэндлеры, DDL шести SQLite-баз при импорте, 3 daemon-потока (курс валют, eSIM-списания, бэкап в 15:00 МСК), polling |
| Mini-app API | `api.py` (FastAPI) | авторизация Telegram, покупки из веб-аппа; пишет в те же файлы, что и бот |
| Вебхуки платежей | `nicepay.py`, `cryptomus.py` (FastAPI) | приём колбэков; захардкоженный токен бота, `from bot import …` (импорт всего монолита с его side effects) |
| Бот поддержки | `support_bot.py` | отдельный токен (захардкожен), python-telegram-bot |
| Такси-бот | `taxi_bot.py` | отдельный токен (захардкожен), telebot |
| Бэкап | `backup.py` | локальный снапшот 8 баз + отправка **только users.db** в архив-группы |

### 1.2. Данные

9 SQLite-баз (`files/users.db`, `arhive.db`, `user_data.db`, `mods.db`,
`donations.db`, `penalties.db`, `cards.db`, `codes.db`, `otzivi.db`)
плюс ~12 JSON-файлов, которые читаются и перезаписываются целиком из
нескольких мест и нескольких процессов: `esim.json` (каталог/цены),
`eSIM/esim_answer.json` (сток eSIM), `files/count.json` (счётчик заявок),
`promocode.json`, `ref_data.json`, `valuta.json`, `analytic_clicks_data.json`,
`yoomany_requisites.json`, `Yoomoney/pending_applications.json` и др.
Все пути относительные, cwd — корень проекта.

### 1.3. Реестр проблем, подтверждённых кодом и практикой

| # | Проблема | Где в коде | Последствие (случалось) |
|---|---|---|---|
| P1 | Баланс меняется из ~6 функций, часть **не пишет** в `balance_log` (`update_balanse`, `change_deposit`, реф. балансы) | `help.py` | леджер неполный, инциденты с балансами не разбираются по журналу |
| P2 | Нет идемпотентности начислений: Lava-поллер и кнопка «проверить оплату» начисляют независимо; поллер запускается потоком на каждый инвойс и может дублироваться | `bot.py: poll_lava_payment`, `check_lava_payment` | двойные начисления |
| P3 | Поллеры платежей живут в памяти — рестарт бота убивает их, оплаченные инвойсы «повисают» | `bot.py: threading.Thread(poll_lava_payment)` | ручной разбор оплат после каждого деплоя |
| P4 | `count.json`: read-modify-write без блокировок из **двух процессов** (bot и api); файл сбрасывался | `help.py: to_arhiv`, `api.py` | переиспользование номеров заявок |
| P5 | Цена хранится в `esim.json["price"]` и продублирована текстом в `tariff` | `esim.json` | рассинхрон цены в кнопке и в описании |
| P6 | Сток eSIM — RMW целого JSON; блокировка есть только внутри процесса бота | `bot.py: _deliver_esim_units` | гонки при параллельных покупках |
| P7 | Деплой scp-ом поверх рабочей директории | практика | затирание `users.db`, восстанавливали по экспорту TG-канала |
| P8 | В TG-архив ежедневно уходит только `users.db`; локальный снапшот — `shutil.copy2` под живой записью; восстановимость не проверяется | `backup.py`, `bot.py: _daily_db_backup_loop` | восстановление — героизм, а не процедура |
| P9 | Незащищённые вызовы Telegram API (`delete_message` и др.) внутри хэндлеров; одна ошибка хэндлера валит polling-цикл | `bot.py`, 54 вызова `delete_message` | бот «зависает» до рестарта |
| P10 | Архив-рассылки в мёртвые группы: ошибки молча глотаются на каждой отправке навсегда | `send_to_archives` | шум в логах, потеря части архива |
| P11 | `print()` вместо логирования, нет сквозного идентификатора заявки в логах | везде | инциденты не восстанавливаются по логам |
| P12 | Секреты в git: ключи Lava, токены ботов (nicepay/cryptomus/support/taxi), merchant-JWT, ключ VPN-API | `bot.py`, `nicepay.py`, `cryptomus.py`, `support_bot.py`, `taxi_bot.py`, `help.py` | компрометация = потеря денег |
| P13 | Таблица `users` без PRIMARY KEY (`id INTEGER NOT NULL`) — возможны дубли строк | `bot.py` DDL | UPDATE по дублю обновляет обе строки / баланс двоится |
| P14 | Импорт `bot.py` имеет side effects: DDL, 3 потока, chdir; `nicepay.py` импортирует монолит целиком | `bot.py` верхний уровень | нельзя тестировать, вебхук-процессы тащат за собой всё |
| P15 | Деньги хранятся во float (`REAL`) | вся схема | копеечные расхождения при сложении |

Целевая архитектура ниже закрывает каждый пункт конструктивно, а не заплаткой.

---

## 2. Ключевые решения (и почему)

1. **Модульный монолит, один репозиторий (GitHub), один VPS, Docker Compose.**
   Нагрузка телеграм-бота не требует микросервисов; команда маленькая.
   Код живёт в приватном GitHub-репозитории — он источник правды; деплой —
   `git pull && docker compose up -d --build` (та же модель, что уже работает
   у vpn_bot на этом сервере). Разделение — на уровне пакетов и
   контейнеров (бот / api / спутники), не сервисов.

2. **pyTelegramBotAPI (telebot) остаётся.** Переписывание на aiogram не решает
   ни одной проблемы из реестра — все они в слое данных и денег. Меняем
   структуру, а не фреймворк.

3. **Одна база `data/tgpay.db` (SQLite, WAL) вместо 9 баз и 12 JSON.**
   SQLite в WAL-режиме с `busy_timeout` спокойно держит несколько процессов
   на одном хосте и такую нагрузку. Одна база = один бэкап, одна транзакция
   на бизнес-операцию (списание + леджер + заявка + сток атомарно), один
   `integrity_check`. Postgres — осознанно отложен (см. §12): он даёт выгоду
   только при выносе процессов на другие хосты, а стоит отдельного
   администрирования на этом же VPS.

4. **Деньги — только через леджер.** Таблица `ledger` — единственный источник
   правды об изменениях баланса; `users.balance` — производная величина,
   обновляемая в той же транзакции и сверяемая джобом. Каждая запись леджера
   имеет уникальный `idem_key` — идемпотентность начислений обеспечивается
   схемой (UNIQUE), а не дисциплиной программистов.

5. **Платёж — это строка в БД со статус-машиной, а не поток в памяти.**
   Один фоновой watcher опрашивает все pending-платежи; кнопка «проверить»
   и вебхук вызывают ту же функцию `settle()`. Дедупликация поллеров и
   переживание рестартов — by design.

6. **Код и данные разделены физически.** Всё изменяемое — в `data/`
   (в `.gitignore`), в контейнеры она попадает только как volume.
   Деплой — `git pull` + пересборка образа; образ по определению не содержит
   данных, затирание базы деплоем становится невозможным классом ошибок.

7. **Импорт любого модуля не имеет side effects.** Ни DDL, ни потоков,
   ни chdir, ни создания TeleBot на верхнем уровне. Всё стартует явно в
   `main()` точек входа. Это делает код тестируемым и позволяет вебхукам
   импортировать домен, не поднимая бота.

8. **Секреты — только в `.env` на сервере.** Всё, что сейчас захардкожено,
   выносится и **ротируется** (токены уже в истории git — считаем их
   скомпрометированными).

---

## 3. Целевая структура

```
tgpay/
├── pyproject.toml              # зависимости, dev-инструменты
├── Dockerfile                  # один образ на все процессы (меняется только команда)
├── docker-compose.yml          # bot / api / support / taxi; volume ./data, env_file .env
├── .github/
│   └── workflows/
│       └── ci.yml              # тесты + линт на каждый push/PR (деплой — вручную, см. ниже)
├── .env                        # секреты (только на сервере, в .gitignore)
├── data/                       # ВСЁ изменяемое состояние (в .gitignore, volume контейнеров)
│   ├── tgpay.db                # единая база (WAL)
│   ├── media/                  # картинки тарифов, шаблоны PDF, логотипы
│   └── backups/                # локальные снапшоты
├── migrations/                 # нумерованные .sql + простой runner (без Alembic)
│   ├── 0001_init.sql
│   └── ...
├── scripts/
│   ├── migrate_legacy.py       # разовый перенос files/*.db + JSON → tgpay.db
│   ├── reconcile.py            # сверки: SUM(ledger)==balance, legacy vs new
│   └── restore_check.py        # проверка восстановимости бэкапа
└── tgpay/                      # python-пакет
    ├── bot.py                  # тонкая точка входа: main() → tg.app.run()
    │                           #   (python -m tgpay.bot; сам ничего не содержит)
    ├── config.py               # ЕДИНСТВЕННОЕ чтение .env; пути, ID групп, админы
    ├── db.py                   # connect(): WAL, busy_timeout, foreign_keys; миграции
    ├── log.py                  # настройка logging, контекст request-id
    │
    ├── domain/                 # бизнес-логика. НЕ импортирует telebot/fastapi
    │   ├── ledger.py           # apply()/balance() — все операции с деньгами
    │   ├── orders.py           # заявки: номер, статус, архивная запись
    │   ├── users.py            # регистрация, ранги, активность, блокировки
    │   ├── esim.py             # каталог, сток (claim), выдача, PDF-квитанции
    │   ├── esim_subs.py        # подписки, идемпотентные списания по периодам
    │   ├── referral.py         # реф. начисления (через ledger)
    │   ├── promocodes.py       # промокоды
    │   ├── penalties.py        # штрафы/касса модераторов
    │   ├── vpn.py              # интеграция с vpn_bot (БД + API)
    │   └── reviews.py          # отзывы, карточки (PIL)
    │
    ├── payments/               # провайдеры и жизненный цикл платежа
    │   ├── registry.py         # create()/settle()/expire() — статус-машина
    │   ├── watcher.py          # единый цикл опроса pending-платежей
    │   ├── lava.py             # клиент API Lava
    │   ├── cryptomus.py        # клиент + разбор вебхука
    │   ├── nicepay.py          # клиент + разбор вебхука
    │   ├── yoomoney.py         # проверка переводов
    │   └── vouchers.py         # ваучеры/коды
    │
    ├── tg/                     # телеграм-слой основного бота
    │   ├── app.py              # создание TeleBot, регистрация хэндлеров, run()
    │   ├── middleware.py       # обёртка каждого хэндлера: try/except + лог + request-id
    │   ├── safe.py             # safe_delete/safe_edit/safe_send (ApiTelegramException)
    │   ├── archive.py          # рассылки в архив-группы с реестром живых групп
    │   ├── keyboards.py
    │   ├── states.py           # именованные состояния FSM (enum), хранение в БД
    │   └── handlers/           # по доменам: start.py, deposit.py, esim.py,
    │                           #   replenish.py, admin.py, referral.py, ...
    │
    ├── jobs/                   # фоновые задачи
    │   ├── scheduler.py        # один поток-планировщик с журналом запусков в БД
    │   ├── rates.py            # курс валют (кэш в БД, не в глобале)
    │   ├── esim_charges.py     # ежемесячные списания
    │   ├── backup.py           # снапшот + отправка в TG + ротация
    │   └── reconcile.py        # ежедневная сверка леджера и балансов
    │
    ├── api/                    # FastAPI: mini-app + ВСЕ платёжные вебхуки
    │   ├── app.py
    │   ├── miniapp.py
    │   └── webhooks.py         # /cryptomus, /nicepay → payments.settle()
    │
    ├── support/                # бот поддержки (отдельный процесс)
    └── taxi/                   # такси-бот (отдельный процесс)
```

### Точки входа: Docker Compose

Один `Dockerfile` (python-slim, зависимости из `pyproject.toml`), четыре
сервиса в `docker-compose.yml` — различаются только командой:

| Сервис | Команда | Примечание |
|---|---|---|
| `bot` | `python -m tgpay.bot` | polling + scheduler + watcher |
| `api` | `uvicorn tgpay.api.app:app --host 0.0.0.0 --port 8000` | mini-app + вебхуки (один процесс вместо api.py+nicepay.py+cryptomus.py) |
| `support` | `python -m tgpay.support` | |
| `taxi` | `python -m tgpay.taxi` | |

Общие для всех сервисов: `restart: unless-stopped` (замена systemd
`Restart=always`), `env_file: .env`, volume `./data:/app/data`,
`logging: json-file` с ротацией (логи — `docker logs tgpay-bot`).
Пути к данным собираются в `config.py` от корня пакета — вопрос
«какая у процесса cwd» перестаёт быть источником багов.

### Деплой через GitHub

1. Код — в приватном GitHub-репозитории; на сервере — клон с deploy key
   (read-only). Прямой scp файлов на сервер запрещён: всё, что не прошло
   через git, на прод не попадает (история, ревью, откат `git revert`).
2. Деплой: `cd /root/tgpay && git pull && docker compose up -d --build`
   (пересобираются и перезапускаются только изменившиеся сервисы).
   Та же команда — на тестовом стенде (отдельный клон + свой `.env`
   с тестовым токеном).
3. CI (GitHub Actions, `ci.yml`): на каждый push/PR — линт + unit-тесты
   (`domain`, `payments`); мёржить в `main` можно только зелёным.
   Автодеплой по push намеренно НЕ включается: прод катится руками
   после теста (правило «не деплоить в прод без разрешения»).
4. Откат = `git revert` (или `git checkout <tag>`) + тот же
   `docker compose up -d --build`; данные не затрагиваются (volume).

---

## 4. Правила зависимостей слоёв

```
tg, api, support, taxi   →  payments, domain, jobs(запуск), config, log, db
jobs                     →  payments, domain, config, log, db
payments                 →  domain(ledger, orders), config, log, db
domain                   →  config, log, db
db, log                  →  config
config                   →  stdlib + dotenv
```

1. **Вниз можно, вверх нельзя.** `domain` не знает про Telegram и FastAPI.
   Всё, что нужно отправить пользователю по итогам доменной операции,
   возвращается результатом (dataclass), а отправляет его вызывающий слой.
2. **Никаких прямых `sqlite3.connect` вне `db.py`** и никаких `open()` для
   файлов данных вне `domain`/`config`. Одна точка настройки соединения
   (WAL, busy_timeout, foreign_keys, row_factory).
3. **Никаких изменений баланса вне `domain/ledger.py`** — это правило №1
   всего проекта, оно проверяется grep-ом на код-ревью:
   `UPDATE users SET balance` встречается ровно в одном файле.
4. **Импорт без side effects** (см. §2 п.7) — проверяется тестом
   `import tgpay.<каждый модуль>` в CI/локально.

---

## 5. Схема данных (целевая)

Одна база `data/tgpay.db`. Деньги — INTEGER в копейках. Ниже — ядро схемы;
полный DDL живёт в `migrations/0001_init.sql`.

```sql
CREATE TABLE users (
    id            INTEGER PRIMARY KEY,          -- tg id; PK, а не «просто колонка»
    username      TEXT,
    balance       INTEGER NOT NULL DEFAULT 0,   -- копейки; производная от ledger
    ref_balance   INTEGER NOT NULL DEFAULT 0,
    referrer_id   INTEGER REFERENCES users(id),
    total_spent   INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    last_seen_at  TEXT,
    blocked       INTEGER NOT NULL DEFAULT 0
    -- Неотрицательность НЕ закрепляется CHECK-ом: в легаси есть исторические
    -- отрицательные балансы, и они переносятся как есть. Для новых операций
    -- неминус гарантирует ledger.apply (условие WHERE balance + :a >= 0).
);

-- ЕДИНЫЙ леджер: единственный источник правды об изменениях баланса
CREATE TABLE ledger (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    amount        INTEGER NOT NULL,             -- +начисление / -списание, копейки
    balance_after INTEGER NOT NULL,
    kind          TEXT NOT NULL,                -- deposit|purchase|refund|adjust|referral|sub_charge|withdraw
    idem_key      TEXT NOT NULL UNIQUE,         -- идемпотентность на уровне схемы
    order_id      INTEGER REFERENCES orders(id),
    actor         TEXT NOT NULL,                -- 'user' | 'admin:<id>' | 'provider:lava' | 'job:esim_subs'
    comment       TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_ledger_user ON ledger(user_id, id);

-- Заявки: замена count.json + arhive.db/uslugi.
-- AUTOINCREMENT гарантирует монотонность и невозможность переиспользования номера.
-- sqlite_sequence сидируется текущим значением счётчика при миграции.
CREATE TABLE orders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,   -- номер заявки = request-id в логах
    user_id     INTEGER NOT NULL REFERENCES users(id),
    service     TEXT NOT NULL,                        -- 'esim:Vodafone', 'topup:ua', ...
    amount      INTEGER NOT NULL,
    status      TEXT NOT NULL DEFAULT 'created',      -- created|approved|declined|canceled
    payload     TEXT,                                 -- JSON: номер телефона, оператор и т.п.
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at   TEXT
);

-- Платежи: замена потоков-поллеров в памяти
CREATE TABLE payments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    provider     TEXT NOT NULL,                 -- lava|cryptomus|nicepay|yoomoney|voucher|manual
    external_id  TEXT NOT NULL,                 -- order_id/invoice_id у провайдера
    user_id      INTEGER NOT NULL REFERENCES users(id),
    amount       INTEGER,                       -- может уточняться провайдером
    status       TEXT NOT NULL DEFAULT 'pending', -- pending|succeeded|expired|canceled
    message_id   INTEGER,                       -- «⏳ ожидаем оплату» для подчистки
    expires_at   TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    settled_at   TEXT,
    UNIQUE (provider, external_id)
);
CREATE INDEX idx_payments_pending ON payments(status) WHERE status = 'pending';

-- Каталог eSIM: замена esim.json. Цена хранится ОДИН раз;
-- текст тарифа — шаблон с {price}/{monthly}, рендерится из этих же полей → P5 закрыт.
CREATE TABLE esim_catalog (
    operator     TEXT PRIMARY KEY,              -- Vodafone|Kievstar|Lifecell|France35GB|...
    title        TEXT NOT NULL,
    price        INTEGER NOT NULL,
    cost_uah     REAL,
    cost_rub     INTEGER,                       -- для операторов с фикс. себестоимостью
    monthly_uah  REAL,                          -- абонплата подписки (NULL = нет)
    tariff_tpl   TEXT NOT NULL,                 -- текст с плейсхолдерами
    image        TEXT,
    active       INTEGER NOT NULL DEFAULT 1
);

-- Сток eSIM: замена eSIM/esim_answer.json. Выдача — атомарный claim.
CREATE TABLE esim_stock (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    operator     TEXT NOT NULL REFERENCES esim_catalog(operator),
    payload      TEXT NOT NULL,                 -- JSON: file_id/картинка/pdf_fields
    status       TEXT NOT NULL DEFAULT 'free',  -- free|issued
    order_id     INTEGER REFERENCES orders(id),
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    issued_at    TEXT
);
CREATE INDEX idx_stock_free ON esim_stock(operator) WHERE status = 'free';

-- Реестр архив-групп: замена жёсткого списка из .env → P10 закрыт
CREATE TABLE archive_targets (
    chat_id     INTEGER PRIMARY KEY,
    active      INTEGER NOT NULL DEFAULT 1,
    fail_count  INTEGER NOT NULL DEFAULT 0,
    last_error  TEXT
);

-- Прочие домены — по той же логике таблиц:
-- esim_subscriptions (+ уникальность списания за период, см. §7),
-- promocodes, promocode_uses, referral_rates, penalties, mod_cash,
-- donations, reviews, cards, vouchers, user_states, settings(k,v),
-- analytics_clicks, withdraw_requests.
```

Что уходит совсем: `count.json` (→ `orders` AUTOINCREMENT), `esim.json`
(→ `esim_catalog`), `esim_answer.json` (→ `esim_stock`), `promocode.json`,
`ref_data.json`, `valuta.json` и `analytic_clicks_data.json` (→ таблицы
`settings`/`rates`/`analytics_clicks`), `Yoomoney/pending_applications.json`
(→ `payments` с provider='yoomoney'). JSON как формат остаётся только внутри
колонок `payload`.

---

## 6. Деньги: леджер и идемпотентность

Единственная функция, меняющая баланс:

```python
# domain/ledger.py
def apply(conn, *, user_id: int, amount: int, kind: str, idem_key: str,
          actor: str, order_id: int | None = None, comment: str = "") -> LedgerResult:
    """Атомарно изменить баланс и записать операцию.
    Повторный вызов с тем же idem_key — no-op, возвращает уже применённую запись."""
    with conn:  # BEGIN IMMEDIATE ... COMMIT
        try:
            cur = conn.execute(
                "UPDATE users SET balance = balance + :a "
                "WHERE id = :u AND balance + :a >= 0",
                {"a": amount, "u": user_id})
            if cur.rowcount == 0:
                raise InsufficientFunds(user_id, amount)
            balance_after = conn.execute(
                "SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()[0]
            conn.execute(
                "INSERT INTO ledger (user_id, amount, balance_after, kind, "
                " idem_key, order_id, actor, comment) VALUES (?,?,?,?,?,?,?,?)",
                (user_id, amount, balance_after, kind, idem_key, order_id, actor, comment))
            return LedgerResult(applied=True, balance_after=balance_after)
        except sqlite3.IntegrityError:   # UNIQUE(idem_key) — уже проведено
            return LedgerResult(applied=False, balance_after=current_balance(conn, user_id))
```

Соглашения по `idem_key`:

| Операция | idem_key |
|---|---|
| Начисление по платежу | `pay:{provider}:{external_id}` |
| Списание за заявку | `order:{order_id}` |
| Реф. начисление | `ref:{order_id}` |
| Абонплата eSIM за период | `esimsub:{sub_id}:{YYYY-MM}` |
| Ручная корректировка админом | `adj:{uuid}` (генерируется при подтверждении, не при вводе) |

Инварианты денег (проверяются джобом `jobs/reconcile.py` ежедневно,
расхождение — алерт в админ-группу):

1. `users.balance == COALESCE(SUM(ledger.amount) по user_id, 0) + начальное сальдо миграции`
   (сальдо фиксируется записью `kind='adjust', comment='migration opening balance'`).
2. Новая операция не может увести баланс ниже нуля — гарантируется
   `ledger.apply` (легаси-минусы, перенесённые миграцией, допускаются и
   постепенно гасятся; список таких пользователей — в отчёте reconcile).
3. Каждый `payments.status='succeeded'` имеет ровно одну строку леджера
   с `idem_key = pay:{provider}:{external_id}`.

Это закрывает P1, P2 (частично — см. §7), P13, P15.

---

## 7. Платежи: статус-машина вместо потоков

Жизненный цикл: `pending → succeeded | expired | canceled`.
Переход в `succeeded` — единственное место, откуда вызывается `ledger.apply`:

```python
# payments/registry.py
def settle(payment_id: int, provider_status: str, amount: int) -> SettleResult:
    # шлюз №1: перевести статус может только один вызов
    cur = conn.execute(
        "UPDATE payments SET status='succeeded', amount=?, settled_at=datetime('now') "
        "WHERE id = ? AND status = 'pending'", (amount, payment_id))
    if cur.rowcount == 0:
        return SettleResult(already=True)
    # шлюз №2: идемпотентность леджера (страхует от логических ошибок выше)
    ledger.apply(conn, user_id=..., amount=amount, kind="deposit",
                 idem_key=f"pay:{p.provider}:{p.external_id}",
                 actor=f"provider:{p.provider}")
    ...
```

**Watcher** (`payments/watcher.py`) — один цикл в scheduler-е, каждые
10–15 секунд: `SELECT * FROM payments WHERE status='pending'`, для каждого —
запрос статуса у провайдера, затем `settle()` / `expire()`. Следствия:

- поток-на-инвойс исчезает как класс → дубликатов поллеров не бывает (P2);
- рестарт процесса ничего не теряет — pending лежит в БД (P3);
- кнопка «проверить оплату» вызывает тот же код для одного платежа —
  гонка с watcher-ом безопасна благодаря двум шлюзам;
- вебхуки cryptomus/nicepay в `api/webhooks.py` тоже сводятся к `settle()`
  (с проверкой подписи); три FastAPI-процесса сливаются в один;
- по `expired` watcher подчищает сообщение «⏳ ожидаем оплату» через
  `payments.message_id` и `safe_delete`.

Списания по eSIM-подпискам идемпотентны по периоду
(`esimsub:{sub_id}:{YYYY-MM}`): даже если джоб запустится дважды
(рестарт, ручной прогон) — второе списание не пройдёт.

---

## 8. Надёжность Telegram-слоя

1. **Middleware-обёртка каждого хэндлера** (`tg/middleware.py`): регистрация
   хэндлеров идёт через декоратор, который ловит любое исключение, пишет его
   в лог с request-id и user_id, отвечает пользователю «произошла ошибка,
   мы уже знаем» и, при всплеске, шлёт троттлированный алерт в админ-группу.
   Polling-цикл не видит исключений хэндлеров вообще (P9).
2. **`tg/safe.py`**: `safe_delete`, `safe_edit`, `safe_send` — обёртки над
   Telegram API, глотающие ожидаемые `ApiTelegramException`
   («message to delete not found», «bot was blocked») и логирующие остальное.
   Голые `bot.delete_message` в хэндлерах запрещены (grep-правило).
3. **Архив-рассылки** (`tg/archive.py`): отправка по `archive_targets`
   с `active=1`; после N подряд ошибок группа деактивируется и админам
   уходит уведомление — мёртвые группы перестают маскировать потерю
   архива (P10).
4. **FSM**: именованные enum-состояния (`states.py`) вместо `range(80)`,
   хранение в таблице `user_states` — состояние переживает рестарт;
   `register_next_step_handler` не используется (теряется при рестарте).
5. **Polling**: `infinity_polling(logger_level=…)` + docker
   `restart: unless-stopped` как последний рубеж.

---

## 9. Фоновые задачи

Один поток-планировщик (`jobs/scheduler.py`) с таблицей `job_runs`
(job, started_at, finished_at, ok, detail) вместо трёх самодельных
`while True + sleep` потоков:

| Джоб | Период | Замечание |
|---|---|---|
| `payments.watcher` | 10–15 с | §7 |
| `rates.refresh` | 1 ч | курс — в таблицу `rates`, а не в глобальную переменную |
| `esim_charges` | 1 ч | идемпотентно по периоду |
| `backup` | ежедневно 03:00 и 15:00 МСК | §11 |
| `reconcile` | ежедневно | §6, отчёт в админ-группу |
| `restore_check` | еженедельно | §11 |

Каждый тик джоба обёрнут в try/except с логом — упавший джоб не убивает
планировщик и виден в `job_runs`.

---

## 10. Наблюдаемость

1. **`print` запрещён** (grep-правило/линтер). Только `logging` через
   `tgpay/log.py`: единый формат
   `%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s`,
   вывод в stdout → docker json-file с ротацией (`docker logs tgpay-bot`).
2. **request-id = номер заявки (`orders.id`)**, а до создания заявки —
   `u<user_id>`. Прокидывается через `contextvars` в middleware — каждый
   лог внутри обработки помечен автоматически. Инцидент «куда делись деньги
   по заявке 16208» разбирается одним
   `docker logs tgpay-bot | grep '\[16208\]'` плюс выборкой из `ledger`
   по `order_id`.
3. **Ошибки — в админ-группу** с троттлингом (не чаще раза в N минут на
   однотипную), чтобы алерты не превращались в шум.
4. Дешёвые метрики — SQL по своим же таблицам: объём начислений за день
   (`ledger`), конверсия платежей (`payments`), остаток стока (`esim_stock`),
   здоровье джобов (`job_runs`). Отдельная инфраструктура метрик не нужна.

---

## 11. Бэкапы и восстановление

Сейчас уже есть и **сохраняется**: локальные снапшоты + отправка базы в
TG-архив-группы (это спасло бизнес при затирании users.db). Целевой процесс
делает это корректным и проверяемым:

1. **Снапшот** (`jobs/backup.py`, дважды в день):
   `PRAGMA wal_checkpoint(TRUNCATE)` → снапшот через **`sqlite3` backup API**
   (консистентен под живой записью; `shutil.copy2` — нет, P8) →
   zip вместе с `data/media` → `data/backups/tgpay-YYYYMMDD-HHMM.zip`.
2. **Оффсайт**: zip уходит документом во все активные `archive_targets`.
   Теперь это **вся база** (леджер, заявки, сток, промокоды), а не только
   users.db. TG-группа остаётся честным оффсайтом «бесплатно»; при росте —
   добавить S3-совместимое хранилище тем же джобом.
3. **Ротация**: локально — 14 дневных + 8 недельных; в TG история хранится
   сама.
4. **Проверка восстановимости** (`restore_check`, еженедельно): взять
   последний zip → распаковать во временную директорию →
   `PRAGMA integrity_check` → сравнить `COUNT(users)`, `SUM(balance)`,
   `MAX(orders.id)` с продом → отчёт в админ-группу. Бэкап, который никто
   не пробовал восстановить, бэкапом не считается.
5. **Процедура восстановления** — README в `scripts/`: остановить юниты →
   распаковать zip в `data/` → запустить → `reconcile.py`. Проверяется на
   тестовом стенде при `restore_check`.
6. **Деплой не может тронуть данные**: `data/` в `.gitignore` и подключается
   к контейнерам как volume; деплой — `git pull && docker compose up -d
   --build` (scp поверх рабочей директории запрещён). Образ не содержит
   данных by construction — это закрывает P7 навсегда, а не инструкцией
   «будь осторожен».

---

## 12. Безопасность

1. **Все секреты — в `.env`** (токены четырёх ботов, ключи Lava/Cryptomus/
   NicePay, JWT-секрет mini-app, ключ VPN-API). В коде — только
   `config.py` → `os.environ`.
2. **Ротация утёкших секретов — обязательный пункт миграции** (P12): всё,
   что лежит в истории git, считается скомпрометированным. Ротировать у
   провайдеров и в BotFather, старые ключи отозвать.
3. Вебхуки принимают только подписанные запросы (подпись Lava/Cryptomus/
   NicePay проверяется до любых действий); mini-app — проверка
   Telegram-хэша + JWT (уже есть, переносится).
4. Админство — по таблице/конфигу, а не по спискам id, разбросанным по коду.

---

## 13. Миграция с текущей системы

Философия: **сначала остановить кровотечение денег в текущем коде, затем
freeze-and-cut перенос данных и кода**. Разовый перенос с коротким простоем
честнее «двойной записи» в обе схемы: у бизнеса есть ночные окна, а двойная
запись в живом монолите — это недели риска ради избежания 30 минут простоя.

Инфраструктура уже готова: тестовый стенд `/root/test_bot` (отдельный токен)
и прод `/root/bot` на том же сервере.

### Перенос данных: `scripts/migrate_legacy.py`

Один скрипт, прогоняется многократно на тесте, один раз на проде:

| Источник | Приёмник | Примечание |
|---|---|---|
| `files/users.db: users` | `users` | дедупликация по id (сейчас PK нет!) — при дублях берётся строка с максимальным balance + алерт в отчёт; REAL → копейки (round 2); отрицательные балансы (в проде есть) переносятся как есть — см. §6 |
| `files/users.db: balance_log` | `ledger` | как исторические записи с `idem_key='legacy:<rowid>'`; **сальдо**: `balance - SUM(legacy ledger)` фиксируется записью `kind='adjust', comment='migration opening balance'` — история неполна (P1), и мы это честно оформляем, а не подгоняем |
| `files/arhive.db: uslugi` | `orders` | `sqlite_sequence` сидируется `MAX(number, count.json)` — номера продолжаются, коллизий нет |
| `esim.json` | `esim_catalog` | цена — из `price`; текст → шаблон с `{price}`; расхождения цены и текста выявляются на этом шаге и разрешаются владельцем руками |
| `eSIM/esim_answer.json` | `esim_stock` | |
| `esim_subscriptions` (users.db) | `esim_subscriptions` | |
| `promocode.json`, `ref_data.json`, `valuta.json`, `analytic_clicks_data.json`, `Yoomoney/*` | таблицы | |
| `mods.db`, `penalties.db`, `donations.db`, `otzivi.db`, `cards.db`, `codes.db`, `user_data.db` | таблицы | user_states — из `system_data` |

После прогона — `scripts/reconcile.py` печатает сверку: число пользователей,
суммарный баланс (в копейках), число заявок, `MAX(orders.id)`, остаток стока
по операторам — и сравнивает с legacy-источниками. Расхождение ≠ 0 —
миграция не принимается.

### Cutover (ночью, окно ~30 минут)

1. Остановить старые процессы (`systemctl stop bot api …` — legacy ещё на
   systemd; новые сервисы поднимаются уже в docker).
2. `backup.py` — финальный снапшот legacy (он же rollback-точка).
3. `migrate_legacy.py` → `reconcile.py` → отчёт OK.
4. Старт новых юнитов → smoke-чек-лист (см. ниже) на реальном боте.
5. Rollback-план: остановить новые юниты, запустить старые — legacy-файлы
   не модифицируются миграцией вообще (только чтение).

### Чек-лист эквивалентности (тест-стенд и smoke после cutover)

Фиксированный список сценариев, для каждого сверяется: баланс до/после,
строки `ledger`, запись `orders`, сообщение в архив-группу:

старт/регистрация с реф. ссылкой → пополнение каждым способом (Lava — включая
«кнопка + watcher одновременно», ваучер, ручное админом) → покупка eSIM со
стоком / без стока (pending, ручная выдача) → PDF-квитанция → пополнение
номера UA/RU → промокод → реф. начисление и вывод → eSIM-подписка (списание,
недостаток средств) → штрафы/касса модератора → блокировка → бэкап-джоб →
restore_check.

Плюс unit-тесты на `domain` и `payments` (теперь возможны: логика отделена
от telebot): идемпотентность `ledger.apply`, гонка `settle` из двух потоков,
атомарный claim стока, списание при нехватке средств.

---

## 14. Дорожная карта

### Этап 0 — остановить кровотечение (в текущем коде, до редизайна; ~1 неделя)

Деньги текут сейчас, cutover — через недели. Минимальные вмешательства
в legacy:

- [ ] Все мутации баланса → через `add_deposit` (правятся `update_balanse`,
      `change_deposit`, реф. операции — чтобы писали в `balance_log`).
- [ ] `balance_log.idem_key` (UNIQUE) + ключ `pay:lava:{order_id}` в
      поллере и в кнопке `lava_paid` — двойное начисление невозможно.
- [ ] Реестр запущенных поллеров (dict по order_id) — второй поток на тот же
      ордер не стартует.
- [ ] `count.json` → таблица-счётчик в `users.db` (атомарный UPDATE…RETURNING),
      `api.py` переводится на неё же.
- [ ] `try/except` вокруг всех `delete_message`; обёртка хэндлеров.
- [ ] Деплой-скрипт: запрет scp в `files/` (или перенос данных из-под кода).

**Критерии готовности:** сверка `SUM(balance_log) vs balans` даёт стабильный
дельта-отчёт (новых расхождений нет за 7 дней); ни одного дубля начислений
в `balance_log` по idem_key; номера заявок монотонны при параллельных
покупках из бота и mini-app.

### Этап 1 — фундамент новой системы (~1–2 недели)

- [ ] Приватный GitHub-репозиторий: код заливается, deploy key на сервере,
      секреты вычищены из истории (ротация — см. §12).
- [ ] `Dockerfile` + `docker-compose.yml`; `ci.yml` (линт + тесты на push/PR).
- [ ] Пакет `tgpay/`: config, db, log, миграции, схема `0001_init.sql`.
- [ ] `domain/ledger.py`, `payments/registry.py + watcher.py` + unit-тесты.
- [ ] `scripts/migrate_legacy.py` + `reconcile.py`; многократные прогоны на
      копии прод-данных.

**Критерии:** тесты зелёные (включая гонки settle и claim стока);
reconcile на копии прода = 0 расхождений; полный прогон миграции < 5 минут.

### Этап 2 — перенос функционала на тестовый стенд (~2–4 недели)

- [ ] Хэндлеры переносятся доменами: deposit → esim → replenish → админка →
      рефералка/промокоды → штрафы/касса → прочее. Приоритет — по денежному
      обороту.
- [ ] `api/` (mini-app + вебхуки), `support/`, `taxi/` — на общий config
      и данные.
- [ ] Тест-бот живёт на новом коде **в docker** (отдельный клон репозитория
      + свой `.env`) с мигрированной копией прод-данных; чек-лист
      эквивалентности прогоняется целиком; деплой на тест — только
      `git pull && docker compose up -d --build`.

**Критерии:** 100% чек-листа проходит на тест-боте; неделя работы тест-бота
без ошибок уровня ERROR в логах; reconcile-джоб на тесте — 0 расхождений.

### Этап 3 — cutover прода (1 ночь + неделя наблюдения)

- [ ] Процедура из §13; smoke-чек-лист; усиленное наблюдение неделю.
- [ ] Ротация всех утёкших секретов, `.env`-only; отзыв старых ключей.
- [ ] Старые файлы (`files/*.db`, JSON) остаются read-only ещё месяц, затем
      уходят в последний архивный zip.

**Критерии:** неделя прода: reconcile = 0, дубликатов начислений = 0,
падений polling = 0, `restore_check` = OK.

### Этап 4 — по мере роста (опционально, по сигналам)

- Postgres — если появится второй хост или упрёмся в конкуренцию записи
  (сигнал: устойчивые `SQLITE_BUSY` в логах). Репозитории в `db.py`/`domain`
  делают замену локальной.
- Очередь задач (Redis+RQ) — если фоновые работы перестанут помещаться
  в один процесс.
- S3-оффсайт бэкапов — при росте ценности данных.

---

## 15. Чего сознательно НЕ делаем

- **Микросервисы, K8s, шины сообщений** — не тот масштаб; Docker Compose
  на одном VPS проще диагностируется и дешевле. (Docker используется как
  упаковка процессов и изоляция данных, а не как оркестрация.)
- **Автодеплой из CI в прод** — CI гоняет тесты, но прод катится руками
  после проверки на тесте (осознанное правило владельца).
- **Переход на aiogram/webhook-режим для основного бота** — не решает ни
  одной проблемы из реестра; long polling надёжен за NAT и прост.
- **Postgres на старте** — выгода не окупает администрирование (§14, этап 4).
- **Двойная запись legacy+new при миграции** — freeze-and-cut с rollback-ом
  безопаснее и на порядок проще (§13).
- **ORM (SQLAlchemy)** — на этом объёме схемы голый SQL в репозиториях
  читабельнее и предсказуемее.

---

## 16. Инварианты целевой системы

Прежний список инвариантов («bot.py как точка входа», «фиксированный порядок
регистрации хэндлеров», «относительные пути», «файлы данных не двигаются»)
описывал ограничения legacy-кода, а не ценности системы. Он заменяется
инвариантами, которые защищают деньги и восстановимость:

1. **Баланс меняется только через `ledger.apply`**; каждая запись имеет
   уникальный `idem_key`. `SUM(ledger) == users.balance` — сверяется
   ежедневно.
2. **Начисление по платежу происходит не более одного раза** — гарантия
   схемы (UNIQUE), а не кода.
3. **Номера заявок монотонны и никогда не переиспользуются**
   (`orders` AUTOINCREMENT).
4. **`data/` не трогается деплоем** и целиком попадает в каждый бэкап.
5. **Импорт любого модуля — без side effects**; polling, потоки и DDL
   стартуют только из `main()`.
6. **Ошибка одного хэндлера не роняет процесс** (middleware + safe-обёртки).
7. **Бэкап считается существующим, только если `restore_check` его
   восстановил** (еженедельная проверка).
8. **Секреты не попадают в git** — только `.env` на сервере.
