import datetime
import sqlite3

USERS_DB = 'files/users.db'

# Месячная абонплата (₴) по операторам — справочно.
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
            method TEXT DEFAULT 'card',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        cols = [r[1] for r in db.execute("PRAGMA table_info(esim_subscriptions)").fetchall()]
        if 'method' not in cols:
            db.execute("ALTER TABLE esim_subscriptions ADD COLUMN method TEXT DEFAULT 'card'")
        db.execute('''CREATE TABLE IF NOT EXISTS esim_user_settings (
            user_id INTEGER PRIMARY KEY,
            card_default INTEGER DEFAULT 1
        )''')


def has_active(user_id: int, operator: str) -> bool:
    with sqlite3.connect(USERS_DB) as db:
        row = db.execute(
            'SELECT 1 FROM esim_subscriptions WHERE user_id=? AND operator=? AND active=1',
            (user_id, operator)
        ).fetchone()
        return row is not None


def register(user_id: int, operator: str, method: str = 'card') -> bool:
    """Записать подписку eSIM, если активной ещё нет. True — если создана новая."""
    monthly = ESIM_MONTHLY_UAH.get(operator, 0)
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
            (user_id, operator, monthly, next_charge, method)
        )
        return True


def get_card_default(user_id: int) -> bool:
    """По умолчанию оплата eSIM картой (True). Можно отключить в профиле."""
    with sqlite3.connect(USERS_DB) as db:
        row = db.execute(
            'SELECT card_default FROM esim_user_settings WHERE user_id=?', (user_id,)
        ).fetchone()
        return True if row is None else bool(row[0])


def set_card_default(user_id: int, value: bool):
    with sqlite3.connect(USERS_DB) as db:
        db.execute(
            'INSERT INTO esim_user_settings (user_id, card_default) VALUES (?,?) '
            'ON CONFLICT(user_id) DO UPDATE SET card_default=excluded.card_default',
            (user_id, 1 if value else 0)
        )
