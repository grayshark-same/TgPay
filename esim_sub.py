import datetime
import sqlite3

USERS_DB = 'files/users.db'

# Месячная абонплата (₴) по операторам — списывается с баланса по текущему курсу.
ESIM_MONTHLY_UAH = {
    'Vodafone': 420,
    'Kievstar': 350,
    'Lifecell': 250,
}


def init_db():
    with sqlite3.connect(USERS_DB) as db:
        db.execute('''CREATE TABLE IF NOT EXISTS esim_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            operator TEXT NOT NULL,
            monthly_uah REAL NOT NULL,
            next_charge TIMESTAMP NOT NULL,
            active INTEGER DEFAULT 1,
            method TEXT DEFAULT 'balance',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cols = [r[1] for r in db.execute("PRAGMA table_info(esim_subscriptions)").fetchall()]
        if 'method' not in cols:
            db.execute("ALTER TABLE esim_subscriptions ADD COLUMN method TEXT DEFAULT 'balance'")


def register(user_id: int, operator: str) -> bool:
    """Создать подписку на ежемесячное списание абонплаты с баланса.
    Первый месяц входит в цену eSIM, поэтому следующее списание — через 30 дней.
    Возвращает True, если создана новая (для операторов без месячной платы — False)."""
    monthly = ESIM_MONTHLY_UAH.get(operator)
    if not monthly:
        return False
    with sqlite3.connect(USERS_DB) as db:
        existing = db.execute(
            'SELECT id FROM esim_subscriptions WHERE user_id=? AND operator=? AND active=1',
            (user_id, operator)
        ).fetchone()
        if existing:
            return False
        next_charge = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
        db.execute(
            'INSERT INTO esim_subscriptions (user_id, operator, monthly_uah, next_charge, method) '
            'VALUES (?,?,?,?,?)',
            (user_id, operator, monthly, next_charge, 'balance')
        )
        return True


def get_user_subs(user_id: int):
    """Активные balance-подписки пользователя (для показа в профиле)."""
    with sqlite3.connect(USERS_DB) as db:
        return db.execute(
            "SELECT id, operator, monthly_uah, next_charge FROM esim_subscriptions "
            "WHERE user_id=? AND active=1 AND method='balance' ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()


def cancel(sub_id: int, user_id: int) -> bool:
    """Отключить автопродление подписки. True — если что-то отключили."""
    with sqlite3.connect(USERS_DB) as db:
        cur = db.execute(
            'UPDATE esim_subscriptions SET active=0 WHERE id=? AND user_id=? AND active=1',
            (sub_id, user_id)
        )
        return cur.rowcount > 0


def get_due_subs():
    """Подписки, у которых подошёл срок списания с баланса."""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect(USERS_DB) as db:
        return db.execute(
            "SELECT id, user_id, operator, monthly_uah FROM esim_subscriptions "
            "WHERE active=1 AND method='balance' AND next_charge <= ?",
            (now,)
        ).fetchall()


def _advance(sub_id: int):
    next_charge = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')
    with sqlite3.connect(USERS_DB) as db:
        db.execute('UPDATE esim_subscriptions SET next_charge=? WHERE id=?', (next_charge, sub_id))


def _deactivate(sub_id: int):
    with sqlite3.connect(USERS_DB) as db:
        db.execute('UPDATE esim_subscriptions SET active=0 WHERE id=?', (sub_id,))


def process_charges(bot_instance, uah_rate: float):
    """Списать абонплату с баланса за все просроченные подписки. Сумма = monthly_uah * курс."""
    from help import get_balans, add_deposit
    for sub_id, user_id, operator, monthly_uah in get_due_subs():
        rub_amount = round(monthly_uah * uah_rate)
        balance = float(get_balans(user_id) or 0)
        if balance >= rub_amount:
            add_deposit(user_id, -rub_amount, description=f'Абонплата eSIM {operator}')
            _advance(sub_id)
            try:
                bot_instance.send_message(
                    user_id,
                    f'📱 <b>Абонплата eSIM {operator}</b>\n'
                    f'💸 Списано {rub_amount}₽ ({monthly_uah:.0f}₴ по курсу)\n'
                    f'📅 Следующее списание через 30 дней',
                    parse_mode='HTML'
                )
            except Exception as e:
                print(f'[esim_sub] notify error user={user_id}: {e}')
        else:
            _deactivate(sub_id)
            try:
                bot_instance.send_message(
                    user_id,
                    f'❌ <b>Автосписание eSIM {operator} приостановлено</b>\n\n'
                    f'Нужно {rub_amount}₽, на балансе {balance:.0f}₽.\n'
                    f'Пополните баланс и оформите eSIM заново.',
                    parse_mode='HTML'
                )
            except Exception as e:
                print(f'[esim_sub] notify error user={user_id}: {e}')
