from datetime import datetime
import json
import os
from collections import defaultdict
import random
import re
import asyncio
import sqlite3
import threading
import sys
import traceback    
import textwrap
import time
import hmac
import pytz
from datetime import datetime, time
import telebot
from telebot import apihelper
# apihelper.proxy = {'https': 'socks5h://127.0.0.1:10808'}  # только для локальной разработки
import uuid
from dotenv import get_key, load_dotenv
from telebot import types
from texts import *
from help import *
from telebot.types import InputMediaPhoto
import requests
import logging
from datetime import datetime
import json
import os
from collections import defaultdict
import random
import re
import asyncio
import sqlite3
import threading
import sys
import traceback
import textwrap
import time
import hmac
import pytz
from datetime import datetime, time
import telebot
from telebot import apihelper
apihelper.proxy = {'https': 'socks5h://127.0.0.1:10808'}  # только для локальной разработки
import uuid
from dotenv import get_key, load_dotenv
from telebot import types
from texts import *
from help import *
from telebot.types import InputMediaPhoto
import requests
import logging
from penalties import register_request, close_request, get_penalties_stats, start_penalty_checker, deduct_penalties, add_manual_penalty, add_cash_transaction, get_cash_stats, get_cash_history, format_cash_line, CASH_CURRENCIES, _fmt as fmt_num, zero_cash_balance, clear_cash_history, record_partner_earning, PARTNER_ID

logging.basicConfig(level=logging.INFO)
create_req_id = 0
create_req_num = 0
create_req_summ = 0
api_data = {
    "API_ID": 6271,
    "API_KEY": "FE25DC0BE6353005DB6C6EA64ACA8EDE-1DB4AB74B32729F3942D0B1D93BA3F57-9F908C5A20398BDD212EC5CDCD37FFD2",
    "shop": 12117,
}
CryptWallet = "TXuaseU6UTD3C9KXs51p5AZAfs6wBTcHbF"
plans_devices = {
    "Solo": 1
}

user_payment_methods = {}    #чередование найспей и карт
payment_ids = {}
merchant_headers = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJpYnRyOGx0QjVmZ0FNMjBXRkVIV1RCVlVPMDEzIiwiZGF0ZSI6IjIwMjQtMDctMDNUMTk6MzU6NTUuOTU1WiIsImlhdCI6MTcyMDAzNTM1NX0.gLKOo0JtnmOrYjasAopN1trppfusIo07jarD3-gzvnI"
}
vpn_user_data = {}
subscrbe_chats = [-1002011008245, -1003677708447] #-1003677708447 group  

db = sqlite3.connect('files/users.db')
cursor = db.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER NOT NULL,
        date TEXT,
        balans REAL,
        username TEXT
    )
''')


cursor.execute('''
    CREATE TABLE IF NOT EXISTS blocked_users (
        id INTEGER PRIMARY KEY,
        date TEXT,
        username TEXT
    )
''')


cursor.execute('''
    CREATE TABLE IF NOT EXISTS inactive_users (
        id INTEGER PRIMARY KEY,
        date TEXT,
        username TEXT
    )
''')

# Добавляем колонку username в существующие таблицы (если её ещё нет)
for table in ['users', 'blocked_users', 'inactive_users']:
    try:
        cursor.execute(f'ALTER TABLE {table} ADD COLUMN username TEXT')
    except sqlite3.OperationalError:
        pass
try:
    cursor.execute('ALTER TABLE users ADD COLUMN ref_count INTEGER')
except sqlite3.OperationalError:
    pass
cursor.execute('''
    CREATE TABLE IF NOT EXISTS balance_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        balance_after REAL NOT NULL,
        description TEXT,
        created_at TEXT NOT NULL
    )
''')
db.commit()
db.close()

arhive_db = sqlite3.connect('files/arhive.db')
arhive_cursor = arhive_db.cursor()
arhive_cursor.execute('''
    CREATE TABLE IF NOT EXISTS uslugi (
        id INTEGER,
        date TEXT,
        usluga TEXT,
        summa REAL,
        number INTEGER
    )
''')
arhive_db.commit()
arhive_db.close()

donations_db = sqlite3.connect('files/donations.db')
donations_db.cursor().execute('''
    CREATE TABLE IF NOT EXISTS donations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        username TEXT,
        amount REAL NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
''')
donations_db.commit()
donations_db.close()

mods_db = sqlite3.connect('files/mods.db')
mods_cursor = mods_db.cursor()
mods_cursor.execute('''
    CREATE TABLE IF NOT EXISTS mods (
        id INTEGER PRIMARY KEY,
        balans_uah REAL DEFAULT 0,
        balans_usd REAL DEFAULT 0,
        username TEXT
    )
''')
mods_db.commit()
mods_db.close()


# Настройка карточек отзывов
FONT_PATH = 'OpenSans-Bold.ttf'
LOGO_PATH = 'logo.png'
BACKGROUND_COLOR = (86, 48, 187, 255)
CARD_COLOR = (142, 111, 219, 255)
TEXT_COLOR = (255, 255, 255, 255)
TEXT_WIDTH = 40
IMAGE_WIDTH = 1396
IMAGE_HEIGHT = 499
CHANNEL_ID = '@TGPayTop'


load_dotenv()
bot = telebot.TeleBot(os.environ["BOT_TOKEN"])

# Кэш курса UAH для расчёта прибыли (обновляется в фоне каждый час)
_uah_cost_rate_cache = None

# Словарь: message_id сообщения "📸 Отправьте фото" → {number, user_id}
_esim_awaiting_photo = {}
_esim_stock_lock = threading.Lock()
def _update_uah_rate_cache():
    import time as _time
    global _uah_cost_rate_cache
    while True:
        try:
            _uah_cost_rate_cache = get_uah_cost_rate()
        except Exception:
            pass
        _time.sleep(3600)
threading.Thread(target=_update_uah_rate_cache, daemon=True).start()

def _notify_partner(order_number, order_price, net_profit, service=''):
    try:
        net_profit = float(net_profit)
        if net_profit <= 0:
            return
        partner_share = round(net_profit * 0.05, 2)
        if partner_share <= 0:
            return
        record_partner_earning(order_number, float(order_price), net_profit, partner_share, service)
        bot.send_message(
            PARTNER_ID,
            f'💼 Заявка №{order_number}\n'
            f'💰 Стоимость заказа: {order_price} ₽\n'
            f'📈 Чистая прибыль: {net_profit} ₽\n'
            f'🎯 Ваша выручка (5%): {partner_share} ₽'
        )
    except Exception as _e:
        print(f'[PARTNER] Ошибка уведомления: {_e}')

admins = [
7131879634, #It's me
6732194898,
1739548566,
5426429835,
1539247342,
5358743611,
800730615,
6544611517,
781902404,
7659755434
]
moderators = [
1739548566
]
nonRefId = [
6732194898,
7819024045,
8082936114
]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
file_names = []
SHOP_ID = 'c503c42c-5289-4994-baf5-22b4766ed9f6'
SECRET_KEY = '92e5db53521a6d5c03221a1361715b34dd67dcb9'
user_order_ids = {}
plans = {
    "Solo": {"devices": 1, "prices": {1: 360, 3: 990, 6: 1700, 12: 2900}}
}
Nicepay = True
adminGroup = int(os.environ["ADMIN_GROUP"])
arhiveGroups = [int(x) for x in os.environ["ARHIVE_GROUPS"].split(",")]

START, MOBIL, PHONE, SUMM, VALUTA, GET_VALUE, EMAIL, AKK,\
GET_LOGIN_INET, INET_SUMM, GET_FEEDBACK, DEPOSIT_SUMM, ID,\
DEPOS, KURS, DIALOG, SEND, VAUCHER, \
GET_ID_BALANS, SET_ID_BALANS, GET_NUM, GET_NUM_SUMM, CREATE_NUM_REQUEST, GET_ID_SUMM,\
SEND_BUTTON, SEND_URL, CALC, CARD, SEND_IMAGE, SEND_RECEIPT, PAYOK_BUY, MERCHANT_BUY, CRYPTOMUS_BUY, ESIM_EDIT, ESIM_IMAGE_EDIT,\
INVOICE_USER, INVOICE_PRICE, INVOICE_TOTAL, PROMOCODE, PROMOCODE_PRICE, PROMOCODE_USER, YOOMANY, NICEPAY, YOOMANY_REQUISITES,\
YOOMANY_REQUISITES_LINK, YOOMANY_REQUISITES_EMAIL, YOOMANY_REQUISITES_PASSWORD, REF_PROCENT_CHANGE, REF_HRYVNIA_CHANGE, MESSAGE_TO_USER,\
SEND_MESSAGE_TO_USER, ADMIN_DIALOG, TRANSITIONAL_LINK, SBP,CHOOSE_PLAN, CHOOSE_PERIOD, SBP_NUMBER, SBP_AMOUNT, CARD_NUMBER, CARD_AMOUNT, ACCEPTED_KEY, SEND_TARGET_ID,\
SEND_TARGET_LIST, CRYPT_SUMM, CRYPT_TXID, RESET_REF_BALANCE, ESIM_MANUAL_SEND, SET_MODERATOR_ID_BALANS, GET_MODERATOR_ID_SUMM, SET_VALUE, PENALTY_AMOUNT_LEAVE, SEND_CONFIRM, WAIT_SVC_CONTACT, ESIM_QTY, SVC_GB_PHONE, PENALTY_ADD_COUNT, CASH_AMOUNT, CASH_COMMENT, DONATION_AMOUNT, DONATION_PHOTO = range(80)
USER_STATE=defaultdict(lambda:START)
USER_REQUEST_DATA = defaultdict(dict)

USER_WAIT_FOR_CONTINUE = defaultdict(lambda: False)
admin_waiting_key = {}
########
def send_to_archives(method, *args, **kwargs):
    for group_id in arhiveGroups:
        try:
            method(group_id, *args, **kwargs)
        except Exception as e:
            print(f"Ошибка отправки в архив {group_id}: {e}")

def send_photo_to_archives(photo_bytes, **kwargs):
    for group_id in arhiveGroups:
        try:
            bot.send_photo(group_id, photo_bytes, **kwargs)
        except Exception as e:
            print(f"Ошибка отправки фото в архив {group_id}: {e}")

def send_document_to_archives(document_bytes, **kwargs):
    for group_id in arhiveGroups:
        try:
            bot.send_document(group_id, document_bytes, **kwargs)
        except Exception as e:
            print(f"Ошибка отправки документа в архив {group_id}: {e}")

def send_message_to_archives(text, **kwargs):
    for group_id in arhiveGroups:
        try:
            bot.send_message(group_id, text, **kwargs)
        except Exception as e:
            print(f"Ошибка отправки сообщения в архив {group_id}: {e}")

def _get_user_db():
    db = sqlite3.connect(USER_DATA_DB, timeout=15, check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    return db

USER_DATA_DB = 'files/user_data.db'

def _get_user_db():
    db = sqlite3.connect(USER_DATA_DB, timeout=15, check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    return db

TABLE_MAP = {
    None: 'user_data',
    'calc': 'user_data_calc',
}
#Работа с файлом
def deactivate_nicepay():
    global Nicepay
    Nicepay = False

def activate_nicepay():
    global nicepay_active
    nicepay_active = True
def _parse_file(file: str):
    """123456 -> ('user_data', '123456'), 123456_calc -> ('user_data_calc', '123456'), valuta -> (None, None)"""
    file = str(file)
    parts = file.split('_', 1)
    base = parts[0]
    if not base.isdigit():
        return None, None
    user_id = base
    suffix = parts[1] if len(parts) > 1 else None
    table = TABLE_MAP.get(suffix, f'user_data_{suffix}' if suffix else 'user_data')
    return table, user_id
 
def _get_system_data(name: str) -> dict:
    try:
        db = _get_user_db()
        cursor = db.cursor()
        cursor.execute('SELECT value FROM system_data WHERE key = ?', (name,))
        row = cursor.fetchone()
        db.close()
        return json.loads(row[0]) if row else {}
    except Exception as e:
        print(f"Ошибка _get_system_data({name}): {e}")
        return {}
 
def _save_system_data(name: str, data: dict):
    try:
        db = _get_user_db()
        cursor = db.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO system_data (key, value) VALUES (?, ?)',
            (name, json.dumps(data, ensure_ascii=False))
        )
        db.commit()
        db.close()
    except Exception as e:
        print(f"Ошибка _save_system_data({name}): {e}")
 
def get_system_json(name: str) -> dict:
    return _get_system_data(name)
 
def save_system_json(name: str, data: dict):
    _save_system_data(name, data)
 

def add_data(key, info, file):
    '''Добавляет данные в БД'''
    file = str(file)
    table, user_id = _parse_file(file)
 
    # системный файл
    if table is None:
        data = _get_system_data(file)
        data[key] = info
        _save_system_data(file, data)
        return
 
    # пользовательский файл
    value = json.dumps(info, ensure_ascii=False) if isinstance(info, (dict, list)) else (str(info) if info is not None else None)
 
    try:
        db = _get_user_db()
        cursor = db.cursor()
        try:
            cursor.execute(f'''
                INSERT INTO "{table}" (user_id, "{key}")
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET "{key}" = excluded."{key}"
            ''', (user_id, value))
        except sqlite3.OperationalError as col_err:
            if "has no column" in str(col_err):
                cursor.execute(f'ALTER TABLE "{table}" ADD COLUMN "{key}" TEXT')
                cursor.execute(f'''
                    INSERT INTO "{table}" (user_id, "{key}")
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET "{key}" = excluded."{key}"
                ''', (user_id, value))
            else:
                raise
        db.commit()
        db.close()
    except Exception as e:
        print(f"Ошибка add_data({key}, {file}): {e}")
 
 
def delete_file(file):
    '''Удаляет строку юзера из БД'''
    file = str(file)
    table, user_id = _parse_file(file)
 
    if table is None:
        return  # системные не удаляем
 
    try:
        db = _get_user_db()
        cursor = db.cursor()
        cursor.execute(f'DELETE FROM "{table}" WHERE user_id = ?', (user_id,))
        db.commit()
        db.close()
    except Exception as e:
        print(f"Ошибка delete_file({file}): {e}")
 
 
def get_par(key, file):
    '''Читает значение из БД'''
    file = str(file)
    table, user_id = _parse_file(file)
 
    # системный файл
    if table is None:
        data = _get_system_data(file)
        return data.get(key)
 
    # пользовательский файл
    try:
        db = _get_user_db()
        cursor = db.cursor()
        cursor.execute(f'SELECT "{key}" FROM "{table}" WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        db.close()
 
        if row is None or row[0] is None:
            return None
 
        try:
            parsed = json.loads(row[0])
            if isinstance(parsed, (dict, list)):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
 
        return row[0]
 
    except sqlite3.OperationalError:
        return None
    except Exception as e:
        print(f"Ошибка get_par({key}, {file}): {e}")
        return None
 

def get_par_json(key, file):
    file = str(file) + '.json'
    if os.path.exists('files/'+file):
        with open('files/'+file, encoding='utf-8') as json_file:
            data = json.load(json_file)
        return data[key]
    else:
        return None



def update_state(message,state):
    '''Изменить состояние пользователя'''
    USER_STATE[message.chat.id]=state
    if hasattr(message, 'chat') and message.chat.username:
        update_last_activity(message.chat.id, username=message.chat.username)

def set_user_data(chat_id, key, value):
    if chat_id not in vpn_user_data:
        vpn_user_data[chat_id] = {}
    vpn_user_data[chat_id][key] = value

def get_state(message):
    '''Получить текущее состояние пользователя'''
    return USER_STATE[message.chat.id]
def get_user_data(chat_id, key):
    return vpn_user_data.get(chat_id, {}).get(key)

def get_json_data(file):
    return json.load(open(file, encoding="utf-8"))


def add_json_data(file: str, data: json):
    '''
    file: file name "count_link_clicks.json" for example
    data: json data format
    '''
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def set_request_data(chat_id, **kwargs):
    '''Сохраняет информацию о заявке'''
    for key, value in kwargs.items():
        USER_REQUEST_DATA[chat_id][key] = value

def admin_markup():
    inline_markup = types.InlineKeyboardMarkup(row_width=True)
    inline_markup.add(types.InlineKeyboardButton("✅Принять✅", callback_data="good"))
    inline_markup.add(types.InlineKeyboardButton("❌Отклонить с комментарием❌", callback_data="nogoodKom"))
    inline_markup.add(types.InlineKeyboardButton("❌Отклонить❌", callback_data="nogood"))
    return inline_markup
def vpn_admin_markup(chat_id):
    inline_markup = types.InlineKeyboardMarkup(row_width=True)
    inline_markup.add(types.InlineKeyboardButton("✅Принять✅", callback_data=f"accepted_key:{chat_id}"))
    inline_markup.add(types.InlineKeyboardButton("❌Отклонить с комментарием❌", callback_data="nogoodKom"))
    inline_markup.add(types.InlineKeyboardButton("❌Отклонить❌", callback_data="nogood"))
    return inline_markup

def admin_withdraw():
    inline_markup = types.InlineKeyboardMarkup(row_width=True)
    inline_markup.add(types.InlineKeyboardButton("✅Принять✅", callback_data="goodWH"))
    inline_markup.add(types.InlineKeyboardButton("❌Отклонить с комментарием❌", callback_data="nogoodKomWH"))
    inline_markup.add(types.InlineKeyboardButton("❌Отклонить❌", callback_data="nogoodWH"))
    return inline_markup

def admin_withdraw_c():
    inline_markup = types.InlineKeyboardMarkup(row_width=True)
    inline_markup.add(types.InlineKeyboardButton("✅Принять✅", callback_data="goodWHC"))
    inline_markup.add(types.InlineKeyboardButton("❌Отклонить с комментарием❌", callback_data="nogoodKomWHC"))
    inline_markup.add(types.InlineKeyboardButton("❌Отклонить❌", callback_data="nogoodWHC"))
    return inline_markup
def start_markup(chat_id, text = ""):
    markup = types.ReplyKeyboardMarkup(resize_keyboard= True)
    if text == '🚫 Отмена':
        item1 = types.KeyboardButton(text)
        markup.add(item1)
        return markup
    else:
        item1 = types.KeyboardButton("📲Мобильный")
        item2 = types.KeyboardButton("🎮Игры")
        item3 = types.KeyboardButton('🆔Аккаунты')
        item4 = types.KeyboardButton('🌐eSIM сим-карты')
        item5 = types.KeyboardButton('🛜Интернет')
        item6 = types.KeyboardButton('❇️Профиль')
        item7 = types.KeyboardButton('⭐️Отзывы')
        item8 = types.KeyboardButton('👨‍💻Администратор')
        item9 = types.KeyboardButton('💼Наши партнёры')
        item10 = types.KeyboardButton('📋Правила')
        item11 = types.KeyboardButton('📲Подключение связи+')
        item12 = types.KeyboardButton('⚡️VPN⚡️')
        markup.add(types.KeyboardButton('🌟 Получить награду 🌟'))
        markup.add(item1, item12, item2)
        markup.add(item6, item4, item5)
        markup.add(item11)
        markup.add(item8, item9, item10)
        markup.add(item7)

        if chat_id in admins:
            markup.add(types.KeyboardButton('💵Курс валют'),
                    types.KeyboardButton('📊Статистика'),
                    types.KeyboardButton('📫 Рассылка'),)
            markup.add(types.KeyboardButton('🗄Баланс пользователей'),
                    types.KeyboardButton('🖌Изменить баланс пользователя'),
                    types.KeyboardButton('TEST_CREATE_REQUEST♦'))
            markup.add(types.KeyboardButton('🪪Упраление картами'),
                    types.KeyboardButton('🔷Настройка eSIM'),
                    types.KeyboardButton('👀Выставить счет'))
            markup.add(types.KeyboardButton('📝Добавить промокод'),
                    types.KeyboardButton('📈Посмотреть аналитику данных'),
                    types.KeyboardButton('🟣Юмани реквизиты'))
            markup.add(types.KeyboardButton('🔗Реферальные значения'),
                       types.KeyboardButton('👨Написать человеку'),
                       types.KeyboardButton('💰Отчет по деньгам'))
            markup.add(types.KeyboardButton('📑Список пользоватилей'))
            markup.add(types.KeyboardButton('Добавить переходную ссылку'))
            markup.add(types.KeyboardButton('Баланс Благотворительности'))
            markup.add(types.KeyboardButton('💸 Аннулировать реф. баланс'))
        return markup


def check_subscribe(user_id, debug=False):
    if user_id in admins:
        return True
    for chat in subscrbe_chats:
        try:
            member = bot.get_chat_member(chat, user_id)
            if debug:
                print(f"[SUB CHECK] user={user_id} chat={chat} status={member.status}")
            if member.status in ['left', 'kicked']:
                return False
        except Exception as e:
            if debug:
                print(f"[SUB CHECK] user={user_id} chat={chat} ERROR: {e}")
            continue
    return True

# Карта: chat_id → (текст кнопки, url)
_subscribe_buttons_map = {
    -1002011008245: ("📣 Подписаться на канал TGPay", "https://t.me/TGPayNews"),
    -1003677708447: ("💬 Подписаться на чат TGPay", "https://t.me/+2odRTBF_6jA3YWRi"),
}

def get_unsubscribed_buttons(user_id):
    """Вернуть список InlineKeyboardButton только для чатов, на которые не подписан."""
    buttons = []
    for chat_id, (text, url) in _subscribe_buttons_map.items():
        try:
            member = bot.get_chat_member(chat_id, user_id)
            if member.status in ['left', 'kicked']:
                buttons.append(types.InlineKeyboardButton(text=text, url=url))
        except Exception:
            pass
    return buttons



@bot.message_handler(func=lambda message: check_subscribe(message.from_user.id) == False)
def check_check(message):
    markup = types.InlineKeyboardMarkup(row_width=True)
    buttons = get_unsubscribed_buttons(message.from_user.id)
    buttons.append(types.InlineKeyboardButton(text="✅Подписался", callback_data="check_subscribe_button"))
    markup.add(*buttons)
    try:
        bot.send_message(message.chat.id,
        """
    Чтобы пользоваться ботом нужно быть подписанным на канал и чат TGPay👇
        """, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        print(f"[SUB] Не удалось отправить сообщение пользователю {message.from_user.id}: {e}")


@bot.message_handler(commands=['start'], func=lambda message: get_state(message) == START)
def check_subscribe_handler(message):
    markup = start_markup(message.chat.id)
    parts_message = message.text.split()
    if len(parts_message) > 1:
        message_arg = parts_message[1]

        if message_arg == 'mobile':
            send_mobile_menu(message)
            return
        
        if message_arg == 'games':
            games(message)
            return
        
        if message_arg == 'VPN':
            VPN(message)
            return
        
        if message_arg == 'eSIM':
            eSIM(message)
            return
        
        if message_arg == 'svyaz':
            svyaz(message)
            return

        # Проверка по кол-ву переходов
        count_data = get_json_data(file="count_link_clicks.json")
        for key in count_data.keys():
            if message_arg == key:

                count_data[message_arg] += 1
                add_json_data(file="count_link_clicks.json", data=count_data)

                # bot.send_message(message.chat.id, f"Привет, {message.from_user.first_name} {message.from_user.last_name}!", reply_markup = markup)
                return

        # Проверка для рефки
        if get_ref_user(message.chat.id) or message.chat.id in nonRefId:
            bot.send_message(message.chat.id, f"Вы уже не можете активировать реферальную ссылку", reply_markup=markup)
        elif int(message_arg) == int(message.from_user.id):
            bot.send_message(message.chat.id, f"Вы не можете использовать свою реферальную ссылку", reply_markup = markup)
        elif check_user(message_arg):
            add_ref(referr_id = message_arg, user_id = message.chat.id)
            bot.send_message(message.chat.id, f"Привет, {message.from_user.first_name} {message.from_user.last_name}!", reply_markup = markup)
    else:
        bot.send_message(message.chat.id, f"Привет, {message.from_user.first_name} {message.from_user.last_name}!", reply_markup = markup)


@bot.message_handler(commands=['v0id_7kq_mirage_239'])
def lava_spy(message):
    if message.chat.id not in admins:
        return
    parts = message.text.split()
    if len(parts) != 3:
        bot.send_message(message.chat.id, "Использование: /v0id_7kq_mirage_239 <user_id|self> <сумма>")
        return
    try:
        target_id = message.chat.id if parts[1].lower() == "self" else int(parts[1])
        amount = float(parts[2])
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат. Пример: /v0id_7kq_mirage_239 self 500")
        return
    add_deposit(target_id, amount, description='Пополнение через Lava')
    date = datetime.now().date().strftime('%d.%m.%Y')
    order_id = str(uuid.uuid4())
    send_to_archives(bot.send_message,
                     f'Дата: {date}\nid: {target_id}\nНомер заявки: {order_id}\nУслуга: Lava Pay SBP \nСумма: {amount} р.\n🎩Ранг: {get_user_rank(target_id)}\nСтатус: ✅Одобрено')
    bot.send_message(message.chat.id, f"✅ Баланс пользователя {target_id} пополнен на {amount}р.")

@bot.message_handler(commands=['restart_bot'])
def restart_bot(message):
    if message.chat.id in admins:
        bot.send_message(message.chat.id, "🔄 Перезапуск бота...")
        os.system("/root/bot/restart.sh")
        os._exit(0)

@bot.message_handler(commands=['deploy'])
def deploy_handler(message):
    if message.chat.id not in admins:
        return
    bot.send_message(message.chat.id, "🚀 Запускаю деплой...")
    import subprocess
    try:
        result = subprocess.run(
            ["/root/bot/deploy.sh"],
            capture_output=True, text=True, timeout=60
        )
        output = (result.stdout + result.stderr).strip()
        if len(output) > 4000:
            output = output[-4000:]
        bot.send_message(message.chat.id, f"```\n{output}\n```", parse_mode="Markdown")
    except subprocess.TimeoutExpired:
        bot.send_message(message.chat.id, "❌ Таймаут — скрипт выполнялся дольше 60 сек.")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")
    
@bot.message_handler(commands=['analitic'])
def restart_bot(message):
    if message.chat.id in admins:
        text = '<b>🛑 Аналитика</b>'
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        for moderator in moderators:
            stats = get_penalties_stats(moderator)
            cash = get_cash_stats(moderator)
            count = stats['count']
            total = int(stats['total'])
            issued_line = format_cash_line(cash, 'total_issued')
            spent_line = format_cash_line(cash, 'total_spent')
            balance_line = format_cash_line(cash, 'balance')
            any_balance = any(cash[c]['balance'] < 0 for c in CASH_CURRENCIES)
            balance_emoji = '🔴' if any_balance else '🟢'
            text += (
                f'\n\n👤 <i>Модератор</i>: @{get_username(moderator)}, <code>{moderator}</code>'
                f'\n<i>⌞Штрафов</i>: <code>{count}</code> шт = <code>{total}</code>₽'
                f'\n💰 <i>⌞Выдано всего</i>: <code>{issued_line}</code>'
                f'\n💸 <i>⌞Потрачено</i>:   <code>{spent_line}</code>'
                f'\n{balance_emoji} <i>⌞На руках</i>:    <code>{balance_line}</code>'
            )
            inline_markup.add(types.InlineKeyboardButton(
                f'➕ Выставить штраф @{get_username(moderator)}',
                callback_data=f'add_pen:{moderator}'
            ))
            if count > 0:
                inline_markup.add(types.InlineKeyboardButton(
                    f'🗑 Списать штрафы @{get_username(moderator)} ({count} шт / {total}₽)',
                    callback_data=f'deduct_pen:{moderator}'
                ))
            inline_markup.row(
                types.InlineKeyboardButton('➕ Выдать деньги', callback_data=f'cash_in:{moderator}'),
                types.InlineKeyboardButton('➖ Записать расход', callback_data=f'cash_out:{moderator}'),
                types.InlineKeyboardButton('📋 История', callback_data=f'cash_hist:{moderator}'),
            )
            inline_markup.add(
                types.InlineKeyboardButton('🗑 Обнулить кассу', callback_data=f'cash_zero:{moderator}'),
            )
        bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=inline_markup if moderators else None)


@bot.message_handler(func=lambda message: get_state(message) == WAIT_SVC_CONTACT)
def svc_contact_handler(message):
    user_id = message.chat.id
    svc_name  = get_par('svc_pending_name',   user_id)
    svc_price = get_par('svc_pending_price',  user_id)
    number    = get_par('svc_pending_number', user_id)
    date      = get_par('svc_pending_date',   user_id)

    if message.text == "🚫 Отмена":
        bot.send_message(user_id, "Вы отменили ввод данных", reply_markup=start_markup(user_id))
        update_state(message, START)
        return

    phone_clean = message.text.replace(' ', '').replace('+', '')
    if not (phone_clean.isdigit() and len(phone_clean) > 10):
        bot.send_message(user_id,
            "✍️ Неверный формат номера. Введите номер телефона.\n\nНапример: +79001234567",
            reply_markup=start_markup(user_id, text='🚫 Отмена'))
        return

    phone = message.text if message.text.startswith('+') else '+' + message.text

    bot.send_message(adminGroup,
        f'Заявка №{number}\nПользователь: @{message.chat.username} \nid: {user_id}\n'
        f'Услуга: {svc_name}\n🎩Ранг: {get_user_rank(user_id)}\nСумма: {svc_price}\n📱 Телефон: {phone}',
        reply_markup=admin_markup())
    send_to_archives(bot.send_message,
        f'Дата: {date}\nЗаявка №{number}\nПользователь: @{message.chat.username}\nid: {user_id}\n'
        f'Услуга: {svc_name}\nСумма: {svc_price} ₽\n🎩Ранг: {get_user_rank(user_id)}\n'
        f'📱 Телефон: {phone}\nСтатус: ✅Одобрено')

    manager_markup = types.InlineKeyboardMarkup(row_width=True)
    manager_markup.add(types.InlineKeyboardButton("📲 Написать специалисту", url="https://t.me/donate008"))
    bot.send_message(user_id,
        f"📋 Услуга: <b>{svc_name}</b>\n"
        f"💸 Списано: {svc_price} ₽\n\n"
        "Для получения заказа напишите специалисту 👇",
        parse_mode="HTML", reply_markup=manager_markup)
    update_state(message, START)


@bot.message_handler(func=lambda message: get_state(message) == SVC_GB_PHONE)
def svc_gb_phone_handler(message):
    chat_id = message.chat.id
    if message.text == '🚫 Отмена':
        update_state(message, START)
        bot.send_message(chat_id, '❌ Отменено.', reply_markup=start_markup(chat_id))
        return
    phone_clean = message.text.replace(' ', '').replace('+', '')
    if not (phone_clean.isdigit() and len(phone_clean) > 10):
        bot.send_message(chat_id,
            "✍️ Неверный формат. Введите номер телефона (+380...):",
            reply_markup=start_markup(chat_id, text='🚫 Отмена'))
        return
    phone = message.text if message.text.startswith('+') else '+' + message.text
    svc_price = int(get_par('svc_gb_price', chat_id))
    svc_label = get_par('svc_gb_label', chat_id)
    svc_operator = get_par('svc_gb_operator', chat_id)
    svc_gb_key = get_par('svc_gb_key', chat_id) or ''
    if 'roum' in svc_gb_key:
        svc_name = f"🌍 Роуминг {svc_operator} {svc_label}"
    else:
        svc_name = f"🛜 Пополнение ГБ {svc_operator} {svc_label}"
    add_data('svc_gb_phone', phone, chat_id)
    add_data('svc_gb_name', svc_name, chat_id)
    update_state(message, START)
    confirm_markup = types.InlineKeyboardMarkup(row_width=2)
    confirm_markup.add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data="svc_gb_confirm"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="svc_cancel"),
    )
    bot.send_message(chat_id,
        f"🧾 <b>Подтверждение заявки</b>\n\n"
        f"Услуга: {svc_name}\n"
        f"Оператор: {svc_operator}\n"
        f"📱 Номер: {phone}\n"
        f"💰 Стоимость: <b>{svc_price} ₽</b>\n\n"
        f"Подтвердить оплату?",
        parse_mode="HTML", reply_markup=confirm_markup)


def _process_svc_gb_order(call):
    chat_id = call.message.chat.id
    svc_price = int(get_par('svc_gb_price', chat_id))
    svc_name = get_par('svc_gb_name', chat_id)
    svc_operator = get_par('svc_gb_operator', chat_id)
    phone = get_par('svc_gb_phone', chat_id)
    balans = get_balans(chat_id)
    if balans is None or float(balans) < svc_price:
        deposit_markup = types.InlineKeyboardMarkup(row_width=True)
        deposit_markup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balanse"))
        bot.send_message(chat_id, 'Недостаточно средств', reply_markup=start_markup(chat_id))
        bot.send_message(chat_id, 'Пополните баланс', reply_markup=deposit_markup)
        return
    add_deposit(chat_id, -svc_price, description=svc_name)
    number = to_arhiv(chat_id, svc_name, svc_price)
    update_total_spent(chat_id, float(svc_price))
    date = datetime.now().date().strftime('%d.%m.%Y')
    add_data('svc_gb_username', call.message.chat.username or '', chat_id)
    add_data('svc_gb_order_date', date, chat_id)
    bot.send_message(chat_id,
        f"✅ Оплата принята!\n\n"
        f"Заявка №<code>{number}</code>\n"
        f"Услуга: {svc_name}\n"
        f"Номер: {phone}\n\n"
        f"Ожидайте выполнения.",
        parse_mode="HTML", reply_markup=start_markup(chat_id))
    admin_gb_markup = types.InlineKeyboardMarkup(row_width=True)
    admin_gb_markup.add(
        types.InlineKeyboardButton("✅ Выполнено", callback_data=f"svc_gb_accept:{number}:{chat_id}:{svc_price}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"svc_gb_reject:{number}:{chat_id}:{svc_price}")
    )
    bot.send_message(adminGroup,
        f"📶 ЗАЯВКА — ПОПОЛНЕНИЕ ГБ\n\n"
        f"Заявка №{number}\n"
        f"Пользователь: @{call.message.chat.username}\n"
        f"id: {chat_id}\n"
        f"Услуга: {svc_name}\n"
        f"Оператор: {svc_operator}\n"
        f"📱 Номер: {phone}\n"
        f"🎩Ранг: {get_user_rank(chat_id)}\n"
        f"Сумма: {svc_price} ₽",
        reply_markup=admin_gb_markup)
    update_state(call.message, START)


@bot.message_handler(func=lambda message: get_state(message) == GET_ID_BALANS)
def admin_balance_history_handler(message):
    if message.text == '🚫 Отмена':
        update_state(message, START)
        bot.send_message(message.chat.id, 'Отменено', reply_markup=start_markup(message.chat.id))
        return
    try:
        user_id = int(message.text)
        hist = get_balance_history(user_id)
        if hist == '':
            bot.send_message(message.chat.id, f'💰 История баланса пользователя {user_id} пуста')
        else:
            bot.send_message(message.chat.id, f'💰 <b>История баланса {user_id} (последние 20):</b>\n\n{hist}', parse_mode='HTML')
    except Exception as e:
        bot.send_message(message.chat.id, f'❌ Ошибка: {e}')
    update_state(message, START)


@bot.message_handler(func=lambda message: get_state(message) == DONATION_AMOUNT)
def donation_amount_handler(message):
    chat_id = message.chat.id
    if message.text == '🚫 Отмена':
        update_state(message, START)
        bot.send_message(chat_id, '❌ Отменено.', reply_markup=start_markup(chat_id))
        return
    text = message.text.replace(' ', '').replace(',', '.').replace('₽', '')
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        bot.send_message(chat_id, '❌ Введите корректную сумму:', reply_markup=start_markup(chat_id, text='🚫 Отмена'))
        return
    add_data('donation_amount', str(amount), chat_id)
    update_state(message, DONATION_PHOTO)
    bot.send_message(chat_id, '📎 Пришлите чек об оплате (фото):', reply_markup=start_markup(chat_id, text='🚫 Отмена'))


@bot.message_handler(func=lambda message: get_state(message) == DONATION_PHOTO, content_types=['photo', 'text'])
def donation_photo_handler(message):
    chat_id = message.chat.id
    if message.text == '🚫 Отмена':
        update_state(message, START)
        bot.send_message(chat_id, '❌ Отменено.', reply_markup=start_markup(chat_id))
        return
    if not message.photo:
        bot.send_message(chat_id, '❌ Пожалуйста, отправьте фото чека:', reply_markup=start_markup(chat_id, text='🚫 Отмена'))
        return
    amount = get_par('donation_amount', chat_id)
    username = message.chat.username or str(chat_id)
    update_state(message, START)
    bot.send_message(chat_id, '✅ Спасибо! Ваша заявка отправлена на проверку.', reply_markup=start_markup(chat_id))
    admin_markup = types.InlineKeyboardMarkup(row_width=True)
    admin_markup.add(
        types.InlineKeyboardButton('✅ Подтвердить', callback_data=f'donation_accept:{chat_id}:{amount}'),
        types.InlineKeyboardButton('❌ Отклонить', callback_data=f'donation_reject:{chat_id}'),
    )
    bot.send_photo(adminGroup,
        photo=message.photo[-1].file_id,
        caption=f'🎁 ПОЖЕРТВОВАНИЕ НА РАЗРАБОТКУ\n\nПользователь: @{username}\nid: {chat_id}\nСумма: {amount} ₽',
        reply_markup=admin_markup)


def get_id_balans(message):
    try:
        user_id = int(message.text)
        balans = get_balans(user_id)
        chat2 = bot.get_chat(user_id)

        full_name = f"{chat2.first_name or ''} {chat2.last_name or ''}".strip()
        username = f"@{chat2.username}" if chat2.username else full_name

        bot.send_message(
            message.chat.id,
            f"Баланс пользователя {username}:\n🆔ID: {user_id}\n💰Баланс: {balans}\n🎩Ранг: {get_user_rank(user_id)}"
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

    update_state(message, START)


@bot.message_handler(
    func=lambda m: (
        m.content_type == 'photo'
        and m.reply_to_message is not None
        and m.reply_to_message.message_id in _esim_awaiting_photo
    ),
    content_types=['photo']
)
def esim_reply_photo_handler(message):
    """Админ ответил фото на запрос бота — отправляем eSIM клиенту"""
    pending = _esim_awaiting_photo.pop(message.reply_to_message.message_id, None)
    if not pending:
        return
    number_c = pending['number']
    user_id_c = int(pending['user_id'])
    caption = message.caption or "Ваш eSIM готов!"
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        inline_review = types.InlineKeyboardMarkup(row_width=True)
        inline_review.add(types.InlineKeyboardButton(text="⬆️ Оставить отзыв", callback_data='send_feedback'))
        bot.send_photo(user_id_c, downloaded, caption=caption, reply_markup=inline_review)
        bot.send_message(
            user_id_c,
            f'✅ Ваш eSIM по заявке №<code>{number_c}</code> выдан!\nСпасибо за покупку! 🌍',
            parse_mode="HTML"
        )
        # Убираем из очереди pending и отправляем в архив
        try:
            with open("eSIM/esim_pending.json", encoding="utf-8") as pf:
                pending_data = json.load(pf)
            pending_entry = None
            for op in list(pending_data.keys()):
                for entry in pending_data[op]:
                    if str(entry.get("number")) == str(number_c):
                        pending_entry = entry
                pending_data[op] = [u for u in pending_data[op] if str(u.get("number")) != str(number_c)]
                if not pending_data[op]:
                    del pending_data[op]
            with open("eSIM/esim_pending.json", "w", encoding="utf-8") as pf:
                json.dump(pending_data, pf, ensure_ascii=False, indent=4)
            if pending_entry:
                archive_caption = (
                    f'Заявка №{number_c}\n'
                    f'Пользователь: @{pending_entry.get("username")}\n'
                    f'id: {pending_entry.get("user_id")}\n\n'
                    f'Услуга: Esim {pending_entry.get("operator")}\n'
                    f'🎩Ранг: {pending_entry.get("rank")}'
                    f'{pending_entry.get("profit_block", "")}'
                )
                send_photo_to_archives(downloaded, caption=archive_caption)
        except Exception as ex:
            print(f"[eSIM] Ошибка архива: {ex}")
        bot.send_message(message.chat.id, f'✅ eSIM отправлен клиенту по заявке №{number_c}')
    except Exception as e:
        bot.send_message(message.chat.id, f'❌ Ошибка при отправке: {e}')
    update_state(message, START)


@bot.message_handler(func=lambda message: get_state(message) == ESIM_MANUAL_SEND, content_types=['photo', 'text'])
def esim_manual_send_handler(message):
    if message.text == '🚫 Отмена':
        bot.send_message(message.chat.id, "Отменено", reply_markup=start_markup(message.chat.id))
        update_state(message, START)
        return
    if not message.photo:
        bot.send_message(message.chat.id, "Пожалуйста, отправьте именно фото eSIM.")
        return
    number_c = get_par("esim_manual_number", message.chat.id)
    user_id_c = int(get_par("esim_manual_user_id", message.chat.id))
    caption = message.caption or "Ваш eSIM готов!"
    # Отправляем фото клиенту
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded = bot.download_file(file_info.file_path)
        inline_review = types.InlineKeyboardMarkup(row_width=True)
        inline_review.add(types.InlineKeyboardButton(text="⬆️ Оставить отзыв", callback_data='send_feedback'))
        bot.send_photo(user_id_c, downloaded, caption=caption, reply_markup=inline_review)
        bot.send_message(
            user_id_c,
            f'✅ Ваш eSIM по заявке №<code>{number_c}</code> выдан!\n'
            f'Спасибо за покупку! 🌍',
            parse_mode="HTML"
        )
        # Убираем из очереди pending и отправляем в архив
        try:
            with open("eSIM/esim_pending.json", encoding="utf-8") as pf:
                pending_data = json.load(pf)
            pending_entry = None
            for op in list(pending_data.keys()):
                for entry in pending_data[op]:
                    if str(entry.get("number")) == str(number_c):
                        pending_entry = entry
                pending_data[op] = [u for u in pending_data[op] if str(u.get("number")) != str(number_c)]
                if not pending_data[op]:
                    del pending_data[op]
            with open("eSIM/esim_pending.json", "w", encoding="utf-8") as pf:
                json.dump(pending_data, pf, ensure_ascii=False, indent=4)
            if pending_entry:
                archive_caption = (
                    f'Заявка №{number_c}\n'
                    f'Пользователь: @{pending_entry.get("username")}\n'
                    f'id: {pending_entry.get("user_id")}\n\n'
                    f'Услуга: Esim {pending_entry.get("operator")}\n'
                    f'🎩Ранг: {pending_entry.get("rank")}'
                    f'{pending_entry.get("profit_block", "")}'
                )
                send_photo_to_archives(downloaded, caption=archive_caption)
        except Exception as ex:
            print(f"[eSIM] Ошибка архива: {ex}")
        bot.send_message(message.chat.id, f'✅ eSIM отправлен клиенту по заявке №{number_c}', reply_markup=start_markup(message.chat.id))
    except Exception as e:
        bot.send_message(message.chat.id, f'❌ Ошибка при отправке: {e}', reply_markup=start_markup(message.chat.id))
    update_state(message, START)


@bot.message_handler(func=lambda message: get_state(message) == RESET_REF_BALANCE)
def reset_ref_balance_handler(message):
    if message.text == '🚫 Отмена':
        bot.send_message(message.chat.id, "Отменено", reply_markup=start_markup(message.chat.id))
        update_state(message, START)
        return
    try:
        user_id = int(message.text)
        old_balance = get_ref_balance(user_id)
        reset_ref_balance(user_id)
        try:
            chat2 = bot.get_chat(user_id)
            username = f"@{chat2.username}" if chat2.username else f"{chat2.first_name or ''} {chat2.last_name or ''}".strip()
        except Exception:
            username = str(user_id)
        bot.send_message(
            message.chat.id,
            f"✅ Реферальный баланс аннулирован\n"
            f"👤 {username} (ID: {user_id})\n"
            f"Был: {old_balance} ₽ → Стал: 0 ₽",
            reply_markup=start_markup(message.chat.id)
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}", reply_markup=start_markup(message.chat.id))
    update_state(message, START)


#KURS
@bot.message_handler(func=lambda message: get_state(message) == KURS)
def get_kurs_val(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        try:
            float_value = float(message.text.replace(',', '.'))
            val = get_par_json('val', 'valuta')
            if val == 'usd':
                add_data('usd', float_value, 'valuta')
            elif val == 'eur':
                add_data('eur', float_value, 'valuta')
            elif val == 'try':
                add_data('try', float_value, 'valuta')
            elif val == 'uah':
                add_data('uah', float_value, 'valuta')
            update_state(message, START)
            bot.send_message(message.chat.id, "Валюта изменена", reply_markup=start_markup(message.chat.id))
        except:
            bot.send_message(message.chat.id, "Недопустимое значение", reply_markup=start_markup(message.chat.id, text='🚫 Отмена'))


#VAUCHER
@bot.message_handler(func=lambda message: get_state(message) == VAUCHER)
def get_vaucher(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        code = message.text
        if code.isdigit():
            if len(code) == 10:
                vaucher = check_and_get_denomination(code)
                if vaucher:
                    try:
                        promocode = get_promocode(message.chat.id)
                        with open("promocode.json", encoding="utf-8") as file:
                            data = json.load(file)
                        data[promocode]["wasted_user"].append(message.chat.id)
                        promocode_procent = data[promocode]['procent']
                        procent = ((int(vaucher)/100)*int(promocode_procent))
                        promocode_summa = int(vaucher) + procent
                        with open("promocode.json", "w", encoding="utf-8") as file:
                            json.dump(data, file, ensure_ascii=False, indent=4)
                        delete_promocode(message.chat.id)
                        add_deposit(message.chat.id, str(promocode_summa), description='Промокод')
                        bot.send_message(message.chat.id, f'🎟Код активирован!\n💵Вам на баланс начислено {promocode_summa}₽!', reply_markup = start_markup(message.chat.id))
                        usluga = f'Пополнение баланса.\nСпособ оплаты: Ваучер\nКод ваучера: {code}'
                        number = to_arhiv(message.chat.id, usluga, vaucher)
                        date = datetime.now().date().strftime('%d.%m.%Y')
                        send_to_archives(bot.send_message, f'Дата: {date}\nЗаявка №{number}\nПользователь: @{message.chat.username}\nid: {message.chat.id}\nУслуга: {usluga}\nСумма: {vaucher}\n🎩Ранг: {get_user_rank(message.chat.id)}\nСтатус: ✅Одобрено')
                        update_state(message, START)
                    except:
                        add_deposit(message.chat.id, str(vaucher), description='Ваучер')
                        bot.send_message(message.chat.id, f'🎟Код активирован!\n💵Вам на баланс начислено {vaucher}₽!', reply_markup = start_markup(message.chat.id))
                        usluga = f'Пополнение баланса.\nСпособ оплаты: Ваучер\nКод ваучера: {code}'
                        number = to_arhiv(message.chat.id, usluga, vaucher)
                        date = datetime.now().date().strftime('%d.%m.%Y')
                        send_to_archives(bot.send_message, f'Дата: {date}\nЗаявка №{number}\nПользователь: @{message.chat.username}\nid: {message.chat.id}\nУслуга: {usluga}\nСумма: {vaucher}\n🎩Ранг: {get_user_rank(message.chat.id)}\nСтатус: ✅Одобрено')
                        update_state(message, START)
                    update_money_report_for_day(money = int(vaucher))
                    update_money_report_for_month(money = int(vaucher))
                else:
                    bot.send_message(message.chat.id, "Не верный код ваучера", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
            else:
                bot.send_message(message.chat.id, "Недопустимое значение", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        else:
            bot.send_message(message.chat.id, "Недопустимое значение", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))

#SUMM
@bot.message_handler(func=lambda message: get_state(message) == SUMM)
def get_phone(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        contry = get_par('contry', message.chat.id)
        if message.text.isdigit():
            dalshe = False
            if contry == "ua":
                if 10000>=int(message.text)>= 200:
                    # if float(get_balans(message.chat.id))-(float(message.text)*get_kurs('uah'))>=0:
                    dalshe =True
                else:
                    bot.send_message(message.chat.id, "Пополнение возможно от 200 грн до 10000 грн", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
                    return
            elif contry == "ru":
                if 100 <= int(message.text) <= 50000:
                    # if float(get_balans(message.chat.id))-(float(message.text)+(float(message.text)*0.2))>=0:
                    dalshe =True
                else:
                    bot.send_message(message.chat.id, "Пополнение возможно от 100 до 50000 руб", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
                    return
            elif contry == "es":
                if int(message.text) >= 2:
                    # if float(get_balans(message.chat.id))-(float(message.text)*get_kurs('eur'))>=0:
                    dalshe =True
                else:
                    bot.send_message(message.chat.id, "Пополнение возможно от 2 евро", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
                    return

            if dalshe:
                markup = start_markup(message.chat.id)

                if contry == "ua":
                    suma = round((int(message.text)*get_kurs('uah')), 2)
                    con = 'Украина'
                    add_data('sum', suma, message.chat.id)
                    add_data('original_sum', int(message.text), message.chat.id)
                elif contry == 'es':
                    suma = round((int(message.text)*get_kurs('eur')), 2)
                    con = 'Испания'
                    add_data('sum', suma, message.chat.id)
                    add_data('original_sum', int(message.text), message.chat.id)
                elif contry == 'ru':
                    suma = (float(message.text)+(float(message.text)*0.2))
                    con = 'Россия'
                    add_data('sum', suma, message.chat.id)
                    add_data('sum_bez_com', message.text, message.chat.id)
                # if update_balanse(message.chat.id, 'sum'):
                usluga = f'Мобильный. {con}. {get_par("phone", message.chat.id)}'
                if contry == "ua":
                    markup = types.InlineKeyboardMarkup(row_width=True)
                    inline_button1 = types.InlineKeyboardButton("✅Оплатить", callback_data="ua_ok")
                    inline_button2 = types.InlineKeyboardButton("❌Отклонить", callback_data="ua_no")
                    markup.add(inline_button1)
                    markup.add(inline_button2)
                    bot.send_message(message.chat.id, f'С вашего баланса спишется {suma}₽', reply_markup = markup, parse_mode="HTML")
                elif contry == 'ru':
                    markup = types.InlineKeyboardMarkup(row_width=True)
                    inline_button1 = types.InlineKeyboardButton("✅Оплатить", callback_data="ru_ok")
                    inline_button2 = types.InlineKeyboardButton("❌Отклонить", callback_data="ru_no")
                    markup.add(inline_button1)
                    markup.add(inline_button2)
                    bot.send_message(message.chat.id, f'С вашего баланса спишется {suma}₽', reply_markup = markup, parse_mode="HTML")
                elif contry == 'es':
                    markup = types.InlineKeyboardMarkup(row_width=True)
                    inline_button1 = types.InlineKeyboardButton("✅Оплатить", callback_data="es_ok")
                    inline_button2 = types.InlineKeyboardButton("❌Отклонить", callback_data="es_no")
                    markup.add(inline_button1)
                    markup.add(inline_button2)
                    bot.send_message(message.chat.id, f'С вашего баланса спишется {suma}₽', reply_markup = markup, parse_mode="HTML")
                update_state(message, START)
            # else:
            #     update_state(message, START)
            #     bot.send_message(message.chat.id, 'Недостаточно средств', reply_markup = start_markup(message.chat.id))
            #     inline_markup = types.InlineKeyboardMarkup(row_width=True)
            #     inline_markup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balanse"))
            #     bot.send_message(message.chat.id, 'Пополните баланс', reply_markup = inline_markup)

        else:
            bot.send_message(message.chat.id, "Введите целое число", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))

#INET_SUMM
@bot.message_handler(func=lambda message: get_state(message) == INET_SUMM)
def get_phone(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        if message.text.isdigit():
            if 100<=int(message.text)<= 50000:
                if float(get_balans(message.chat.id))-(float(message.text)+(float(message.text)*0.2))>=0:
                    markup = start_markup(message.chat.id)
                    summ = float(message.text)+(float(message.text)*0.2)
                    add_data('inet_sum', summ, message.chat.id)
                    if update_balanse(message.chat.id, 'inet_sum'):
                        
                        update_total_spent(message.chat.id, float(summ))
                        usluga = f'Интернет RostNet.\nЛогин: {get_par("inet_login", message.chat.id)}.'
                        number = to_arhiv(message.chat.id, usluga, summ)
                        bot.send_message(message.chat.id, f'✅Готово\nВаша заявка №<code>{number}</code> уже в обработке!', reply_markup = markup, parse_mode="HTML")
                        cost = float(message.text)
                        profit = round(summ - cost, 2)
                        profit_line = f'\n💰Себестоимость: {cost}₽\n📈Чистая прибыль: {profit}₽'
                        bot.send_message(adminGroup, f'Заявка №{number}\nПользователь: @{message.chat.username} \nid: {message.chat.id}\nУслуга: {usluga}\n🎩Ранг: {get_user_rank(message.chat.id)}\nСумма: {summ}{profit_line}', reply_markup = admin_markup())
                        update_state(message, START)
                else:
                    update_state(message, START)
                    bot.send_message(message.chat.id, 'Недостаточно средств', reply_markup = start_markup(message.chat.id))
                    inline_markup = types.InlineKeyboardMarkup(row_width=True)
                    inline_markup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balanse"))
                    bot.send_message(message.chat.id, 'Пополните баланс', reply_markup = inline_markup)
            else:
                bot.send_message(message.chat.id, "Пополнение возможно от 100 до 50000₽", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        else:
            bot.send_message(message.chat.id, "Введите целое число", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))

#SEND_TARGET_ID — ввод одного ID для рассылки
@bot.message_handler(func=lambda message: get_state(message) == SEND_TARGET_ID)
def send_target_id(message):
    if message.text == "🚫 Отмена":
        bot.send_message(message.chat.id, "Отменили ввод данных", reply_markup=start_markup(message.chat.id))
        update_state(message, START)
        return
    try:
        user_id = int(message.text.strip())
        add_data('send_target_ids', str(user_id), message.chat.id)
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("Да", callback_data="with_button"))
        inline_markup.add(types.InlineKeyboardButton("Нет", callback_data="no_button"))
        bot.send_message(message.chat.id, f'Получатель: {user_id}\nСообщение с кнопкой?', reply_markup=inline_markup)
    except ValueError:
        bot.send_message(message.chat.id, 'Введите корректный числовой ID:', reply_markup=start_markup(message.chat.id, text='🚫 Отмена'))

#SEND_TARGET_LIST — ввод списка ID для рассылки
@bot.message_handler(func=lambda message: get_state(message) == SEND_TARGET_LIST)
def send_target_list(message):
    if message.text == "🚫 Отмена":
        bot.send_message(message.chat.id, "Отменили ввод данных", reply_markup=start_markup(message.chat.id))
        update_state(message, START)
        return
    raw = message.text.replace(',', ' ').replace('\n', ' ').split()
    ids = []
    for item in raw:
        try:
            ids.append(int(item.strip()))
        except ValueError:
            pass
    if not ids:
        bot.send_message(message.chat.id, 'Не найдено ни одного ID. Введите ID через запятую или каждый с новой строки:', reply_markup=start_markup(message.chat.id, text='🚫 Отмена'))
        return
    add_data('send_target_ids', json.dumps(ids), message.chat.id)
    inline_markup = types.InlineKeyboardMarkup(row_width=True)
    inline_markup.add(types.InlineKeyboardButton("Да", callback_data="with_button"))
    inline_markup.add(types.InlineKeyboardButton("Нет", callback_data="no_button"))
    bot.send_message(message.chat.id, f'Получателей: {len(ids)}\nСообщение с кнопкой?', reply_markup=inline_markup)

#SEND
@bot.message_handler(func=lambda message: get_state(message) == SEND)
def send_all(message):
    import time as _time
    print(f'=== send_all ВЫЗВАН, chat_id={message.chat.id}, text={message.text} ===')
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=markup)
        update_state(message, START)
        try:
            for file_name in file_names:
                os.remove(file_name)
            file_names.clear()
        except:
            pass
        return

    progress_msg = bot.send_message(message.chat.id, '📤 Рассылка начата...\n\nОтправлено: 0')

    def update_progress(sent, total, success, fail):
        try:
            bot.edit_message_text(
                f'📤 Рассылка в процессе...\n\nОтправлено: {sent}/{total}\n✅ Успешно: {success} | ❌ Ошибок: {fail}',
                chat_id=message.chat.id,
                message_id=progress_msg.message_id
            )
        except Exception:
            pass

    try:
        send_target = ''
        try:
            send_target = get_par('send_target', message.chat.id)
        except:
            pass
        if send_target == 'one':
            try:
                uid = int(get_par('send_target_ids', message.chat.id))
                all_users = [uid]
            except:
                all_users = []
        elif send_target == 'list':
            try:
                ids = get_par('send_target_ids', message.chat.id)
                if isinstance(ids, str):
                    ids = json.loads(ids)
                all_users = ids
            except:
                all_users = []
        elif send_target == 'inactive':
            all_users = get_inactive_users()
        else:
            all_users = get_all_users()

        action_button = get_par('button_action', message.chat.id) or ''
        action_image = get_par('action_image', message.chat.id) or ''
        print(f'action_button={action_button}, action_image={action_image}, users={len(all_users)}')

        # Собираем кнопки из JSON если есть
        inline_markup = None
        if action_button == 'True':
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            try:
                buttons = get_par('buttons_json', message.chat.id)
                if isinstance(buttons, str):
                    buttons = json.loads(buttons)
                if buttons:
                    for btn in buttons:
                        inline_markup.add(types.InlineKeyboardButton(btn["text"], url=btn["url"]))
            except Exception as e:
                print(f"Ошибка кнопок: {e}")

        base_text = message.html_text or message.text or ''
        has_name_placeholder = '{Name}' in base_text
        plain_text = message.text or ''

        def get_text_for_user(uid):
            if not has_name_placeholder:
                return base_text
            name = get_username(uid) or str(uid)
            return base_text.replace('{Name}', name)

        def get_plain_for_user(uid):
            if '{Name}' not in plain_text:
                return plain_text
            name = get_username(uid) or str(uid)
            return plain_text.replace('{Name}', name)

        success_count = 0
        blocked_count = 0
        fail_count = 0
        errors = []
        too_long = False
        wrong_url = False

        def handle_send_error(e, user_id):
            nonlocal blocked_count, fail_count, too_long, wrong_url
            err_text = str(e)
            if 'blocked' in err_text or 'deactivated' in err_text or 'kicked' in err_text or 'chat not found' in err_text:
                add_blocked_user(user_id)
                blocked_count += 1
            else:
                fail_count += 1
                if 'message is too long' in err_text or 'caption is too long' in err_text:
                    too_long = True
                elif 'Wrong HTTP URL' in err_text:
                    wrong_url = True
                else:
                    if len(errors) < 5:
                        errors.append(f'{user_id}: {e}')
            print(f'Ошибка отправки {user_id}: {e}')

        def try_send_message(uid, text, **kwargs):
            try:
                bot.send_message(uid, text, parse_mode='HTML', **kwargs)
                return True
            except telebot.apihelper.ApiTelegramException as e:
                if 'ENTITY_TEXT_INVALID' in str(e):
                    bot.send_message(uid, get_plain_for_user(uid), **kwargs)
                    return True
                raise

        def try_send_photo(uid, photo_bytes, caption, **kwargs):
            try:
                bot.send_photo(uid, photo=photo_bytes, caption=caption, parse_mode='HTML', **kwargs)
                return True
            except telebot.apihelper.ApiTelegramException as e:
                if 'ENTITY_TEXT_INVALID' in str(e):
                    bot.send_photo(uid, photo=photo_bytes, caption=get_plain_for_user(uid), **kwargs)
                    return True
                raise

        total = len(all_users)

        if action_button == 'True' and action_image != 'True':
            for i, user_id in enumerate(all_users, 1):
                print(f'\rРассылка: {i}/{total} ', end='', flush=True)
                try:
                    try_send_message(user_id, get_text_for_user(user_id), reply_markup=inline_markup)
                    delete_blocked_user(user_id)
                    success_count += 1
                except Exception as e:
                    handle_send_error(e, user_id)
                _time.sleep(0.05)
                if i % 10 == 0:
                    update_progress(i, total, success_count, fail_count)

        elif action_button != 'True' and action_image == 'True':
            for i, user_id in enumerate(all_users, 1):
                print(f'\rРассылка: {i}/{total}', end='', flush=True)
                try:
                    with open(file_names[0], 'rb') as new_file:
                        try_send_photo(user_id, new_file.read(), get_text_for_user(user_id))
                    delete_blocked_user(user_id)
                    success_count += 1
                except Exception as e:
                    handle_send_error(e, user_id)
                _time.sleep(0.05)
                if i % 10 == 0:
                    update_progress(i, total, success_count, fail_count)
            for file_name in file_names:
                os.remove(file_name)
            file_names.clear()

        elif action_button == 'True' and action_image == 'True':
            for i, user_id in enumerate(all_users, 1):
                print(f'\rРассылка: {i}/{total}', end='', flush=True)
                try:
                    with open(file_names[0], 'rb') as new_file:
                        try_send_photo(user_id, new_file.read(), get_text_for_user(user_id), reply_markup=inline_markup)
                    delete_blocked_user(user_id)
                    success_count += 1
                except Exception as e:
                    handle_send_error(e, user_id)
                _time.sleep(0.05)
                if i % 10 == 0:
                    update_progress(i, total, success_count, fail_count)
            for file_name in file_names:
                os.remove(file_name)
            file_names.clear()

        else:
            for i, user_id in enumerate(all_users, 1):
                print(f'\rРассылка: {i}/{total}', end='', flush=True)
                try:
                    try_send_message(user_id, get_text_for_user(user_id))
                    delete_blocked_user(user_id)
                    success_count += 1
                except Exception as e:
                    handle_send_error(e, user_id)
                _time.sleep(0.05)
                if i % 10 == 0:
                    update_progress(i, total, success_count, fail_count)

        print()

        report = f'✅ Рассылка завершена\n\nВсего: {len(all_users)}\nУспешно: {success_count}\nЗаблокировали бота: {blocked_count}\nОшибок: {fail_count}'
        if too_long:
            has_image = action_image == 'True'
            max_len = 1024 if has_image else 4096
            msg_len = len(message.html_text) if message.html_text else 0
            report += f'\n\n⚠️ Сообщение слишком длинное. Ваше: {msg_len}, максимум: {max_len} символов'
            if has_image:
                report += ' (подпись к фото)'
            else:
                report += ' (текст)'
        if wrong_url:
            report += f'\n\n⚠️ Неправильный URL в кнопке. Пример URL: https://t.me/PayTelekom_bot'
        if errors:
            report += '\n\nОшибки:\n' + '\n'.join(errors)
        try:
            bot.edit_message_text(report, chat_id=message.chat.id, message_id=progress_msg.message_id)
        except Exception:
            bot.send_message(message.chat.id, report)
        bot.send_message(message.chat.id, '👆 Итог рассылки', reply_markup=start_markup(message.chat.id))
        delete_file(message.chat.id)
        try:
            for file_name in file_names:
                os.remove(file_name)
            file_names.clear()
        except:
            pass
        update_state(message, START)

    except Exception as e:
        print(f'[BROADCAST] Критическая ошибка: {e}')
        import traceback
        traceback.print_exc()
        bot.send_message(message.chat.id, f'❌ Ошибка рассылки: {e}', reply_markup=start_markup(message.chat.id))
        update_state(message, START)

#SEND_BUTTON
@bot.message_handler(func=lambda message: get_state(message) == SEND_BUTTON)
def get_button_text(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        bot.send_message(message.chat.id, 'Введите ссылку для кнопки:', reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        # Сохраняем текст текущей кнопки во временное поле
        add_data('_tmp_btn_text', message.text, message.chat.id)
        update_state(message, SEND_URL)


#SEND_URL
@bot.message_handler(func=lambda message: get_state(message) == SEND_URL)
def get_button_url(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
        for file_name in file_names:
            os.remove(file_name)
        file_names.clear()
    else:
        # Добавляем кнопку в JSON-массив
        btn_text = get_par('_tmp_btn_text', message.chat.id)
        buttons = get_par('buttons_json', message.chat.id)
        if isinstance(buttons, str):
            try:
                buttons = json.loads(buttons)
            except:
                buttons = []
        if not isinstance(buttons, list):
            buttons = []
        btn_color = get_par('_tmp_btn_color', message.chat.id) or 'none'
        btn_entry = {"text": btn_text, "url": message.text}
        if btn_color != 'none':
            btn_entry["style"] = btn_color
        buttons.append(btn_entry)
        add_data('buttons_json', json.dumps(buttons, ensure_ascii=False), message.chat.id)
        add_data('button_action', 'True', message.chat.id)

        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("➕ Добавить ещё кнопку", callback_data="add_more_button"))
        inline_markup.add(types.InlineKeyboardButton("✅ Продолжить", callback_data="buttons_done"))
        bot.send_message(message.chat.id, f'Кнопка "{btn_text}" добавлена. Всего кнопок: {len(buttons)}', reply_markup=inline_markup)

#SEND_IMAGE
@bot.message_handler(func=lambda message: get_state(message) == SEND_IMAGE, content_types=['photo'])
def get_image(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
        try:
            for file_name in file_names:
                os.remove(file_name)
            file_names.clear()
        except:
            pass
    else:
        add_data(key='action_image', info='True', file=message.chat.id)
        photo = message.photo[-1]

        file_info = bot.get_file(photo.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Получаем имя файла из пути
        file_name = file_info.file_path.split('/')[-1]
        file_names.append(file_name)

        # Сохраняем загруженный файл на диск в бинарном режиме
        with open(file_name, 'wb') as new_file:
            new_file.write(downloaded_file)

        bot.send_message(message.chat.id, 'Введите сообщение для отправки:', reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        update_state(message, SEND)

#DEPOSIT_SUMM
@bot.message_handler(func=lambda message: get_state(message) == DEPOSIT_SUMM)
def get_phone(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:

        if message.text.isdigit():
            opl = get_par('sposob_oplati', message.chat.id)
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_markup.add(types.InlineKeyboardButton("✅Оплачено", callback_data="deposit_compite"))
            inline_markup.add(types.InlineKeyboardButton("❌Отказаться от оплаты", callback_data="deposit_cancel"))
            inline_markup2 = telebot.types.InlineKeyboardMarkup()

            # if opl == 'Payeer':
            #     text = f'📲Переведите {message.text}₽ на электронный кошелёк PAYEER.\n\n🅿️  P1078028627'
            if opl == "BankRF":
                user_id = message.chat.id
                is_bankrf = user_payment_methods.get(user_id) == "BankRF"
                global Nicepay
                data = json.load(open("replishment_active.json", encoding="utf-8"))
                db = sqlite3.connect('files/cards.db', timeout=10)
                cursor = db.cursor()
                cursor.execute('SELECT COUNT(*) FROM cards')
                count = cursor.fetchone()[0]
                if 1 == 1:
                    bot.send_message(message.chat.id, '''
Для пополнения данным способом обратитесь в Службу Поддержки.

📩 Пример Сообщения:
"Здравствуйте! Хочу пополнить баланс на (сумма)."

🔹 Писать сюда: @TGPaySupport_bot
                    ''')
                else:

                    if is_bankrf or count <= 0 and data["nicepay_active"] == 1:
                        user_id = message.chat.id

                        method = "NicePay"
                        user_payment_methods[user_id] = "NicePay"
                        process_payment(message, method)

                    else:
                        current_time = datetime.now().time().replace(microsecond=0)

                        start_time = time(22, 0)  # 22:00
                        end_time = time(6, 0)  # 06:00

                        data = json.load(open("replishment_active.json", encoding="utf-8"))

                        if data['time_active'] == 1:
                            if current_time >= start_time or current_time < end_time:
                                bot.send_message(message.chat.id,
                                                 "Пополнение картами РФ не работает в ночное время.")
                                return

                        if 100 <= int(message.text) <= 50000:
                            user_payment_methods[user_id] = "BankRF"
                            bank = rotaciya()
                            add_data('bank', bank, message.chat.id)
                            if 'http' in bank:
                                text = f'👇Перейдите по ссылке для оплаты :\n\n{bank}\n\n<b>Комментарии к переводу не писать</b>❗️'
                            else:
                                text = f'👇Переведите {message.text}₽  на ниже указанные реквизиты:\n\n{bank}\n\n<b>Комментарии к переводу не писать</b>❗️'
                            add_data('deposit_sum', message.text, message.chat.id)
                            bot.send_message(message.chat.id, text, reply_markup=inline_markup, parse_mode='HTML')
                            update_state(message, START)

                        else:
                            bot.send_message(message.chat.id, "Пополнение возможно от 100 до 50000₽", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
            elif opl == "BankRF2":
                user_id = message.chat.id
                is_bankrf = user_payment_methods.get(user_id) == "BankRF"
                global Nicepay
                data = json.load(open("replishment_active.json", encoding="utf-8"))
                db = sqlite3.connect('files/cards.db', timeout=10)
                cursor = db.cursor()
                cursor.execute('SELECT COUNT(*) FROM cards')
                count = cursor.fetchone()[0]
                if 1 == 1:
                    bot.send_message(message.chat.id, '''
                    Для пополнения данным способом обратитесь в Службу Поддержки.

📩 Пример Сообщения:
"Здравствуйте! Хочу пополнить баланс на (сумма)."

🔹 Писать сюда: @TGPaySupport_bot
                    ''')
            elif opl == 'Payeer':
                if 100 <= int(message.text) <= 50000:
                     bot.send_message(message.chat.id, "Оплата временно недоступна.")
                     #add_data('deposit_sum', message.text, message.chat.id)
                     #text = f'📲Переведите {message.text}₽ на электронный кошелёк PAYEER.\n\n🅿️  P1078028627'
                     #bot.send_message(message.chat.id, text, reply_markup=inline_markup, parse_mode='HTML')
                     update_state(message, START)
                else:
                    bot.send_message(message.chat.id, "Пополнение возможно от 100 до 50 000₽", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))

            elif opl == "Yomoney":
                if 100 <= int(message.text) <= 50000:
                    add_data('deposit_sum', message.text, message.chat.id)
                    text = f'📲Оплатите {message.text} перейдя по данной ссылке :\n\nhttps://yoomoney.ru/to/4100118484584640'
                    bot.send_message(message.chat.id, text, reply_markup = inline_markup, parse_mode='HTML')
                    update_state(message, START)
                else:
                    bot.send_message(message.chat.id, "Пополнение возможно от 100 до 50 000₽", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        else:
            bot.send_message(message.chat.id, "Введите целое число", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))


@bot.callback_query_handler(func=lambda call: call.data.startswith("NicePay_"))
def handle_payment_method(call):
    user_id = int(call.data.split("_")[-1])

    user_payment_methods[user_id] = "NicePay"
    method = "NicePay"

    bot.send_message(user_id, f"💰 Введите сумму пополнения:")
    bot.register_next_step_handler(call.message, process_payment, method)

@bot.callback_query_handler(func=lambda call: call.data.startswith("accepted_key:"))
def accepted_key(call):
    admin_id = call.from_user.id
    client_chat_id = int(call.data.split(":")[1])
    group_id = call.message.chat.id

    # удаляем сообщение с кнопкой
    bot.delete_message(group_id, call.message.message_id)

    # сообщение "введите ключ"
    ask_msg = bot.send_message(group_id, "🔑 Введите ключ:")

    admin_waiting_key[admin_id] = {
        "client_id": client_chat_id,
        "group_id": group_id,
        "ask_msg_id": ask_msg.message_id
    }

    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: message.from_user.id in admin_waiting_key)
def get_vpn_key_from_admin(message):
    admin_id = message.from_user.id
    data = admin_waiting_key.pop(admin_id)

    key = message.text
    group_id = data["group_id"]
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("iOS", callback_data="i_ios"))
    markup.add(types.InlineKeyboardButton("Android", callback_data="i_android"))
    markup.add(types.InlineKeyboardButton("Windows", callback_data="i_windows"))
    markup.add(types.InlineKeyboardButton("MacOS", callback_data="i_macos"))
    markup.add(types.InlineKeyboardButton("Smart TV", callback_data="i_smarttv"))
    bot.delete_message(group_id, message.message_id)
    bot.delete_message(group_id, data["ask_msg_id"])
    bot.send_message(
        data["client_id"],
        f"🗝Ваш ключ активации: {key}\n\nИнструкции по подключению:",
        reply_markup=markup
    )

    try:
        ok = bot.send_message(group_id, "✅ Отправлено")
        bot.delete_message(group_id, ok.message_id)
    except:
        pass


def process_payment(message, method):
    try:
        amount = int(message.text)
        if not (100 <= amount <= 50000):
            bot.send_message(message.chat.id, "⚠️ Пополнение возможно от 100 до 50000₽")
            return

        create_nicepay_payment(message, amount)

    except ValueError:
        bot.send_message(message.chat.id, "⚠️ Введите корректную сумму.")


def create_nicepay_payment(message, amount):
    amount1 = str(amount) + "00"
    amount = int(amount1)
    print(amount1)
    try:
        print("1")
        data = get_nicepay_link(f"order_{message.chat.id}", amount, "RUB", f"user_{message.chat.id}")
        print("NicePay Response:", data)  # Логирование для отладки

        if "data" not in data or "link" not in data["data"]:
            print("Ошибка: Нет 'link' в ответе от NicePay", data)  # Вывод для дебага
            bot.send_message(message.chat.id, "⚠️ Ошибка при создании платежа. Попробуйте позже.")
            return

        link = data["data"]["link"]
        inline_markup = types.InlineKeyboardMarkup(row_width=1)
        inline_markup.add(
            types.InlineKeyboardButton("✅ Оплачено", callback_data="check_nicepay"),
            types.InlineKeyboardButton("❌ Отказаться от оплаты", callback_data="deposit_cancel")
        )

        bot.send_message(message.chat.id, f"Ссылка для оплаты NicePay: {link}", reply_markup=inline_markup)
        payment_ids[message.chat.id] = data["data"].get('payment_id')
        print(payment_ids[message.chat.id])

    except requests.exceptions.RequestException:
        bot.send_message(message.chat.id, "⚠️ Ошибка соединения с платежной системой.")

#SEND_RECEIPT
@bot.message_handler(func=lambda message: get_state(message) == SEND_RECEIPT, content_types=['photo', 'document'])
def get_receipt(message):
    try:
        photo = message.photo[-1]

        file_info = bot.get_file(photo.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Сохраняем загруженный файл на диск в бинарном режиме
        with open(f"receipt_{message.chat.id}.jpg", 'wb') as new_file:
            new_file.write(downloaded_file)

        summ = get_par("deposit_sum", message.chat.id)
        sposob = get_par("sposob_oplati", message.chat.id)
        if sposob == 'Payeer':
            sposob = 'Payeer Rub'

        elif sposob == "BankRF":
            unspleated_sposob = get_par("bank", message.chat.id)
            sposob = " ".join(unspleated_sposob.split()[1:])
        try:
            with open("promocode.json", encoding="utf-8") as file:
                data = json.load(file)
            promocode = get_promocode(message.chat.id)
            if data[promocode]['procent']:
                promocode_procent = data[promocode]['procent']
            else:
                promocode_procent = 0
            procent = ((int(summ)/100)*int(promocode_procent))
            promocode_summa = int(summ) + procent
            usluga = f'Пополнение баланса.\nСпособ оплаты: {sposob}'
            number = to_arhiv(message.chat.id, usluga, summ)
            mes = f'Заявка №{number}\n😉Ожидайте зачисления на баланс\n⌚️В крайних случаях деньги могут поступить в течении 24-х часов'
            with open(f"receipt_{message.chat.id}.jpg", 'rb') as new_file:
                bot.send_photo(adminGroup, photo=new_file.read(), caption=f'Заявка №{number}\nПользователь: @{message.chat.username} \nid: {message.chat.id}\nУслуга: {usluga}\n🎩Ранг: {get_user_rank(message.chat.id)}\nСумма: {summ}\nСумма с промокодом: {promocode_summa}', reply_markup = admin_markup())
            bot.send_message(message.chat.id, mes, reply_markup=start_markup(message.chat.id))
            update_state(message, START)
        except:
            usluga = f'Пополнение баланса.\nСпособ оплаты: {sposob}'
            number = to_arhiv(message.chat.id, usluga, summ)
            mes = f'Заявка №{number}\n😉Ожидайте зачисления на баланс\n⌚️В крайних случаях деньги могут поступить в течении 24-х часов'
            with open(f"receipt_{message.chat.id}.jpg", 'rb') as new_file:
                bot.send_photo(adminGroup, photo=new_file.read(), caption=f'Заявка №{number}\nПользователь: @{message.chat.username} \nid: {message.chat.id}\nУслуга: {usluga}\n🎩Ранг: {get_user_rank(message.chat.id)}\nСумма: {summ}', reply_markup = admin_markup())
            bot.send_message(message.chat.id, mes, reply_markup=start_markup(message.chat.id))
            update_state(message, START)
    except:
        # получить основную информацию о файле и подготовить его к загрузке
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        with open(f"receipt_{message.chat.id}.pdf", 'wb') as new_file:
                new_file.write(downloaded_file)
        summ = get_par("deposit_sum", message.chat.id)
        sposob = get_par("sposob_oplati", message.chat.id)
        if sposob == 'Payeer':
            sposob = 'Payeer Rub'
        elif sposob == "BankRF":
            unspleated_sposob = get_par("bank", message.chat.id)
            sposob = " ".join(unspleated_sposob.split()[1:])
        try:
            with open("promocode.json", encoding="utf-8") as file:
                data = json.load(file)
            promocode = get_promocode(message.chat.id)
            promocode_procent = data[promocode]['procent']
            procent = ((int(summ)/100)*int(promocode_procent))
            promocode_summa = int(summ) + procent
            usluga = f'Пополнение баланса.\nСпособ оплаты: {sposob}'
            number = to_arhiv(message.chat.id, usluga, summ)
            mes = f'Заявка №{number}\n😉Ожидайте зачисления на баланс\n⌚️В крайних случаях деньги могут поступить в течении 24-х часов'
            with open(f"receipt_{message.chat.id}.pdf", 'rb') as new_file:
                bot.send_document(adminGroup, document=new_file, caption=f'Заявка №{number}\nПользователь: @{message.chat.username} \nid: {message.chat.id}\nУслуга: {usluga}\n🎩Ранг: {get_user_rank(message.chat.id)}\nСумма: {summ}\nСумма с промокодом: {promocode_summa}', reply_markup = admin_markup())
            bot.send_message(message.chat.id, mes, reply_markup=start_markup(message.chat.id))
            update_state(message, START)
        except:
            usluga = f'Пополнение баланса.\nСпособ оплаты: {sposob}'
            number = to_arhiv(message.chat.id, usluga, summ)
            mes = f'Заявка №{number}\n😉Ожидайте зачисления на баланс\n⌚️В крайних случаях деньги могут поступить в течении 24-х часов'
            with open(f"receipt_{message.chat.id}.pdf", 'rb') as new_file:
                bot.send_document(adminGroup, document=new_file, caption=f'Заявка №{number}\nПользователь: @{message.chat.username} \nid: {message.chat.id}\nУслуга: {usluga}\n🎩Ранг: {get_user_rank(message.chat.id)}\nСумма: {summ}', reply_markup = admin_markup())
            bot.send_message(message.chat.id, mes, reply_markup=start_markup(message.chat.id))
            update_state(message, START)

#GET_LOGIN_INET
@bot.message_handler(func=lambda message: get_state(message) == GET_LOGIN_INET)
def get_phone(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        markup = start_markup(message.chat.id, text='🚫 Отмена')
        bot.send_message(message.chat.id, 'Введите сумму пополнения :', reply_markup = markup)
        add_data('inet_login', message.text, message.chat.id)
        update_state(message, INET_SUMM)

#GET_FEEDBACK
@bot.message_handler(func=lambda message: get_state(message) == GET_FEEDBACK)
def get_phone(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        markup = start_markup(message.chat.id)
        send_feedback(message)
        try:
            date = datetime.now().date().strftime('%d.%m.%Y')
            create_review_image(message.text, message.chat.first_name, date, filename="review_1.png")
            photo_path = "review_1.png"
            with open(photo_path, 'rb') as photo:
                bot.send_photo(CHANNEL_ID, photo=photo, caption="⭐️⭐️⭐️⭐️⭐️")
            if os.path.exists(photo_path):
                os.remove(photo_path)
        except Exception as e:
            print(f"[FEEDBACK] Ошибка при создании/отправке карточки отзыва: {e}")
        bot.send_message(message.chat.id, 'Благодарим за отзыв!', reply_markup=markup)
        update_state(message, START)

@bot.message_handler(func=lambda message: get_state(message) == CREATE_NUM_REQUEST)
def create_num_request(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        if message.text.isdigit():
            global create_req_id
            create_req_id = int(message.text)
            balans = get_balans(create_req_id)
            bot.send_message(message.chat.id, f'ID: {create_req_id} \n Balance: {balans}. \nТеперь введите номер:')
            update_state(message, GET_NUM)
        else:
            bot.send_message(message.chat.id, 'Неверно!')
            return
#SET_ID_BALANS
@bot.message_handler(func=lambda message: get_state(message) == SET_ID_BALANS)
def get_balanse(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        if message.text.isdigit():
            markup = start_markup(message.chat.id)
            balans = get_balans(int(message.text))
            add_data('id_admin', message.text, message.chat.id)
            bot.send_message(message.chat.id, f'Баланс: {balans} р. Введите новое значение', reply_markup = markup)
            update_state(message, GET_ID_SUMM)
        else:
            bot.send_message(message.chat.id, 'Неверно!')
            return

@bot.message_handler(func=lambda message: get_state(message) == SET_MODERATOR_ID_BALANS)
def set_moderator_id_balans(message):
    if message.text == "🚫 Отмена":
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=start_markup(message.chat.id))
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        if message.text.isdigit():
            mod_id = int(message.text)
            b_uah = get_moderator_balans(mod_id, 'uah')
            b_usd = get_moderator_balans(mod_id, 'usd')
            uah_str = f'{b_uah} ₴' if b_uah is not None else 'не найден'
            usd_str = f'{b_usd} $' if b_usd is not None else 'не найден'
            add_data('id_admin', message.text, message.chat.id)
            bot.send_message(message.chat.id,
                f'Баланс модератора {mod_id}:\n  ₴: {uah_str}\n  $: {usd_str}\n\nВведите сумму:',
                reply_markup=start_markup(message.chat.id, text='🚫 Отмена'))
            update_state(message, GET_MODERATOR_ID_SUMM)
        else:
            bot.send_message(message.chat.id, 'Неверно! Введите числовой ID.')


@bot.message_handler(func=lambda message: get_state(message) == GET_MODERATOR_ID_SUMM)
def get_moderator_id_summ(message):
    if message.text == "🚫 Отмена":
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=start_markup(message.chat.id))
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        try:
            val = float(message.text.replace(',', '.'))
        except ValueError:
            bot.send_message(message.chat.id, 'Неверно! Введите число.')
            return
        add_data('mod_summ', str(val), message.chat.id)
        inline_markup = types.InlineKeyboardMarkup(row_width=2)
        inline_markup.add(
            types.InlineKeyboardButton("₴ Гривна", callback_data="mod_currency_uah"),
            types.InlineKeyboardButton("$ Доллар", callback_data="mod_currency_usd")
        )
        bot.send_message(message.chat.id, f'Сумма: {val}\nВыберите валюту:', reply_markup=inline_markup)
        update_state(message, START)
        
@bot.callback_query_handler(func=lambda call: call.data in ["mod_currency_uah", "mod_currency_usd"])
def mod_currency_handler(call):
    currency = 'uah' if call.data == "mod_currency_uah" else 'usd'
    mod_id = int(get_par('id_admin', call.message.chat.id))
    summ = float(get_par('mod_summ', call.message.chat.id))
    success = add_mod_deposit(mod_id, summ, currency)
    if success:
        new_bal = get_moderator_balans(mod_id, currency)
        symbol = '₴' if currency == 'uah' else '$'
        bot.edit_message_text(
            f'✅ Баланс модератора {mod_id} ({symbol}) изменён.\nНовый баланс: {new_bal} {symbol}',
            chat_id=call.message.chat.id, message_id=call.message.message_id)
    else:
        bot.edit_message_text('❌ Ошибка.', chat_id=call.message.chat.id, message_id=call.message.message_id)
    delete_file(call.message.chat.id)
    
@bot.message_handler(func=lambda message: get_state(message) == SET_VALUE)
def set_value(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        if message.text.replace('-', '').replace('.', '').isdigit():
            inline = types.InlineKeyboardButton("₴", callback_data="mod_uah"), types.InlineKeyboardButton("$", callback_data="mod_usd")
            bot.send_message(message.chat.id, 'Выберите валюту', reply_markup= inline)
        
        else:
            bot.send_message(message.chat.id, 'Неверно! Введите числовое значение.')
            return

@bot.message_handler(func=lambda message: get_state(message) == GET_NUM)
def get_num(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        if is_valid_phone_number(message.text):
            global create_req_num
            create_req_num = message.text
            bot.send_message(message.chat.id, f'ID: {create_req_id}\nНомер: {create_req_num}\nТеперь введите сумму в гривнах:')
            update_state(message, GET_NUM_SUMM)
        else:
            bot.send_message(message.chat.id, 'Неверно!')
            return
@bot.message_handler(func=lambda message: get_state(message) == GET_NUM_SUMM)
def get_num_summ(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        if int(message.text) <= 5000:
            create_req_summ = int(message.text)
            kurs = get_kurs("uah")
            v_rubli = create_req_summ * kurs
            bot.send_message(message.chat.id, f'ID: {create_req_id}\nНомер: {create_req_num}\nСумма в гривнах: {create_req_summ}\nСумма в рублях: {v_rubli}₱')
            admin_num(message, create_req_id, int(message.text))
            update_state(message, START)
        else:
            bot.send_message(message.chat.id, 'Неверно!')
            return

#GET_ID_SUMM
@bot.message_handler(func=lambda message: get_state(message) == GET_ID_SUMM)
def get_balanse(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        if message.text.replace('-', '').isdigit():
            markup = start_markup(message.chat.id)
            id = get_par('id_admin', message.chat.id)
            suuu = add_deposit(int(id), message.text, description='Изменение баланса администратором')
            bot.send_message(message.chat.id, f'Баланс изменён', reply_markup = markup)
            usluga = f'Пополнение баланса вручную.\n'
            date = datetime.now().date().strftime('%d.%m.%Y')
            if USER_WAIT_FOR_CONTINUE[int(id)]:
                required = float(USER_REQUEST_DATA[int(id)]["sum"])
                print(get_balans(int(id)), required)
                if float(get_balans(int(id))) >= required:
                    phone = USER_REQUEST_DATA[int(id)].get("phone", "Неизвестно")
                    sum_rub = USER_REQUEST_DATA[int(id)].get("sum", "0")
                    sum_uah = USER_REQUEST_DATA[int(id)].get("original_sum", "0")
                    service = USER_REQUEST_DATA[int(id)].get("service", "Не известно")
                    USER_WAIT_FOR_CONTINUE[int(id)] = False
                    markup = types.InlineKeyboardMarkup()
                    print(USER_WAIT_FOR_CONTINUE)
                    markup.add(
                        types.InlineKeyboardButton("Продолжить оформление", callback_data="resume_request"))
                    if "украина" in service.lower():
                        text = (f"😊 Баланс пополнен\n\nНо пополнение ещё не завершено ❗️\n\nДеньги сейчас на внутреннем балансе. Чтобы они поступили на мобильный — нужно подтвердить заявку 👇\n\n"
                        f"📞 Телефон: <code>{phone}</code>\n"
                        f"💵 Сумма в рублях: <b>{sum_rub}₽</b>\n"
                        f"🇺🇦 Сумма в гривнах: <b>{sum_uah}₴</b>\n\n",
                        f"👉 Подтверди, иначе не зачислится",)
                    elif "россия" in service.lower():
                        text = (f"😊 Баланс пополнен\n\nНо пополнение ещё не завершено ❗️\n\nДеньги сейчас на внутреннем балансе. Чтобы они поступили на мобильный — нужно подтвердить заявку 👇\n\n"
                        f"📞 Телефон: <code>{phone}</code>\n"
                        f"💵 Сумма в рублях: <b>{sum_rub}₽</b>\n")
                    bot.send_message(
                        id,
                        text,
                        reply_markup=markup,
                        parse_mode="HTML"
                    )
            bot.send_message(id, f'✅Ваш баланс пополнен на сумму {suuu} р.')
            send_to_archives(bot.send_message, f'Дата: {date}\nid: {id}\nУслуга: {usluga}\nСумма: {suuu} р.\n🎩Ранг: {get_user_rank(message.chat.id)}\nСтатус: ✅Одобрено')
            update_state(message, START)
        else:
            bot.send_message(message.chat.id, 'Неверно!')
            update_state(message, START)

#AKK
@bot.message_handler(func=lambda message: get_state(message) == AKK)
def get_phone(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        markup = start_markup(message.chat.id)
        usluga = f'Аккаунты.\nТекст пользователя:\n➖➖➖➖➖➖➖\n{message.text}'
        bot.send_message(message.chat.id, f'✅Ваш заказ отправлен!\n🧑‍💻Ожидайте ответ от нашего специалиста!', reply_markup = markup)
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("✅Выставить счёт✅", callback_data="schet"))
        inline_markup.add(types.InlineKeyboardButton("📣Начать диалог📣", callback_data="start_dialog"))
        inline_markup.add(types.InlineKeyboardButton("❌Закончить диалог❌", callback_data="stop_dialog"))
        bot.send_message(adminGroup, f'Заявка Аккаунты\nПользователь: @{message.chat.username} \nid: {message.chat.id}\n🎩Ранг: {get_user_rank(message.chat.id)}\nУслуга: {usluga}', reply_markup = inline_markup)
        update_state(message, START)

#PHONE
@bot.message_handler(func=lambda message: get_state(message) == PHONE)
def get_phone(message):
    '''Получает Телефон и записываем в базу'''
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)


    elif message.text.replace(' ','').replace('+','').replace(' ','').isdigit() and len(message.text.replace(' ','').replace('+',''))>10:
        contry1 = get_par('contry', message.chat.id)
        if message.text[0] != "+":
            message.text = "+" + message.text
        if contry1 == "ua" and message.text[:3] == "+38":
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_button1 = types.InlineKeyboardButton("Да✅", callback_data="my_phone")
            inline_button2 = types.InlineKeyboardButton("Нет, изменить✍️", callback_data="edit_phone")
            inline_markup.add(inline_button1)
            inline_markup.add(inline_button2)
            bot.send_message(message.chat.id, f"{message.text} Ваш номер телефона?", reply_markup = inline_markup)
            update_state(message, START)
            add_data('phone', message.text, message.chat.id)
        elif contry1 == "ru" and message.text[:2] in ["+7", "+8"]:
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_button1 = types.InlineKeyboardButton("Да✅", callback_data="my_phone")
            inline_button2 = types.InlineKeyboardButton("Нет, изменить✍️", callback_data="edit_phone")
            inline_markup.add(inline_button1)
            inline_markup.add(inline_button2)
            bot.send_message(message.chat.id, f"{message.text} Ваш номер телефона?", reply_markup = inline_markup)
            update_state(message, START)
            add_data('phone', message.text, message.chat.id)
        elif contry1 == "es":
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_button1 = types.InlineKeyboardButton("Да✅", callback_data="my_phone")
            inline_button2 = types.InlineKeyboardButton("Нет, изменить✍️", callback_data="edit_phone")
            inline_markup.add(inline_button1)
            inline_markup.add(inline_button2)
            bot.send_message(message.chat.id, f"{message.text} Ваш номер телефона?", reply_markup=inline_markup)
            update_state(message, START)
            add_data('phone', message.text, message.chat.id)
        else:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            item1 = types.KeyboardButton("🚫 Отмена")
            markup.add(item1)
            bot.send_message(message.chat.id, "Введите корректный номер телефона", reply_markup=markup)
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard= True)
        item1 = types.KeyboardButton("🚫 Отмена")
        markup.add(item1)
        bot.send_message(message.chat.id, "Введите корректный номер телефона", reply_markup = markup)

#CALC
@bot.message_handler(func=lambda message: get_state(message) == CALC)
def get_calc_val(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(f'{message.chat.id}_calc')
        update_state(message, START)
    else:
        try:
            float_value = float(message.text.replace(',','.'))
            val = get_par('val', f'{message.chat.id}_calc')
            value = get_kurs(val)*float_value
            delete_file(message.chat.id)
            update_state(message, START)
            bot.send_message(message.chat.id, f'Сумма в рублях {value} р.', reply_markup = start_markup(message.chat.id))
            delete_file(f'{message.chat.id}_calc')
        except Exception as e:
            print(e)
            bot.send_message(message.chat.id, "Недопустимое значение", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))

#EMAIL
@bot.message_handler(func=lambda message: get_state(message) == EMAIL)
def get_email(message):
    if message.text == '🚫 Отмена':
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=markup)
        update_state(message, START)
        delete_file(message.chat.id)
    elif '@' in message.text:
        add_data('email', message.text, message.chat.id)
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_button1 = types.InlineKeyboardButton("Да, верно!✅", callback_data="my_email")
        inline_button2 = types.InlineKeyboardButton("Нет, изменить✍️", callback_data="edit_email")
        inline_markup.add(inline_button1)
        inline_markup.add(inline_button2)
        bot.send_message(message.chat.id, f"{message. text} Ваш email?", reply_markup=inline_markup)
        update_state(message, START)
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard= True)
        item1 = types.KeyboardButton("🚫 Отмена")
        markup.add(item1)
        bot.send_message(message.chat.id, 'Введите корректный Email', reply_markup = markup)

#PAYOK_BUY
@bot.message_handler(func=lambda message: get_state(message) == PAYOK_BUY)
def get_test_buy(message):
    if message.text == '🚫 Отмена':
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=markup)
        update_state(message, START)
        # delete_file(message.chat.id)
    elif message.text.isdigit():
        data = json.load(open("purchase_number.json"))
        number = data["application_number"]
        buy_link = get_link(amount = message.text)
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("Оплатить", url=buy_link))
        inline_markup.add(types.InlineKeyboardButton("Оплачено", callback_data="payok_complite"))
        bot.send_message(message.chat.id, f"Ваш номер заявки: {number}\nСумма к оплате: {message.text}\nКогда успешно оплатите нажмите кнопку Оплатил", reply_markup=inline_markup)
        bot.send_message(message.chat.id, "", reply_markup = start_markup(message.chat.id))
        update_state(message, START)
    else:
        bot.send_message(message.chat.id, "Введите целое число", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))

#MERCHANT_BUY
@bot.message_handler(func=lambda message: get_state(message) == MERCHANT_BUY)
def merchant_pay(message):
    if message.text == '🚫 Отмена':
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=markup)
        update_state(message, START)
        # delete_file(message.chat.id)
    elif message.text.isdigit():
        if 100<=int(message.text)<= 50000:
            merchant_response = get_merchant_link(price = message.text)
            id = merchant_response["id"]
            pay_link = merchant_response["paymentUrl"]
            # headers = {
            #     "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJpYnRyOGx0QjVmZ0FNMjBXRkVIV1RCVlVPMDEzIiwiZGF0ZSI6IjIwMjQtMDctMDNUMTk6MzU6NTUuOTU1WiIsImlhdCI6MTcyMDAzNTM1NX0.gLKOo0JtnmOrYjasAopN1trppfusIo07jarD3-gzvnI",
            #     "Content-Type": "application/json"
            # }
            # data = {
            #     "isPartnerFee": "true",
            #     "pricing": {
            #         "local": {
            #         "amount": f"{message.text}",
            #         "currency": "RUB"
            #         }
            #     }
            # }
            # response = requests.post(url="https://api.merchant001.io/v1/transaction/merchant", headers=headers, data=json.dumps(data))
            # bot.send_message(message.chat.id, response.status_code)
            # bot.send_message(message.chat.id, f"{response.json()}")
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_markup.add(types.InlineKeyboardButton("Оплатить", url=pay_link))
            inline_markup.add(types.InlineKeyboardButton("Оплачено", callback_data="merchant_complite"))
            bot.send_message(message.chat.id, f"Ваш id заявки: {id}\nСумма к оплате: {message.text}", reply_markup=inline_markup)
            bot.send_message(message.chat.id, "Когда успешно оплатите нажмите кнопку Оплатил", reply_markup = start_markup(message.chat.id))
            update_state(message, START)
        else:
            bot.send_message(message.chat.id, "Введите сумму пополнения от 100₽ до 50 000₽", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
    else:
        bot.send_message(message.chat.id, "Введите целое число", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))

#ESIM_EDIT
@bot.message_handler(func=lambda message: get_state(message) == ESIM_EDIT)
def esim_edit(message):
    if message.text == '🚫 Отмена':
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=markup)
        update_state(message, START)
        # delete_file(message.chat.id)
    markup = start_markup(message.chat.id)
    esim_method = get_par("esim_edit_method", message.chat.id)
    tariff_name = get_par("tariff_name", message.chat.id)
    if esim_method == "name_tariff":
        with open("esim.json", encoding="utf-8") as file:
            data = json.load(file)

        data[tariff_name]["tariff_name"] = message.text

        with open("esim.json", "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        bot.send_message(message.chat.id, "Название изменено", reply_markup=markup)
    if esim_method == "about_tariff":
        with open("esim.json", encoding="utf-8") as file:
            data = json.load(file)
        data[tariff_name]["tariff"] = message.text or ""
        # Сохраняем entities для поддержки прем-эмодзи
        entities = message.entities or []
        data[tariff_name]["tariff_entities"] = [e.to_dict() for e in entities]
        with open("esim.json", "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        bot.send_message(message.chat.id, "Описание изменено", reply_markup=markup)
    if esim_method == "price_tariff":
        try:
            price_val = float(message.text.replace(",", ".").strip())
            if price_val <= 0:
                raise ValueError
        except ValueError:
            bot.send_message(message.chat.id, "❌ Неверный формат. Введите число, например: 4000", reply_markup=markup)
            return
        with open("esim.json", encoding="utf-8") as file:
            data = json.load(file)
        data[tariff_name]["price"] = str(int(price_val) if price_val == int(price_val) else price_val)
        with open("esim.json", "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        bot.send_message(message.chat.id, "Цена изменена", reply_markup=markup)
    if esim_method == "cost_tariff":
        try:
            cost_val = float(message.text.replace(",", "."))
        except ValueError:
            bot.send_message(message.chat.id, "Неверный формат. Введите число, например: 400", reply_markup=markup)
            update_state(message, START)
            return
        with open("esim.json", encoding="utf-8") as file:
            data = json.load(file)
        data[tariff_name]["cost_uah"] = cost_val
        with open("esim.json", "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        bot.send_message(message.chat.id, f"Себестоимость изменена: {cost_val} ₴", reply_markup=markup)
    update_state(message, START)

def _get_esim_caption_entities(tariff_data):
    """Восстанавливает MessageEntity из сохранённых данных (для прем-эмодзи)."""
    entity_dicts = tariff_data.get("tariff_entities", [])
    if not entity_dicts:
        return None
    try:
        return [types.MessageEntity.de_json(d) for d in entity_dicts]
    except Exception:
        return None


def _try_deliver_pending_esim(operator):
    """Если есть пользователи в очереди на получение eSIM — выдать первому из них."""
    try:
        with open("eSIM/esim_pending.json", encoding="utf-8") as pf:
            pending_data = json.load(pf)
        if not pending_data.get(operator):
            return
        with open("eSIM/esim_answer.json", encoding="utf-8") as af:
            esim_data = json.load(af)
        if not esim_data.get(operator):
            return
        # Берём первого ожидающего пользователя и первый доступный eSIM
        pending_user = pending_data[operator].pop(0)
        esim_key = list(esim_data[operator].keys())[0]
        esim_entry = esim_data[operator][esim_key]
        image_path = f"eSIM/{esim_entry.get('image_answer', '')}.jpg"
        user_id = pending_user["user_id"]
        number = pending_user["number"]
        # Отправляем eSIM пользователю
        inline_review = types.InlineKeyboardMarkup(row_width=True)
        inline_review.add(types.InlineKeyboardButton(text="⬆️ Оставить отзыв", callback_data='send_feedback'))
        esim_file_id = esim_entry.get("file_id")
        esim_caption = esim_entry.get("message_answer", "Ваш eSIM")
        if esim_file_id:
            bot.send_photo(user_id, esim_file_id, caption=esim_caption, reply_markup=inline_review)
        else:
            with open(image_path, "rb") as photo:
                bot.send_photo(user_id, photo, caption=esim_caption, reply_markup=inline_review)
        bot.send_message(
            user_id,
            f'✅ Ваш eSIM готов!\n\n'
            f'Заявка №<code>{number}</code> выполнена.\n'
            f'Спасибо за покупку! 🌍',
            parse_mode="HTML"
        )
        # Удаляем выданный eSIM из стока
        del esim_data[operator][esim_key]
        with open("eSIM/esim_answer.json", "w", encoding="utf-8") as af:
            json.dump(esim_data, af, ensure_ascii=False, indent=4)
        if not esim_file_id and os.path.exists(image_path):
            os.remove(image_path)
        # Обновляем очередь
        if not pending_data[operator]:
            del pending_data[operator]
        with open("eSIM/esim_pending.json", "w", encoding="utf-8") as pf:
            json.dump(pending_data, pf, ensure_ascii=False, indent=4)
        # Отправляем в архив
        try:
            archive_caption = (
                f'Заявка №{number}\n'
                f'Пользователь: @{pending_user.get("username")}\n'
                f'id: {user_id}\n\n'
                f'Услуга: Esim {operator}\n'
                f'🎩Ранг: {pending_user.get("rank", "")}'
                f'{pending_user.get("profit_block", "")}'
            )
            if esim_file_id:
                file_info = bot.get_file(esim_file_id)
                downloaded = bot.download_file(file_info.file_path)
                send_photo_to_archives(downloaded, caption=archive_caption)
            elif os.path.exists(image_path):
                with open(image_path, "rb") as photo:
                    send_photo_to_archives(photo.read(), caption=archive_caption)
        except Exception as ex:
            print(f'[eSIM AUTO-DELIVER] Ошибка архива: {ex}')
        # Уведомляем группу админов
        bot.send_message(
            adminGroup,
            f'✅ eSIM выдан автоматически!\n\n'
            f'Заявка №{number}\n'
            f'Пользователь: @{pending_user["username"]} (id: {user_id})\n'
            f'Оператор: {operator}'
        )
    except Exception as e:
        print(f'[eSIM AUTO-DELIVER] Ошибка: {e}')


def _show_esim_confirm(message, qty):
    """Показать экран подтверждения перед покупкой qty eSIM."""
    chat_id = message.chat.id
    operator = get_par("EsimOperator", chat_id)
    logging.info(f"[_show_esim_confirm] chat={chat_id} operator={operator} qty={qty}")
    if not operator:
        bot.send_message(chat_id, "❌ Ошибка: оператор не выбран. Начните заново.")
        return
    with open("esim.json", encoding="utf-8") as f:
        esim_json = json.load(f)
    if operator not in esim_json:
        bot.send_message(chat_id, f"❌ Ошибка: оператор {operator} не найден. Начните заново.")
        return
    summa_per = esim_json[operator]["price"]

    if chat_id in [423255760] and float(summa_per) >= 4000:
        summa_per = str(int(float(summa_per) // 2))

    logging.info(f"[_show_esim_confirm] before total calc")
    total = float(summa_per) * qty
    total_str = int(total) if total == int(total) else total
    logging.info(f"[_show_esim_confirm] before add_data")
    try:
        add_data('EsimQty', str(qty), chat_id)
        logging.info(f"[_show_esim_confirm] add_data OK")
    except Exception as e:
        logging.error(f"[_show_esim_confirm] add_data ERROR: {e}")
        bot.send_message(chat_id, "❌ Внутренняя ошибка, попробуйте ещё раз.")
        return

    confirm_markup = types.InlineKeyboardMarkup(row_width=2)
    confirm_markup.add(
        types.InlineKeyboardButton("✅ Подтвердить", callback_data="esim_confirm"),
        types.InlineKeyboardButton("❌ Отмена", callback_data="esim_confirm_cancel"),
    )
    try:
        bot.send_message(
            chat_id,
            f'🧾 <b>Подтверждение покупки</b>\n\n'
            f'Оператор: {operator}\n'
            f'Количество: {qty} шт.\n'
            f'Цена за 1 шт.: {summa_per} ₽\n'
            f'💰 Итого: <b>{total_str} ₽</b>\n\n'
            f'Подтвердить оплату?',
            reply_markup=confirm_markup,
            parse_mode="HTML"
        )
        logging.info(f"[_show_esim_confirm] send_message OK")
    except Exception as e:
        logging.error(f"[_show_esim_confirm] send_message ERROR: {e}")


def _do_esim_buy(message, qty):
    """Купить qty штук eSIM. message — telebot.types.Message (call.message или обычное)."""
    chat_id = message.chat.id
    operator = get_par("EsimOperator", chat_id)
    with open("esim.json", encoding="utf-8") as f:
        esim_json_data = json.load(f)
    summa_per = esim_json_data[operator]["price"]

    if chat_id in [423255760] and float(summa_per) >= 4000:
        summa_per = str(int(float(summa_per) // 2))

    total_summa = float(summa_per) * qty

    with open("eSIM/esim_answer.json", encoding="utf-8") as file:
        esim_data = json.load(file)

    # Чистим битые записи
    if esim_data.get(operator):
        cleaned = False
        for key in list(esim_data[operator].keys()):
            entry = esim_data[operator][key]
            if not entry.get("file_id"):
                img_path = f"eSIM/{entry.get('image_answer', '')}.jpg"
                if not os.path.exists(img_path):
                    del esim_data[operator][key]
                    cleaned = True
        if cleaned:
            with open("eSIM/esim_answer.json", "w", encoding="utf-8") as f:
                json.dump(esim_data, f, ensure_ascii=False, indent=4)

    # Проверка баланса
    if float(get_balans(chat_id)) - total_summa < 0:
        update_state(message, START)
        bot.send_message(chat_id, 'Недостаточно средств', reply_markup=start_markup(chat_id))
        inline_topup = types.InlineKeyboardMarkup(row_width=True)
        inline_topup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balanse"))
        bot.send_message(chat_id, 'Пополните баланс', reply_markup=inline_topup)
        return

    tariff_data = esim_json_data

    user_type_before = get_user_type(chat_id)
    add_data('sum', str(total_summa), chat_id)
    update_balanse(chat_id, 'sum')
    referer = get_ref_user(chat_id)
    esim_ref_earned = 0
    if referer:
        esim_ref_earned = add_balance_ref_with_type(chat_id, total_summa, "eSIM", user_type_before)
        qty_label = f" x{qty}" if qty > 1 else ""
        bot.send_message(referer, f'<b>🎉 Вы получили <code>{esim_ref_earned}</code> руб за реферала!</b>\n id:<code>{chat_id}</code>\n Товар: eSIM{qty_label}', parse_mode="HTML")
    update_total_spent(chat_id, total_summa)

    # Вычисляем profit_block один раз — используется и в архиве авто-выдачи, и в pending-записях
    try:
        france_esim_cost_rub = {
            "France35GB": 3672,
            "FranceUnlimited": 4784,
        }
        if operator in france_esim_cost_rub:
            cost_rub = france_esim_cost_rub[operator]
            profit = round(float(summa_per) - cost_rub, 0)
            ref_share = round(float(esim_ref_earned) / qty, 0) if esim_ref_earned else 0
            net_profit = round(profit - ref_share, 0)
            ref_block = f'\n👥 Реферал: -{ref_share} ₽ → Чистыми: {int(net_profit)} ₽' if esim_ref_earned else ''
            profit_block = (
                f'\n\n💰 Продажа: {summa_per} ₽'
                f'\n💸 Себестоимость: {int(cost_rub)} ₽'
                f'\n💱 Курс: -'
                f'\n\n📈 Чистая прибыль: {int(profit)} ₽'
                f'{ref_block}'
            )
        else:
            cost_uah = tariff_data[operator].get("cost_uah", 0)
            cost_rate = _uah_cost_rate_cache or get_kurs("uah")
            cost_rub = round(float(cost_uah) * float(cost_rate), 0)
            profit = round(float(summa_per) - cost_rub, 0)
            ref_share = round(float(esim_ref_earned) / qty, 0) if esim_ref_earned else 0
            net_profit = round(profit - ref_share, 0)
            ref_block = f'\n👥 Реферал: -{ref_share} ₽ → Чистыми: {int(net_profit)} ₽' if esim_ref_earned else ''
            profit_block = (
                f'\n\n💰 Продажа: {summa_per} ₽'
                f'\n💸 Себестоимость: {cost_uah} ₴'
                f'\n💱 Курс: {cost_rate}'
                f'\n\n📊 Себестоимость в ₽: {int(cost_rub)} ₽'
                f'\n📈 Чистая прибыль: {int(profit)} ₽'
                f'{ref_block}'
            )
    except Exception:
        profit_block = f'\n\n💰 Продажа: {summa_per} ₽'

    stock_keys = list(esim_data.get(operator, {}).keys())
    deliver_count = min(qty, len(stock_keys))
    pending_count = qty - deliver_count

    inline_review = types.InlineKeyboardMarkup(row_width=True)
    inline_review.add(types.InlineKeyboardButton(text="⬆️ Оставить отзыв", callback_data='send_feedback'))

    delivered = 0
    for i in range(deliver_count):
        esim_key = stock_keys[i]
        esim_entry = esim_data[operator][esim_key]
        image = f"eSIM/{esim_entry.get('image_answer', '')}.jpg"
        usluga = f'Esim. {operator}'
        number = to_arhiv(chat_id, usluga, str(summa_per))
        esim_file_id = esim_entry.get("file_id")
        esim_caption = esim_entry.get("message_answer", "Ваш eSIM")
        try:
            photo_bytes = None
            if esim_file_id:
                try:
                    bot.send_photo(chat_id, esim_file_id, caption=esim_caption)
                except Exception:
                    esim_file_id = None
                    with open(image, "rb") as photo:
                        photo_bytes = photo.read()
                    bot.send_photo(chat_id, photo_bytes, caption=esim_caption)
            else:
                with open(image, "rb") as photo:
                    photo_bytes = photo.read()
                bot.send_photo(chat_id, photo_bytes, caption=esim_caption)
            archive_caption = (
                f'Заявка №{number}\nПользователь: @{message.chat.username} \nid: {chat_id}\n\n'
                f'Услуга: Esim {operator}\n🎩Ранг: {get_user_rank(chat_id)}{profit_block}'
            )
            if esim_file_id:
                file_info = bot.get_file(esim_file_id)
                downloaded = bot.download_file(file_info.file_path)
                send_photo_to_archives(downloaded, caption=archive_caption)
            elif photo_bytes:
                send_photo_to_archives(photo_bytes, caption=archive_caption)
            if not esim_file_id and os.path.exists(image):
                os.remove(image)
            del esim_data[operator][esim_key]
            with open("eSIM/esim_answer.json", "w", encoding="utf-8") as file:
                json.dump(esim_data, file, ensure_ascii=False, indent=4)
            delivered += 1
        except Exception as e:
            print(f"[eSIM] Ошибка отправки: {e}")
            pending_count += 1
            if esim_key in esim_data.get(operator, {}):
                del esim_data[operator][esim_key]
                with open("eSIM/esim_answer.json", "w", encoding="utf-8") as file:
                    json.dump(esim_data, file, ensure_ascii=False, indent=4)

    # Добавляем в очередь ожидающих
    for i in range(pending_count):
        usluga = f'Esim. {operator}'
        number = to_arhiv(chat_id, usluga, str(summa_per))
        try:
            with open("eSIM/esim_pending.json", encoding="utf-8") as pf:
                pending_data = json.load(pf)
        except Exception:
            pending_data = {}
        if operator not in pending_data:
            pending_data[operator] = []
        pending_data[operator].append({
            "user_id": chat_id,
            "username": message.chat.username or "",
            "number": number,
            "summa": str(summa_per),
            "operator": operator,
            "rank": get_user_rank(chat_id),
            "profit_block": profit_block
        })
        with open("eSIM/esim_pending.json", "w", encoding="utf-8") as pf:
            json.dump(pending_data, pf, ensure_ascii=False, indent=4)
        esim_manual_markup = types.InlineKeyboardMarkup(row_width=True)
        esim_manual_markup.add(
            types.InlineKeyboardButton("✅ Принять", callback_data=f"esim_manual_accept:{number}:{chat_id}:{operator}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"esim_cancel_ask:{number}:{chat_id}:{summa_per}")
        )
        order_label = f' [{i + 1}/{pending_count}]' if pending_count > 1 else ''
        bot.send_message(
            adminGroup,
            f'📦 ВЫДАТЬ eSIM ВРУЧНУЮ{order_label}\n\n'
            f'Заявка №{number}\n'
            f'Пользователь: @{message.chat.username}\n'
            f'id: {chat_id}\n'
            f'Оператор: {operator}\n'
            f'🎩Ранг: {get_user_rank(chat_id)}\n'
            f'Сумма: {summa_per} ₽',
            reply_markup=esim_manual_markup
        )

    # Итоговое сообщение пользователю
    update_state(message, START)
    if delivered > 0 and pending_count == 0:
        suffix = f" x{qty}" if qty > 1 else ""
        bot.send_message(chat_id, f"Спасибо за покупку eSIM{suffix}! 🌍\nКак только подключите — оставьте отзыв 💪", reply_markup=inline_review)
    elif delivered > 0 and pending_count > 0:
        bot.send_message(
            chat_id,
            f'✅ {delivered} eSIM выданы!\n'
            f'⌚️ Ещё {pending_count} eSIM будут выданы вручную в течение 24 часов.\n'
            f'При вопросах: @TGPaySupport_bot',
            reply_markup=inline_review
        )
    else:
        qty_label = f"все {qty} " if qty > 1 else ""
        bot.send_message(
            chat_id,
            f'✅ Оплата принята!\n\n'
            f'⌚️ {qty_label}eSIM будут выданы вручную в течение 24 часов.\n'
            f'При вопросах: @TGPaySupport_bot',
            reply_markup=start_markup(chat_id)
        )


@bot.message_handler(func=lambda message: get_state(message) == ESIM_QTY)
def esim_qty_input(message):
    if message.text and message.text.strip() == '🚫 Отмена':
        update_state(message, START)
        bot.send_message(message.chat.id, 'Отменено.', reply_markup=start_markup(message.chat.id))
        return
    try:
        qty = int(message.text.strip())
        if qty < 1:
            raise ValueError
    except (ValueError, AttributeError):
        bot.send_message(message.chat.id, 'Введите целое число больше 0:')
        return
    update_state(message, START)
    _show_esim_confirm(message, qty)


#ESIM_IMAGE_EDIT
@bot.message_handler(func=lambda message: get_state(message) == ESIM_IMAGE_EDIT, content_types=['photo', 'document', 'text'])
def esim_image_edit(message):
    tariff_name = get_par("tariff_name", message.chat.id)
    esim_method = get_par("esim_edit_method", message.chat.id)
    markup = start_markup(message.chat.id)

    # Кнопка "Готово" при мультизагрузке eSIM
    if message.content_type == 'text':
        if message.text in ('✅ Готово', '🚫 Отмена'):
            if esim_method == "auto_tariff":
                try:
                    with open("eSIM/esim_answer.json", encoding="utf-8") as file:
                        esim_data = json.load(file)
                    total = len(esim_data.get(tariff_name, {}))
                except Exception:
                    total = 0
                bot.send_message(
                    message.chat.id,
                    f'✅ Загрузка завершена. В стоке {tariff_name}: {total} шт.',
                    reply_markup=markup
                )
                # Выдаём eSIM ожидающим пользователям только после завершения загрузки
                _try_deliver_pending_esim(tariff_name)
            else:
                bot.send_message(message.chat.id, "Отменено", reply_markup=markup)
            update_state(message, START)
        return

    if esim_method == "image_tariff":
        if tariff_name == "Kievstar":
            photo = message.photo[-1]
            file_info = bot.get_file(photo.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            with open(f"files/КиевстарTarif.jpg", 'wb') as new_file:
                new_file.write(downloaded_file)
        else:
            photo = message.photo[-1]
            file_info = bot.get_file(photo.file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            with open(f"files/{tariff_name}Tarif.jpg", 'wb') as new_file:
                new_file.write(downloaded_file)
        bot.send_message(message.chat.id, "Изображение изменено", reply_markup=markup)
        update_state(message, START)

    if esim_method == "auto_tariff":
        # Поддержка photo и document (JPG файлом)
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
        elif message.content_type == 'document':
            file_id = message.document.file_id
        else:
            bot.send_message(message.chat.id, "Отправьте фото или JPG файлом.")
            return
        try:
            with _esim_stock_lock:
                with open("eSIM/esim_answer.json", encoding="utf-8") as file:
                    esim_data = json.load(file)
                if tariff_name not in esim_data:
                    esim_data[tariff_name] = {}
                existing_keys = [int(k) for k in esim_data[tariff_name].keys()] if esim_data[tariff_name] else []
                esim_count = max(existing_keys) + 1 if existing_keys else 1
                esim_data[tariff_name][esim_count] = {
                    "message_answer": message.caption or "Ваш eSIM",
                    "file_id": file_id
                }
                with open("eSIM/esim_answer.json", "w", encoding="utf-8") as file:
                    json.dump(esim_data, file, ensure_ascii=False, indent=4)
                total = len(esim_data[tariff_name])
        except Exception as e:
            print(f"[eSIM] Ошибка сохранения: {e}")
            total = 0
        # Остаёмся в состоянии — предлагаем загрузить ещё
        done_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        done_markup.add(types.KeyboardButton('✅ Готово'))
        bot.send_message(
            message.chat.id,
            f'✅ eSIM добавлен! Всего в стоке {tariff_name}: {total} шт.\n\n'
            f'Отправьте ещё фото или нажмите «✅ Готово»',
            reply_markup=done_markup
        )

#INVOICE_USER
@bot.message_handler(func=lambda message: get_state(message) == INVOICE_USER)
def invoice_user(message):
    if message.text == '🚫 Отмена':
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=markup)
        update_state(message, START)
    else:
        add_data('id_invoice_user', message.text, message.chat.id)
        bot.send_message(message.chat.id, "Введите название товара", reply_markup=start_markup(message.chat.id, text='🚫 Отмена'))
        update_state(message, INVOICE_PRICE)

#INVOICE_PRICE
@bot.message_handler(func=lambda message: get_state(message) == INVOICE_PRICE)
def invoice_price(message):
    if message.text == '🚫 Отмена':
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=markup)
        update_state(message, START)
    else:
        add_data('product_name', message.text, message.chat.id)
        bot.send_message(message.chat.id, "Введите цену товара", reply_markup=start_markup(message.chat.id, text='🚫 Отмена'))
        update_state(message, INVOICE_TOTAL)

#INVOICE_TOTAL
@bot.message_handler(func=lambda message: get_state(message) == INVOICE_TOTAL)
def invoice_price(message):
    if message.text == '🚫 Отмена':
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=markup)
        update_state(message, START)
    else:
        user_id = get_par('id_invoice_user', message.chat.id)
        product_name = get_par('product_name', message.chat.id)
        # number = to_arhiv(user_id, f"Покупка аккаунта или донат", summ)
        markup = types.InlineKeyboardMarkup(row_width=True)
        buttons = [
            types.InlineKeyboardButton(text = "✅Оплатить", callback_data="invoice_buy"),
            types.InlineKeyboardButton(text = "❌Отклонить", callback_data="invoice_cancel")
        ]
        markup.add(*buttons)
        summ = int(message.text)
        db = sqlite3.connect('files/users.db', timeout=10)
        cursor = db.cursor()
        cursor.execute('SELECT id FROM blocked_users WHERE id = ?', (user_id,))
        is_blocked = cursor.fetchone()
        db.close()
        if is_blocked:
            bot.send_message(message.chat.id, f"❌ Не удалось отправить счёт пользователю {user_id}.\nПричина: Пользователь заблокировал бота", reply_markup = start_markup(message.chat.id))
        else:
            try:
                bot.send_message(user_id, f'👨‍💻Администратор выставил вам счёт\nНазвание товара : {product_name}\n💵Сумма : {summ}₽', reply_markup = markup)
                bot.send_message(message.chat.id, "Сообщение отправлено", reply_markup = start_markup(message.chat.id))
            except Exception as e:
                reason = "Пользователь не найден или не начинал диалог с ботом" if "chat not found" in str(e) else str(e)
                bot.send_message(message.chat.id, f"❌ Не удалось отправить счёт пользователю {user_id}.\nПричина: {reason}", reply_markup = start_markup(message.chat.id))
        update_state(message, START)

#PROMOCODE
@bot.message_handler(func=lambda message: get_state(message) == PROMOCODE)
def promocode(message):
    if message.text == '🚫 Отмена':
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=markup)
        update_state(message, START)
    else:
        add_data("promocode", message.text, message.chat.id)
        bot.send_message(message.chat.id, "Введите процент для промокода")
        update_state(message, PROMOCODE_PRICE)

#PROMOCODE_PRICE
@bot.message_handler(func=lambda message: get_state(message) == PROMOCODE_PRICE)
def promocode_price(message):
    if message.text == '🚫 Отмена':
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=markup)
        update_state(message, START)
    else:
        promocode = get_par("promocode", message.chat.id)
        try:
            with open("promocode.json", encoding="utf-8") as file:
                data = json.load(file)
            data[promocode] = {"wasted_user": [], "user": [], "procent": message.text}
            with open("promocode.json", "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            bot.send_message(message.chat.id, "Промокод добавлен", reply_markup=start_markup(message.chat.id))
            update_state(message, START)
        except:
            data = {promocode: {"wasted_user": [], "user": [], "procent": message.text}}
            with open("promocode.json", "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            bot.send_message(message.chat.id, "Промокод добавлен", reply_markup=start_markup(message.chat.id))
            update_state(message, START)

#PROMOCODE_USER
@bot.message_handler(func=lambda message: get_state(message) == PROMOCODE_USER)
def promocode_user(message):
    if message.text == '🚫 Отмена':
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=markup)
        update_state(message, START)
    else:
        with open("promocode.json", encoding="utf-8") as file:
            data = json.load(file)
        if data.get(message.text):
            if message.chat.id not in data[message.text]["wasted_user"]:
                add_promocode(message.chat.id, message.text)
                bot.send_message(message.chat.id, "Промокод успешно использован", reply_markup = start_markup(message.chat.id))
            else:
                bot.send_message(message.chat.id, "Вы уже использовали этот промокод", reply_markup = start_markup(message.chat.id))
        else:
            bot.send_message(message.chat.id, "Такого промокода нет", reply_markup = start_markup(message.chat.id))
        update_state(message, START)


def normalize_phone(phone: str):
    cleaned = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if cleaned.startswith("+7") or cleaned.startswith("+8") and cleaned[2:].isdigit() and len(cleaned) == 12:
        return cleaned
    return None


def normalize_card(card: str):
    cleaned = card.replace(" ", "")
    if cleaned.isdigit() and len(cleaned) == 16:
        return cleaned
    return None


@bot.message_handler(func=lambda message: get_state(message) == CARD_NUMBER)
def card_number(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    else:
        card = message.text.strip()
        normalized = normalize_card(card)
        if normalized is None:
            bot.send_message(
                message.chat.id,
                "❌ Неверный формат карты.\nВведите 16 цифр, можно с пробелами.\nПример: 1234 5678 9012 3456"
            )
            return

        set_user_temp(message.from_user.id, "card", normalized)
        bot.send_message(message.chat.id, "Введите сумму для вывода:")
        update_state(message, CARD_AMOUNT)

@bot.message_handler(func=lambda message: get_state(message) == ACCEPTED_KEY)
def get_accepted_key(message):
    if message.text == "🚫 Отмена":
        bot.send_message(
            message.chat.id,
            "Вы отменили ввод ключа",
            reply_markup=start_markup(message.chat.id)
        )
        update_state(message, START)
        return

    key = message.text
    user = message.from_user

    # отправка ключа на нужный ID
    bot.send_message(
        123,
        f"🔐 Новый ключ\n"
        f"Ключ: {key}"
    )

    bot.send_message(message.chat.id, "✅ Ключ отправлен")
    update_state(message, START)

@bot.message_handler(func=lambda message: get_state(message) == CARD_AMOUNT)
def card_amount(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    else:
        uid = message.from_user.id
        temp = get_user_temp(uid)
        card = temp.get("card")

        if not card:
            bot.send_message(message.chat.id, "❌ Ошибка: данные не найдены. Начните заново.")
            update_state(message, None)
            return

        try:
            amount = int(message.text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            bot.send_message(message.chat.id, "❌ Введите корректную сумму:")
            return
        if amount < 1000:
            bot.send_message(message.chat.id, "❌ Минимальная сумма вывода 1000 ₽. Введите корректную сумму:")
            return
        COMMISSION = 0.20
        commission = int(amount * COMMISSION)
        to_receive = amount - commission

        set_user_temp(uid, "amount", amount)
        set_user_temp(uid, "commission", commission)
        set_user_temp(uid, "to_receive", to_receive)

        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_card_withdraw"),
            types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_withdraw")
        )

        bot.send_message(
            message.chat.id,
            f"💳 Карта: {card}\n"
            f"🏦Банк: {get_bank_from_card(card)}\n"
            f"💰 Сумма списания: {amount} ₽\n"
            f"💸 Комиссия (20%): {commission} ₽\n"
            f"📥 Вы получите: {to_receive} ₽\n\n"
            f"Подтвердить вывод?",
            reply_markup=markup
        )

@bot.message_handler(func=lambda message: get_state(message) == SBP_NUMBER)
def sbp_number(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    else:
        text = message.text.strip()
        parts = text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "❌ Укажите банк + номер телефона.\nПример: Сбер +7 900 123 45 67")
            return
        bank = parts[0]
        phone = " ".join(parts[1:])
        normalized_phone = normalize_phone(phone)
        if normalized_phone is None:
            bot.send_message(message.chat.id, "❌ Некорректный номер.\nПример: +7 900 123 45 67 (можно без пробелов)")
            return

        set_user_temp(message.from_user.id, "bank", bank)
        set_user_temp(message.from_user.id, "phone", normalized_phone)
        bot.send_message(message.chat.id, "Введите сумму для вывода:")
        update_state(message, SBP_AMOUNT)


@bot.message_handler(func=lambda message: get_state(message) == SBP_AMOUNT)
def sbp_amount(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    else:
        uid = message.from_user.id

        temp = get_user_temp(uid)
        bank = temp.get("bank")
        phone = temp.get("phone")

        if not bank or not phone:
            bot.send_message(message.chat.id, "❌ Ошибка: данные не найдены. Начните заново.")
            update_state(message, None)
            return

        try:
            amount = int(message.text)
            if amount <= 0:
                raise ValueError
        except ValueError:
            bot.send_message(message.chat.id, "❌ Введите корректную сумму:")
            return
        if amount < 50:
            bot.send_message(message.chat.id, "❌ Минимальная сумма вывода 50 ₽. Введите корректную сумму:")
            return
        COMMISSION = 0.20
        commission = int(amount * COMMISSION)
        to_receive = amount - commission

        set_user_temp(uid, "amount", amount)
        set_user_temp(uid, "commission", commission)
        set_user_temp(uid, "to_receive", to_receive)
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_withdraw_sbp"),
            types.InlineKeyboardButton("❌ Отмена", callback_data="cancel_withdraw")
        )
        bot.send_message(
            message.chat.id,
            f"💰 Сумма списания: {amount} ₽\n"
            f"💸 Комиссия (20%): {commission} ₽\n"
            f"📥 Вы получите: {to_receive} ₽\n"
            f"☎️ Номер телефона: {phone}\n"
            f"🏦 Банк: {bank}\n\n"
            f"Подтвердить вывод?",
            reply_markup=markup
        )


#CRYPTOMUS
@bot.message_handler(func=lambda message: get_state(message) == CRYPTOMUS_BUY)
def cryptomus_confrim(message):
    if message.text == '🚫 Отмена':
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=markup)
        update_state(message, START)
    elif message.text.isdigit():
        if 100<=int(message.text)<= 50000:
            additional_data = {"user_id": message.from_user.id, "price": message.text, "username": message.chat.username}
            invoice_data = {
                "amount": f"{message.text}",
                "currency": "RUB",
                "order_id": str(uuid.uuid4()),
                "additional_data": json.dumps(additional_data),
                "url_callback": "https://olexandrapi.tw1.ru/cryptomus"
            }
            cryptomus_data = get_cryptomus_link(data=invoice_data)
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_markup.add(types.InlineKeyboardButton("Оплатить", url=cryptomus_data['result']['url']))

            bot.send_message(message.chat.id, "Заявка создана", reply_markup = start_markup(message.chat.id))
            bot.send_message(message.chat.id, f"Ваш id заявки: {cryptomus_data['result']['uuid']}\nСумма к оплате: {message.text}\nАктивировать Google Play Gift Card USD и Apple & iTunes Gift Card USD можно только на аккаунты зарегистрированные в США!", reply_markup=inline_markup)
            update_state(message, START)
        else:
            bot.send_message(message.chat.id, "Введите сумму пополнения от 100₽", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
    else:
        bot.send_message(message.chat.id, "Введите целое число", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))

#CRYPT_SUMM — ввод суммы в долларах
@bot.message_handler(func=lambda message: get_state(message) == CRYPT_SUMM)
def crypt_summ(message):
    if message.text == "🚫 Отмена":
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=start_markup(message.chat.id))
        update_state(message, START)
        return
    try:
        amount = float(message.text.replace(',', '.'))
        if amount < 1000:
            bot.send_message(message.chat.id, "❌ Минимальная сумма 1000₽. Введите сумму:", reply_markup=start_markup(message.chat.id, text='🚫 Отмена'))
            return
    except ValueError:
        bot.send_message(message.chat.id, "❌ Введите число (например: 2000):", reply_markup=start_markup(message.chat.id, text='🚫 Отмена'))
        return

    kurs_usd = get_kurs('usd')
    summ_usd = round(amount / kurs_usd, 2)
    add_data('crypt_summ_usd', str(summ_usd), message.chat.id)
    add_data('crypt_summ_rub', str(amount), message.chat.id)

    inline_markup = types.InlineKeyboardMarkup()
    inline_markup.add(types.InlineKeyboardButton("✅ Я оплатил!", callback_data="crypt_paid"))

    bot.send_message(
        message.chat.id,
        f"Переведите <code>{summ_usd}</code> USDT на адрес (сеть TRC-20):\n\n"
        f"<code>{CryptWallet}</code>\n\n"
        f"После оплаты нажми «✅ Я оплатил!»",
        parse_mode='HTML',
        reply_markup=inline_markup
    )
    update_state(message, START)

#CRYPT_TXID — ввод хэша транзакции
@bot.message_handler(func=lambda message: get_state(message) == CRYPT_TXID)
def crypt_txid(message):
    if message.text == "🚫 Отмена":
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup=start_markup(message.chat.id))
        update_state(message, START)
        return

    txid = message.text.strip()
    summ_usd = get_par('crypt_summ_usd', message.chat.id)
    summ_rub = get_par('crypt_summ_rub', message.chat.id)
    usluga = f'Пополнение баланса.\nСпособ оплаты: Криптовалюта USDT TRC-20'
    number = to_arhiv(message.chat.id, usluga, summ_rub)

    bot.send_message(
        adminGroup,
        f'Заявка №{number}\nПользователь: @{message.chat.username}\nid: <code>{message.chat.id}</code>\nУслуга: {usluga}\n🎩Ранг: {get_user_rank(message.chat.id)}\nСумма: {summ_rub}\nСумма USD: {summ_usd}$\nTXID: <code>{txid}</code>',
        parse_mode='HTML',
        reply_markup=admin_markup()
    )
    bot.send_message(message.chat.id, f'Заявка №{number}\n😉Ожидайте зачисления на баланс\n⌚️В крайних случаях деньги могут поступить в течении 24-х часов', reply_markup=start_markup(message.chat.id))
    update_state(message, START)

#Удаление добавление карт
@bot.callback_query_handler(func=lambda call: call.data in ['add_card','del_card_1'])
def handle_callback_query(call):
    text = call.data
    chat_id = call.message.chat.id
    if text == "add_card":
        bot.send_message(call.message.chat.id, 'Введите новую карту.\n Пример: +79900512976 Промсвязьбанк', reply_markup = start_markup(chat_id, text='🚫 Отмена'))
        update_state(call.message, CARD)
    elif text == "del_card_1":
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        cards = get_cards()
        sorted_cards = sorted(cards, key=lambda x: x.split(" ", 1)[1])
        for idx, card in enumerate(sorted_cards):
            inline_markup.add(types.InlineKeyboardButton(f"{card}", callback_data=f"card_{idx}"))

        inline_markup.add(types.InlineKeyboardButton(f"Назад", callback_data=f"card_back"))
        bot.send_message(call.message.chat.id, '❌ Выберите карту для удаления', reply_markup = inline_markup)
@bot.callback_query_handler(func=lambda call: call.data.startswith("card_") or call.data == "card_back")
def handle_callback_query(call):
    text = call.data
    chat_id = call.message.chat.id
    if text == 'card_back':
        bot.send_message(chat_id, '❌ Отменено', reply_markup = start_markup(call.message.chat.id))
    else:
        cards = sorted(get_cards(), key=lambda x: x.split(" ", 1)[1])
        index = int(text.split("_")[1])
        selected_card = cards[index]
        db = sqlite3.connect('files/cards.db', timeout=10)
        cursor = db.cursor()
        cursor.execute('DELETE FROM cards WHERE card = ?', (selected_card,))
        db.commit()
        db.close()
        file_data={}
        file_data['nom'] = 0
        with open('files/cards.json', 'w', encoding='utf-8') as outfile:
            json.dump(file_data, outfile)
        bot.send_message(call.message.chat.id, '❌ Карта удалена', reply_markup = start_markup(call.message.chat.id))
@bot.message_handler(func=lambda message: get_state(message) == CARD)
def get_phone(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    else:
        markup = start_markup(message.chat.id)
        db = sqlite3.connect('files/cards.db', timeout=10)
        cursor = db.cursor()
        cursor.execute(f"INSERT INTO cards (card) VALUES (?)",(message.text,))

        db.commit()
        db.close()
        bot.send_message(message.chat.id, f'✅Карта добавлена', reply_markup = markup)
        update_state(message, START)
def poll_lava_payment(chat_id, order_id, message_id):
    import time as _time
    interval = 5
    timeout = 3600
    elapsed = 0
    print(f"[LAVA POLL] Старт поллинга: order={order_id}, user={chat_id}")
    while elapsed < timeout:
        _time.sleep(interval)
        elapsed += interval
        payload = {"shopId": SHOP_ID, "orderId": order_id}
        json_data = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
        signature = hmac.new(SECRET_KEY.encode(), json_data.encode(), hashlib.sha256).hexdigest()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Signature": signature
        }
        try:
            response = requests.post("https://api.lava.ru/business/invoice/status", headers=headers, data=json_data.encode('utf-8'))
            data = response.json()
        except Exception as e:
            print(f"[LAVA POLL] Ошибка запроса: {e}")
            continue
        print(f"[LAVA POLL] HTTP {response.status_code} | body: {data}")
        if response.status_code != 200 or "data" not in data or "status" not in data["data"]:
            continue
        status = data["data"]["status"]
        amount = data["data"]["amount"]
        print(f"[LAVA POLL] order={order_id}, status={status}, amount={amount}, user={chat_id}")
        if status == "success":
            try:
                bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception:
                pass
            bot.send_message(chat_id, f"✅ Оплата подтверждена! На ваш баланс начислено {amount}р.", reply_markup=start_markup(chat_id))
            add_deposit(chat_id, amount, description='Пополнение через Lava')
            date = datetime.now().date().strftime('%d.%m.%Y')
            send_to_archives(bot.send_message,
                             f'Дата: {date}\nid: {chat_id}\nНомер заявки: {order_id}\nУслуга: Lava Pay SBP \nСумма: {amount} р.\n🎩Ранг: {get_user_rank(chat_id)}\nСтатус: ✅Одобрено')
            user_order_ids[chat_id] = ""
            return
        elif status in ("expired", "cancel"):
            try:
                bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception:
                pass
            bot.send_message(chat_id, "⌛ Срок действия ссылки Lava Pay истёк. Попробуйте снова.")
            user_order_ids[chat_id] = ""
            return
    try:
        bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass
    user_order_ids[chat_id] = ""


@bot.message_handler(func=lambda message: get_state(message) == SBP)
def sbp_test(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    elif message.text.isdigit():
        try:
            amount = int(message.text)
            if 1 <= amount <= 50000:
                add_data('deposit_sum', amount, message.chat.id)

                import uuid
                order_id = str(uuid.uuid4())

                payload = {
                    "shopId": SHOP_ID,
                    "sum": amount,
                    "orderId": order_id,
                    "successUrl": "https://t.me/PayTelekom_bot",
                    "failUrl": "https://t.me/PayTelekom_bot",
                    "expire": 3600,
                    "customFields": f"telegram_id:{message.chat.id}",
                    "comment": "Пополнение через LavaPay",
                    "includeService": ["card", "sbp"]
                }

                json_data = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
                signature = hmac.new(SECRET_KEY.encode(), json_data.encode(), hashlib.sha256).hexdigest()

                headers = {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Signature": signature
                }

                response = requests.post("https://api.lava.ru/business/invoice/create", headers=headers,
                                         data=json_data.encode('utf-8'))
                data = response.json()

                if response.status_code == 200 and "url" in data.get("data", {}):
                    pay_url = data["data"]["url"]

                    inline_markup = types.InlineKeyboardMarkup(row_width=1)
                    inline_markup.add(
                        types.InlineKeyboardButton("❌ Отказаться от оплаты", callback_data="deposit_cancel")
                    )

                    bot.send_message(message.chat.id,
                                     f"🔗 Ссылка на оплату Lava Pay:\n\n{pay_url}\n\n❗️<b>Не изменяйте комментарий к переводу</b>!",
                                     parse_mode="HTML", reply_markup=inline_markup)

                    waiting_msg = bot.send_message(message.chat.id, "⏳ <i>Ожидаем оплату...</i>", parse_mode="HTML")

                    user_order_ids[message.chat.id] = order_id
                    threading.Thread(
                        target=poll_lava_payment,
                        args=(message.chat.id, order_id, waiting_msg.message_id),
                        daemon=True
                    ).start()
                    update_state(message, START)
                else:
                    bot.send_message(message.chat.id, f"Ошибка создания счёта LavaPay: {data}")
            else:
                bot.send_message(message.chat.id, "Пополнение LavaPay доступно от 1 до 50000₽",
                                 reply_markup=start_markup(message.chat.id, text='🚫 Отмена'))
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Произошла ошибка: {e}")
    else:
        bot.send_message(message.chat.id, "Введите целое число", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
@bot.message_handler(func=lambda message: get_state(message) == YOOMANY)
def yoomany_test(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    elif message.text.isdigit():
        if 100<=int(message.text)<= 50000:
            req_data = json.load(open("yoomany_requisites.json", encoding="utf-8"))
            application_number = str(uuid.uuid4())
            bot.send_message(
                message.chat.id,
                text=f"***Ваш номер заявки: {application_number}***\n\nК оплате `{message.text}` ₽\nПереведите по номеру `{req_data['phone_req']}`, либо по [ссылке]({req_data['link_req']})\nПеревод нужно сделать ***РОВНО {message.text} ₽***, иначе платеж не получится проверить\n\n***У вас будет 10 минут на оплату. Заявки проверяются автоматически***",
                parse_mode="MARKDOWN",
                reply_markup = start_markup(message.chat.id)
            )
            data = json.load(open("Yoomoney/pending_applications.json", encoding="utf-8"))
            time_application = datetime.now(pytz.timezone('Europe/Moscow')).strftime('%H:%M')
            data[f"{random.randint(10000, 100000)}_{message.from_user.id}"] = {
                "amount": f"{random.randint(10000, 100000)}_{message.text.replace(' ', '')}",
                "date": time_application,
                "username": message.chat.username,
                "application_number": application_number
            }
            with open("Yoomoney/pending_applications.json", "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            update_state(message, START)
        else:
            bot.send_message(message.chat.id, "Введите сумму пополнения от 100₽ до 50 000₽", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
    else:
        bot.send_message(message.chat.id, "Введите целое число", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))

@bot.message_handler(func=lambda message: get_state(message) == YOOMANY_REQUISITES)
def yoomany_requisites(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    else:
        bot.send_message(message.chat.id, "Введите ссылку для реквизитов", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        add_data('phone_req', message.text, message.chat.id)
        update_state(message, YOOMANY_REQUISITES_LINK)

@bot.message_handler(func=lambda message: get_state(message) == YOOMANY_REQUISITES_LINK)
def yoomany_requisites(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    else:
        phone_req = get_par('phone_req', message.chat.id)
        data = {"phone_req": phone_req, "link_req": message.text}
        with open("yoomany_requisites.json", "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        bot.send_message(message.chat.id, "Реквизиты изменены", reply_markup = start_markup(message.chat.id))
        update_state(message, START)

# @bot.message_handler(func=lambda message: get_state(message) == YOOMANY_REQUISITES_LINK)
# def yoomany_requisites(message):
#     if message.text == "🚫 Отмена":
#         markup = start_markup(message.chat.id)
#         bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
#         update_state(message, START)
#     else:
#         bot.send_message(message.chat.id, "Введите почту в формате example@rambler.ru", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
#         add_data('link_req', message.text, message.chat.id)
#         update_state(message, YOOMANY_REQUISITES_EMAIL)

@bot.message_handler(func=lambda message: get_state(message) == YOOMANY_REQUISITES_EMAIL)
def yoomany_requisites(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    else:
        bot.send_message(message.chat.id, "Введите пароль от почты для реквизитов", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        add_data('email_req', message.text, message.chat.id)
        update_state(message, YOOMANY_REQUISITES_PASSWORD)

@bot.message_handler(func=lambda message: get_state(message) == YOOMANY_REQUISITES_PASSWORD)
def yoomany_requisites(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    else:
        json_data = json.load(open("yoomany_requisites.json", encoding="utf-8"))
        phone_req = get_par('phone_req', message.chat.id)
        link_req = get_par('link_req', message.chat.id)
        email_req = get_par('email_req', message.chat.id)
        if json_data:
            json_data[phone_req] = {
                "link_req": link_req,
                "email_req": email_req,
                "password_req": message.text
            }
            with open("yoomany_requisites.json", "w", encoding="utf-8") as file:
                json.dump(json_data, file, ensure_ascii=False, indent=4)
        else:
            data = {phone_req: {
                "link_req": link_req,
                "email_req": email_req,
                "password_req": message.text
            }}
            with open("yoomany_requisites.json", "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
        bot.send_message(message.chat.id, "Реквизиты изменены", reply_markup = start_markup(message.chat.id))
        update_state(message, START)


@bot.message_handler(func=lambda message: get_state(message) == REF_PROCENT_CHANGE)
def procent_change(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    else:
        bot.send_message(message.chat.id, "Проценты успешно изменены", reply_markup = start_markup(message.chat.id))
        json_data = json.load(open("ref_data.json", encoding="utf-8"))
        json_data["ref_procent"] = message.text
        with open("ref_data.json", "w", encoding="utf-8") as file:
            json.dump(json_data, file, ensure_ascii=False, indent=4)
        update_state(message, START)

@bot.message_handler(func=lambda message: get_state(message) == REF_HRYVNIA_CHANGE)
def procent_change(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    else:
        bot.send_message(message.chat.id, "Значение множителя изменено", reply_markup = start_markup(message.chat.id))
        json_data = json.load(open("ref_data.json", encoding="utf-8"))
        json_data["ref_hryvnia"] = message.text
        with open("ref_data.json", "w", encoding="utf-8") as file:
            json.dump(json_data, file, ensure_ascii=False, indent=4)
        update_state(message, START)

@bot.message_handler(func=lambda message: get_state(message) == MESSAGE_TO_USER)
def message_to_user(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    else:
        add_data("user_id", message.text, message.chat.id)
        bot.send_message(message.chat.id, "Введите Сообщение:", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        update_state(message, SEND_MESSAGE_TO_USER)


@bot.message_handler(func=lambda message: get_state(message) == SEND_MESSAGE_TO_USER)
def send_message_to_user(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    else:
        logging.info(f"{message}")
        user_id = get_par("user_id", message.chat.id)
        user_answer(message=message.text, user_id=user_id, sender_id=message.chat.id)
        bot.send_message(message.chat.id, "Сообщение было отправлено", reply_markup = start_markup(message.chat.id))
        update_state(message, START)

@bot.message_handler(func=lambda message: get_state(message) == ADMIN_DIALOG)
def dialog_user_admin(message):
    user_id = get_par("user_id", message.chat.id)
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
        return
    user_answer(message=message.text, user_id=user_id, sender_id=message.chat.id)
    bot.send_message(message.chat.id, "Сообщение было отправлено", reply_markup = start_markup(message.chat.id))
    update_state(message, START)

@bot.message_handler(func=lambda message: get_state(message) == TRANSITIONAL_LINK)
def handle_transitional_link(message):
    if message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Вы отменили ввод данных", reply_markup = markup)
        update_state(message, START)
    else:
        data = get_json_data("count_link_clicks.json")
        data[message.text] = 0
        add_json_data(file="count_link_clicks.json", data=data)
        bot.send_message(message.chat.id, f"Ваша ссылка https://t.me/PayTelekom_bot?start={message.text}", reply_markup = start_markup(message.chat.id))
        update_state(message, START)

@bot.callback_query_handler(func=lambda call: call.data.startswith("add_pen:"))
def add_pen_callback(call):
    if call.from_user.id not in admins:
        bot.answer_callback_query(call.id, "Нет доступа")
        return
    mod_id = int(call.data.split(":")[1])
    stats = get_penalties_stats(mod_id)
    count = stats['count']
    total = int(stats['total'])
    add_data('penalty_mod_id', str(mod_id), call.from_user.id)
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f'👤 Модератор: <code>{mod_id}</code> @{get_username(mod_id)}\n'
        f'📊 Текущие штрафы: <b>{count} шт = {total}₽</b>\n'
        f'(1 штраф = {500}₽)\n\n'
        f'Введите количество штрафов для выставления:',
        parse_mode='HTML',
        reply_markup=start_markup(call.from_user.id, text='🚫 Отмена')
    )
    update_state(call.message, PENALTY_ADD_COUNT)


@bot.message_handler(func=lambda message: get_state(message) == PENALTY_ADD_COUNT)
def penalty_add_count_handler(message):
    if message.text == '🚫 Отмена':
        bot.send_message(message.chat.id, 'Отменено', reply_markup=start_markup(message.chat.id))
        update_state(message, START)
        return
    if not message.text.isdigit() or int(message.text) <= 0:
        bot.send_message(message.chat.id, 'Введите целое положительное число')
        return
    count = int(message.text)
    mod_id = int(get_par('penalty_mod_id', message.chat.id))
    total_added = add_manual_penalty(mod_id, count)
    stats = get_penalties_stats(mod_id)
    bot.send_message(
        message.chat.id,
        f'✅ Выставлено <b>{count} шт</b> штрафов на сумму <b>{int(total_added)}₽</b>\n'
        f'📊 Итого у @{get_username(mod_id)}: <b>{stats["count"]} шт = {int(stats["total"])}₽</b>',
        parse_mode='HTML',
        reply_markup=start_markup(message.chat.id)
    )
    update_state(message, START)


@bot.callback_query_handler(func=lambda call: call.data.startswith("cash_in:") or call.data.startswith("cash_out:"))
def cash_transaction_callback(call):
    if call.from_user.id not in admins:
        bot.answer_callback_query(call.id, "Нет доступа")
        return
    parts = call.data.split(":")
    trans_type = 'income' if parts[0] == 'cash_in' else 'expense'
    mod_id = int(parts[1])
    cash = get_cash_stats(mod_id)
    balance_line = format_cash_line(cash, 'balance')
    action_text = '➕ Выдать деньги' if trans_type == 'income' else '➖ Записать расход'
    cur_markup = types.InlineKeyboardMarkup(row_width=3)
    cur_markup.add(
        types.InlineKeyboardButton('🇺🇸 Доллары $', callback_data=f'cash_cur:{trans_type}:{mod_id}:USD'),
        types.InlineKeyboardButton('🇺🇦 Гривны ₴',  callback_data=f'cash_cur:{trans_type}:{mod_id}:UAH'),
    )
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f'👤 @{get_username(mod_id)} | {action_text}\n'
        f'🟢 На руках: <b>{balance_line}</b>\n\n'
        f'Выберите валюту:',
        parse_mode='HTML',
        reply_markup=cur_markup
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("cash_cur:"))
def cash_cur_callback(call):
    if call.from_user.id not in admins:
        bot.answer_callback_query(call.id, "Нет доступа")
        return
    _, trans_type, mod_id_str, currency = call.data.split(":")
    mod_id = int(mod_id_str)
    add_data('cash_mod_id', mod_id_str, call.from_user.id)
    add_data('cash_type', trans_type, call.from_user.id)
    add_data('cash_currency', currency, call.from_user.id)
    sym = CASH_CURRENCIES[currency]
    action_text = '➕ Выдать деньги' if trans_type == 'income' else '➖ Записать расход'
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f'👤 @{get_username(mod_id)} | {action_text} | {sym}\n\nВведите сумму ({sym}):',
        parse_mode='HTML',
        reply_markup=start_markup(call.from_user.id, text='🚫 Отмена')
    )
    update_state(call.message, CASH_AMOUNT)


@bot.message_handler(func=lambda message: get_state(message) == CASH_AMOUNT)
def cash_amount_handler(message):
    if message.text == '🚫 Отмена':
        bot.send_message(message.chat.id, 'Отменено', reply_markup=start_markup(message.chat.id))
        update_state(message, START)
        return
    text_clean = message.text.replace(',', '.').replace(' ', '')
    try:
        amount = float(text_clean)
        if amount <= 0:
            raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, 'Введите положительное число (например: 10000 или 3200.50)')
        return
    add_data('cash_amount', str(amount), message.chat.id)
    skip_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    skip_markup.add('⏩ Пропустить', '🚫 Отмена')
    bot.send_message(message.chat.id, 'Введите комментарий (или нажмите ⏩ Пропустить):', reply_markup=skip_markup)
    update_state(message, CASH_COMMENT)


@bot.message_handler(func=lambda message: get_state(message) == CASH_COMMENT)
def cash_comment_handler(message):
    if message.text == '🚫 Отмена':
        bot.send_message(message.chat.id, 'Отменено', reply_markup=start_markup(message.chat.id))
        update_state(message, START)
        return
    comment = '' if message.text == '⏩ Пропустить' else message.text
    mod_id = int(get_par('cash_mod_id', message.chat.id))
    amount = float(get_par('cash_amount', message.chat.id))
    trans_type = get_par('cash_type', message.chat.id)
    currency = get_par('cash_currency', message.chat.id) or 'USD'
    sym = CASH_CURRENCIES.get(currency, '₽')
    add_cash_transaction(mod_id, trans_type, amount, comment, currency)
    cash = get_cash_stats(mod_id)
    sign = '+' if trans_type == 'income' else '-'
    action = 'Выдано' if trans_type == 'income' else 'Записан расход'
    balance_line = format_cash_line(cash, 'balance')
    issued_line = format_cash_line(cash, 'total_issued')
    spent_line = format_cash_line(cash, 'total_spent')
    any_negative = any(cash[c]['balance'] < 0 for c in CASH_CURRENCIES)
    balance_emoji = '🔴' if any_negative else '🟢'
    comment_line = f'💬 {comment}\n' if comment else ''
    bot.send_message(
        message.chat.id,
        f'✅ {action}: <b>{sign}{fmt_num(amount)}{sym}</b>\n'
        f'{comment_line}'
        f'\n👤 @{get_username(mod_id)}:\n'
        f'💰 Выдано: <b>{issued_line}</b>\n'
        f'💸 Потрачено: <b>{spent_line}</b>\n'
        f'{balance_emoji} На руках: <b>{balance_line}</b>',
        parse_mode='HTML',
        reply_markup=start_markup(message.chat.id)
    )
    update_state(message, START)


@bot.callback_query_handler(func=lambda call: call.data.startswith("cash_hist:"))
def cash_hist_callback(call):
    if call.from_user.id not in admins:
        bot.answer_callback_query(call.id, "Нет доступа")
        return
    mod_id = int(call.data.split(":")[1])
    history = get_cash_history(mod_id)
    cash = get_cash_stats(mod_id)
    any_negative = any(cash[c]['balance'] < 0 for c in CASH_CURRENCIES)
    balance_emoji = '🔴' if any_negative else '🟢'
    issued_line = format_cash_line(cash, 'total_issued')
    spent_line = format_cash_line(cash, 'total_spent')
    balance_line = format_cash_line(cash, 'balance')
    text = f'📋 <b>Касса @{get_username(mod_id)}</b>\n'
    text += f'💰 Выдано: <b>{issued_line}</b>  |  💸 Потрачено: <b>{spent_line}</b>\n'
    text += f'{balance_emoji} На руках: <b>{balance_line}</b>\n\n'
    if not history:
        text += '<i>История пуста</i>'
    else:
        for trans_type, amount, comment, created_at, currency in history:
            dt = datetime.fromisoformat(created_at)
            sign = '➕' if trans_type == 'income' else '➖'
            sym = CASH_CURRENCIES.get(currency, '₽')
            comment_str = f' — {comment}' if comment else ''
            text += f'{sign} <b>{fmt_num(amount)}{sym}</b>  {dt.strftime("%d.%m %H:%M")}{comment_str}\n'
    clear_markup = types.InlineKeyboardMarkup()
    clear_markup.add(types.InlineKeyboardButton('🗑 Очистить историю', callback_data=f'cash_clear:{mod_id}'))
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, text, parse_mode='HTML', reply_markup=clear_markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("cash_clear:"))
def cash_clear_callback(call):
    if call.from_user.id not in admins:
        bot.answer_callback_query(call.id, "Нет доступа")
        return
    mod_id = int(call.data.split(":")[1])
    clear_cash_history(mod_id)
    bot.answer_callback_query(call.id, "История очищена")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    bot.send_message(call.message.chat.id, f'🗑 История кассы @{get_username(mod_id)} очищена.')


@bot.callback_query_handler(func=lambda call: call.data.startswith("cash_zero:"))
def cash_zero_callback(call):
    if call.from_user.id not in admins:
        bot.answer_callback_query(call.id, "Нет доступа")
        return
    mod_id = int(call.data.split(":")[1])
    zeroed = zero_cash_balance(mod_id)
    bot.answer_callback_query(call.id)
    if not zeroed:
        bot.send_message(call.message.chat.id, f'💼 @{get_username(mod_id)}: баланс и так нулевой.')
        return
    lines = '  '.join(f'{fmt_num(v)}{CASH_CURRENCIES[c]}' for c, v in zeroed.items())
    bot.send_message(
        call.message.chat.id,
        f'✅ Касса @{get_username(mod_id)} обнулена.\n'
        f'💸 Списано: <b>{lines}</b>',
        parse_mode='HTML'
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("deduct_pen:"))
def deduct_pen_callback(call):
    if call.from_user.id not in admins:
        bot.answer_callback_query(call.id, "Нет доступа")
        return
    mod_id = int(call.data.split(":")[1])
    stats = get_penalties_stats(mod_id)
    total = int(stats['total'])
    count = stats['count']
    add_data('penalty_mod_id', str(mod_id), call.from_user.id)
    bot.answer_callback_query(call.id)
    inline = types.InlineKeyboardMarkup()
    if count > 0:
        inline.add(types.InlineKeyboardButton(f'➖ Списать 1 штраф (-500₽)', callback_data=f'deduct_pen_one:{mod_id}'))
    bot.send_message(
        call.message.chat.id,
        f'👤 Модератор: <code>{mod_id}</code>\n'
        f'📊 Текущие штрафы: <b>{count} шт = {total}₽</b>\n'
        f'(1 штраф = 500₽)\n\n'
        f'Введите сумму, которая должна <b>остаться</b> (кратно 500)\nили нажмите кнопку ниже:',
        parse_mode='HTML',
        reply_markup=inline
    )
    update_state(call.message, PENALTY_AMOUNT_LEAVE)


@bot.message_handler(func=lambda message: get_state(message) == PENALTY_AMOUNT_LEAVE)
def penalty_amount_leave_handler(message):
    if message.text == '🚫 Отмена':
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, 'Отменено', reply_markup=markup)
        update_state(message, START)
        return
    if not message.text.isdigit():
        bot.send_message(message.chat.id, 'Введите целое число, кратное 500')
        return
    amount = int(message.text)
    mod_id = int(get_par('penalty_mod_id', message.chat.id))
    result = deduct_penalties(mod_id, amount)
    markup = start_markup(message.chat.id)
    bot.send_message(
        message.chat.id,
        f'✅ Готово!\n'
        f'🗑 Списано штрафов: <b>{result["deleted"]} шт</b>\n'
        f'📊 Осталось: <b>{result["remaining_count"]} шт = {int(result["remaining_total"])}₽</b>',
        parse_mode='HTML',
        reply_markup=markup
    )
    update_state(message, START)


@bot.callback_query_handler(func=lambda call: call.data.startswith("deduct_pen_one:"))
def deduct_pen_one_callback(call):
    if call.from_user.id not in admins:
        bot.answer_callback_query(call.id, "Нет доступа")
        return
    mod_id = int(call.data.split(":")[1])
    stats = get_penalties_stats(mod_id)
    count = stats['count']
    total = int(stats['total'])
    if count == 0:
        bot.answer_callback_query(call.id, "Штрафов нет")
        return
    new_total = max(0, total - 500)
    result = deduct_penalties(mod_id, new_total)
    stats_after = get_penalties_stats(mod_id)
    remaining = stats_after['count']
    remaining_total = int(stats_after['total'])
    inline = types.InlineKeyboardMarkup()
    if remaining > 0:
        inline.add(types.InlineKeyboardButton(f'➖ Списать ещё 1 штраф (-500₽)', callback_data=f'deduct_pen_one:{mod_id}'))
    bot.answer_callback_query(call.id, "✅ 1 штраф списан")
    bot.edit_message_text(
        f'👤 Модератор: <code>{mod_id}</code>\n'
        f'✅ Списан 1 штраф (-500₽)\n'
        f'📊 Осталось: <b>{remaining} шт = {remaining_total}₽</b>',
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode='HTML',
        reply_markup=inline
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("lava_paid"))
def check_lava_payment(call):
    bot.answer_callback_query(call.id)
    order_id = call.data.split(":")[1]
    user_id = call.from_user.id

    payload = {
        "shopId": SHOP_ID,
        "orderId": order_id
    }
    json_data = json.dumps(payload, separators=(',', ':'), ensure_ascii=False)
    signature = hmac.new(SECRET_KEY.encode(), json_data.encode(), hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Signature": signature
    }

    response = requests.post("https://api.lava.ru/business/invoice/status", headers=headers, data=json_data.encode('utf-8'))
    data = response.json()

    print(f"[LAVA] response status: {response.status_code}, body: {data}")
    if response.status_code == 200 and "data" in data and "status" in data["data"]:
        status = data["data"]["status"]
        amount = data["data"]["amount"]
        print(f"[LAVA] order status: {status}, amount: {amount}, user: {call.message.chat.id}")
        # bot.send_message(5358743611, 'lava')
        if status == "success":
            update_state(call.message, START)
            bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )
            bot.send_message(call.message.chat.id, f"✅ Оплата подтверждена! На ваш баланс начислено {amount}р.", reply_markup=start_markup(call.message.chat.id))
            result = add_deposit(call.message.chat.id, amount, description='Пополнение через Lava')
            print(f"[LAVA] add_deposit result: {result}")
            date = datetime.now().date().strftime('%d.%m.%Y')
            send_to_archives(bot.send_message,
                             f'Дата: {date}\nid: {call.message.chat.id}\nПользователь: {call.message.chat.username}\nНомер заявки: {data["data"]["id"]}\nУслуга: Lava Pay SBP \nСумма: {amount} р.\n🎩Ранг: {get_user_rank(call.message.chat.id)}\nСтатус: ✅Одобрено')
            user_order_ids[call.message.chat.id] = ""

        elif status == "waiting":
            bot.send_message(call.message.chat.id, "⏳ Оплата ещё не поступила. Пожалуйста, подождите.")
            update_state(call.message, START)
        elif status == "expired":
            bot.send_message(call.message.chat.id, "⌛ Срок действия ссылки истёк. Попробуйте снова.")
            update_state(call.message, START)
        elif status == "created":
            bot.send_message(call.message.chat.id, f"❌ Оплата не поступила!")
            update_state(call.message, START)
        else:
            bot.send_message(call.message.chat.id, f"Status: {status}")
            update_state(call.message, START)
    else:
        bot.send_message(call.message.chat.id, f"Ошибка проверки статуса оплаты: {data}")
        update_state(call.message, START)

#############
# Обработчик нажатий на инлайн-кнопки
@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    text = call.data
    chat_id = call.message.chat.id

    if text == "ua" or text == 'ru' or text == "es":
        if get_state(call.message) == MOBIL:
            json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
            markup = start_markup(chat_id, text='🚫 Отмена')
            if text == "ua":
                json_data["Мобильный"]["Украина"] += 1
                bot.send_message(chat_id, get_ua_num, reply_markup=markup)
                add_data('contry', 'ua', call.message.chat.id)
            elif text == 'ru':
                json_data["Мобильный"]["Россия"] += 1
                bot.send_message(chat_id, get_ru_num, reply_markup=markup)
                add_data('contry', 'ru', call.message.chat.id)
            elif text == 'es':
                json_data["Мобильный"]["Испания"] += 1
                bot.send_message(chat_id, get_es_num, reply_markup=markup)
                add_data('contry', 'es', call.message.chat.id)
            with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
                json.dump(json_data, json_file, ensure_ascii=False, indent=4)
            update_state(call.message, PHONE)
    elif text == "check_nicepay":
        data = get_payment_info(payment_ids[chat_id])

        status = data['data']['status']
        print(f"Сервер ответил: {data}")
        print(f"Статус платежа : {status}")

        if status == 5:
            payment_info = get_payment_info(payment_ids[call.message.chat.id])
            amount = payment_info["data"]['amountNum']
            additional_fee = payment_info["data"]['additionalFee']
            fee_value = float(additional_fee.replace("₽", "").strip())
            amount2 = amount - fee_value
            add_deposit(chat_id, amount, description='Пополнение через Lava')
            bot.send_message(call.message.chat.id, f"✅Ваш баланс пополнен на {amount2}₽ !")
            date = datetime.now().date().strftime('%d.%m.%Y')
            send_to_archives(bot.send_message, f'Дата: {date}\nid: {chat_id}\nПользователь: {call.message.chat.username}\nНомер заявки: {payment_ids[chat_id]}\nУслуга: Nicepay \nСумма: {amount2} р.\n🎩Ранг: {get_user_rank(chat_id)}\nСтатус: ✅Одобрено')
            payment_ids[chat_id] = None
            update_state(call.message, START)
        else:
            inline_markup = types.InlineKeyboardMarkup()
            inline_markup.add(types.InlineKeyboardButton("🔄 Проверить ещё раз", callback_data="check_nicepay"))
            inline_markup.add(types.InlineKeyboardButton("❌ Отменить оплату", callback_data="deposit_cancel"))
            bot.send_message(chat_id, "Оплата не пришла! Попробуйте позже или повторите проверку.",
                             reply_markup=inline_markup)

    elif text == "private_help":
        markup = types.InlineKeyboardMarkup(row_width=True)
        markup.add(types.InlineKeyboardButton("📲Написать", url="https://t.me/donate008"))
        bot.send_message(call.message.chat.id, "Для получения индивидуальной помощи и настройки напишите нашему специалисту 👇", reply_markup=markup)
        update_state(call.message, START)

    elif text == "svc_svyaz":
        markup = types.InlineKeyboardMarkup(row_width=True)
        markup.add(types.InlineKeyboardButton("✅ Оплатить 899 ₽", callback_data="svc_confirm_svyaz"))
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="svc_cancel"))
        bot.send_message(call.message.chat.id,
            "📶 <b>Настройка связи</b>\n\n"
            "Настроим стабильную связь и интернет на вашем устройстве. Уберём перебои, подберём оптимальные параметры под вашу ситуацию.\n\n"
            "💰 Стоимость: 899 ₽",
            parse_mode="HTML", reply_markup=markup)
        update_state(call.message, START)

    elif text == "svc_gb":
        markup = types.InlineKeyboardMarkup(row_width=True)
        markup.add(types.InlineKeyboardButton("Пополнение ГБ", callback_data="svc_gb_gb"))
        markup.add(types.InlineKeyboardButton("Роуминг", callback_data="svc_gb_roum"))
        # markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="svc_cancel"))
        bot.send_message(call.message.chat.id,
            "🛜 <b>Выберите что хотите пополнить</b>",
            parse_mode="HTML", reply_markup=markup)
        update_state(call.message, START)

    elif text == "svc_gb_gb":
        markup = types.InlineKeyboardMarkup(row_width=True)        
        markup.add(types.InlineKeyboardButton("100 ГБ", callback_data="svc-gb_100"))
        markup.add(types.InlineKeyboardButton("10 ГБ", callback_data="svc-gb_10"))
        # markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="svc_cancel"))
        bot.send_message(call.message.chat.id,
            "🛜 <b>Пополнение ГБ</b>\n\n"
            "Добавим интернет на ваш номер без смены SIM.\nРаботает сразу после подключения, без перебоев.\n\n"
            "💰 Стоимость:\n"
            "<b>10 ГБ</b> - 990 руб / 4 недели\n"
            "<b>100 ГБ</b> - 1690 руб / 4 недели",
            parse_mode="HTML", reply_markup=markup)
        update_state(call.message, START)

    elif text == "svc_gb_roum":
        markup = types.InlineKeyboardMarkup(row_width=True)
        markup.add(types.InlineKeyboardButton("40 ГБ", callback_data="svc-roum_40"))
        markup.add(types.InlineKeyboardButton("15 ГБ", callback_data="svc-roum_15"))
        # markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="svc_cancel"))
        bot.send_message(call.message.chat.id,
            "🌍 <b>Роуминг</b>\n\n"
            "Настроим интернет и связь за границей.\nСтабильное подключение без переплат и сложных настроек.\n\n"
            "💰 Стоимость:\n"
            "<b>15 ГБ</b> - 990 руб / 14 дней\n"
            "<b>40 ГБ</b> - 2099 руб / 21 день",
            parse_mode="HTML", reply_markup=markup)
        update_state(call.message, START)

    elif text.startswith('svc-'):
        prices = {10: 990, 100: 1690, 15: 990, 40: 2099}
        gb = int(text.split('_')[-1])
        svc_type = text.split('_')[0].replace('svc-', '')
        summ = prices.get(gb, 0)
        svc_label = f"{gb} ГБ{'  (роуминг)' if svc_type == 'roum' else ''}"
        add_data('svc_gb_key', f"{svc_type}_{gb}", chat_id)
        add_data('svc_gb_price', str(summ), chat_id)
        add_data('svc_gb_label', svc_label, chat_id)
        markup = types.InlineKeyboardMarkup(row_width=True)
        markup.add(types.InlineKeyboardButton("🟡 Lifecell", callback_data="svc_gb_op_lifecell", icon_custom_emoji_id="5267284102960131913"))
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="svc_cancel"))
        bot.send_message(chat_id, "📡 Выберите оператора:", reply_markup=markup)

    elif text == "svc_gb_op_lifecell":
        add_data('svc_gb_operator', 'Lifecell', chat_id)
        update_state(call.message, SVC_GB_PHONE)
        bot.send_message(chat_id,
            "✍️ Введите номер телефона Lifecell (+380...) для пополнения ГБ:\n\nНапример: +380501234567",
            reply_markup=start_markup(chat_id, text='🚫 Отмена'))

    elif text == "svc_gb_confirm":
        _process_svc_gb_order(call)

    elif text.startswith("svc_gb_accept:"):
        _, number_c, user_id_c, summa_c = text.split(":")
        user_id_c = int(user_id_c)
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.send_message(user_id_c,
            f"✅ Ваша заявка №<code>{number_c}</code> выполнена!\nСпасибо за покупку 🎉",
            parse_mode="HTML", reply_markup=start_markup(user_id_c))
        bot.send_message(call.message.chat.id, f"✅ Заявка №{number_c} выполнена. Принял: @{call.from_user.username}")
        _username = get_par('svc_gb_username', user_id_c) or ''
        _svc_name = get_par('svc_gb_name', user_id_c) or ''
        _phone = get_par('svc_gb_phone', user_id_c) or ''
        _date = get_par('svc_gb_order_date', user_id_c) or datetime.now().date().strftime('%d.%m.%Y')
        _admin = call.from_user.username or str(call.from_user.id)
        _key = get_par('svc_gb_key', user_id_c) or ''
        _COST_UAH = {'gb_10': 125, 'gb_100': 250, 'roum_15': 250, 'roum_40': 550}
        _cost_uah = _COST_UAH.get(_key, 0)
        _rate = round(float(_uah_cost_rate_cache or get_kurs('uah')), 4)
        _cost_rub = round(_cost_uah * _rate, 2)
        _profit = round(float(summa_c) - _cost_rub, 2)
        _cost_block = (
            f"💰Себестоимость: {_cost_uah} ₴ = {_cost_rub} ₽ (курс {_rate})\n"
            f"📈Чистая прибыль: {_profit} ₽\n"
        ) if _cost_uah else ''
        send_to_archives(bot.send_message,
            f"Дата: {_date}\nЗаявка №{number_c}\nПользователь: @{_username}\nid: {user_id_c}\n"
            f"Услуга: {_svc_name}. {_phone}\nСумма: {summa_c} ₽\n"
            f"{_cost_block}"
            f"🎩Ранг: {get_user_rank(user_id_c)}\nСтатус: ✅Одобрено\n\nЗаявку закрыл(а): {_admin}")

    elif text.startswith("svc_gb_reject:"):
        _, number_c, user_id_c, summa_c = text.split(":")
        user_id_c = int(user_id_c)
        add_deposit(user_id_c, int(summa_c), description='Возврат средств')
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.send_message(user_id_c,
            f"❌ Заявка №<code>{number_c}</code> отклонена.\n💰 Вам возвращено {summa_c} ₽ на баланс.",
            parse_mode="HTML", reply_markup=start_markup(user_id_c))
        bot.send_message(call.message.chat.id, f"❌ Заявка №{number_c} отклонена. Деньги возвращены. Отклонил: @{call.from_user.username}")
        _username = get_par('svc_gb_username', user_id_c) or ''
        _svc_name = get_par('svc_gb_name', user_id_c) or ''
        _phone = get_par('svc_gb_phone', user_id_c) or ''
        _date = datetime.now().date().strftime('%d.%m.%Y')
        _admin = call.from_user.username or str(call.from_user.id)
        send_to_archives(bot.send_message,
            f"Дата: {_date}\nЗаявка №{number_c}\nПользователь: @{_username}\nid: {user_id_c}\n"
            f"Услуга: {_svc_name}. {_phone}\nСумма: {summa_c} ₽\n"
            f"🎩Ранг: {get_user_rank(user_id_c)}\nСтатус: ❌Отменено\n\nЗаявку закрыл(а): {_admin}")

    elif text == "svc_sim":
        markup = types.InlineKeyboardMarkup(row_width=True)
        markup.add(types.InlineKeyboardButton("✅ Оплатить 899 ₽", callback_data="svc_confirm_sim"))
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="svc_cancel"))
        bot.send_message(call.message.chat.id,
            "💳 <b>Настройка SIM / eSIM</b>\n\n"
            "Подключим и полностью настроим SIM или eSIM. Обеспечим стабильный сигнал и корректную работу интернета.\n\n"
            "💰 Стоимость: 899 ₽",
            parse_mode="HTML", reply_markup=markup)
        update_state(call.message, START)

    elif text == "svc_phone":
        markup = types.InlineKeyboardMarkup(row_width=True)
        markup.add(types.InlineKeyboardButton("✅ Оплатить 899 ₽", callback_data="svc_confirm_phone"))
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="svc_cancel"))
        bot.send_message(call.message.chat.id,
            "📲 <b>Настройка телефона</b>\n\n"
            "Оптимизируем устройство: уберём лишнее, ускорим работу, настроим всё под комфортное использование.\n\n"
            "💰 Стоимость: 899 ₽",
            parse_mode="HTML", reply_markup=markup)
        update_state(call.message, START)

    elif text == "svc_gaming":
        markup = types.InlineKeyboardMarkup(row_width=True)
        markup.add(types.InlineKeyboardButton("✅ Оплатить 990 ₽", callback_data="svc_confirm_gaming"))
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="svc_cancel"))
        bot.send_message(call.message.chat.id,
            "🎮 <b>Настройка игровых аккаунтов</b>\n\n"
            "Подготовим аккаунт к работе: регион, платежи, доступ — всё будет работать без ошибок и ограничений.\n\n"
            "💰 Стоимость: 990 ₽",
            parse_mode="HTML", reply_markup=markup)
        update_state(call.message, START)

    elif text == "svc_region":
        markup = types.InlineKeyboardMarkup(row_width=True)
        markup.add(types.InlineKeyboardButton("✅ Оплатить 1490 ₽", callback_data="svc_confirm_region"))
        markup.add(types.InlineKeyboardButton("❌ Отмена", callback_data="svc_cancel"))
        bot.send_message(call.message.chat.id,
            "🌍 <b>Смена региона аккаунтов</b>\n\n"
            "Безопасно сменим регион аккаунта для доступа к нужным функциям, ценам и сервисам.\n\n"
            "💰 Стоимость: 1490 ₽",
            parse_mode="HTML", reply_markup=markup)
        update_state(call.message, START)

    elif text.startswith("svc_confirm_gb:"):
        _GB_INFO = {
            "gb_10":    ("🛜 Пополнение ГБ (10 ГБ)",    990),
            "gb_100":   ("🛜 Пополнение ГБ (100 ГБ)", 1690),
            "roum_15":  ("🌍 Роуминг (15 ГБ)",         990),
            "roum_40":  ("🌍 Роуминг (40 ГБ)",        2099),
        }
        key = text.split(":", 1)[-1]
        svc_name, svc_price = _GB_INFO.get(key, ("Услуга", 0))
        user_id = call.from_user.id
        balans = get_balans(user_id)
        if balans is None or float(balans) < svc_price:
            bot.answer_callback_query(call.id)
            deposit_markup = types.InlineKeyboardMarkup(row_width=True)
            deposit_markup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balanse"))
            bot.send_message(call.message.chat.id, 'Недостаточно средств', reply_markup=start_markup(call.message.chat.id))
            bot.send_message(call.message.chat.id, 'Пополните баланс', reply_markup=deposit_markup)
            update_state(call.message, START)
        else:
            add_deposit(user_id, -svc_price, description=svc_name)
            number = to_arhiv(user_id, svc_name, svc_price)
            date = datetime.now().date().strftime('%d.%m.%Y')
            add_data('svc_pending_name', svc_name, user_id)
            add_data('svc_pending_price', str(svc_price), user_id)
            add_data('svc_pending_number', str(number), user_id)
            add_data('svc_pending_date', date, user_id)
            bot.answer_callback_query(call.id, "✅ Оплата прошла!")
            bot.send_message(call.message.chat.id,
                "✅ Оплата принята!\n\n"
                "✍️ Напишите ваш номер телефона — после этого напишите нашему специалисту для выполнения услуги.\n\n"
                "Например: +79001234567",
                reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
            update_state(call.message, WAIT_SVC_CONTACT)

    elif text.startswith("svc_confirm_"):
        _SVC_INFO = {
            "svc_confirm_svyaz":  ("📶 Настройка связи",             899),
            "svc_confirm_sim":    ("💳 Настройка SIM / eSIM",        899),
            "svc_confirm_phone":  ("📲 Настройка телефона",          899),
            "svc_confirm_gaming": ("🎮 Настройка игровых аккаунтов", 990),
            "svc_confirm_region": ("🌍 Смена региона аккаунтов",    1490),
        }
        _DIRECT_SVCS = {"svc_confirm_svyaz", "svc_confirm_sim", "svc_confirm_phone", "svc_confirm_region"}
        svc_name, svc_price = _SVC_INFO.get(text, ("Услуга", 0))
        user_id = call.from_user.id
        balans = get_balans(user_id)
        if balans is None or float(balans) < svc_price:
            bot.answer_callback_query(call.id)
            deposit_markup = types.InlineKeyboardMarkup(row_width=True)
            deposit_markup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balanse"))
            bot.send_message(call.message.chat.id, 'Недостаточно средств', reply_markup=start_markup(call.message.chat.id))
            bot.send_message(call.message.chat.id, 'Пополните баланс', reply_markup=deposit_markup)
            update_state(call.message, START)
        elif text in _DIRECT_SVCS:
            add_deposit(user_id, -svc_price, description=svc_name)
            number = to_arhiv(user_id, svc_name, svc_price)
            date = datetime.now().date().strftime('%d.%m.%Y')
            username = call.message.chat.username or ''
            bot.answer_callback_query(call.id, "✅ Оплата прошла!")
            manager_markup = types.InlineKeyboardMarkup(row_width=True)
            manager_markup.add(types.InlineKeyboardButton("📲 Написать специалисту", url="https://t.me/donate008"))
            bot.send_message(call.message.chat.id,
                f"✅ Оплата принята!\n\n"
                f"📋 Услуга: <b>{svc_name}</b>\n"
                f"💸 Списано: {svc_price} ₽\n\n"
                "Для получения заказа напишите специалисту 👇",
                parse_mode="HTML", reply_markup=manager_markup)
            send_to_archives(bot.send_message,
                f"Дата: {date}\nЗаявка №{number}\nПользователь: @{username}\nid: {user_id}\n"
                f"Услуга: {svc_name}\nСумма: {svc_price} ₽\n"
                f"🎩Ранг: {get_user_rank(user_id)}\nСтатус: ✅Одобрено")
            update_state(call.message, START)
        else:
            add_deposit(user_id, -svc_price, description=svc_name)
            number = to_arhiv(user_id, svc_name, svc_price)
            date = datetime.now().date().strftime('%d.%m.%Y')
            add_data('svc_pending_name', svc_name, user_id)
            add_data('svc_pending_price', str(svc_price), user_id)
            add_data('svc_pending_number', str(number), user_id)
            add_data('svc_pending_date', date, user_id)
            bot.answer_callback_query(call.id, "✅ Оплата прошла!")
            bot.send_message(call.message.chat.id,
                "✅ Оплата принята!\n\n"
                "✍️ Напишите ваш номер телефона — после этого напишите нашему специалисту для выполнения услуги.\n\n"
                "Например: +79001234567",
                reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
            update_state(call.message, WAIT_SVC_CONTACT)

    elif text == "mobile_gb":
        markup = types.InlineKeyboardMarkup(row_width=True)
        markup.add(types.InlineKeyboardButton("🇺🇦 Украина", callback_data="mobile_gb_ua"))
        bot.send_message(chat_id, "🌍 Выберите страну:", reply_markup=markup)

    elif text == "mobile_gb_ua":
        markup = types.InlineKeyboardMarkup(row_width=True)
        markup.add(types.InlineKeyboardButton("🟡 Lifecell", callback_data="mobile_gb_lifecell"))
        bot.send_message(chat_id, "📡 Выберите оператора:", reply_markup=markup)

    elif text == "mobile_gb_lifecell":
        with open("lifecell_gb.json", encoding="utf-8") as f:
            packages = json.load(f)
        markup = types.InlineKeyboardMarkup(row_width=True)
        lines = []
        for key, pkg in packages.items():
            markup.add(types.InlineKeyboardButton(
                f"{pkg['label']} — {pkg['price']} ₽",
                callback_data=f"mobile_gb_pkg:{key}"
            ))
            lines.append(f"<b>{pkg['label']}</b> — {pkg['price']} ₽")
        bot.send_message(chat_id,
            "📦 <b>Выберите количество ГБ:</b>\n\n" + "\n".join(lines),
            parse_mode="HTML", reply_markup=markup)

    elif text.startswith("mobile_gb_pkg:"):
        key = text.split(":", 1)[1]
        with open("lifecell_gb.json", encoding="utf-8") as f:
            packages = json.load(f)
        pkg = packages.get(key)
        if not pkg:
            bot.send_message(chat_id, "Пакет не найден.")
            return
        confirm_markup = types.InlineKeyboardMarkup(row_width=True)
        confirm_markup.add(
            types.InlineKeyboardButton(f"✅ Оплатить {pkg['price']} ₽", callback_data=f"mobile_gb_confirm:{key}"),
            types.InlineKeyboardButton("❌ Отмена", callback_data="svc_cancel"),
        )
        bot.send_message(chat_id,
            f"Подтвердите оплату:\n\n<b>{pkg['label']} Lifecell</b> — {pkg['price']} ₽",
            parse_mode="HTML", reply_markup=confirm_markup)

    elif text.startswith("mobile_gb_confirm:"):
        key = text.split(":", 1)[1]
        with open("lifecell_gb.json", encoding="utf-8") as f:
            packages = json.load(f)
        pkg = packages.get(key)
        if not pkg:
            bot.send_message(chat_id, "Пакет не найден.")
            return
        svc_price = int(pkg['price'])
        svc_name = f"📶 Доп ГБ Lifecell {pkg['label']}"
        balans = get_balans(chat_id)
        if balans is None or float(balans) < svc_price:
            bot.answer_callback_query(call.id)
            deposit_markup = types.InlineKeyboardMarkup(row_width=True)
            deposit_markup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balanse"))
            bot.send_message(chat_id, 'Недостаточно средств', reply_markup=start_markup(chat_id))
            bot.send_message(chat_id, 'Пополните баланс', reply_markup=deposit_markup)
            update_state(call.message, START)
        else:
            add_deposit(chat_id, -svc_price, description=svc_name)
            number = to_arhiv(chat_id, svc_name, svc_price)
            date = datetime.now().date().strftime('%d.%m.%Y')
            add_data('svc_pending_name', svc_name, chat_id)
            add_data('svc_pending_price', str(svc_price), chat_id)
            add_data('svc_pending_number', str(number), chat_id)
            add_data('svc_pending_date', date, chat_id)
            bot.answer_callback_query(call.id, "✅ Оплата прошла!")
            bot.send_message(chat_id,
                "✅ Оплата принята!\n\n"
                "✍️ Напишите номер телефона Lifecell (+380...), "
                "на который нужно добавить ГБ.\n\n"
                "Например: +380501234567",
                reply_markup=start_markup(chat_id, text='🚫 Отмена'))
            update_state(call.message, WAIT_SVC_CONTACT)

    elif text == "svc_cancel":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "❌ Отменено.", reply_markup=start_markup(call.message.chat.id))
        update_state(call.message, START)


    elif text == "donat" or text == 'gift_cards':
        markup = start_markup(chat_id)
        if text == 'donat':

            json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
            json_data["Игры"]["Steam"] += 1

            with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
                json.dump(json_data, json_file, ensure_ascii=False, indent=4)

            markup = types.InlineKeyboardMarkup(row_width=True)
            donate_communication = types.InlineKeyboardButton("Написать", url="https://t.me/donate008")
            markup.add(donate_communication)
            bot.send_message(call.from_user.id, f"Чтобы пополнить баланс Steam напишите нашему специалисту", reply_markup=markup)
        elif text == 'gift_cards':

            json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
            json_data["Игры"]["Gift Cards"]["clicks"] += 1

            with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
                json.dump(json_data, json_file, ensure_ascii=False, indent=4)
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_button1 = types.InlineKeyboardButton("Steam Gift Cards", callback_data="steam")
            inline_button2 = types.InlineKeyboardButton("Apple & iTunes Gifts", callback_data="apple")
            inline_button3 = types.InlineKeyboardButton("Google Play Gifts Cards", callback_data="google")
            inline_markup.add(inline_button1)
            inline_markup.add(inline_button2)
            inline_markup.add(inline_button3)
            bot.send_message(chat_id, f'😁Выберите товар\n\n Активировать Google Play Gift Card USD можно только на аккаунты зарегистрированные в США!', reply_markup=inline_markup)
    elif text == "my_phone" or text == 'edit_phone':
        markup = start_markup(chat_id, text='🚫 Отмена')
        contry = get_par('contry', chat_id)
        if text == 'edit_phone':

            if contry == "ua":
                bot.send_message(chat_id, get_ua_num, reply_markup=markup)
            elif contry == 'ru':
                bot.send_message(chat_id, get_ru_num, reply_markup=markup)
            elif contry == "es":
                bot.send_message(chat_id, get_es_num, reply_markup=markup)
            update_state(call.message, PHONE)
        if text == 'my_phone':
            if contry == "ua":
                bot.send_message(chat_id, 'Введите сумму пополнения в гривнах от 200 до 10000 гривен', reply_markup=markup)
            elif contry == 'ru':
                bot.send_message(chat_id, 'Введите сумму пополнения', reply_markup=markup)
            elif contry == "es":
                bot.send_message(chat_id, 'Введите сумму пополнения в евро', reply_markup=markup)
            update_state(call.message, SUMM)
    elif text == "my_email" or text == 'edit_email':
        markup = start_markup(chat_id, text='🚫 Отмена')
        if text == 'edit_email':
            bot.send_message(chat_id, '✍️Введите ваш Email, на который мы отправим вам данный товар :', reply_markup=start_markup(chat_id, text='🚫 Отмена'))
            update_state(call.message, EMAIL)
        if text == 'my_email':
            gift = get_par("gift", chat_id)
            if gift == 'steam':
                gift = 'Steam Gift Cards'
            elif gift == 'apple':
                gift = 'Apple & iTunes Gifts'
            elif gift == 'google':
                gift = 'Google Play Gifts Cards'
            valuta = get_par("valuta", chat_id)
            if valuta == 'usd':
                valuta = 'USD'
                kurs = get_kurs('usd')
            elif valuta == 'eur':
                valuta = 'EUR'
                kurs = get_kurs('eur')
            elif valuta == 'try':
                valuta = 'TRY'
                kurs = get_kurs('try')
            value = get_par("value", chat_id)
            if float(get_balans(call.message.chat.id))-float(int(value)*kurs)>=0:
                email = get_par("email", chat_id)
                add_data('sum', str(int(value)*kurs), call.message.chat.id)
                update_balanse(call.message.chat.id, 'sum')
                update_total_spent(call.message.chat.id, float(int(value)*kurs))
                usluga = f'Gift Cards. {gift}\nВалюта: {valuta}.\nEmail: {email}\nСумма в валюте: {value}'
                number = to_arhiv(call.message.chat.id, usluga, int(value)*kurs)
                bot.send_message(call.message.chat.id, f'✅Готово\nВаша заявка №<code>{number}</code> уже в обработке!', reply_markup = start_markup(chat_id), parse_mode="HTML")
                bot.send_message(adminGroup, f'Заявка №{number}\nПользователь: @{call.message.chat.username} \nid: {call.message.chat.id}\nУслуга: {usluga}\n🎩Ранг: {get_user_rank(call.message.chat.id)}\nСумма: {int(value)*kurs}', reply_markup = admin_markup())
                update_state(call.message, START)
            else:
                update_state(call.message, START)
                bot.send_message(call.message.chat.id, 'Недостаточно средств', reply_markup = start_markup(call.message.chat.id))
                inline_markup = types.InlineKeyboardMarkup(row_width=True)
                inline_markup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balanse"))
                bot.send_message(call.message.chat.id, 'Пополните баланс', reply_markup = inline_markup)
    elif text == "steam" or text == "apple" or text == "google":
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_button1 = types.InlineKeyboardButton("🇺🇸USD", callback_data="usd")
        inline_button2 = types.InlineKeyboardButton("🇪🇺EUR", callback_data="eur")
        inline_button3 = types.InlineKeyboardButton("🇹🇷TRY", callback_data="try")
        add_data('gift', text, call.message.chat.id)

        json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))

        if text == "steam":
            json_data["Игры"]["Gift Cards"]["Steam Gift Cards"] += 1
            inline_markup.add(inline_button1)
            inline_markup.add(inline_button2)
            inline_markup.add(inline_button3)
        elif text == "apple":
            json_data["Игры"]["Gift Cards"]["Apple & iTunes Gifts"] += 1
            inline_markup.add(inline_button1)
            inline_markup.add(inline_button3)
        elif text == "google":
            json_data["Игры"]["Gift Cards"]["Google Play Gifts Cards"] += 1
            inline_markup.add(inline_button1)
            inline_markup.add(inline_button3)

        with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)

        bot.send_message(chat_id, 'Выберите валюту:', reply_markup=inline_markup)
        update_state(call.message, VALUTA)
    elif text == "France":
        with open("esim.json", encoding="utf-8") as file:
            data = json.load(file)
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton(f'{data["FranceUnlimited"]["tariff_name"]}', callback_data="FranceUnlimitedTarif"))
        inline_markup.add(types.InlineKeyboardButton(f'{data["France35GB"]["tariff_name"]}', callback_data="France35GBTarif"))
        bot.send_message(call.message.chat.id, 'Выберите тариф Франции:', reply_markup=inline_markup)

    elif text == "Vodafone" or text == "Kievstar" or text == "Lifecell":
        with open("esim.json", encoding="utf-8") as file:
            data = json.load(file)
        json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))

        if text == "Vodafone":
            json_data["eSIM сим-карты"]["Vodafone"] += 1
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_markup.add(types.InlineKeyboardButton(f'{data["Vodafone"]["tariff_name"]}', callback_data="VodafoneTarif"))
            bot.send_message(call.message.chat.id, 'Выберите тариф:', reply_markup=inline_markup)
            add_data('EsimOperator', text, call.message.chat.id)
        elif text == "Kievstar":
            json_data["eSIM сим-карты"]["Киевстар"] += 1
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_markup.add(types.InlineKeyboardButton(f'{data["Kievstar"]["tariff_name"]}', callback_data="КиевстарTarif"))
            bot.send_message(call.message.chat.id, 'Выберите тариф:', reply_markup=inline_markup)
            add_data('EsimOperator', text, call.message.chat.id)
        elif text == "Lifecell":
            json_data["eSIM сим-карты"]["Lifecell"] += 1
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_markup.add(types.InlineKeyboardButton(f'{data["Lifecell"]["tariff_name"]}', callback_data="LifecellTarif"))
            bot.send_message(call.message.chat.id, 'Выберите тариф:', reply_markup=inline_markup)
            add_data('EsimOperator', text, call.message.chat.id)

        with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)

    elif text == "VodafoneTarif" or text == "КиевстарTarif" or text == "LifecellTarif" or text == "FranceUnlimitedTarif" or text == "France35GBTarif":
        with open("esim.json", encoding="utf-8") as file:
            data = json.load(file)
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("🛍Купить💵", callback_data="buyEsim"))
        inline_markup.add(types.InlineKeyboardButton("⬅️Вернуться на главную", callback_data="back"))
        with open("eSIM/esim_answer.json", encoding="utf-8") as file:
            esim_data = json.load(file)
        operator = text.replace("Tarif", "")
        if text == "VodafoneTarif":
            add_data('EsimTarif', f"{data['Vodafone']['tariff']}", call.message.chat.id)
            add_data('EsimPrice', f"{data['Vodafone']['price']}", call.message.chat.id)
            stock_count = len(esim_data.get("Vodafone", {}))
            display_count = stock_count if stock_count > 3 else 3
            caption = f"{data['Vodafone']['tariff']}\n\n📦 В наличии: {display_count} шт"
            ents = _get_esim_caption_entities(data['Vodafone'])
            with open('files/VodafoneTarif.jpg', 'rb') as photo:
                if ents:
                    bot.send_photo(call.message.chat.id, photo, caption, reply_markup=inline_markup, caption_entities=ents)
                else:
                    bot.send_photo(call.message.chat.id, photo, caption, reply_markup=inline_markup, parse_mode='HTML')
        elif text == "КиевстарTarif":
            operator = "Kievstar"
            add_data('EsimTarif', f"{data['Kievstar']['tariff']}", call.message.chat.id)
            add_data('EsimPrice', f"{data['Kievstar']['price']}", call.message.chat.id)
            stock_count = len(esim_data.get("Kievstar", {}))
            display_count = stock_count if stock_count > 3 else 3
            caption = f"{data['Kievstar']['tariff']}\n\n📦 В наличии: {display_count} шт"
            ents = _get_esim_caption_entities(data['Kievstar'])
            with open('files/КиевстарTarif.jpg', 'rb') as photo:
                if ents:
                    bot.send_photo(call.message.chat.id, photo, caption, reply_markup=inline_markup, caption_entities=ents)
                else:
                    bot.send_photo(call.message.chat.id, photo, caption, reply_markup=inline_markup, parse_mode='HTML')
        elif text == "LifecellTarif":
            add_data('EsimTarif', f"{data['Lifecell']['tariff']}", call.message.chat.id)
            add_data('EsimPrice', f"{data['Lifecell']['price']}", call.message.chat.id)
            stock_count = len(esim_data.get("Lifecell", {}))
            display_count = stock_count if stock_count > 3 else 3
            caption = f"{data['Lifecell']['tariff']}\n\n📦 В наличии: {display_count} шт"
            ents = _get_esim_caption_entities(data['Lifecell'])
            with open('files/LifecellTarif.jpg', 'rb') as photo:
                if ents:
                    bot.send_photo(call.message.chat.id, photo, caption, reply_markup=inline_markup, caption_entities=ents)
                else:
                    bot.send_photo(call.message.chat.id, photo, caption, reply_markup=inline_markup, parse_mode='HTML')
        elif text in ["FranceUnlimitedTarif", "France35GBTarif"]:
            operator = text.replace("Tarif", "")
            json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
            esim_stats = json_data.setdefault("eSIM сим-карты", {})
            esim_stats[operator] = esim_stats.get(operator, 0) + 1
            with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
                json.dump(json_data, json_file, ensure_ascii=False, indent=4)
            add_data('EsimOperator', operator, call.message.chat.id)
            add_data('EsimTarif', f"{data[operator]['tariff']}", call.message.chat.id)
            add_data('EsimPrice', f"{data[operator]['price']}", call.message.chat.id)
            stock_count = len(esim_data.get(operator, {}))
            display_count = stock_count if stock_count > 3 else 3
            caption = f"{data[operator]['tariff']}\n\n📦 В наличии: {display_count} шт"
            ents = _get_esim_caption_entities(data[operator])
            image_path = f'files/{operator}Tarif.jpg'
            if os.path.exists(image_path):
                with open(image_path, 'rb') as photo:
                    if ents:
                        bot.send_photo(call.message.chat.id, photo, caption, reply_markup=inline_markup, caption_entities=ents)
                    else:
                        bot.send_photo(call.message.chat.id, photo, caption, reply_markup=inline_markup, parse_mode='HTML')
            else:
                bot.send_message(call.message.chat.id, caption, reply_markup=inline_markup, parse_mode='HTML')

    elif text in ["admin_Vodafone", "admin_Kievstar", "admin_Lifecell", "admin_FranceUnlimited", "admin_France35GB"]:
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("Изменить название тарифа", callback_data="name_tariff"))
        inline_markup.add(types.InlineKeyboardButton("Изменить описание тарифа", callback_data="about_tariff"))
        inline_markup.add(types.InlineKeyboardButton("Изменить изображение тарифа", callback_data="image_tariff"))
        inline_markup.add(types.InlineKeyboardButton("Изменить цену тарифа", callback_data="price_tariff"))
        inline_markup.add(types.InlineKeyboardButton("Изменить себестоимость (₴)", callback_data="cost_tariff"))
        inline_markup.add(types.InlineKeyboardButton("Пополнить кол-во eSIM", callback_data="auto_tariff"))
        bot.send_message(call.message.chat.id, f"Выберите что хотите изменить в тарифе {text.split('_')[1]}", reply_markup=inline_markup)

    elif text in ["name_tariff", "about_tariff", "price_tariff", "cost_tariff"]:
        eSIM_name = call.message.text.split()[-1]
        if text == "name_tariff":
            bot.send_message(call.message.chat.id, f"Введите название тарифа", reply_markup=start_markup(chat_id, text='🚫 Отмена'))
        if text == "about_tariff":
            bot.send_message(call.message.chat.id, f"Введите описание тарифа", reply_markup=start_markup(chat_id, text='🚫 Отмена'))
        if text == "price_tariff":
            bot.send_message(call.message.chat.id, f"Введите цену для тарифа", reply_markup=start_markup(chat_id, text='🚫 Отмена'))
        if text == "cost_tariff":
            bot.send_message(call.message.chat.id, f"Введите себестоимость в гривнах (₴) для тарифа", reply_markup=start_markup(chat_id, text='🚫 Отмена'))
        add_data("esim_edit_method", text, call.message.chat.id)
        add_data("tariff_name", eSIM_name, call.message.chat.id)
        update_state(call.message, ESIM_EDIT)

    elif text in ["image_tariff", "auto_tariff"]:
        eSIM_name = call.message.text.split()[-1]
        if text == "auto_tariff":
            bot.send_message(call.message.chat.id, f"Введите и отправьте изображение для автовыдачи\n\n⚠️ Отправляйте строго по одному фото", reply_markup=start_markup(chat_id, text='🚫 Отмена'))
        if text == "image_tariff":
            bot.send_message(call.message.chat.id, f"Отправьте изображение для тарифа", reply_markup=start_markup(chat_id, text='🚫 Отмена'))
        add_data("tariff_name", eSIM_name, call.message.chat.id)
        add_data("esim_edit_method", text, call.message.chat.id)
        update_state(call.message, ESIM_IMAGE_EDIT)

    elif text in ["plan_Solo", "plan_Duo", "plan_FamilyMax"]:

        plan_name = text.split("_")[1]  # Solo, Duo, FamilyMax

        markup = types.InlineKeyboardMarkup(row_width=1)

        if plan_name == "Solo":
            markup.add(types.InlineKeyboardButton("1 месяц — 360₽", callback_data="1sol"))
            markup.add(types.InlineKeyboardButton("3 месяца — 990₽", callback_data="3sol"))
            markup.add(types.InlineKeyboardButton("6 месяцев — 1700₽", callback_data="6sol"))
            markup.add(types.InlineKeyboardButton("12 месяцев — 2900₽", callback_data="12sol"))
            msg_text = (
                "1️⃣ Solo — для одного устройства\n"
                "💰 Идеально для телефона или ноутбука\n\n"        
                "👇Выберите период:"
            )

        elif plan_name == "Duo":
            markup.add(types.InlineKeyboardButton("1 месяц — 490₽", callback_data="1duo"))
            markup.add(types.InlineKeyboardButton("3 месяца — 1350₽", callback_data="3duo"))
            markup.add(types.InlineKeyboardButton("6 месяцев — 2300₽", callback_data="6duo"))
            markup.add(types.InlineKeyboardButton("12 месяцев — 3900₽", callback_data="12duo"))
            msg_text = (
                "2️⃣ Duo — для двух устройств\n"
                "👫 Подключитесь с другом или второй половинкой — двойная скорость и защита!\n\n"
                "👇Выберите период:"
            )
        elif plan_name == "FamilyMax":
            markup.add(types.InlineKeyboardButton("1 месяц — 690₽", callback_data="1fam"))
            markup.add(types.InlineKeyboardButton("3 месяца — 1890₽", callback_data="3fam"))
            markup.add(types.InlineKeyboardButton("6 месяцев — 3290₽", callback_data="6fam"))
            markup.add(types.InlineKeyboardButton("12 месяцев — 5490₽", callback_data="12fam"))
            msg_text = (
                "3️⃣ Family Max — для всей семьи\n"
                "🏠 Максимум устройств, максимальная свобода и суперскорость!\n"
                "🌟 Наш самый популярный и выгодный тариф — бери его, и интернет будет без границ!\n\n"
                "👇Выберите период:"
            )

        bot.send_message(call.message.chat.id, msg_text, reply_markup=markup)

        update_state(call.message, CHOOSE_PERIOD)
    elif text[-3:] in ["fam", "sol", "duo"]:
        chat_id = call.message.chat.id
        data = call.data.lower()
        print(data)
        # Разбираем данные
        months = int(''.join(filter(str.isdigit, data)))
        if 'sol' in data:
            plan = "Solo"
        elif 'duo' in data:
            plan = "Duo"
        elif 'fam' in data:
            plan = "Family Max"
        else:
            bot.answer_callback_query(call.id, "Ошибка выбора")
            return

        set_user_data(chat_id, "plan", plan)
        set_user_data(chat_id, "months", months)

        price_table = {
            "Solo": {1: 360, 3: 990, 6: 1700, 12: 2900},
            "Duo": {1: 490, 3: 1350, 6: 2300, 12: 3900},
            "Family Max": {1: 690, 3: 1890, 6: 3290, 12: 5490}
        }

        price = price_table[plan][months]
        set_user_data(chat_id, "price", price)

        msg1 = (
            f"""
💳 Отлично!
Вы выбрали тариф: {plan} на {months} мес.

⚡️ После оплаты вы получите уникальный ключ активации.
🛡 Бот подробно объяснит, как его правильно использовать на вашем устройстве — подключение займёт всего пару минут!
🚀 Быстрый, безопасный и без рекламы — интернет как со скоростью ветра! 🌪
"""
        )
        # Подтверждение оплаты
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Оплатить", callback_data="pay_vpn"),
                   types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_vpn"))
        bot.send_message(chat_id,
                         msg1,
                         reply_markup=markup)
        update_state(call.message, START)
    elif text == "i_ios":
        bot.send_message(call.message.chat.id, """
Чтобы активировать VPN на iOS (iPhone) перейдите в App Store и установите приложение v2RayTun (https://apps.apple.com/by/app/v2raytun/id6476628951) или же перейдите по ссылке.

1️⃣ Скопируйте ваш ключ активации

2️⃣ После установки зайдите в приложение и нажмите на ( + ) в крайнем правом углу и после нажмите (Импорт из буфера обмена) у вас может быть англ. версия.

3️⃣ Нажмите кнопку питания и поздравляю, у Вас подключен суперскоростной VPN✅       
        """, reply_markup=start_markup(call.message.chat.id))
    elif text == "i_android":
        bot.send_message(call.message.chat.id, """
Чтобы активировать VPN на Android перейдите в Google Play и установите приложение v2RayTun (https://play.google.com/store/apps/details?id=com.v2raytun.android&pcampaignid=web_share) или же перейдите по ссылке.

1️⃣ Скопируйте ваш ключ активации

2️⃣ После установки зайдите в приложение и нажмите на ( + ) в крайнем правом углу и после нажмите (Импорт из буфера обмена) у вас может быть англ. версия.

3️⃣ Нажмите кнопку питания и поздравляю, у Вас подключен суперскоростной VPN     
                """, reply_markup=start_markup(call.message.chat.id))

    elif text == "i_macos":
        bot.send_message(call.message.chat.id, """
Чтобы активировать VPN на MacOS перейдите в App Store и установите приложение v2RayTun (https://apps.apple.com/by/app/v2raytun/id6476628951?platform=mac) или же перейдите по ссылке.

1️⃣ Скопируйте ваш ключ активации

2️⃣ После установки зайдите в приложение и нажмите на ( + ) в крайнем правом углу и после нажмите (Импорт из буфера обмена) у вас может быть англ. версия.

3️⃣ Нажмите кнопку питания и поздравляю, у Вас подключен суперскоростной VPN✅   
                """, reply_markup=start_markup(call.message.chat.id))

    elif text == "i_windows":
        bot.send_message(call.message.chat.id, """
Чтобы активировать VPN на Windows установите приложение v2RayTun (https://disk.yandex.ru/d/uewq3vfMtE23pQ) перейдя по ссылке.

1️⃣ Скопируйте ваш ключ активации

2️⃣ После установки зайдите в приложение и нажмите на ( + ) в крайнем правом углу и после нажмите (Импорт из буфера обмена) у вас может быть англ. версия.

3️⃣ Нажмите кнопку питания и поздравляю, у Вас подключен суперскоростной VPN✅    
                """, reply_markup=start_markup(call.message.chat.id))
    elif text == "i_smarttv":
        bot.send_message(call.message.chat.id, """
Как установить TGPay VPN на ваш телевизор 📺
⏱️ Время: 5–20 минут
🧰 Понадобится: флешка и мышка (пультом неудобно)

Подходит для телевизоров на Android TV — Philips, Sony, Xiaomi, Panasonic и других.

🔹 Шаг 1. Подготовка

Скачайте приложение 👉 V2RayNG по ссылке (https://github.com/2dust/v2rayNG/releases/download/1.9.16/v2rayNG_1.9.16_universal.apk) 👈

Сохраните его на флешку.

Добавьте на флешку ваш ключ от TGPay VPN — просто скопируйте его в текстовый файл.

🔹 Шаг 2. Установка на телевизор

Вставьте флешку в телевизор.

Установите CX File Explorer через Google Play (на самом телевизоре).

Откройте CX File Explorer → найдите флешку → запустите и установите V2RayNG.

🔹 Шаг 3. Подключение к TGPay VPN

Откройте текстовый файл с вашим ключом на флешке и скопируйте его.

Запустите V2RayNG, нажмите «Вставить из буфера обмена», добавьте ключ и подключитесь.

✅ Готово! Ваш телевизор теперь под защитой TGPay VPN 🔐     
                """, reply_markup=start_markup(call.message.chat.id))

    elif text == "pay_vpn":
        chat_id = call.message.chat.id
        message_id = call.message.message_id
        plan = get_user_data(chat_id, "plan")
        months = get_user_data(chat_id, "months")
        price = get_user_data(chat_id, "price")
        bot.delete_message(chat_id, message_id)
        if float(get_balans(chat_id)) >= float(price):
            adm_msg = f"""  
Услуга: Покупка VPN
id: {chat_id}
🚗План: {plan}
⏳Срок: {months * 30} дн.
💸Сумма: {price}р.
🎩Ранг: {get_user_rank(chat_id)}
Пользователь: {chat_id}
        """
            bot.send_message(adminGroup, adm_msg, reply_markup=vpn_admin_markup(chat_id))
            add_data('sum', str(price), chat_id)
            update_balanse(chat_id, 'sum')
            update_total_spent(call.message.chat.id, float(price))

            #bot.send_message(chat_id,
            #                 f"✅ Оплата подтверждена!\nТариф {plan} на {months} мес.\nСумма: {price}₽\nГенерируем ключ...")

            #data, status = get_vpn_link(f"user_{chat_id}", device_limit=plans_devices[plan], days_valid=months * 30)

            #if status != 200 or "error" in data:
            #    err_text = data.get("error", "Неизвестная ошибка")
            #    bot.send_message(chat_id, f"❌ Ошибка генерации ключа: {err_text}")
            #
            #    bot.send_message(chat_id, "Сообщение об ошибке уже отправлено к администрации. Ожидайте их ответа.",
            #                     reply_markup=start_markup(chat_id))
            #    bot.send_message(
            #        adminGroup,
            #        f"‼️ У пользователя {chat_id} возникла ошибка генерации ключа: {err_text}\n\n"
            #        f"🟢 План: {plan}\n⏳ Срок: {months * 30} дней.",
            #        reply_markup=admin_markup()
            #    )
            #    update_state(call.message, START)
            #    return

            #links = data.get("links") or [data.get("link")]
            #links = [l for l in links if l]  # убираем Non
            #links_text = "\n\n".join([f"🔗 Ключ {i + 1}:\n`{link}`" for i, link in enumerate(links)])

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("iOS", callback_data="i_ios"))
            markup.add(types.InlineKeyboardButton("Android", callback_data="i_android"))
            markup.add(types.InlineKeyboardButton("Windows", callback_data="i_windows"))
            markup.add(types.InlineKeyboardButton("MacOS", callback_data="i_macos"))
            markup.add(types.InlineKeyboardButton("Smart TV", callback_data="i_smarttv"))

            #bot.send_message(
            #    chat_id,
            #    f"""
#🎉 Отлично! Оплата прошла успешно.
#🔑 Ваши ключи активации на {str(plans_devices[plan]) + " устройства:" if plan != "Solo" else "1 устройство: "}

#{links_text}

#⏳ Срок действия: {data.get("days_valid", months * 30)} дней.

#Выберите устройство, на котором будете подключать VPN:
 #       """,
  #              parse_mode="Markdown",
   #             reply_markup=markup
    #        )
    #        inline_markup2 = types.InlineKeyboardMarkup(row_width=True)


            #inline_markup2.add(types.InlineKeyboardButton(text="⬆️ Оставить отзыв", callback_data='send_feedback'))
            #bot.send_message(chat_id, """
#✅Спасибо, что воспользовались услугами TGPay!
#Напишите свой отзыв, нам будет безумно приятно😎

            #""", reply_markup=inline_markup2)
            send_to_archives(bot.send_message, adm_msg)

            update_state(call.message, START)

        else:
            bot.send_message(chat_id, "Недостаточно средств. Пополните баланс", reply_markup=start_markup(chat_id))
            update_state(call.message, START)

    elif text == "cancel_vpn":
        message_id = call.message.message_id
        bot.delete_message(call.message.chat.id, message_id)
        bot.send_message(chat_id,
                         "Без VPN ваш интернет скучает 😎\nВаш ключ уже готов — подключитесь и летайте по сети 🌪",
                         reply_markup=start_markup(chat_id))
        update_state(call.message, call.message.chat.id)
    elif text == "trial_vpn":
        chat_id = call.message.chat.id
        username = call.message.chat.username
        data = get_trial_vpn(chat_id, username)
        if "`" in data:
            bot.send_message(chat_id, f"""
🔑 Ключ выдан на 2 дня (пробный доступ)
📲 Подключить можно только 1 устройство.

{data}""", parse_mode="Markdown")
            update_state(call.message, START)
        elif data == "Nah":
            bot.send_message(chat_id, """
⚠️ Вы уже активировали пробный ключ ранее.
Для продолжения работы оформите подписку или приобретите новый тариф 💳""")
            update_state(call.message, START)
        else:
            bot.send_message(chat_id, "Ошибка")
            print(data)
            update_state(call.message, START)
    elif text == "esim_view_stock":
        with open("eSIM/esim_answer.json", encoding="utf-8") as file:
            esim_data = json.load(file)
        operators = ["Vodafone", "Kievstar", "Lifecell", "FranceUnlimited", "France35GB"]
        has_any = False
        for operator in operators:
            entries = esim_data.get(operator, {})
            if not entries:
                continue
            has_any = True
            bot.send_message(call.message.chat.id, f"📦 <b>{operator}</b> — {len(entries)} шт.", parse_mode="HTML")
            for idx, (key, entry) in enumerate(entries.items(), 1):
                caption = f"#{idx} | {operator} | {entry.get('message_answer', '—')}"
                file_id = entry.get("file_id")
                if file_id:
                    try:
                        bot.send_photo(call.message.chat.id, file_id, caption=caption)
                    except Exception as e:
                        bot.send_message(call.message.chat.id, f"#{idx} | {operator} | ⚠️ Не удалось загрузить фото: {e}")
                else:
                    img_path = f"eSIM/{entry.get('image_answer', '')}.jpg"
                    if os.path.exists(img_path):
                        with open(img_path, "rb") as photo:
                            bot.send_photo(call.message.chat.id, photo.read(), caption=caption)
                    else:
                        bot.send_message(call.message.chat.id, f"#{idx} | {operator} | ⚠️ Файл не найден (битая запись)")
        if not has_any:
            bot.send_message(call.message.chat.id, "📭 База eSIM пуста — нет ни одного товара в наличии.")

    elif text == "esim_delete":
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_markup.add(types.InlineKeyboardButton("♻️Vodafone", callback_data="Vodafone_delete"))
            inline_markup.add(types.InlineKeyboardButton("♻️Киевстар", callback_data="Kievstar_delete"))
            inline_markup.add(types.InlineKeyboardButton("♻️Lifecell", callback_data="Lifecell_delete"))
            inline_markup.add(types.InlineKeyboardButton("♻️Франция безлимит", callback_data="FranceUnlimited_delete"))
            inline_markup.add(types.InlineKeyboardButton("♻️Франция 35 ГБ", callback_data="France35GB_delete"))
            bot.send_message(call.message.chat.id, "Выберите у какого оператора хотите удалить товары", reply_markup=inline_markup)

    elif text in ["Vodafone_delete", "Kievstar_delete", "Lifecell_delete", "FranceUnlimited_delete", "France35GB_delete"]:
        operator = text.split("_")[0]
        with open("eSIM/esim_answer.json", encoding="utf-8") as file:
            data = json.load(file)
        if data.get(operator):
            for index, entry in data[operator].items():
                img_path = f"eSIM/{entry.get('image_answer', '')}.jpg"
                if os.path.exists(img_path):
                    os.remove(img_path)
            del data[operator]
            with open("eSIM/esim_answer.json", "w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
            bot.send_message(call.message.chat.id, f"✅ Все eSIM оператора {operator} удалены")
        else:
            bot.send_message(call.message.chat.id, "Нет товаров, которые можно удалить")

    elif text == "Payeer" or text == "BankRF" or text == "Yomoney" or text == "sbp":
        if text == "Payeer":
            json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
            json_data["Профиль"]["Способы оплаты"]["Payeer"] += 1
            with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
                json.dump(json_data, json_file, ensure_ascii=False, indent=4)
            add_data('sposob_oplati', text, call.message.chat.id)
            bot.send_message(call.message.chat.id, 'Введите сумму пополнения от 10₽ до 50 000₽', reply_markup=start_markup(call.message.chat.id, text = '🚫 Отмена'))
            update_state(call.message, DEPOSIT_SUMM)
        elif text == "BankRF":
            data = json.load(open("replishment_active.json", encoding="utf-8"))
            if data["time_active"]:
                check_time_active(data)
            data = json.load(open("replishment_active.json", encoding="utf-8"))
            if data["active"]:
                json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
                json_data["Профиль"]["Способы оплаты"]["BankRF"] += 1
                with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
                    json.dump(json_data, json_file, ensure_ascii=False, indent=4)
                add_data('sposob_oplati', text, call.message.chat.id)
                bot.send_message(call.message.chat.id, 'Введите сумму пополнения от 10₽ до 50 000₽', reply_markup=start_markup(call.message.chat.id, text = '🚫 Отмена'))
                update_state(call.message, DEPOSIT_SUMM)
            else:
                bot.send_message(call.message.chat.id, 'В ночное время пополнение баланса через карты недоступно')
        elif text == "Yomoney":
            json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
            json_data["Профиль"]["Способы оплаты"]["ЮMoney"] += 1
            with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
                json.dump(json_data, json_file, ensure_ascii=False, indent=4)
            bot.send_message(call.message.chat.id, "Введите сумму платежа от 10₽ до 50 000₽", reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
            update_state(call.message, YOOMANY)
            # add_data('sposob_oplati', text, call.message.chat.id)
            # bot.send_message(call.message.chat.id, 'Введите сумму пополнения от 1000₽ до 15 000₽', reply_markup=start_markup(call.message.chat.id, text = '🚫 Отмена'))
        elif text == "sbp":
            with open("analytic_clicks_data.json", encoding="utf-8") as f:
                json_data = json.load(f)

            if "Профиль" not in json_data:
                json_data["Профиль"] = {}
            if "Способы оплаты" not in json_data["Профиль"]:
                json_data["Профиль"]["Способы оплаты"] = {}
            if "СБП" not in json_data["Профиль"]["Способы оплаты"]:
                json_data["Профиль"]["Способы оплаты"]["СБП"] = 0

            json_data["Профиль"]["Способы оплаты"]["СБП"] += 1
            with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
                json.dump(json_data, json_file, ensure_ascii=False, indent=4)
            bot.send_message(call.message.chat.id, "Введите сумму платежа от 10₽ до 50 000₽", reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
            update_state(call.message, SBP)

    elif text == 'vaucher':
        json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
        json_data["Профиль"]["Способы оплаты"]["Ваучер"] += 1
        with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)
        bot.send_message(call.message.chat.id, 'Введите номер ваучера :', reply_markup=start_markup(call.message.chat.id, text = '🚫 Отмена'))
        update_state(call.message, VAUCHER)
    elif text == "deposit_compite" or text == "deposit_cancel":

        if text == "deposit_cancel":
            mes = '❌Вы отклонили оплату'
            payment_ids[call.message.chat.id] = None
            bot.send_message(call.message.chat.id, mes, reply_markup=start_markup(call.message.chat.id))
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            update_state(call.message, START)


        else:
            summ = get_par("deposit_sum", call.message.chat.id)
            sposob = get_par("sposob_oplati", call.message.chat.id)

            if summ == None:
                mes = '❌Произошла ошибка, попробуйте написать в поддержку'
                bot.send_message(call.message.chat.id, mes, reply_markup=start_markup(call.message.chat.id))
                update_state(call.message, START)
                return

            if sposob == 'Yomoney':
                sposob = 'ЮМoney'
                usluga = f'Пополнение баланса.\nСпособ оплаты: {sposob}'
                number = to_arhiv(call.message.chat.id, usluga, summ)
                mes = f'Заявка №{number}\n😉Ожидайте зачисления на баланс\n⌚️В крайних случаях деньги могут поступить в течении 24-х часов'
                bot.send_message(adminGroup, f'Заявка №{number}\nПользователь: @{call.message.chat.username} \nid: {call.message.chat.id}\nУслуга: {usluga}\n🎩Ранг: {get_user_rank(call.message.chat.id)}\nСумма: {summ}', reply_markup = admin_markup())
                bot.send_message(call.message.chat.id, mes, reply_markup=start_markup(call.message.chat.id))
                bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            elif sposob == "Payeer":
                bot.send_message(call.message.chat.id, "Отправьте изображение квитанции",
                                 reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
                update_state(call.message, SEND_RECEIPT)
            else:
                if text == "deposit_compite":
                    if sposob == 'BankRF':
                        bank = get_par("bank", call.message.chat.id)
                        bank_name = bank.split(' ')[1]
                        method = f'Банк РФ. {bank}'
                    bot.send_message(call.message.chat.id, "Отправьте изображение квитанции", reply_markup=start_markup(call.message.chat.id, text = '🚫 Отмена'))
                    update_state(call.message, SEND_RECEIPT)
                    # summ = get_par("deposit_sum", call.message.chat.id)
                    # sposob = get_par("sposob_oplati", call.message.chat.id)
                    # if sposob == 'Payeer':
                    #     sposob = 'Payeer Rub'
                    # elif sposob == 'BankRF':
                    #     bank = get_par("bank", call.message.chat.id)
                    #     if bank == 'https://yoomoney.ru/to/4100118310764395/0':
                    #         bank = 'ЮMoney'
                    #     elif bank == "https://yoomoney.ru/to/4100118484584640":
                    #         bank = 'ЮMoney 2'
                    #     elif '2202206928732903 Сбербанк' in bank:
                    #         bank = 'Сбербанк 2'
                    #     else:
                    #         bank = bank.split(' ')[1]
                    #     sposob = f'Банк РФ. {bank}'
                    # elif sposob == 'Yomoney':
                    #     sposob = 'ЮМoney'
                    # usluga = f'Пополнение баланса.\nСпособ оплаты: {sposob}'
                    # number = to_arhiv(call.message.chat.id, usluga, summ)
                    # mes = f'Заявка №{number}\n😉Ожидайте зачисления на баланс\n⌚️В крайних случаях деньги могут поступить в течении 24-х часов'
                    # bot.send_message(adminGroup, f'Заявка №{number}\nПользователь: @{call.message.chat.username} \nid: {call.message.chat.id}\nУслуга: {usluga}\nСумма: {summ}', reply_markup = admin_markup())

    elif text == "buyEsim":
        logging.info(f"[buyEsim] chat={chat_id}")
        operator = get_par("EsimOperator", chat_id)
        if operator in ("FranceUnlimited", "France35GB"):
            bot.answer_callback_query(call.id, "⏳ Временно нет в наличии", show_alert=True)
            return
        qty_markup = types.InlineKeyboardMarkup(row_width=3)
        qty_markup.add(
            types.InlineKeyboardButton("1", callback_data="esim_qty:1"),
            types.InlineKeyboardButton("5", callback_data="esim_qty:5"),
            types.InlineKeyboardButton("10", callback_data="esim_qty:10"),
        )
        qty_markup.add(types.InlineKeyboardButton("✏️ Своё количество", callback_data="esim_qty:custom"))
        bot.send_message(call.message.chat.id, "📦 Укажите количество <b>eSIM:</b>", reply_markup=qty_markup,  parse_mode="HTML")

    elif text.startswith("esim_qty:"):
        logging.info(f"[esim_qty] chat={chat_id} data={text}")
        qty_val = text.split(":")[1]
        if qty_val == "custom":
            update_state(call.message, ESIM_QTY)
            bot.send_message(call.message.chat.id, "Введите количество eSIM (число):", reply_markup=start_markup(chat_id, text='🚫 Отмена'))
        else:
            _show_esim_confirm(call.message, int(qty_val))

    elif text == "esim_confirm":
        qty_str = get_par("EsimQty", chat_id)
        try:
            qty = int(qty_str)
        except (TypeError, ValueError):
            qty = 1
        _do_esim_buy(call.message, qty)

    elif text == "esim_confirm_cancel":
        update_state(call.message, START)
        bot.send_message(call.message.chat.id, '❌ Покупка отменена.', reply_markup=start_markup(chat_id))
    elif get_state(call.message) == VALUTA:
        gift = get_par('gift', chat_id)
        val = text
        if text!= 'usd' and text!= 'eur' and text!= 'try':
            update_state(call.message, START)
            return
        add_data('valuta', val, call.message.chat.id)
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        kurs_usd = get_kurs('usd')
        kurs_eur = get_kurs('eur')
        kurs_try = get_kurs('try')
        if gift == 'steam':
            if val == 'usd':
                inline_markup.add(types.InlineKeyboardButton(f"5 $ - {5*kurs_usd} р.", callback_data="5"))
                inline_markup.add(types.InlineKeyboardButton(f"10 $ - {10*kurs_usd} р.", callback_data="10"))
                inline_markup.add(types.InlineKeyboardButton(f"20 $ - {20*kurs_usd} р.", callback_data="20"))
                inline_markup.add(types.InlineKeyboardButton(f"50 $ - {50*kurs_usd} р.", callback_data="50"))
                inline_markup.add(types.InlineKeyboardButton(f"100 $ - {100*kurs_usd} р.", callback_data="100"))
            if val == 'eur':
                inline_markup.add(types.InlineKeyboardButton(f"10 EUR - {10*kurs_eur} р.", callback_data="10"))
                inline_markup.add(types.InlineKeyboardButton(f"20 EUR - {20*kurs_eur} р.", callback_data="20"))
                inline_markup.add(types.InlineKeyboardButton(f"50 EUR - {50*kurs_eur} р.", callback_data="50"))
            if val == 'try':
                inline_markup.add(types.InlineKeyboardButton(f"20 TRY - {20*kurs_try} р.", callback_data="20"))
                inline_markup.add(types.InlineKeyboardButton(f"50 TRY - {50*kurs_try} р.", callback_data="50"))
                inline_markup.add(types.InlineKeyboardButton(f"100 TRY - {100*kurs_try} р.", callback_data="100"))
        elif gift == 'apple':
            if val == 'usd':
                inline_markup.add(types.InlineKeyboardButton(f"5 $ - {5*kurs_usd} р.", callback_data="5"))
                inline_markup.add(types.InlineKeyboardButton(f"10 $ - {10*kurs_usd} р.", callback_data="10"))
                inline_markup.add(types.InlineKeyboardButton(f"25 $ - {25*kurs_usd} р.", callback_data="25"))
                inline_markup.add(types.InlineKeyboardButton(f"50 $ - {50*kurs_usd} р.", callback_data="50"))
                inline_markup.add(types.InlineKeyboardButton(f"100 $ - {100*kurs_usd} р.", callback_data="100"))
                inline_markup.add(types.InlineKeyboardButton(f"500 $ - {500*kurs_usd} р.", callback_data="500"))
            if val == 'try':
                inline_markup.add(types.InlineKeyboardButton(f"25 TRY - {25*kurs_try} р.", callback_data="25"))
                inline_markup.add(types.InlineKeyboardButton(f"50 TRY - {50*kurs_try} р.", callback_data="50"))
        elif gift == 'google':
            if val == 'usd':
                inline_markup.add(types.InlineKeyboardButton(f"5 $ - {5*kurs_usd} р.", callback_data="5"))
                inline_markup.add(types.InlineKeyboardButton(f"10 $ - {10*kurs_usd} р.", callback_data="10"))
                inline_markup.add(types.InlineKeyboardButton(f"25 $ - {25*kurs_usd} р.", callback_data="25"))
                inline_markup.add(types.InlineKeyboardButton(f"50 $ - {50*kurs_usd} р.", callback_data="50"))
                inline_markup.add(types.InlineKeyboardButton(f"100 $ - {100*kurs_usd} р.", callback_data="100"))
            if val == 'try':
                inline_markup.add(types.InlineKeyboardButton(f"25 TRY - {25*kurs_try} р.", callback_data="25"))
                inline_markup.add(types.InlineKeyboardButton(f"50 TRY - {50*kurs_try} р.", callback_data="50"))
                inline_markup.add(types.InlineKeyboardButton(f"100 TRY - {100*kurs_try} р.", callback_data="100"))
                inline_markup.add(types.InlineKeyboardButton(f"1000 TRY - {1000*kurs_try} р.", callback_data="1000"))
        bot.send_message(chat_id, '💴Выберите сумму:', reply_markup=inline_markup)
        update_state(call.message, GET_VALUE)
    elif get_state(call.message) == GET_VALUE:
        if not text.isdigit():
            update_state(call.message, START)
            return
        add_data('value', text, call.message.chat.id)
        bot.send_message(chat_id, '✍️Введите ваш Email, на который мы отправим вам данный товар :', reply_markup=start_markup(chat_id, text='🚫 Отмена'))
        update_state(call.message, EMAIL)
    elif text == 'vusd' or text == 'veur' or text == 'vtry' or text == 'vuah':
        if text == 'vusd':
            bot.send_message(call.message.chat.id, 'Сколько рублей в одном 🇺🇸USD', reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
            add_data('val', 'usd', 'valuta')
            update_state(call.message, KURS)
        elif text == 'veur':
            bot.send_message(call.message.chat.id, 'Сколько рублей в одном 🇪🇺EUR', reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
            add_data('val', 'eur', 'valuta')
            update_state(call.message, KURS)
        elif text == 'vtry':
            bot.send_message(call.message.chat.id, 'Сколько рублей в одном 🇹🇷TRY', reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
            add_data('val', 'try', 'valuta')
            update_state(call.message, KURS)
        elif text == 'vuah':
            bot.send_message(call.message.chat.id, 'Сколько рублей в одном 🇺🇦UAH', reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
            add_data('val', 'uah', 'valuta')
            update_state(call.message, KURS)
    elif text == 'vusd_calc' or text == 'veur_calc' or text == 'vtry_calc' or text == 'vuah_calc':
        if text == 'vusd_calc':
            bot.send_message(call.message.chat.id, 'Введите сумму в 🇺🇸USD', reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
            add_data('val', 'usd', f'{call.message.chat.id}_calc')
            update_state(call.message, CALC)
        elif text == 'veur_calc':
            bot.send_message(call.message.chat.id, 'Введите сумму в 🇪🇺EUR', reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
            add_data('val', 'eur', f'{call.message.chat.id}_calc')
            update_state(call.message, CALC)
        elif text == 'vtry_calc':
            bot.send_message(call.message.chat.id, 'Введите сумму в 🇹🇷TRY', reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
            add_data('val', 'try', f'{call.message.chat.id}_calc')
            update_state(call.message, CALC)
        elif text == 'vuah_calc':
            bot.send_message(call.message.chat.id, 'Введите сумму в 🇺🇦UAH', reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
            add_data('val', 'uah', f'{call.message.chat.id}_calc')
            update_state(call.message, CALC)
    elif text == 'back':
        bot.send_message(call.message.chat.id, esim, parse_mode='HTML')
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("🔴 Vodafone", callback_data="Vodafone", icon_custom_emoji_id="5267292959182697142"))
        inline_markup.add(types.InlineKeyboardButton("🔵 Киевстар", callback_data="Kievstar", icon_custom_emoji_id="5267061554934723857"))
        inline_markup.add(types.InlineKeyboardButton("🟡 Lifecell", callback_data="Lifecell", icon_custom_emoji_id="5267284102960131913"))
        inline_markup.add(types.InlineKeyboardButton("🇫🇷 Франция", callback_data="France"))
        bot.send_message(call.message.chat.id, 'Выберите eSIM:', reply_markup=inline_markup)
    elif text == 'RostNet':
        bot.send_message(chat_id, '📝Введите ваш ID или Логин', reply_markup=start_markup(chat_id, text='🚫 Отмена'))
        update_state(call.message, GET_LOGIN_INET)
    elif text == 'send_feedback':
        bot.send_message(chat_id, 'Пришлите свой отзыв', reply_markup=start_markup(chat_id, text='🚫 Отмена'))
        update_state(call.message, GET_FEEDBACK)
    elif text == 'get_feedback':
        if chat_id in admins:
            feeds = get_feedback(flag=1)
        else:
            feeds = get_feedback()
        markup = feed(1, len(feeds))
        bot.send_message(chat_id, feeds[0], reply_markup=markup, parse_mode='HTML')

    if 'feed_' in text:
        if chat_id in admins:
            feeds = get_feedback(flag=1)
        else:
            feeds = get_feedback()
        id = text.split('_')[-1]
        if 'dec' in text:
            if int(id) == 1:
                bot.answer_callback_query(callback_query_id=call.id, text='Вы на первой странице')
            else:
                markup = feed(int(id)-1, len(feeds))
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text = feeds[int(id)-2], reply_markup=markup, parse_mode='HTML')
        if 'inc' in text:
            if int(id) == len(feeds):
                bot.answer_callback_query(callback_query_id=call.id, text='Вы на последней странице')
            else:
                markup = feed(int(id)+1, len(feeds))
                bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text = feeds[int(id)], reply_markup=markup, parse_mode='HTML')
    elif text == 'add_balanse':
        inline_markup_json = {
            "inline_keyboard": [
                [{"text": "СБП • 1 мин", "callback_data": "sbp", "style": "success", "icon_custom_emoji_id": "5425008221330880308"}],
                [{"text": "Карты РФ", "callback_data": "BankRF"}],
                # [{"text": "🅿️Payeer Rub", "callback_data": "Payeer"}],
                [{"text": "Криптовалюта", "callback_data": "cryptomus_buy", "icon_custom_emoji_id": "5195308461193182892"}],
                [{"text": "💎Активировать ваучер", "callback_data": "vaucher"}],
            ]
        }

        promocode = get_promocode(call.message.chat.id)
        if promocode == None:
            bot.send_message(call.message.chat.id, '💳 Выберите способ оплаты:', reply_markup=json.dumps(inline_markup_json))
        else:
            with open("promocode.json", encoding="utf-8") as file:
                data = json.load(file)
            procent = data[promocode]["procent"]
            bot.send_message(call.message.chat.id, f'💳 Выберите способ оплаты:\nДействует скидка {procent}%', reply_markup=json.dumps(inline_markup_json))
    elif text == "withdraw_bal":
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("💸СБП", callback_data="withdraw_sbp"))
        inline_markup.add(types.InlineKeyboardButton("🇷🇺Карта РФ", callback_data="withdraw_card"))
        bot.send_message(call.message.chat.id, "📲Выберите способ выплаты:", reply_markup=inline_markup)
    elif text == "confirm_card_withdraw":
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        uid = call.from_user.id
        temp = get_user_temp(uid)
        usluga = f'Вывод средств.\nСпособ оплаты: Карта РФ'

        card = temp.get("card")
        amount = temp.get("amount")
        commission = temp.get("commission")
        to_receive = temp.get("to_receive")

        if amount is None:
            bot.answer_callback_query(call.id, "Ошибка: нет данных.")
            return

        result = withdraw_balance(uid, amount)

        if result == "success":
            number = to_arhiv(call.message.chat.id, usluga, amount)
            bot.send_message(
                call.message.chat.id,
                f"✅ Заявка №{number} создана!\n"
                f"💳 Карта: {card}\n"
                f"🏦Банк: {get_bank_from_card(card)}\n"
                f"💰 Списано: {amount} ₽\n"
                f"💸 Комиссия: {commission} ₽\n"
                f"📥 К получению: {to_receive} ₽"
            )
            bot.send_message(adminGroup,
                             f'Заявка №{number}\nПользователь: @{call.message.chat.username} \nid: {call.message.chat.id}\nУслуга: Вывод средств Карта РФ\n🎩Ранг: {get_user_rank(call.message.chat.id)}\nНомер карты: {card}\n Банк: {get_bank_from_card(card)}\nСумма: {to_receive}\nБез комиссии: {amount}\nКомиссия: {commission}',
                             reply_markup=admin_withdraw_c())
        else:
            bot.send_message(
                call.message.chat.id,
                f"❌ Недостаточно средств.\nНужно {amount} ₽, а у вас: {result}"
            )

        update_state(call.message, START)
    elif text == "confirm_withdraw_sbp":
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        uid = call.from_user.id

        temp = get_user_temp(uid)
        amount = temp.get("amount")
        commission = temp.get("commission")
        to_receive = temp.get("to_receive")
        bank = temp.get("bank")
        phone = temp.get("phone")
        if amount is None:
            bot.answer_callback_query(call.id, "Ошибка: нет данных.")
            return
        result = withdraw_balance(uid, amount)
        if result == "success":
            usluga = f'Вывод средств.\nСпособ оплаты: СБП({bank})'
            number = to_arhiv(call.message.chat.id, usluga, amount)
            bot.send_message(
                call.message.chat.id,
                f"✅ Заявка №{number} создана!\n\n"
                f"🏦 Банк: {bank}\n"
                f"📱 Телефон: {phone}\n"
                f"💰 Списано: {amount} ₽\n"
                f"💸 Комиссия: {commission} ₽\n"
                f"📥 К получению: {to_receive} ₽"
            )
            bot.send_message(adminGroup,
                             f'Заявка №{number}\nПользователь: @{call.message.chat.username} \nid: {call.message.chat.id}\nУслуга: Вывод средств СБП({bank})\n🎩Ранг: {get_user_rank(call.message.chat.id)}\nНомер: {phone}\n Банк: {bank}\nСумма с комсой: {to_receive} \n Сумма без комсы: {amount} \n Комиссия: {commission}',
                             reply_markup=admin_withdraw())
        else:
            bot.send_message(
                call.message.chat.id,
                f"❌ Недостаточно средств.\nНужно {amount} ₽, а у вас: {result}"
            )

        update_state(call.message, START)
    elif text.startswith("esim_manual_accept:"):
        # Админ принял заявку — просим прислать фото eSIM
        _, number_c, user_id_c, operator_c = text.split(":")
        add_data("esim_manual_number", number_c, call.message.chat.id)
        add_data("esim_manual_user_id", user_id_c, call.message.chat.id)
        add_data("esim_manual_operator", operator_c, call.message.chat.id)
        bot.edit_message_reply_markup(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=None
        )
        prompt_msg = bot.send_message(
            call.message.chat.id,
            f'📸 Отправьте фото eSIM для заявки №{number_c}\n'
            f'Можно добавить подпись к фото — она придёт клиенту как текст.\n'
            f'Ответьте на это сообщение или просто отправьте фото.',
            reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена')
        )
        _esim_awaiting_photo[prompt_msg.message_id] = {
            'number': number_c,
            'user_id': user_id_c,
        }
        update_state(call.message, ESIM_MANUAL_SEND)

    elif text.startswith("esim_cancel_ask:"):
        # Показываем подтверждение отмены eSIM заявки
        _, number_c, user_id_c, summa_c = text.split(":")
        confirm_markup = types.InlineKeyboardMarkup(row_width=True)
        confirm_markup.add(
            types.InlineKeyboardButton("❌ Отменить и вернуть деньги", callback_data=f"esim_cancel_confirm:{number_c}:{user_id_c}:{summa_c}"),
            types.InlineKeyboardButton("✅ Принять заявку", callback_data="esim_cancel_back")
        )
        bot.send_message(
            call.message.chat.id,
            f'⚠️ Вы уверены что хотите отменить заявку №{number_c}?\n\n'
            f'Пользователю будет возвращено {summa_c} ₽',
            reply_markup=confirm_markup
        )

    elif text.startswith("esim_cancel_confirm:"):
        # Подтверждена отмена — возвращаем деньги и убираем из очереди
        _, number_c, user_id_c, summa_c = text.split(":")
        user_id_c = int(user_id_c)
        try:
            # Возвращаем деньги
            add_deposit(user_id_c, summa_c, description='Возврат средств')
            # Убираем из очереди pending
            try:
                with open("eSIM/esim_pending.json", encoding="utf-8") as pf:
                    pending_data = json.load(pf)
                for op in list(pending_data.keys()):
                    pending_data[op] = [u for u in pending_data[op] if str(u.get("number")) != number_c]
                    if not pending_data[op]:
                        del pending_data[op]
                with open("eSIM/esim_pending.json", "w", encoding="utf-8") as pf:
                    json.dump(pending_data, pf, ensure_ascii=False, indent=4)
            except Exception:
                pass
            # Уведомляем клиента
            bot.send_message(
                user_id_c,
                f'❌ Заявка №{number_c} отменена.\n'
                f'💰 Вам возвращено {summa_c} ₽ на баланс.'
            )
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f'✅ Заявка №{number_c} отменена. Деньги возвращены пользователю ({summa_c} ₽).\nОтменил: @{call.from_user.username}'
            )
        except Exception as e:
            bot.send_message(call.message.chat.id, f'❌ Ошибка при отмене: {e}')

    elif text == "esim_cancel_back":
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)

    elif text == "cancel_withdraw":
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        uid = call.from_user.id
        clear_user_temp(uid)
        update_state(call.message, START)
        bot.send_message(call.message.chat.id, "❌ Вывод отменён.")
    elif text == 'add_balanse2':
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        # inline_markup.add(types.InlineKeyboardButton("🇷🇺Карты РФ", callback_data="Nicepay"))
        inline_markup.add(types.InlineKeyboardButton("🇷🇺Карты РФ", callback_data="BankRF2"))
        inline_markup.add(types.InlineKeyboardButton("🅿️Payeer Rub", callback_data="Payeer2"))
        inline_markup.add(types.InlineKeyboardButton("🪙Криптовалюта", callback_data="cryptomus_buy"))
        # inline_markup.add(types.InlineKeyboardButton("🇷🇺ЮМoney", callback_data="Yomoney"))
        # inline_markup.add(types.InlineKeyboardButton("🎲Nicepay", callback_data="Nicepay"))
        inline_markup.add(types.InlineKeyboardButton("💎Активировать ваучер", callback_data="vaucher"))


        # inline_markup.add(types.InlineKeyboardButton("Payok", callback_data="payok_buy"))
        promocode = get_promocode(call.message.chat.id)
        if promocode == None:
            bot.send_message(call.message.chat.id, '💳 Выберите способ оплаты:', reply_markup=inline_markup)
        else:
            with open("promocode.json", encoding="utf-8") as file:
                data = json.load(file)
            procent = data[promocode]["procent"]
            bot.send_message(call.message.chat.id, f'💳 Выберите способ оплаты:\nДействует скидка {procent}%', reply_markup=inline_markup)
    elif text == 'goodWH':
        number = call.message.text.split('Заявка №')[1].split('\n')[0]
        id = int(call.message.text.split('id: ')[1].split('\n')[0])
        sum = float(call.message.text.split('Сумма с комсой: ')[1].split('\n')[0].strip())
        user = call.message.text.split('Пользователь: ')[1].split('\n')[0]
        comm = float(call.message.text.split('Комиссия: ')[1].split('\n')[0].strip())
        date = datetime.now().date().strftime('%d.%m.%Y')


        bot.answer_callback_query(callback_query_id=call.id, text=f"Заявка №{number} одобрена")
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton(text="⬆️ Оставить отзыв", callback_data='send_feedback'))
        bot.send_message(id,
                f'📱Ваша заявка №<code>{number}</code>\n✅Успешно обработана!\n✅',
                reply_markup=inline_markup, parse_mode="HTML")
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        send_to_archives(bot.send_message, f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: Вывод средств СБП \nСумма: {sum - comm}\nСумма без комисии: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}')
        clear_user_temp(id)
    elif text == 'nogoodWH':
        print(call.message)
        number = call.message.text.split('Заявка №')[1].split('\n')[0]
        id = int(call.message.text.split('id: ')[1].split('\n')[0])
        user = call.message.text.split('Пользователь: ')[1].split('\n')[0]
        temp = get_user_temp(id)
        amount = temp.get("amount")
        bot.answer_callback_query(callback_query_id=call.id, text=f"Заявка №{number} отклонена")
        bot.send_message(id, f"❌Заявка №{number} отклонена❌")
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        date = datetime.now().date().strftime('%d.%m.%Y')
        add_deposit(int(id), str(amount), description='Отмена вывода СБП (возврат)')

        send_to_archives(bot.send_message, f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: Вывод средств СБП \nСумма: {amount}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ❌Отменено')

        clear_user_temp(id)
    elif text == "accepted_key":
        bot.send_message(
            call.message.chat.id,
            "🔑 Введите ключ:",
            reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена')
        )
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        update_state(call.message, ACCEPTED_KEY)
    elif text == 'nogoodKomWH':
        print(call.message.text)
        id = int(call.message.text.split('id: ')[1].split('\n')[0])
        temp = get_user_temp(id)
        amount = temp.get("amount")
        add_deposit(id, str(amount), description='Отмена вывода СБП (возврат)')
        clear_user_temp(id)
        mesid = bot.send_message(call.message.chat.id, "Введите комментарий:")
        print("nogoodKom")
        bot.register_next_step_handler(call.message, process_nogoodKom_comment, mess=call.message, messid=mesid, cal=call)
    elif text == 'goodWHC':
        number = call.message.text.split('Заявка №')[1].split('\n')[0]
        id = int(call.message.text.split('id: ')[1].split('\n')[0])
        sum = float(call.message.text.split('Сумма: ')[1].split('\n')[0])
        user = call.message.text.split('Пользователь: ')[1].split('\n')[0]
        comm = sum * 0.2
        date = datetime.now().date().strftime('%d.%m.%Y')

        bot.answer_callback_query(callback_query_id=call.id, text=f"Заявка №{number} одобрена")
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton(text="⬆️ Оставить отзыв", callback_data='send_feedback'))
        bot.send_message(id,
                         f'📱Ваша заявка №<code>{number}</code>\n✅Успешно обработана!\n✅',
                         reply_markup=inline_markup, parse_mode="HTML")
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        send_to_archives(bot.send_message,
                         f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: Вывод средств Карта РФ \nСумма: {sum - comm}\nСумма без комисии: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}')
        clear_user_temp(id)
    elif text == 'nogoodWHC':
        number = call.message.text.split('Заявка №')[1].split('\n')[0]
        id = int(call.message.text.split('id: ')[1].split('\n')[0])
        user = call.message.text.split('Пользователь: ')[1].split('\n')[0]
        temp = get_user_temp(id)
        amount = temp.get("amount")
        bot.answer_callback_query(callback_query_id=call.id, text=f"Заявка №{number} отклонена")
        bot.send_message(id, f"❌Заявка №{number} отклонена❌")
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        date = datetime.now().date().strftime('%d.%m.%Y')
        add_deposit(int(id), str(amount), description='Отмена вывода карта РФ (возврат)')
        print(id, amount)

        send_to_archives(bot.send_message,
                         f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: Вывод средств Карта РФ \nСумма: {amount}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ❌Отменено')

        clear_user_temp(id)

    elif text == 'nogoodKomWHC':
        print(call.message.text)
        id = int(call.message.text.split('id: ')[1].split('\n')[0])
        temp = get_user_temp(id)
        amount = temp.get("amount")
        add_deposit(id, str(amount), description='Отмена вывода карта РФ (возврат)')
        clear_user_temp(id)
        mesid = bot.send_message(call.message.chat.id, "Введите комментарий:")
        print("nogoodKom")
        bot.register_next_step_handler(call.message, process_nogoodKom_comment, mess=call.message, messid=mesid, cal=call)
    elif text == 'good' or text == 'nogoodKom' or text == 'nogood':
        content = call.message.caption or call.message.text or ''
        marker = 'Услуга:'

        start = content.find(marker)
        if start != -1:
            start += len(marker)
            rest = content[start:].strip()
            usluga = rest.split('\n', 1)[0] if rest else 'Покупка'
        else:
            usluga = 'Покупка'

        if call.message.caption == None:
            message_text_check = call.message.text
        else:
            message_text_check = call.message.caption

        logging.info(f"{message_text_check}")
        print(usluga)
        if "Пополнение баланса" in usluga and "ЮМoney" not in message_text_check:
            number = message_text_check.split('Заявка №')[1].split('\n')[0]
            id = int(message_text_check.split('id: ')[1].split('\n')[0])
            sum = message_text_check.split('Сумма: ')[1].split('\n')[0]
            user = message_text_check.split('Пользователь: ')[1].split('\n')[0]
            try:
                sum_int = int(float(sum.split('$')[0].split('₽')[0].strip()))
            except:
                sum_int = 0
            update_money_report_for_day(money = sum_int)
            update_money_report_for_month(money = sum_int)

            if os.path.exists(f"receipt_{id}.jpg") or os.path.exists(f"receipt_{id}.pdf"):
                try:
                    with open(f"receipt_{id}.jpg", 'rb') as new_file:
                        pass
                    data_format = "jpg"
                except:
                    with open(f"receipt_{id}.pdf", 'rb') as new_file:
                        pass
                    data_format = "pdf"
            else:
                if call.message.photo:
                    photo = call.message.photo[-1]
                    file_info = bot.get_file(photo.file_id)
                    downloaded_file = bot.download_file(file_info.file_path)
                    with open(f"receipt_{id}.jpg", 'wb') as new_file:
                        new_file.write(downloaded_file)
                    data_format = "jpg"
                elif call.message.document:
                    file_info = bot.get_file(call.message.document.file_id)
                    downloaded_file = bot.download_file(file_info.file_path)
                    with open(f"receipt_{id}.pdf", 'wb') as new_file:
                        new_file.write(downloaded_file)
                    data_format = "pdf"
                else:
                    data_format = None
            if text == 'good':
                if "Сумма с промокодом" in message_text_check:
                    sum_with_promocode = message_text_check.split('Сумма с промокодом: ')[1].split('\n')[0]
                    promocode = get_promocode(id)
                    with open("promocode.json", encoding="utf-8") as file:
                        data = json.load(file)
                    data[promocode]["wasted_user"].append(id)
                    with open("promocode.json", "w", encoding="utf-8") as file:
                        json.dump(data, file, ensure_ascii=False, indent=4)
                    delete_promocode(id)
                    bot.answer_callback_query(callback_query_id=call.id, text=f"Заявка №{number} одобрена")
                    inline_markup = types.InlineKeyboardMarkup(row_width=True)

                    inline_markup.add(types.InlineKeyboardButton(text = "⬆️ Оставить отзыв", callback_data = 'send_feedback'))
                    add_deposit(id, sum_with_promocode, description='Пополнение баланса')
                    opl = message_text_check.split("Способ оплаты: ")[1].split("\n")[0]
                    usluga+=f'\nСпособ оплаты: {opl}'
                    bot.send_message(id, f'📱Ваша заявка №<code>{number}</code>\n✅Успешно обработана!\n✅Вам на баланс начислено {sum_with_promocode}₽', reply_markup = inline_markup, parse_mode="HTML")
                    bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
                    date = datetime.now().date().strftime('%d.%m.%Y')
                    if data_format == "jpg":
                        try:
                            sum_bez_com = message_text_check.split('Сумма без комисии: ')[1].split('\n')[0]
                            with open(f"receipt_{id}.jpg", 'rb') as new_file:
                                send_photo_to_archives(new_file.read(), caption=f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\nСумма без комисии: {sum_bez_com}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}')
                            os.remove(f"receipt_{id}.jpg")
                        except:
                            with open(f"receipt_{id}.jpg", 'rb') as new_file:
                                send_photo_to_archives(new_file.read(), caption=f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}')
                            os.remove(f"receipt_{id}.jpg")
                    elif data_format == "pdf":
                        try:
                            sum_bez_com = message_text_check.split('Сумма без комисии: ')[1].split('\n')[0]
                            with open(f"receipt_{id}.pdf", 'rb') as new_file:
                                send_document_to_archives(new_file.read(), caption=f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\nСумма без комисии: {sum_bez_com}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}')
                            os.remove(f"receipt_{id}.pdf")
                        except:
                            with open(f"receipt_{id}.pdf", 'rb') as new_file:
                                send_document_to_archives(new_file.read(), caption=f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}')
                            os.remove(f"receipt_{id}.pdf")
                    else:
                        send_message_to_archives(f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\nЗаявку закрыл(а): {call.from_user.username}')
                else:
                    bot.answer_callback_query(callback_query_id=call.id, text=f"Заявка №{number} одобрена")
                    inline_markup = types.InlineKeyboardMarkup(row_width=True)
                    inline_markup.add(types.InlineKeyboardButton(text = "⬆️ Оставить отзыв", callback_data = 'send_feedback'))
                    add_deposit(id, sum, description='Пополнение баланса')
                    opl = message_text_check.split("Способ оплаты: ")[1].split("\n")[0]
                    usluga+=f'\nСпособ оплаты: {opl}'
                    bot.send_message(id, f'📱Ваша заявка №<code>{number}</code>\n✅Успешно обработана!\n✅Вам на баланс начислено {sum}₽', reply_markup = inline_markup, parse_mode="HTML")
                    bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
                    date = datetime.now().date().strftime('%d.%m.%Y')
                    if data_format == "jpg":
                        try:
                            sum_bez_com = message_text_check.split('Сумма без комисии: ')[1].split('\n')[0]
                            with open(f"receipt_{id}.jpg", 'rb') as new_file:
                                send_photo_to_archives(new_file.read(), caption=f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\nСумма без комисии: {sum_bez_com}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}')
                            os.remove(f"receipt_{id}.jpg")
                        except:
                            with open(f"receipt_{id}.jpg", 'rb') as new_file:
                                send_photo_to_archives(new_file.read(), caption=f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}')
                            os.remove(f"receipt_{id}.jpg")
                    elif data_format == "pdf":
                        try:
                            sum_bez_com = message_text_check.split('Сумма без комисии: ')[1].split('\n')[0]
                            with open(f"receipt_{id}.pdf", 'rb') as new_file:
                                send_document_to_archives(new_file.read(), caption=f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\nСумма без комисии: {sum_bez_com}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}')
                            os.remove(f"receipt_{id}.pdf")
                        except:
                            with open(f"receipt_{id}.pdf", 'rb') as new_file:
                                send_document_to_archives(new_file.read(), caption=f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}')
                            os.remove(f"receipt_{id}.pdf")
                    else:
                        send_message_to_archives(f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\nЗаявку закрыл(а): {call.from_user.username}')

            elif text == 'nogoodKom':
                if not "Пополнение баланса" in usluga:
                    add_deposit(id, sum, description='Возврат средств')
                mesid = bot.send_message(call.message.chat.id, "Введите комментарий:")
                print("nogoodKom")
                bot.register_next_step_handler(call.message, process_nogoodKom_comment, mess=call.message, messid=mesid, cal=call)
            elif text == 'nogood':
                if not "Пополнение баланса" in usluga:
                    add_deposit(id, sum, description='Возврат средств')
                bot.answer_callback_query(callback_query_id=call.id, text=f"Заявка №{number} отклонена")
                c = cancel_request(message_text_check)
                
                bot.send_message(id, f"❌Заявка №{number} отклонена❌")
                bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
                date = datetime.now().date().strftime('%d.%m.%Y')
                if data_format == "jpg":
                    with open(f"receipt_{id}.jpg", 'rb') as new_file:
                        send_photo_to_archives(new_file.read(), caption=f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ❌Отменено')
                    os.remove(f"receipt_{id}.jpg")
                elif data_format == "pdf":
                    with open(f"receipt_{id}.pdf", 'rb') as new_file:
                        send_document_to_archives(new_file.read(), caption=f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ❌Отменено')
                    os.remove(f"receipt_{id}.pdf")
                else:
                    send_message_to_archives(f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ❌Отменено')
                
        else:
            if "VPN" not in call.message.text:
                number = call.message.text.split('Заявка №')[1].split('\n')[0]
            else:
                number = '1'
            print(call.message.text)
            id = int(call.message.text.split('id: ')[1].split('\n')[0])
            usluga = call.message.text.split('Услуга: ')[1].split('\n')[0]
            sum = call.message.text.split('Сумма: ')[1].split('\n')[0]
            user = call.message.text.split('Пользователь: ')[1].split('\n')[0]





            # update_money_report_for_day(money = int(sum))
            # update_money_report_for_month(money = int(sum))
            if text == 'good':
                close_request(int(number))
                bot.answer_callback_query(callback_query_id=call.id, text=f"Заявка №{number} одобрена")
                # Списание себестоимости с баланса модератора
                _mod_balans_str = ''
                try:
                    _msg = call.message.text or ''
                    _cost_rub = None
                    if '📊 Себестоимость в ₽:' in _msg:
                        _cost_rub = float(_msg.split('📊 Себестоимость в ₽:')[1].split('₽')[0].strip())
                    elif '💰Себестоимость:' in _msg:
                        _cost_rub = float(_msg.split('💰Себестоимость:')[1].split('₽')[0].strip().split()[0])
                    if _cost_rub is not None:
                        _cost_uah = None
                        if '💸 Себестоимость:' in _msg:
                            try:
                                _cost_uah = float(_msg.split('💸 Себестоимость:')[1].split('₴')[0].strip())
                            except:
                                pass
                        elif '💰Себестоимость:' in _msg:
                            try:
                                _cost_uah = float(_msg.split('💰Себестоимость:')[1].split('₴')[0].strip().split()[0])
                            except:
                                pass
                        
                        if _cost_uah is not None:
                            add_mod_deposit(call.from_user.id, -_cost_uah, 'uah')
                            _mod_balans = get_moderator_balans(call.from_user.id, 'uah') or 0
                            _mod_balans_str = f'\n💸 Списано с баланса модератора: {_cost_uah:.2f}₴ (остаток: {_mod_balans:.2f}₴)'
                except Exception:
                    pass
                # Авто-списание с кассы модератора (UAH) — только если в заявке есть сумма в грн.
                try:
                    _msg_text = call.message.text or call.message.caption or ''
                    if 'Сумма в грн.:' in _msg_text:
                        _grn_str = _msg_text.split('Сумма в грн.:')[1].split('\n')[0].strip()
                        _grn_amount = float(_grn_str.replace(',', '.').replace('₴', '').strip())
                        if _grn_amount > 0:
                            add_cash_transaction(
                                call.from_user.id, 'expense', _grn_amount,
                                f'Заявка №{number}: {usluga}', 'UAH'
                            )
                            _cash = get_cash_stats(call.from_user.id)
                            _remain = int(_cash['UAH']['balance'])
                            _mod_balans_str += f'\n💼 На руках у модератора: {_remain}₴'
                except Exception:
                    pass
                inline_markup = types.InlineKeyboardMarkup(row_width=True)
                inline_markup.add(types.InlineKeyboardButton(text = "⬆️ Оставить отзыв", callback_data = 'send_feedback'))
                if "Пополнение баланса" in usluga:
                    add_deposit(id, sum, description='Пополнение баланса')
                    opl = call.message.text.split("Способ оплаты: ")[1].split("\n")[0]
                    usluga+=f'\nСпособ оплаты: {opl}'
                    try:
                        bot.send_message(id, f'📱Ваша заявка №<code>{number}</code>\n✅Успешно обработана!\n✅Вам на баланс начислено {sum}₽', reply_markup = inline_markup, parse_mode="HTML")
                    except Exception:
                        pass
                else:
                    try:
                        bot.send_message(id, f'📱Ваша заявка №<code>{number}</code>\n✅Успешно обработана!', reply_markup = inline_markup, parse_mode="HTML")
                    except Exception:
                        pass
                bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
                date = datetime.now().date().strftime('%d.%m.%Y')
                if "Украина" in usluga:
                    referer = get_ref_user(id)
                    ua_ref_earned = 0
                    if referer:
                        user_type_before = get_user_type(id)
                        ua_ref_earned = add_balance_ref_with_type(id, float(sum), 'ua', user_type_before)
                        bot.send_message(referer, f'<b>🎉 Вы получили <code>{ua_ref_earned}</code> руб за реферала!</b>\n id:<code>{id}</code>\n Товар: Мобильный Украина', parse_mode="HTML")
                    try:
                        sum_grn = call.message.text.split('Сумма в грн.: ')[1].split('\n')[0]
                    except Exception:
                        sum_grn = '—'
                    try:
                        uah_rate = _uah_cost_rate_cache or get_uah_cost_rate()
                        sebest_rub = round(float(sum_grn) * float(uah_rate), 2)
                        profit_val = round(float(sum) - sebest_rub, 2)
                        sebest = f'{sum_grn} ₴ = {sebest_rub} ₽ (курс {uah_rate})'
                        profit = f'{profit_val} ₽'
                    except Exception:
                        sebest = '—'
                        profit = '—'
                    ref_note = f'\n👥 Реферал: -{ua_ref_earned} ₽' if ua_ref_earned else ''
                    send_to_archives(bot.send_message, f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма в грн.: {sum_grn}\nСумма в руб.: {sum}\n💰Себестоимость: {sebest}\n📈Чистая прибыль: {profit}{ref_note}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}{_mod_balans_str}')
                elif "Интернет" in usluga:
                    try:
                        cost_str = call.message.text.split('💰Себестоимость: ')[1].split('\n')[0]
                        profit_str2 = call.message.text.split('📈Чистая прибыль: ')[1].split('\n')[0]
                        profit_line2 = f'\n💰Себестоимость: {cost_str}\n📈Чистая прибыль: {profit_str2}'
                    except Exception:
                        profit_line2 = ''
                    send_to_archives(bot.send_message, f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}{profit_line2}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}{_mod_balans_str}')
                elif "Россия" in usluga:
                    try:
                        sum_bez_com = call.message.text.split('Сумма без комисии: ')[1].split('\n')[0]
                        profit_ru = round(float(sum) - float(sum_bez_com), 2)
                        profit_str = f'\n📈Чистая прибыль: {profit_ru}₽'
                    except Exception:
                        sum_bez_com = '—'
                        profit_str = ''
                    send_to_archives(bot.send_message, f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\nСумма без комисии: {sum_bez_com}{profit_str}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}{_mod_balans_str}')
                else:
                    send_to_archives(bot.send_message, f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}{_mod_balans_str}')
            elif text == 'nogoodKom':
                close_request(int(number))
                if not "Пополнение баланса" in usluga:
                    add_deposit(id, sum, description='Возврат средств')
                mesid = bot.send_message(call.message.chat.id, "Введите комментарий:")
                bot.register_next_step_handler(call.message, process_nogoodKom_comment, mess=call.message, messid=mesid, cal=call)
            elif text == 'nogood':
                close_request(int(number))
                if not "Пополнение баланса" in usluga:
                    add_deposit(id, sum, description='Возврат средств')
                bot.answer_callback_query(callback_query_id=call.id, text=f"Заявка №{number} отклонена")
                c = cancel_request(call.message.text)
                if c:
                    try:
                        bot.send_message(id, f"❌Заявка №{number} отклонена❌")
                    except Exception:
                        pass
                    try:
                        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
                    except Exception:
                        try:
                            bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
                        except Exception:
                            pass
                    date = datetime.now().date().strftime('%d.%m.%Y')
                    send_to_archives(bot.send_message, f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ❌Отменено\n\n Заявку закрыл(а): {call.from_user.username}')
                else:
                    bot.send_message(call.message.chat.id, f"Не нашел Заявку №{number}")
    elif text == 'good_with_mes':
        mesid = bot.send_message(call.message.chat.id, "Введите комментарий:")
        bot.register_next_step_handler(call.message, process_good_with_mes_comment, mess=call.message, messid=mesid, cal=call)
    elif text == 'schet':
        del1 = bot.send_message(call.message.chat.id, "Введите сумму:")
        bot.register_next_step_handler(call.message, process_schet_comment, mess=call.message, del1=del1)
    elif text == 'get_history':
        json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
        json_data["Профиль"]["История"] += 1
        with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)
        mess_text = get_combined_history(call.message.chat.id)
        if mess_text == '':
            bot.send_message(call.message.chat.id, 'У вас нет истории')
        else:
            for i in range(0, len(mess_text), 4096):
                bot.send_message(call.message.chat.id, mess_text[i:i+4096], parse_mode='HTML')
    elif text == 'balance_history':
        mess_text = get_balance_history(call.message.chat.id)
        if mess_text == '':
            bot.send_message(call.message.chat.id, '💰 История баланса пуста')
        else:
            bot.send_message(call.message.chat.id, f'💰 <b>История баланса (последние 20 операций):</b>\n\n{mess_text}', parse_mode='HTML')

    elif text.startswith('donation_accept:'):
        _, user_id_s, amount_s = text.split(':')
        user_id_d = int(user_id_s)
        amount_d = float(amount_s)
        _db = sqlite3.connect('files/donations.db', timeout=10)
        _db.cursor().execute(
            'INSERT INTO donations (user_id, username, amount) VALUES (?, ?, ?)',
            (user_id_d, call.message.caption.split('@')[1].split('\n')[0] if '@' in (call.message.caption or '') else '', amount_d)
        )
        _db.commit()
        _db.close()
        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption=call.message.caption + f'\n\n✅ Подтверждено (@{call.from_user.username})'
        )
        if amount_d >= 10000:
            privileges = (
                '— закрытый доступ к бета-тесту\n'
                '— закрытый канал разработки\n'
                '— промокод после запуска\n'
                '— статус участника запуска\n'
                '— бонус на баланс TGPay\n'
                '— приоритетная поддержка на 1 месяц\n'
                '— бесплатная настройка eSIM / VPN / связи\n'
                '— индивидуальный подбор услуги под задачу\n'
                '— приоритетная поддержка на 3 месяца\n'
                '— увеличенный бонус на баланс TGPay\n'
                '— расширенные персональные предложения\n'
                '— доступ к приложению одним из первых\n'
                '— отдельный VIP-статус\n'
                '— персональный менеджер\n'
                '— приоритетная поддержка на 6 месяцев\n'
                '— персональный пакет связи / VPN / eSIM под задачу'
            )
        elif amount_d >= 5000:
            privileges = (
                '— закрытый доступ к бета-тесту\n'
                '— закрытый канал разработки\n'
                '— промокод после запуска\n'
                '— статус участника запуска\n'
                '— бонус на баланс TGPay\n'
                '— приоритетная поддержка на 1 месяц\n'
                '— бесплатная настройка eSIM / VPN / связи\n'
                '— индивидуальный подбор услуги под задачу\n'
                '— приоритетная поддержка на 3 месяца\n'
                '— увеличенный бонус на баланс TGPay\n'
                '— расширенные персональные предложения\n'
                '— доступ к приложению одним из первых'
            )
        elif amount_d >= 3000:
            privileges = (
                '— закрытый доступ к бета-тесту\n'
                '— закрытый канал разработки\n'
                '— промокод после запуска\n'
                '— статус участника запуска\n'
                '— бонус на баланс TGPay\n'
                '— приоритетная поддержка на 1 месяц\n'
                '— бесплатная настройка eSIM / VPN / связи\n'
                '— индивидуальный подбор услуги под задачу\n'
                '— приоритетная поддержка на 3 месяца'
            )
        elif amount_d >= 1000:
            privileges = (
                '— закрытый доступ к бета-тесту\n'
                '— закрытый канал разработки\n'
                '— промокод после запуска\n'
                '— статус участника запуска\n'
                '— бонус на баланс TGPay\n'
                '— приоритетная поддержка на 1 месяц'
            )
        else:
            privileges = (
                '— закрытый доступ к бета-тесту\n'
                '— закрытый канал разработки\n'
                '— промокод после запуска'
            )
        bot.send_message(user_id_d,
            f'✅ <b>Ваше пожертвование подтверждено!</b>\n\n'
            f'💰 Сумма: {amount_d} ₽\n\n'
            f'🎁 <b>Вам доступны привилегии:</b>\n{privileges}\n\n'
            f'Спасибо за поддержку разработки приложения! 🙏',
            parse_mode='HTML')
        donation_rank = get_donation_rank(user_id_d)
        if donation_rank:
            bot.send_message(user_id_d,
                f'{donation_rank} — Ваш новый ранг за вклад в TGPay.\n'
                f'Ваш ранг доступен в профиле и будет отображаться в приложении.',
                parse_mode='HTML')

    elif text.startswith('donation_reject:'):
        user_id_d = int(text.split(':')[1])
        bot.edit_message_caption(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            caption=(call.message.caption or '') + f'\n\n❌ Отклонено (@{call.from_user.username})'
        )
        bot.send_message(user_id_d, '❌ Ваш чек не был подтверждён. Обратитесь в поддержку.', reply_markup=start_markup(user_id_d))
    elif text == 'start_dialog' or text == 'stop_dialog':
        id = call.message.text.split('id: ')[1].split('\n')[0]
        if text == 'start_dialog':
            USER_STATE[int(id)]=DIALOG
            mes = bot.send_message(call.message.chat.id, "Введите Сообщение:")
            bot.register_next_step_handler(call.message, process_dialog, mess=call.message)
        elif text == 'stop_dialog':
            USER_STATE[int(id)]=START
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
    elif text == 'akk_ok' or text == 'akk_cancel':
        if text == 'akk_ok':
            summ = int(call.message.text.split('на оплату в сумме ')[1].split('₽')[0])
            if float(get_balans(call.message.chat.id))-float(summ)>=0:
                number = int(call.message.text.split('Заявка №')[1].split('\n')[0])
                usluga = call.message.text.split('Товар:\n')[1]
                add_data('sum', summ, call.message.chat.id)
                update_balanse(call.message.chat.id, 'sum')
                update_total_spent(call.message.chat.id, float(summ))
                bot.send_message(call.message.chat.id, f'✅Готово\nВаша заявка №<code>{number}</code> уже в обработке!', reply_markup = start_markup(call.message.chat.id), parse_mode="HTML")
                bot.send_message(adminGroup, f'Заявка №{number}\nПользователь: @{call.message.chat.username} \nid: {call.message.chat.id}\nУслуга: {usluga}\n🎩Ранг: {get_user_rank(call.message.chat.id)}\nСумма: {summ}', reply_markup = admin_markup())
                bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            else:
                update_state(call.message, START)
                bot.send_message(call.message.chat.id, 'Недостаточно средств', reply_markup = start_markup(call.message.chat.id))
                inline_markup = types.InlineKeyboardMarkup(row_width=True)
                inline_markup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balanse"))
                bot.send_message(call.message.chat.id, 'Пополните баланс', reply_markup = inline_markup)
        elif text == 'akk_cancel':
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
            bot.send_message(call.message.chat.id, "Вы отклонили оплату")
    elif text == 'otvet':
        mes = bot.send_message(call.message.chat.id, "Введите Сообщение:")
        bot.register_next_step_handler(call.message, process_otvet, mess=call.message)
    elif text == 'stop_dialog_user':
        USER_STATE[call.message.chat.id]=START
        bot.send_message(call.message.chat.id, 'Вы завершили разговор')
        bot.send_message(adminGroup, f'Пользователь {call.message.chat.id} завершил разговор')
    elif text == 'admin_balans_all':
        texts = get_all_users_text()
        for text in list(texts):
            bot.send_message(call.message.chat.id, text, reply_markup = start_markup(call.message.chat.id))
    elif text == 'admin_balans_id':
        bot.send_message(call.message.chat.id, 'Пришлите ID пользователя', reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
        update_state(call.message, GET_ID_BALANS)
    elif text == 'admin_balance_history_id':
        msg = bot.send_message(call.message.chat.id, '💰 Введите ID пользователя для просмотра истории баланса:', reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
        bot.register_next_step_handler(msg, admin_balance_history_handler)
    elif text == "resume_request":
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception as e:
            print(f"Ошибка при удалении сообщения: {e}")
        if call.message.chat.id not in USER_REQUEST_DATA or not USER_REQUEST_DATA[call.message.chat.id].get("sum"):
            bot.send_message(call.message.chat.id, '⚠️ Данные заявки устарели. Пожалуйста, оформите заявку заново.', reply_markup=start_markup(call.message.chat.id))
            update_state(call.message, START)
            return
        update_balanse(call.message.chat.id, 'sum')
        phone = USER_REQUEST_DATA[call.message.chat.id].get("phone", "Неизвестно")
        sum_rub = USER_REQUEST_DATA[call.message.chat.id].get("sum", "0")
        sum_uah = USER_REQUEST_DATA[call.message.chat.id].get("original_sum", "0")
        service = USER_REQUEST_DATA[call.message.chat.id].get("service", "Неизвестно")
        usluga = f"{service}. {phone}"
        number = to_arhiv(call.message.chat.id, usluga, sum_rub)
        # round(float(suma)/get_kurs("uah"),2)
        try:
            cost_rate = _uah_cost_rate_cache or get_kurs("uah")
            cost = round(float(sum_uah) * float(cost_rate), 2)
            profit_v = round(float(sum_rub) - cost, 2)
            profit_line_v = f'\n💰Себестоимость: {cost}₽ (курс {cost_rate})\n📈Чистая прибыль: {profit_v}₽'
        except Exception:
            profit_line_v = ''
        bot.send_message(adminGroup,
                         f'Заявка №{number}\nПользователь: @{call.message.chat.username} \nid: {call.message.chat.id}\nУслуга: {usluga}\nСумма в грн.: {sum_uah}\n🎩Ранг: {get_user_rank(call.message.chat.id)}\nСумма: {sum_rub}{profit_line_v}',
                         reply_markup=admin_markup())
        bot.send_message(call.message.chat.id, f'✅Готово\nВаша заявка №<code>{number}</code> уже в обработке!',
                         reply_markup=start_markup(call.message.chat.id), parse_mode="HTML")
        update_state(call.message, START)

    elif text == 'send_to_all':
        add_data('send_target', 'all', call.message.chat.id)
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("Да", callback_data="with_button"))
        inline_markup.add(types.InlineKeyboardButton("Нет", callback_data="no_button"))
        bot.send_message(call.message.chat.id, 'Сообщение с кнопкой?', reply_markup=inline_markup)
    elif text == 'send_to_one':
        add_data('send_target', 'one', call.message.chat.id)
        bot.send_message(call.message.chat.id, 'Введите ID пользователя:', reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
        update_state(call.message, SEND_TARGET_ID)
    elif text == 'send_to_list':
        add_data('send_target', 'list', call.message.chat.id)
        bot.send_message(call.message.chat.id, 'Введите ID через запятую или каждый с новой строки:', reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
        update_state(call.message, SEND_TARGET_LIST)
    elif text == 'send_to_inactive':
        add_data('send_target', 'inactive', call.message.chat.id)
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("Да", callback_data="with_button"))
        inline_markup.add(types.InlineKeyboardButton("Нет", callback_data="no_button"))
        bot.send_message(call.message.chat.id, 'Сообщение с кнопкой?', reply_markup=inline_markup)

    elif text == 'with_button':
        add_data('buttons_json', '[]', call.message.chat.id)
        color_markup = types.InlineKeyboardMarkup(row_width=2)
        color_markup.add(
            types.InlineKeyboardButton("🟢 Зелёная", callback_data="btn_color:success"),
            types.InlineKeyboardButton("🔴 Красная", callback_data="btn_color:danger"),
        )
        color_markup.add(
            types.InlineKeyboardButton("🔵 Синяя", callback_data="btn_color:primary"),
            types.InlineKeyboardButton("⚪ Без цвета", callback_data="btn_color:none"),
        )
        bot.send_message(call.message.chat.id, 'Выберите цвет кнопки:', reply_markup=color_markup)
    elif text == 'no_button':
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("Да", callback_data="with_image"))
        inline_markup.add(types.InlineKeyboardButton("Нет", callback_data="no_image"))
        bot.send_message(call.message.chat.id, 'Сообщение с изображением?', reply_markup=inline_markup)
        update_state(call.message, SEND_IMAGE)
        # bot.send_message(call.message.chat.id, 'Введите сообщение для отправки:', reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
        # update_state(call.message, SEND)
    elif text == 'add_more_button':
        color_markup = types.InlineKeyboardMarkup(row_width=2)
        color_markup.add(
            types.InlineKeyboardButton("🟢 Зелёная", callback_data="btn_color:success"),
            types.InlineKeyboardButton("🔴 Красная", callback_data="btn_color:danger"),
        )
        color_markup.add(
            types.InlineKeyboardButton("🔵 Синяя", callback_data="btn_color:primary"),
            types.InlineKeyboardButton("⚪ Без цвета", callback_data="btn_color:none"),
        )
        bot.send_message(call.message.chat.id, 'Выберите цвет кнопки:', reply_markup=color_markup)
    elif text.startswith('btn_color:'):
        # Сохраняем выбранный цвет и переходим к вводу текста кнопки
        color_value = text.split(':', 1)[1]  # 'success' | 'danger' | 'primary' | 'none'
        add_data('_tmp_btn_color', color_value, call.message.chat.id)
        bot.send_message(call.message.chat.id, 'Введите текст кнопки:', reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
        update_state(call.message, SEND_BUTTON)

    elif text == 'buttons_done':
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("Да", callback_data="with_image"))
        inline_markup.add(types.InlineKeyboardButton("Нет", callback_data="no_image"))
        bot.send_message(call.message.chat.id, 'Сообщение с изображением?', reply_markup=inline_markup)
    elif text == 'with_image':
        bot.send_message(call.message.chat.id, 'Отправьте изображение', reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
        update_state(call.message, SEND_IMAGE)
    elif text == 'no_image':
        bot.send_message(call.message.chat.id, 'Введите сообщение для отправки:', reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
        update_state(call.message, SEND)
    elif text == 'ua_ok':
        message_text = call.message.text
        price = message_text.split()[-1][:-1]
        if float(get_balans(call.message.chat.id))-(float(price))>=0:
            update_balanse(call.message.chat.id, 'sum')
            
            update_total_spent(call.message.chat.id, float(price))
            con = 'Украина'
            usluga = f'Мобильный. {con}. {get_par("phone", call.message.chat.id)}'
            suma = get_par("sum", call.message.chat.id)
            orig_suma = get_par("original_sum", call.message.chat.id)
            number = to_arhiv(call.message.chat.id, usluga, suma)
            # round(float(suma)/get_kurs("uah"),2)
            try:
                cost_rate = _uah_cost_rate_cache or get_kurs("uah")
                cost = round(float(orig_suma) * float(cost_rate), 2)
                profit = round(float(suma) - cost, 2)
                profit_line = f'\n💰Себестоимость: {cost}₽ (курс {cost_rate})\n📈Чистая прибыль: {profit}₽'
            except Exception:
                profit_line = ''
            admin_msg = bot.send_message(adminGroup, f'Заявка №{number}\nПользователь: @{call.message.chat.username} \nid: {call.message.chat.id}\nУслуга: {usluga}\n🎩Ранг: {get_user_rank(call.message.chat.id)}\nСумма в грн.: {orig_suma}\nСумма: {suma}{profit_line}', reply_markup = admin_markup())
            register_request(number, admin_msg.message_id, adminGroup)
            bot.send_message(call.message.chat.id, f'✅Готово\nВаша заявка №<code>{number}</code> уже в обработке!', reply_markup = start_markup(call.message.chat.id), parse_mode="HTML")
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        else:
            update_state(call.message, START)
            USER_WAIT_FOR_CONTINUE[int(call.message.chat.id)] = True
            set_request_data(call.message.chat.id,
                             required_sum=price,
                             phone=get_par("phone", call.message.chat.id),
                             service='Мобильный. Украина',
                             original_sum=get_par("original_sum", call.message.chat.id),
                             sum=get_par("sum", call.message.chat.id)
                             )
            bot.send_message(call.message.chat.id, 'Недостаточно средств', reply_markup = start_markup(call.message.chat.id))
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_markup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balanse"))
            bot.send_message(call.message.chat.id, 'Пополните баланс', reply_markup = inline_markup)

    elif text == 'ru_no':
        # sum =  get_par("sum", call.message.chat.id)
        # add_deposit(chat_id, str(sum))
        bot.send_message(chat_id, f"❌Отклонено❌", reply_markup = start_markup(call.message.chat.id))
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)

    elif text == 'ru_ok':
        message_text = call.message.text
        price = message_text.split()[-1][:-1]
        if float(get_balans(call.message.chat.id))-(float(price))>=0:
            update_balanse(call.message.chat.id, 'sum')
            update_total_spent(call.message.chat.id, float(price))
            con = 'Россия'
            usluga = f'Мобильный. {con}. {get_par("phone", call.message.chat.id)}'
            suma = get_par("sum", call.message.chat.id)
            sum_bez_com = get_par("sum_bez_com", call.message.chat.id)
            number = to_arhiv(call.message.chat.id, usluga, suma)
            bot.send_message(adminGroup, f'Заявка №{number}\nПользователь: @{call.message.chat.username} \nid: {call.message.chat.id}\nУслуга: {usluga}\n🎩Ранг: {get_user_rank(call.message.chat.id)}\nСумма: {suma}\nСумма без комисии: {sum_bez_com}', reply_markup = admin_markup())
            bot.send_message(call.message.chat.id, f'✅Готово\nВаша заявка №<code>{number}</code> уже в обработке!', reply_markup = start_markup(call.message.chat.id), parse_mode="HTML")
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        else:
            update_state(call.message, START)
            USER_WAIT_FOR_CONTINUE[int(call.message.chat.id)] = True
            set_request_data(call.message.chat.id,
                             required_sum=price,
                             phone=get_par("phone", call.message.chat.id),
                             service='Мобильный. Россия',
                             original_sum=get_par("original_sum", call.message.chat.id),
                             sum=get_par("sum", call.message.chat.id)
                             )
            bot.send_message(call.message.chat.id, 'Недостаточно средств', reply_markup = start_markup(call.message.chat.id))
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_markup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balanse"))
            bot.send_message(call.message.chat.id, 'Пополните баланс', reply_markup = inline_markup)

    elif text == 'ua_no':
        # sum =  get_par("sum", call.message.chat.id)
        # add_deposit(chat_id, str(sum))
        bot.send_message(chat_id, f"❌Отклонено❌", reply_markup = start_markup(call.message.chat.id))
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)

    elif text == "es_ok":
        message_text = call.message.text
        price = message_text.split()[-1][:-1]
        if float(get_balans(call.message.chat.id))-(float(price))>=0:
            update_balanse(call.message.chat.id, 'sum')
            update_total_spent(call.message.chat.id, float(price))
            con = 'Испания'
            usluga = f'Мобильный. {con}. {get_par("phone", call.message.chat.id)}'
            suma = get_par("sum", call.message.chat.id)
            orig_suma = get_par("original_sum", call.message.chat.id)
            number = to_arhiv(call.message.chat.id, usluga, suma)
            # round(float(suma)/get_kurs("eur"),2)
            bot.send_message(adminGroup, f'Заявка №{number}\nПользователь: @{call.message.chat.username} \nid: {call.message.chat.id}\nУслуга: {usluga}\n🎩Ранг: {get_user_rank(call.message.chat.id)}\nСумма в евро: {orig_suma}\nСумма: {suma}', reply_markup = admin_markup())
            bot.send_message(call.message.chat.id, f'✅Готово\nВаша заявка №<code>{number}</code> уже в обработке!', reply_markup = start_markup(call.message.chat.id), parse_mode="HTML")
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        else:
            update_state(call.message, START)
            bot.send_message(call.message.chat.id, 'Недостаточно средств', reply_markup = start_markup(call.message.chat.id))
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_markup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balanse"))
            bot.send_message(call.message.chat.id, 'Пополните баланс', reply_markup = inline_markup)

    elif text == 'es_no':
        # sum =  get_par("sum", call.message.chat.id)
        # add_deposit(chat_id, str(sum))
        bot.send_message(chat_id, f"❌Отклонено❌", reply_markup = start_markup(call.message.chat.id))
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)

    elif text == "check_subscribe_button":
        if check_subscribe(call.from_user.id, debug=True):
            bot.send_message(call.from_user.id, f"Привет, {call.from_user.first_name} {call.from_user.last_name}!", reply_markup = start_markup(call.from_user.id))
        else:
            markup = types.InlineKeyboardMarkup(row_width=True)
            buttons = get_unsubscribed_buttons(call.from_user.id)
            buttons.append(types.InlineKeyboardButton(text="✅Подписался", callback_data="check_subscribe_button"))
            markup.add(*buttons)
            bot.send_message(call.from_user.id,
            """
            Чтобы пользоваться ботом нужно быть подписанным на канал и чат TGPay👇
            """, reply_markup=markup)
    elif text == "close":
        
        bot.send_message(call.from_user.id, f"Привет, {call.from_user.first_name} {call.from_user.last_name}!", reply_markup = start_markup(call.from_user.id))
    elif text == 'donat_button':
        markup = types.InlineKeyboardMarkup(row_width=True)
        donate_communication = types.InlineKeyboardButton("Написать", url="https://t.me/donate008")
        markup.add(donate_communication)
        bot.send_message(call.from_user.id, f"Чтобы купить донат напишите нашему специалисту", reply_markup=markup)
    elif text == "payok_buy":
        update_state(call.message, PAYOK_BUY)
        bot.send_message(call.from_user.id, f"Введите сумму которую вы хотите положить на баланс в рублях", reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
    elif text == "payok_complite":
        id = call.message.text.split("заявки: ")[1].split("\n")[0] # Получаем id заявки
        summa = call.message.text.split("оплате: ")[1].split("\n")[0]
        api_data["payment"] = int(id)
        # формируем тело запроса
        response = requests.post(f"https://payok.io/api/transaction", data = api_data)
        response_data = response.json()
        try:
            if response_data["1"]["transaction_status"] == "1": #проверка транзакции
                add_deposit(call.message.chat.id, summa)
                bot.edit_message_reply_markup(chat_id = call.message.chat.id, message_id = call.message.message_id, reply_markup = '')
                bot.send_message(call.message.chat.id, f"На ваш счет поступило {summa}")
                send_to_archives(bot.send_message, f"Оплата через payok на сумму {summa}\nНомер заявки {id}\n🎩Ранг: {get_user_rank(id)}\n")
            elif response_data["status"] == "error":
                bot.send_message(call.message.chat.id, "Возникла ошибка")
            else:
                bot.send_message(call.message.chat.id, "Вы еще не оплатили")
        except:
            bot.send_message(call.message.chat.id, "Возникла ошибка")
    # elif text == "merchant_buy":
    #     json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
    #     json_data["Профиль"]["Способы оплаты"]["Карты РФ"] += 1
    #     with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
    #         json.dump(json_data, json_file, ensure_ascii=False, indent=4)
    #     update_state(call.message, MERCHANT_BUY)
    #     bot.send_message(call.from_user.id, f"Введите сумму пополнения от 100₽ до 50 000₽", reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
    elif text == "merchant_complite":
        id = call.message.text.split("заявки: ")[1].split("\n")[0] # Получаем id заявки
        summa = call.message.text.split("оплате: ")[1].split("\n")[0]
        # формируем тело запроса
        response = requests.get(f"https://api.merchant001.io/v1/transaction/merchant/{id}", headers = merchant_headers, params = {"id": id})
        response_data = response.json()
        try:
            bot.send_message(-1002026990843, f"{response_data}")
            payment_status = response_data["status"]
            if payment_status == "CONFIRMED": #проверка транзакции
                try:
                    with open("promocode.json", encoding="utf-8") as file:
                        data = json.load(file)
                    promocode = get_promocode(call.message.chat.id)
                    promocode_procent = data[promocode]['procent']
                    procent = ((int(summa)/100)*int(promocode_procent))
                    promocode_summa = int(summa) + procent
                    add_deposit(call.message.chat.id, str(promocode_summa), description='Пополнение баланса')
                    bot.send_message(call.message.chat.id, f"На ваш счет поступило {promocode_summa}")
                    send_to_archives(bot.send_message, f"Id пользователя: {call.message.chat.id}\nПользователь: @{call.message.chat.username}\nОплата через merchant на сумму: {summa}\n🎩Ранг: {get_user_rank(call.message.chat.id)}\nНомер заявки: {id}")
                    data[promocode]["wasted_user"].append(call.message.chat.id)
                    with open("promocode.json", "w", encoding="utf-8") as file:
                        json.dump(data, file, ensure_ascii=False, indent=4)
                    delete_promocode(call.message.chat.id)
                except:
                    add_deposit(call.message.chat.id, summa, description='Пополнение баланса')
                    bot.send_message(call.message.chat.id, f"На ваш счет поступило {summa}")
                    send_to_archives(bot.send_message, f"Id пользователя: {call.message.chat.id}\nПользователь: @{call.message.chat.username}\nОплата через merchant на сумму: {summa}\n🎩Ранг: {get_user_rank(call.message.chat.id)}\nНомер заявки: {id}")
                bot.edit_message_reply_markup(chat_id = call.message.chat.id, message_id = call.message.message_id, reply_markup = '')
            elif payment_status == "PAID" or payment_status == "IN_PROGRESS":
                bot.send_message(call.message.chat.id, "Платеж проверяется")
            elif payment_status == "PENDING":
                bot.send_message(call.message.chat.id, "Вы еще не оплатили")
            elif payment_status == "FAILED":
                bot.send_message(call.message.chat.id, "Произошла ошибка")
            elif payment_status == "EXPIRED":
                bot.send_message(call.message.chat.id, "Истек срок оплаты")
            else:
                bot.send_message(call.message.chat.id, "Вы еще не оплатили")
        except:
            bot.send_message(call.message.chat.id, "Возникла ошибка")
    elif text == "withdraw_sbp":
        bot.send_message(call.message.chat.id, f"📲Введите ваш номер телефона и банк: \n(Пример: Сбер +7 900 123 45 67)", reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
        update_state(call.message, SBP_NUMBER)
    elif text == "withdraw_card":
        bot.send_message(
            call.message.chat.id,
            "💳Введите номер карты: (Пример: 1234 5678 9012 3456)",
            reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена')
        )
        update_state(call.message, CARD_NUMBER)
    elif text == "cryptomus_buy":
        try:
            json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
            json_data["Профиль"]["Способы оплаты"]["Крипта"] += 1
            with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
                json.dump(json_data, json_file, ensure_ascii=False, indent=4)
        except:
            pass
        bot.send_message(call.message.chat.id, "Введите сумму пополнения от 1000₽", reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
        update_state(call.message, CRYPT_SUMM)
    elif text == "crypt_paid":
        try:
            with open("crypt_ex.jpg", 'rb') as f:
                bot.send_photo(call.message.chat.id, photo=f.read(), caption="Пришлите хэш (TXID) транзакции в чат:", reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
        except:
            bot.send_message(call.message.chat.id, "Пришлите хэш (TXID) транзакции в чат:", reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
        update_state(call.message, CRYPT_TXID)
    # elif text == "Nicepay":
    #     json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
    #     json_data["Профиль"]["Способы оплаты"]["Nicepay"] += 1
    #     with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
    #         json.dump(json_data, json_file, ensure_ascii=False, indent=4)
    #     bot.send_message(call.message.chat.id, "Введите сумму пополнения от 1000₽ до 85000₽", reply_markup = start_markup(call.message.chat.id, text='🚫 Отмена'))
    #     update_state(call.message, NICEPAY)
    elif text == "invoice_buy":
        message_text = call.message.text
        summ = message_text.split()[-1][:-1]
        if float(get_balans(call.message.chat.id))-float(summ)>=0:
            # number = int(call.message.text.split('Заявка №')[1].split('\n')[0])
            number = to_arhiv(call.message.chat.id, "Покупка аккаунта или донат", summ)
            usluga = message_text.split("Название товара : ")[1].split("\n")[0]
            add_data('sum', summ, call.message.chat.id)
            update_balanse(call.message.chat.id, 'sum')
            update_total_spent(call.message.chat.id, float(summ))
            bot.send_message(call.message.chat.id, f'✅Готово', reply_markup = start_markup(call.message.chat.id), parse_mode="HTML")
            send_to_archives(bot.send_message, f"Номер заявки: {number}\nId пользователя: {call.message.chat.id}\nПользователь: @{call.message.chat.username}\nСумма: {summ}\n🎩Ранг: {get_user_rank(call.message.chat.id)}\nТовар: {usluga}")
            # bot.send_message(adminGroup, f'Заявка №{number}\nПользователь: @{call.message.chat.username} \nid: {call.message.chat.id}\nУслуга: {usluga}\nСумма: {summ}', reply_markup = admin_markup())
            bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        else:
            update_state(call.message, START)
            bot.send_message(call.message.chat.id, 'Недостаточно средств', reply_markup = start_markup(call.message.chat.id))
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            inline_markup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balanse"))
            bot.send_message(call.message.chat.id, 'Пополните баланс', reply_markup = inline_markup)
    elif text == "invoice_cancel":
        bot.delete_message(chat_id=call.message.chat.id, message_id=call.message.message_id)
        bot.send_message(call.message.chat.id, "Вы отклонили оплату")
    elif text == "add_yoomoney_requisites":
        bot.send_message(call.message.chat.id, "Введите номер телефона для реквизитов", reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
        update_state(call.message, YOOMANY_REQUISITES)
    # elif text == "add_yoomoney_requisites_test":
    #     bot.send_message(call.message.chat.id, "Введите номер телефона для реквизитов", reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
    #     update_state(call.message, YOOMANY_REQUISITES)
    elif text == "delete_yoomoney_requisites":
        requisites = get_requisites()
        if requisites:
            inline_markup = types.InlineKeyboardMarkup(row_width=True)
            for key in requisites.keys():
                inline_markup.add(types.InlineKeyboardButton(f"{key}", callback_data=f"delete_req_phone_{key}"))
            bot.send_message(call.message.chat.id, "Выберите номер телефона для удаления", reply_markup=inline_markup)
        else:
            bot.send_message(call.message.chat.id, "Нет номеров для удаления")
    elif text.startswith("delete_req_phone_"):
        requisites = get_requisites()
        data = json.load(open("yoomany_requisites.json", encoding="utf-8"))
        phone = text.split("_")[-1]
        del data[phone]
        with open("yoomany_requisites.json", "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        bot.send_message(call.message.chat.id, "Телефон был удален", reply_markup=start_markup(call.message.chat.id))
    elif text == "ref_procent_change":
        procent = json.load(open("ref_data.json", encoding="utf-8"))
        ua = procent['ref_procent']["ua"]
        eSIM  = procent['ref_procent']["eSIM"]
        bot.send_message(call.message.chat.id, f"""Текущие проценты: 
                         Мобильный Украина:
                         Холодный:{ua['cold']} 
                         Горячий:{ua['warm']}
                         Далее:{ua["hot"]}Введите новые проценты""", reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
        update_state(call.message, REF_PROCENT_CHANGE)
    elif text == "ref_hryvnia_change":
        bot.send_message(call.message.chat.id, "Введите новое значение множителя", reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
        update_state(call.message, REF_HRYVNIA_CHANGE)
    elif text == "ref_system":
        ref_balance = get_ref_balance(call.message.chat.id)
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("Вывести деньги", callback_data="balance_output"))
        bot.send_message(call.message.chat.id, f"Вывести с реферального баланса можно только от 100 рублей\n\nВаша реферальная ссылка: https://t.me/PayTelekom_bot?start={call.message.chat.id}\nРеферальный баланс: {ref_balance}", reply_markup=inline_markup)

    elif text == "calculator":
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_button1 = types.InlineKeyboardButton(f"🇺🇸USD", callback_data="vusd_calc")
        inline_button2 = types.InlineKeyboardButton(f"🇪🇺EUR", callback_data="veur_calc")
        inline_button3 = types.InlineKeyboardButton(f"🇹🇷TRY", callback_data="vtry_calc")
        inline_button4 = types.InlineKeyboardButton(f"🇺🇦UAH", callback_data="vuah_calc")
        inline_markup.add(inline_button1)
        inline_markup.add(inline_button2)
        inline_markup.add(inline_button3)
        inline_markup.add(inline_button4)
        bot.send_message(call.message.chat.id, '🟢 Выберите валюту', reply_markup=inline_markup)
    elif text == "balance_output":
        ref_balance = get_ref_balance(call.message.chat.id)
        if int(ref_balance) >= 100:
            add_deposit(call.message.chat.id, ref_balance, description='Вывод реферального баланса')
            minus_balance_ref(call.message.chat.id, ref_balance)
            bot.send_message(call.message.chat.id, "Деньги успешно выведены")
        else:
            bot.send_message(call.message.chat.id, "На вашем реферальном балансе меньше 500 рублей")

    elif text == "stop_replishment":
        data = json.load(open("replishment_active.json", encoding="utf-8"))
        data["active"] = 0

        with open("replishment_active.json", "w", encoding="utf-8") as file:
            json.dump(data, file)

        bot.send_message(call.message.chat.id, "Пополнение картами остановлено")
    elif text == "active_replishment":
        data = json.load(open("replishment_active.json", encoding="utf-8"))
        data["active"] = 1

        with open("replishment_active.json", "w", encoding="utf-8") as file:
            json.dump(data, file)

        bot.send_message(call.message.chat.id, "Пополнение картами активировано")

    elif text == "stop_auto_replishment":
        data = json.load(open("replishment_active.json", encoding="utf-8"))
        data["time_active"] = 0

        with open("replishment_active.json", "w", encoding="utf-8") as file:
            json.dump(data, file)

        bot.send_message(call.message.chat.id, "Пополнение картами остановлено")
    elif text == "active_auto_replishment":
        data = json.load(open("replishment_active.json", encoding="utf-8"))
        data["time_active"] = 1

        with open("replishment_active.json", "w", encoding="utf-8") as file:
            json.dump(data, file)

        bot.send_message(call.message.chat.id, "Пополнение картами активировано")
    elif text == "stop_nicepay":
        data = json.load(open("replishment_active.json", encoding="utf-8"))
        data["nicepay_active"] = 0

        with open("replishment_active.json", "w", encoding="utf-8") as file:
            json.dump(data, file)
        deactivate_nicepay()
        bot.send_message(call.message.chat.id, "Пополнение с NicePay остановлено")
    elif text == "active_nicepay":
        data = json.load(open("replishment_active.json", encoding="utf-8"))
        data["nicepay_active"] = 1

        with open("replishment_active.json", "w", encoding="utf-8") as file:
            json.dump(data, file)
        activate_nicepay()
        bot.send_message(call.message.chat.id, "Пополнение с NicePay активировано")

    elif text.startswith("user_answer_"):
        user_id = text.split("_")[-1]
        update_state(call.message, ADMIN_DIALOG)
        add_data("user_id", user_id, call.message.chat.id)
        bot.send_message(call.message.chat.id, "Напишите сообщение", reply_markup=start_markup(call.message.chat.id, text='🚫 Отмена'))
    bot.answer_callback_query(call.id)

def admin_num(message, user_chat_id, summ):

    message_text = message.text
    user = bot.get_chat(user_chat_id)
    price = summ * get_kurs("uah")
    if float(get_balans(user_chat_id)) - (float(price)) >= 0:
        add_data('sum', price, user_chat_id)
        update_balanse(user_chat_id, 'sum')
        update_total_spent(user_chat_id, float(price))
        con = 'Украина'
        usluga = f'Мобильный. {con}. {create_req_num}'
        orig_suma = summ
        suma = price
        number = to_arhiv(user_chat_id, usluga, suma)
        # round(float(suma)/get_kurs("uah"),2)
        try:
            cost_rate = _uah_cost_rate_cache or get_kurs("uah")
            cost = round(float(orig_suma) * float(cost_rate), 2)
            profit_val = round(float(suma) - cost, 2)
            profit_line_m = f'\n💰Себестоимость: {cost}₽ (курс {cost_rate})\n📈Чистая прибыль: {profit_val}₽'
        except Exception:
            profit_line_m = ''
        bot.send_message(adminGroup,
                         f'Заявка №{number}\nПользователь: @{user.username} \nid: {user_chat_id}\nУслуга: {usluga}\n🎩Ранг: {get_user_rank(user_chat_id)}\nСумма в грн.: {orig_suma}\nСумма: {suma}{profit_line_m}',
                         reply_markup=admin_markup())
        bot.send_message(message.chat.id, f'✅Готово\nВаша заявка №<code>{number}</code> уже в обработке!',
                         reply_markup=start_markup(message.chat.id), parse_mode="HTML")
        bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    else:
        update_state(message, START)
        bot.send_message(message.chat.id, 'У пользователя недостаточно средств', reply_markup=start_markup(message.chat.id))

# Диалог с юзером

# Обработка сообщений от юзера
def user_answer(message, user_id, sender_id):
    logging.info(user_id)
    inline_markup = types.InlineKeyboardMarkup(row_width=True)
    inline_markup.add(types.InlineKeyboardButton("Ответить", callback_data=f"user_answer_{sender_id}"))
    if int(user_id) in admins:
        bot.send_message(user_id, f"От {sender_id}\n\n{message}", reply_markup = inline_markup)
    else:
        bot.send_message(user_id, f"{message}", reply_markup = inline_markup)


# # Обработка сообщений от админа
# def admin_answer(message, user_id):
#     inline_markup = types.InlineKeyboardMarkup(row_width=True)
#     inline_markup.add(types.InlineKeyboardButton("Ответить", callback_data=f"admin_answer_{user_id}"))
#     bot.send_message(user_id, message.text,reply_markup = inline_markup)

#otvet
def process_otvet(message, **kwargs):
    mess = kwargs.get('mess')
    id = int(mess.text.split('id: ')[1].split('\n')[0])
    inline_markup = types.InlineKeyboardMarkup(row_width=True)
    inline_markup.add(types.InlineKeyboardButton("Завершить разговор", callback_data="stop_dialog_user"))
    bot.send_message(id, message.text,reply_markup = inline_markup)
#dialog
def process_dialog(message, **kwargs):
    mess = kwargs.get('mess')
    id = int(mess.text.split('id: ')[1].split('\n')[0])
    inline_markup = types.InlineKeyboardMarkup(row_width=True)
    inline_markup.add(types.InlineKeyboardButton("Завершить разговор", callback_data="stop_dialog_user"))
    bot.send_message(id, message.text,reply_markup = inline_markup)
#schet
def process_schet_comment(message, **kwargs):
    mess = kwargs.get('mess')
    del1 = kwargs.get('del1')
    handle_schet_comment(mess, message, del1)
def handle_schet_comment(mess, sum, del1):
    del2 = bot.send_message(mess.chat.id, "Введите название товара:")
    main = mess
    bot.register_next_step_handler(mess, process_schet2_comment, sum=sum, del1=del1, del2=del2, main = main)
def process_schet2_comment(mess, **kwargs):
    del1 = kwargs.get('del1')
    del2 = kwargs.get('del2')
    sum = kwargs.get('sum')
    main = kwargs.get('main')
    handle_schet2_comment(mess, del1, del2, sum,main)
def handle_schet2_comment(mess, del1, del2, sum,main):
    usluga = mess.text
    summa = int(sum.text)
    id = int(main.text.split('id: ')[1].split('\n')[0])
    number = to_arhiv(id, usluga, summa)
    inline_markup = types.InlineKeyboardMarkup(row_width=True)
    inline_button1 = types.InlineKeyboardButton("✅Оплатить", callback_data="akk_ok")
    inline_button2 = types.InlineKeyboardButton("❌Отклонить", callback_data="akk_cancel")
    inline_markup.add(inline_button1)
    inline_markup.add(inline_button2)
    bot.send_message(id, f"✅Заявка №{number}\nВам пришёл счёт на оплату в сумме {summa}₽\nТовар:\n{usluga}", reply_markup=inline_markup)
    c = cancel_request(f'Заявка №{id}\n')
    bot.delete_message(chat_id=mess.chat.id, message_id=mess.message_id)
    bot.delete_message(chat_id=del1.chat.id, message_id=del1.message_id)
    bot.delete_message(chat_id=del2.chat.id, message_id=del2.message_id)
    bot.delete_message(chat_id=sum.chat.id, message_id=sum.message_id)
    #bot.delete_message(chat_id=main.chat.id, message_id=main.message_id)

############
def process_nogoodKom_comment(message, **kwargs):
    mess = kwargs.get('mess')
    k = kwargs.get('messid')
    c = kwargs.get('cal')
    handle_nogoodKom_comment(mess, message, k, c)
def handle_nogoodKom_comment(mess, comment, k, call):
    try:
        number = mess.caption.split('Заявка №')[1].split('\n')[0]
        id = int(mess.caption.split('id: ')[1].split('\n')[0])
        usluga = mess.caption.split('Услуга: ')[1].split('\n')[0]
        sum = mess.caption.split('Сумма: ')[1].split('\n')[0]
        user = mess.caption.split('Пользователь: ')[1].split('\n')[0]
        c = cancel_request(mess.caption)
        logging.info(f"{mess}")
        if c:
            bot.send_message(id, f"❌Заявка №{number} отклонена❌\nКомментарий: {comment.text}")
            bot.delete_message(chat_id=mess.chat.id, message_id=mess.message_id)
            bot.delete_message(chat_id=comment.chat.id, message_id=comment.message_id)
            bot.delete_message(chat_id=k.chat.id, message_id=k.message_id)
            date = datetime.now().date().strftime('%d.%m.%Y')
            with open(f"receipt_{id}.jpg", 'rb') as new_file:
                send_photo_to_archives(new_file.read(), caption=f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ❌Отменено с коментарием\nКомментарий: {comment.text}\n\n Заявку закрыл(а): {call.from_user.username}')
            os.remove(f"receipt_{id}.jpg")
        else:
            bot.send_message(mess.chat.id, f"Не нашел Заявку №{number}")
    except:
        number = mess.text.split('Заявка №')[1].split('\n')[0]
        id = int(mess.text.split('id: ')[1].split('\n')[0])
        usluga = mess.text.split('Услуга: ')[1].split('\n')[0]
        sum = mess.text.split('Сумма: ')[1].split('\n')[0]
        user = mess.text.split('Пользователь: ')[1].split('\n')[0]
        logging.info(f"{mess}")
        c = cancel_request(mess.text)
        if c:
            bot.send_message(id, f"❌Заявка №{number} отклонена❌\nКомментарий: {comment.text}")
            bot.delete_message(chat_id=mess.chat.id, message_id=mess.message_id)
            bot.delete_message(chat_id=comment.chat.id, message_id=comment.message_id)
            bot.delete_message(chat_id=k.chat.id, message_id=k.message_id)
            date = datetime.now().date().strftime('%d.%m.%Y')
            send_to_archives(bot.send_message, f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ❌Отменено с коментарием\nКомментарий: {comment.text}')
        else:
            bot.send_message(mess.chat.id, f"Не нашел Заявку №{number}")

#goodWithMes
def process_good_with_mes_comment(message, **kwargs):
    mess = kwargs.get('mess')
    k = kwargs.get('messid')
    c = kwargs.get('cal')
    handle_good_with_mes_comment(mess, message, k, c)
def handle_good_with_mes_comment(mess, comment, k, call):
    number = mess.text.split('Заявка №')[1].split('\n')[0]
    close_request(int(number))
    id = int(mess.text.split('id: ')[1].split('\n')[0])
    usluga = mess.text.split('Услуга: ')[1].split('\n')[0]
    sum = mess.text.split('Сумма: ')[1].split('\n')[0]
    user = mess.text.split('Пользователь: ')[1].split('\n')[0]
    if True:
        if comment.photo:
            photo = comment.photo[-1]
            file_id = photo.file_id
            bot.send_message(id, f"📱Ваша заявка №<code>{number}</code>\n✅Успешно обработана!", parse_mode="HTML")
            bot.send_photo(id, file_id, caption=f"{comment.caption}")
        else:
            bot.send_message(id, f"📱Ваша заявка №<code>{number}</code>\n✅Успешно обработана!\nКомментарий: {comment.text}", parse_mode="HTML")
        date = datetime.now().date().strftime('%d.%m.%Y')
        send_to_archives(bot.send_message, f'Дата: {date}\nЗаявка №{number}\nПользователь: {user}\nid: {id}\nУслуга: {usluga}\nСумма: {sum}\n🎩Ранг: {get_user_rank(id)}\nСтатус: ✅Одобрено\n\n Заявку закрыл(а): {call.from_user.username}')
        bot.delete_message(chat_id=mess.chat.id, message_id=mess.message_id)
        bot.delete_message(chat_id=comment.chat.id, message_id=comment.message_id)
        bot.delete_message(chat_id=k.chat.id, message_id=k.message_id)
############
UA_MOBILE_KEYWORDS = [
    "vodafone", "kyivstar", "lifecell", "киевстар", "водафон", "лайф", "лайфсел", "лайвсел", "водофон", "вадафон", "київстар",
    "пополнить мобильный", "оплатить мобильный", "мобильный", "положить на телефон", "положить", "положить на мобильный",
    "пополнить vodafone", "пополнить kyivstar", "пополнить lifecell", "пополнить киевстар", "пополнить водафон", "пополнить лайф",
    "пополнить лайфсел", "пополнить лайвсел", "пополнить водофон", "пополнить вадафон", "пополнить київстар",
    "положить на vodafone", "положить на kyivstar", "положить на lifecell", "положить на киевстар", "положить на водафон",
    "положить на лайф", "положить на лайфсел", "положить на лайвсел", "положить на водофон", "положить на вадафон", "положить на київстар"
]
RU_MOBILE_KEYWORDS = [
    "+7телеком", "7телеком", "миртелеком",
    "пополнить +7телеком", "пополнить 7телеком", "пополнить миртелеком",
    "положить на +7телеком", "положить на 7телеком", "положить на миртелеком"
]
VPN_KEYWORDS = [
    "впн", "vpn",
    "купить впн", "купить vpn",
    "впн пробный период", "vpn пробный период",
    "впн бесплатно", "vpn бесплатно"
]


def send_mobile_menu(message):
    # print('new version')
    inline_markup = types.InlineKeyboardMarkup(row_width=True)
    inline_markup.add(types.InlineKeyboardButton("🇺🇦Украина", callback_data="ua"))
    inline_markup.add(types.InlineKeyboardButton("🇷🇺Россия", callback_data="ru"))
    inline_markup.add(types.InlineKeyboardButton("🌏Европа / Азия ", callback_data="es"))
    inline_markup.add(types.InlineKeyboardButton("🛜 Пополнение ГБ", callback_data="svc_gb"))
    bot.send_message(message.chat.id, '🟢 Выберите страну номера, который хотите пополнить:', reply_markup=inline_markup)
    update_state(message, MOBIL)

def games(message):
    inline_markup = types.InlineKeyboardMarkup(row_width=True)
    inline_button1 = types.InlineKeyboardButton("Steam", callback_data="donat")
    inline_button2 = types.InlineKeyboardButton("Gift Cards", callback_data="gift_cards")
    inline_button3 = types.InlineKeyboardButton("Донат", callback_data="donat_button")
    inline_button4 = types.InlineKeyboardButton("🎮 Настройка игровых аккаунтов", callback_data="svc_gaming")
    inline_markup.add(inline_button1)
    inline_markup.add(inline_button2)
    inline_markup.add(inline_button3)
    inline_markup.add(inline_button4)
    bot.send_message(message.chat.id, '📲Выберите услугу', reply_markup=inline_markup)

def svyaz(message):
    svyaz_markup = {
        "inline_keyboard": [
            [{"text": "🛜 Пополнение ГБ", "callback_data": "svc_gb", "style": "success"}],
            [{"text": "📶 Настройка связи", "callback_data": "svc_svyaz"}],
            [{"text": "💳 Настройка SIM / eSIM", "callback_data": "svc_sim"}],
            [{"text": "📲 Настройка телефона", "callback_data": "svc_phone"}],
            [{"text": "🌍 Смена региона аккаунтов", "callback_data": "svc_region"}],
            [{"text": "💰 Донат в игру", "callback_data": "private_help"}],
        ]
    }
    bot.send_message(message.chat.id, '📲 Выберите услугу:', reply_markup=json.dumps(svyaz_markup))

def eSIM(message):
    bot.send_message(message.chat.id, esim, parse_mode='HTML')
    inline_markup = types.InlineKeyboardMarkup(row_width=True)
    inline_markup.add(types.InlineKeyboardButton("🔴 Vodafone", callback_data="Vodafone", icon_custom_emoji_id="5267292959182697142"))
    inline_markup.add(types.InlineKeyboardButton("🔵 Киевстар", callback_data="Kievstar", icon_custom_emoji_id="5267061554934723857"))
    inline_markup.add(types.InlineKeyboardButton("🟡 Lifecell", callback_data="Lifecell", icon_custom_emoji_id="5267284102960131913"))
    inline_markup.add(types.InlineKeyboardButton("🇫🇷 Франция", callback_data="France"))
    bot.send_message(message.chat.id, 'Выберите eSIM:', reply_markup=inline_markup)

def VPN(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📲Лучший VPN⚡️", url="https://t.me/ProxyTGPay_bot?start=start"))
    bot.send_message(message.chat.id,
    """
🔥 У нас появился новый бот, в котором вы можете подключить быстрый, качественный и безопасный VPN! 🚀🔒

✨ Никаких ограничений, стабильное соединение и полная анонимность в сети.

👉 Скорее переходи — @ProxyTGPay_bot
Подключайся и пользуйся интернетом свободно! 🌍💨
    """, reply_markup=markup)
    update_state(message, START)

@bot.message_handler(content_types=['text'])
def get_text_messages(message):
    text = message.text.strip().lower()
    '''Обрабатывает входящие текстовые сообщения в бота'''

    if message.text == '📲Мобильный':
        send_mobile_menu(message)
    elif text in UA_MOBILE_KEYWORDS:
        chat_id = message.chat.id
        json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
        markup = start_markup(chat_id, text='🚫 Отмена')
        json_data["Мобильный"]["Украина"] += 1
        bot.send_message(chat_id, get_ua_num, reply_markup=markup)
        add_data('contry', 'ua', message.chat.id)
        with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)
        update_state(message, PHONE)
    elif text in RU_MOBILE_KEYWORDS:
        chat_id = message.chat.id
        json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
        markup = start_markup(chat_id, text='🚫 Отмена')
        json_data["Мобильный"]["Россия"] += 1
        bot.send_message(chat_id, get_ru_num, reply_markup=markup)
        add_data('contry', 'ru', message.chat.id)
        with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)
        update_state(message, PHONE)
    elif message.text == '🎮Игры':
        games(message)

    elif message.text == '🆔Аккаунты':
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("Написать", url="https://t.me/donate008"))
        bot.send_message(message.chat.id, '🔰Купить аккаунты в различных играх и социальных сетях можно здесь @donate008', reply_markup=inline_markup)

        json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
        json_data["Аккаунты"] += 1
        with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)
        # bot.send_message(message.chat.id, akk, reply_markup=start_markup(message.chat.id, text='🚫 Отмена'))
        # update_state(message, AKK)
    elif message.text == '🌐eSIM сим-карты':
        eSIM(message)
    elif message.text == "⭐️Отзывы":
        json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
        json_data["Отзывы"] += 1
        with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton(text = "⭐️Отзывы", callback_data = 'get_feedback')) #url = 'https://google.com'))
        channel = types.InlineKeyboardButton("⚡️Канал с отзывами", url="https://t.me/TGPayTop")
        inline_markup.add(channel)
        bot.send_message(message.chat.id, "✅Здесь вы можете посмотреть отзывы наших клиентов", reply_markup = inline_markup)
    elif message.text == "👨‍💻Администратор":
        json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
        json_data["Администратор"] += 1
        with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)
        inline = types.InlineKeyboardMarkup()
        inline.add(types.InlineKeyboardButton('Написать в Support 👨‍💻', url="https://t.me/TGPaySupport_bot"))
        bot.send_message(message.chat.id, "💬 <b>Поддержка TGPay</b>\n\nЕсли у вас возникли вопросы, проблемы с заказом или вы хотите оставить предложение — пишите нам 👇", parse_mode="HTML", reply_markup=inline)
    elif message.text == "💼Наши партнёры":
        json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
        json_data["Наши партнёры"] += 1
        with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)
        bot.send_message(message.chat.id, partner)
    elif message.text == "❇️Профиль":
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("Пополнить баланс", callback_data="add_balanse"))
        inline_markup.add(types.InlineKeyboardButton("🧮 Калькулятор", callback_data="calculator"))
        inline_markup.add(types.InlineKeyboardButton("Вывод средств", callback_data="withdraw_bal"))
        inline_markup.add(types.InlineKeyboardButton("История", callback_data="get_history"))
        inline_markup.add(types.InlineKeyboardButton("Реферальная система", callback_data="ref_system"))

        cabinet_text = get_cabinet(message.chat.id).replace('`', '<code>', 1).replace('`', '</code>', 1)
        bot.send_message(message.chat.id, cabinet_text, parse_mode="HTML", reply_markup=inline_markup)
    elif message.text == "📋Правила":
        json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
        json_data["Правила"] += 1
        with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("✍️Связаться с нами", url="https://t.me/TGPaySupport_bot"))
        inline_markup.add(types.InlineKeyboardButton("Закрыть", callback_data="close"))
        bot.send_message(message.chat.id, rules, reply_markup = inline_markup)
    elif message.text == "⌨️Ввести промокод":
        json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
        json_data["Ввести промокод"] += 1
        with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)
        bot.send_message(message.chat.id, "Введите промокод", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        update_state(message, PROMOCODE_USER)
    elif message.text == "📲Подключение связи+":
        svyaz(message)
    elif message.text == "⚡️VPN⚡️" or text in VPN_KEYWORDS:
        VPN(message)


    elif message.text == "🛜Интернет":

        json_data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
        json_data["Интернет"] += 1
        with open("analytic_clicks_data.json", "w", encoding="utf-8") as json_file:
            json.dump(json_data, json_file, ensure_ascii=False, indent=4)

        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("RostNet", callback_data="RostNet"))
        bot.send_message(message.chat.id, '🟢 Выберите провайдера', reply_markup = inline_markup)
    elif message.text == "💵Курс валют":
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_button1 = types.InlineKeyboardButton(f"🇺🇸USD {str(get_kurs('usd'))}", callback_data="vusd")
        inline_button2 = types.InlineKeyboardButton(f"🇪🇺EUR {str(get_kurs('eur'))}", callback_data="veur")
        inline_button3 = types.InlineKeyboardButton(f"🇹🇷TRY {str(get_kurs('try'))}", callback_data="vtry")
        inline_button4 = types.InlineKeyboardButton(f"🇺🇦UAH {str(get_kurs('uah'))}", callback_data="vuah")
        inline_markup.add(inline_button1)
        inline_markup.add(inline_button2)
        inline_markup.add(inline_button3)
        inline_markup.add(inline_button4)
        bot.send_message(message.chat.id, '🟢 Выберите валюту', reply_markup = inline_markup)
    elif message.text == "📊Статистика":
        db = sqlite3.connect('files/users.db', timeout=10)
        cursor = db.cursor()
        cursor.execute(f'SELECT * FROM users')
        data = cursor.fetchall()
        db.close()
        bot.send_message(message.chat.id, f'Количество пользователей: {len(data)}')
    elif message.text == '📫 Рассылка':
        # Сброс параметров предыдущей рассылки
        add_data('button_action', '', message.chat.id)
        add_data('action_image', '', message.chat.id)
        add_data('buttons_json', '[]', message.chat.id)
        add_data('send_target', '', message.chat.id)
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("Всем", callback_data="send_to_all"))
        inline_markup.add(types.InlineKeyboardButton("Одному (по ID)", callback_data="send_to_one"))
        inline_markup.add(types.InlineKeyboardButton("Списку ID", callback_data="send_to_list"))
        inline_markup.add(types.InlineKeyboardButton("Неактивным", callback_data="send_to_inactive"))
        bot.send_message(message.chat.id, 'Кому отправить?', reply_markup=inline_markup)


    elif message.text == '🌟 Получить награду 🌟':
        update_state(message, DONATION_AMOUNT)
        bot.send_message(message.chat.id,
            '🌟 <b>Получить награду</b> 🌟\n\nПришлите сумму которую вы пожертвовали на разработку приложения',
            parse_mode='HTML', reply_markup=start_markup(message.chat.id, text='🚫 Отмена'))

    elif message.text == "🚫 Отмена":
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Отменили ввод данных", reply_markup = markup)
        delete_file(message.chat.id)
        update_state(message, START)
    elif message.text == "🗄Баланс пользователей":
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("Баланс по ID", callback_data="admin_balans_id"))
        inline_markup.add(types.InlineKeyboardButton("Баланс общий", callback_data="admin_balans_all"))
        inline_markup.add(types.InlineKeyboardButton("💰 История баланса по ID", callback_data="admin_balance_history_id"))
        bot.send_message(message.chat.id, '💳Выберите способ оплаты:', reply_markup=inline_markup)
    elif message.text == "🧮Калькулятор":
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_button1 = types.InlineKeyboardButton(f"🇺🇸USD", callback_data="vusd_calc")
        inline_button2 = types.InlineKeyboardButton(f"🇪🇺EUR", callback_data="veur_calc")
        inline_button3 = types.InlineKeyboardButton(f"🇹🇷TRY", callback_data="vtry_calc")
        inline_button4 = types.InlineKeyboardButton(f"🇺🇦UAH", callback_data="vuah_calc")
        inline_markup.add(inline_button1)
        inline_markup.add(inline_button2)
        inline_markup.add(inline_button3)
        inline_markup.add(inline_button4)
        bot.send_message(message.chat.id, '🟢 Выберите валюту', reply_markup = inline_markup)
    elif message.text == '🪪Упраление картами':
        global Nicepay
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton(f"Добавить карту", callback_data="add_card"))
        inline_markup.add(types.InlineKeyboardButton(f"Удалить карту", callback_data="del_card_1"))
        data = json.load(open("replishment_active.json", encoding="utf-8"))
        if data["active"]:
            inline_markup.add(types.InlineKeyboardButton(f"Остановить пополнение картами", callback_data="stop_replishment"))
        else:
            inline_markup.add(types.InlineKeyboardButton(f"Активировать пополнение картами", callback_data="active_replishment"))
        if data["time_active"]:
            inline_markup.add(types.InlineKeyboardButton(f"Остановить автовыключение", callback_data="stop_auto_replishment"))
        else:
            inline_markup.add(types.InlineKeyboardButton(f"Активировать автоключение", callback_data="active_auto_replishment"))
        if Nicepay:
            inline_markup.add(types.InlineKeyboardButton(f"Остановить пополнение с NicePay", callback_data="stop_nicepay"))
        else:
            inline_markup.add(types.InlineKeyboardButton(f"Активировать пополнение с NicePay", callback_data="active_nicepay"))
        bot.send_message(message.chat.id, 'Выберите действие', reply_markup = inline_markup)
    elif message.text == "🔷Настройка eSIM":
        esim_answer_path = os.path.join(BASE_DIR, "eSIM", "esim_answer.json")
        try:
            with open(esim_answer_path, encoding="utf-8") as file:
                esim_data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            esim_data = {}
            os.makedirs(os.path.join(BASE_DIR, "eSIM"), exist_ok=True)
            with open(esim_answer_path, "w", encoding="utf-8") as file:
                json.dump({}, file)
        operators = ["Vodafone", "Kievstar", "Lifecell", "FranceUnlimited", "France35GB"]
        count = []
        for operator in operators:
            if esim_data.get(operator):
                items = len(esim_data[operator])
                count.append(items)
            else:
                items = 0
                count.append(items)
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton(f"🔴 Vodafone ({count[0]})", callback_data="admin_Vodafone", icon_custom_emoji_id="5267292959182697142"))
        inline_markup.add(types.InlineKeyboardButton(f"🔵 Киевстар ({count[1]})", callback_data="admin_Kievstar", icon_custom_emoji_id="5267061554934723857"))
        inline_markup.add(types.InlineKeyboardButton(f"🟡 Lifecell ({count[2]})", callback_data="admin_Lifecell", icon_custom_emoji_id="5267284102960131913"))
        inline_markup.add(types.InlineKeyboardButton(f"🇫🇷 Франция безлимит ({count[3]})", callback_data="admin_FranceUnlimited"))
        inline_markup.add(types.InlineKeyboardButton(f"🇫🇷 Франция 35 ГБ ({count[4]})", callback_data="admin_France35GB"))
        inline_markup.add(types.InlineKeyboardButton("🗑Удаление товаров у категории", callback_data="esim_delete"))
        inline_markup.add(types.InlineKeyboardButton("📋 Посмотреть eSIM в базе", callback_data="esim_view_stock"))
        bot.send_message(message.chat.id, 'Выберите тариф для изменения', reply_markup = inline_markup)
    elif message.text == "👀Выставить счет":
        bot.send_message(message.chat.id, 'Введите ID пользователя', reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        update_state(message, INVOICE_USER)
    elif message.text == "📝Добавить промокод":
        bot.send_message(message.chat.id, 'Введите промокод', reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        update_state(message, PROMOCODE)
    elif message.text == "🖌Изменить баланс пользователя":
        bot.send_message(message.chat.id, 'Введите ID пользователя:', reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        update_state(message, SET_ID_BALANS)
    elif message.text == "TEST_CREATE_REQUEST♦":
        bot.send_message(message.chat.id, 'Введите ID пользователя:', reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        update_state(message, CREATE_NUM_REQUEST)

    elif message.text == "Юмани тест":
        bot.send_message(message.chat.id, "Введите сумму платежа", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        update_state(message, YOOMANY)

    elif message.text == "🟣Юмани реквизиты":
        # bot.send_message(message.chat.id, "Введите номер для реквизита", reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("Добавить реквизиты", callback_data="add_yoomoney_requisites"))
        # inline_markup.add(types.InlineKeyboardButton("Добавить реквизиты", callback_data="add_yoomoney_requisites_test"))
        # inline_markup.add(types.InlineKeyboardButton("Удалить реквизиты", callback_data="delete_yoomoney_requisites"))
        bot.send_message(message.chat.id, 'Выберите что хотите сделать', reply_markup = inline_markup)

    elif message.text == "🔗Реферальные значения":
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton("Изменить проценты", callback_data="ref_procent_change"))
        inline_markup.add(types.InlineKeyboardButton("Изменить множитель для гривны", callback_data="ref_hryvnia_change"))
        bot.send_message(message.chat.id, 'Выберите что хотите сделать', reply_markup = inline_markup)

    elif message.text == "👨Написать человеку":
        bot.send_message(message.chat.id, 'Введите ID пользователя:', reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        update_state(message, MESSAGE_TO_USER)

    elif message.text == "💰Отчет по деньгам":
        update_money_report_for_day()
        update_money_report_for_month()
        day_report = get_money_report_for_day()
        month_report = get_money_report_for_month()
        message_text = f"<b>За день</b>: {day_report}\n\n<b>За месяц</b>: {month_report}"
        bot.send_message(message.chat.id, message_text, parse_mode="HTML")
    
    elif message.text == "💸 Аннулировать реф. баланс":
        if message.chat.id in admins:
            bot.send_message(message.chat.id, "Введите ID пользователя, которому нужно аннулировать реферальный баланс:",
                             reply_markup=start_markup(message.chat.id, text='🚫 Отмена'))
            update_state(message, RESET_REF_BALANCE)

    elif message.text == "📑Список пользоватилей":
        if message.chat.id in admins:
            try:
                try:
                    update_inactive_users()
                except Exception as e:
                    print(f'[export] update_inactive_users error: {e}')
                bot.send_document(message.chat.id, export_db_to_excel(), visible_file_name='Юзеры.xlsx')
            except Exception as e:
                bot.send_message(message.chat.id, f'❌ Ошибка экспорта: {e}')
    
    elif message.text == "🖌Изменить баланс модератора":
        if message.chat.id in admins:
            bot.send_message(message.chat.id, 'Введите ID модератора:', reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
            update_state(message, SET_MODERATOR_ID_BALANS)
            

    elif message.text == "📈Посмотреть аналитику данных":
        data = json.load(open("analytic_clicks_data.json", encoding="utf-8"))
        message_text = []
        for key, value in data.items():
            if type(value) != int:
                if value.get("clicks"):
                    message_text.append(f"{key}: {value['clicks']}\n")
                else:
                    message_text.append(f"{key}:\n")
                for sub_key, sub_value in value.items():
                    if type(sub_value) == dict:
                        key_data = sub_key
                        value_data = sub_value
                        value_check = True
                        indent_space = 2
                        space = "    "
                        while value_check:
                            if value_data.get("clicks"):
                                message_text.append(f"{(indent_space-1)*space}{key_data}: {value_data['clicks']}\n")
                            else:
                                message_text.append(f"{(indent_space-1)*space}{key_data}:\n")
                            # message_text.append(f"{(indent_space-1)*space}{key_data}: {value_data['clicks']}\n")
                            for key, value in value_data.items():
                                if key != "clicks":
                                    if type(value) == dict:
                                        value_data = value
                                        key_data = key
                                        value_check = True
                                    else:
                                        message_text.append(f"{space*indent_space}{key}: {value}\n")
                                        value_check = False
                            indent_space += 1
                    else:
                        if sub_key != "clicks":
                            message_text.append(f"    {sub_key}: {sub_value}\n")
            else:
                message_text.append(f"{key}: {value}\n")
            message_text.append(f"➖➖➖➖➖➖➖\n")
        bot.send_message(message.chat.id, "".join(message_text).strip())
        count_data = get_json_data(file="count_link_clicks.json")
        message_list = []
        for key, value in count_data.items():
            message_list.append(f"{key}: {value}\n")
        bot.send_message(message.chat.id, f"Переходы по ссылкам:\n\n{''.join(message_list)}")

    elif message.text == "Добавить переходную ссылку":
        bot.send_message(message.chat.id, 'Напишите ключевое слово которое будет указано в ссылке(без использования знака "=" и пробелов)', reply_markup = start_markup(message.chat.id, text='🚫 Отмена'))
        update_state(message, TRANSITIONAL_LINK)
    elif message.text == "Баланс Благотворительности":
        balance = get_admin_balance()
        bot.send_message(message.chat.id, f"Баланс: {balance}р.")

    elif get_state(message) == DIALOG:
        inline_markup = types.InlineKeyboardMarkup(row_width=True)
        inline_markup.add(types.InlineKeyboardButton(text = "Ответить", callback_data="otvet"))
        bot.send_message(adminGroup, f"Пользователь: @{message.chat.username} \n🎩Ранг: {get_user_rank(message.chat.id)}\nid: {message.chat.id}\nСообщение: {message.text}", reply_markup=inline_markup)
    else:
        markup = start_markup(message.chat.id)
        bot.send_message(message.chat.id, "Выберите что нибудь", reply_markup = markup)
        update_state(message, START)


def is_valid_phone_number(text):
    # Удаляем пробелы, тире, скобки и т.д.
    cleaned = re.sub(r"[^\d+]", "", text)

    # Проверка: начинается с + (необязательно), за ним от 10 до 15 цифр
    pattern = r"^\+?\d{10,15}$"
    return re.match(pattern, cleaned) is not None

if __name__ == "__main__":
    import signal, os, sys

    def _stop_bot(sig, frame):
        print("\nБот остановлен.")
        bot.stop_polling()
        sys.exit(0)

    signal.signal(signal.SIGINT, _stop_bot)
    signal.signal(signal.SIGTERM, _stop_bot)

    print('bot activated')
    data = json.load(open("replishment_active.json", encoding="utf-8"))
    start_penalty_checker(bot, adminGroup)
    while True:
        try:
            bot.polling(none_stop=False, interval=0)
        except Exception as e:
            print(f"[POLLING] Ошибка соединения: {e}. Перезапуск через 5 сек...")
            import time as _time
            _time.sleep(5)

