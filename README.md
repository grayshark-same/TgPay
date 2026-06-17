# TGPay

Telegram-бот для приёма платежей, управления балансами и оказания услуг (пополнение мобильного, eSIM, VPN, GB-пакеты и др.).

## Стек

- Python 3.10+
- [pyTelegramBotAPI (telebot)](https://github.com/eternnoir/pyTelegramBotAPI)
- SQLite (несколько баз, доступ через `sqlite3`)
- Lava.ru Business API (приём карт и СБП, polling + webhook)
- Cryptomus (крипто-платежи)
- NicePay, PayOK, ЮMoney (дополнительные способы оплаты)

## Структура файлов

```
bot.py          — основной файл: хендлеры, callback-логика, бизнес-правила
help.py         — вспомогательные функции: балансы, архив, ранги, история
texts.py        — статичные тексты сообщений
penalties.py    — система штрафов модераторов
cryptomus.py    — интеграция с Cryptomus
nicepay.py      — интеграция с NicePay
support_bot.py  — отдельный бот поддержки
yomany_gmail.py — мониторинг ЮMoney через Gmail

files/          — SQLite базы данных (не в репо)
  users.db      — пользователи, балансы, balance_log, подписки
  arhive.db     — архив выполненных заявок
  cards.db      — данные карт для выплат
  penalties.db  — штрафы модераторов
  donations.db  — пожертвования на разработку приложения
  referrals.db  — реферальная система
  mods.db       — балансы модераторов (UAH/USD)

esim.json           — конфиг операторов eSIM (цена, описание)
promocode.json      — промокоды
lifecell_gb.json    — пакеты GB Lifecell
analytic_clicks_data.json — аналитика кликов по разделам
```

## Переменные окружения

Создай файл `.env` в корне проекта:

```env
BOT_TOKEN=<токен бота от @BotFather>
ADMIN_GROUP=<chat_id группы администраторов (отрицательный)>
ARHIVE_GROUPS=<chat_id архивной группы (через запятую)>
```

> ⚠️ `.env` не коммитится в репо. Никогда не добавляй токены в код напрямую.

## Как запустить локально

```bash
# 1. Клонировать и перейти в папку
git clone https://github.com/sowaaaaa/tgpay
cd tgpay

# 2. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Установить зависимости
pip install -r librarise.txt

# 4. Создать .env (см. выше)

# 5. Создать папку для БД
mkdir -p files

# 6. Запустить
python bot.py
```

При первом запуске все SQLite-таблицы создаются автоматически.

## Деплой на сервер

Бот развёрнут на `92.51.37.63`. Тестовый бот — `/root/test_bot/`, продакшен — `/root/bot/`.

Деплой с тестового на прод через `deploy.sh` (запускается на сервере):

```bash
bash /root/test_bot/deploy.sh
```

Скрипт делает `rsync` (без БД и `.env`) и перезапускает `bot.service`.

## Архитектура балансов

- Баланс пользователя хранится в `users.db → users.balans` (рубли, float)
- Все изменения баланса пишутся в `balance_log` (user_id, amount, balance_after, description, created_at)
- Функция `add_deposit(id, summ, description)` — единая точка изменения баланса
- Исключения: `withdraw_balance` (вывод средств) и `update_balance` — тоже пишут в `balance_log`

## Реферальная система

- При регистрации пользователь привязывается к рефереру через `ref_data.json` / `referrals.db`
- При пополнении баланса реферером начисляется процент рефереру (настраивается в боте)
- Накопленный реф. баланс можно вывести через профиль → "Реферальная система"

## Платежи через Lava

1. Создаётся инвойс (`/business/invoice/create`) — пользователь получает ссылку
2. Бот запускает polling в отдельном потоке (`poll_lava_payment`) — проверяет статус каждые 5 сек до 1 часа
3. При статусе `paid` — зачисляется баланс через `add_deposit`
4. Альтернативно: webhook `/business/invoice/webhook` — принимается через отдельный HTTP-сервер (если настроен)

Подпись запросов: HMAC-SHA256 от JSON-тела с `SECRET_KEY`.

## Ранги пользователей

По потраченной сумме (`total_spent`):

| Ранг | Сумма |
|------|-------|
| ❌ | 0 ₽ |
| ✅ | до 1 000 ₽ |
| 💎 | до 10 000 ₽ |
| 🐳 | до 100 000 ₽ |
| 🕶 | 100 000+ ₽ |

По пожертвованиям (`donations.db`):

| Ранг | Сумма |
|------|-------|
| — | < 500 ₽ |
| tg-emoji 5364209244109282901 | 500–999 ₽ |
| tg-emoji 5361664617720325706 | 1 000–2 999 ₽ |
| tg-emoji 5361701438474953213 | 3 000–4 999 ₽ |
| tg-emoji 5364119608141816446 | 5 000–9 999 ₽ |
| tg-emoji 5363918225715243425 | 10 000+ ₽ |
