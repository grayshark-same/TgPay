from calendar import month
import hashlib
import sqlite3
from datetime import datetime
import datetime as dt
import json
import os
from telebot import types
from hashlib import md5
import requests
import base64
import logging
import pytz
import textwrap
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
from pilmoji.source import GoogleEmojiSource
import pandas as pd
from io import BytesIO

FONT_PATH = 'OpenSans-Bold.ttf'
LOGO_PATH = 'logo.png'
BACKGROUND_COLOR = (86, 48, 187, 255)
CARD_COLOR = (142, 111, 219, 255)
TEXT_COLOR = (255, 255, 255, 255)
TEXT_WIDTH = 40
IMAGE_WIDTH = 1396
IMAGE_HEIGHT = 499
CHANNEL_ID = '@TGPayTop'
TEMP_FILE = "files/temp_withdraw.json"

def load_temp():
    if not os.path.exists(TEMP_FILE):
        return {}
    with open(TEMP_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_temp(data):
    with open(TEMP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def set_user_temp(user_id, key, value):
    data = load_temp()
    if str(user_id) not in data:
        data[str(user_id)] = {}
    data[str(user_id)][key] = value
    save_temp(data)

def get_user_temp(user_id):
    data = load_temp()
    return data.get(str(user_id), {})

def clear_user_temp(user_id):
    data = load_temp()
    if str(user_id) in data:
        del data[str(user_id)]
        save_temp(data)

def create_review_image(text, user_name, date, filename):
    font_large = ImageFont.truetype(FONT_PATH, 40)
    font_small = ImageFont.truetype(FONT_PATH, 36)

    logo = Image.open(LOGO_PATH).convert("RGBA").resize((160, 160), Image.Resampling.LANCZOS)
    logo_mask = Image.new("L", logo.size, 0)
    draw_mask_logo = ImageDraw.Draw(logo_mask)
    draw_mask_logo.ellipse((0, 0, logo.size[0], logo.size[1]), fill=255)
    logo.putalpha(logo_mask)

    avatar = Image.open("avatar.png").convert("RGBA").resize((100, 100), Image.Resampling.LANCZOS)
    avatar_mask = Image.new("L", avatar.size, 0)
    draw_mask_avatar = ImageDraw.Draw(avatar_mask)
    draw_mask_avatar.ellipse((0, 0, avatar.size[0], avatar.size[1]), fill=255)
    avatar.putalpha(avatar_mask)

    img = Image.new("RGBA", (IMAGE_WIDTH, IMAGE_HEIGHT), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)

    left_margin = 30
    right_margin = 240
    block_left = left_margin
    block_right = IMAGE_WIDTH - right_margin
    block_margin_x = 200
    block_top = 80
    block_bottom = 419
    draw.rounded_rectangle(
        (block_left, block_top, block_right, block_bottom),
        radius=60,
        fill=(142, 111, 219, 255)
    )

    avatar_x = 80
    avatar_y = 116
    img.paste(avatar, (avatar_x, avatar_y), avatar)

    avatar_center_y = avatar_y + avatar.size[1] // 2

    name_x = avatar_x + avatar.size[0] + 30
    name_y = avatar_center_y - font_small.getbbox(user_name)[3] // 2
    draw.text((name_x, name_y), user_name, font=font_small, fill=TEXT_COLOR)

    text_area_x = 130
    text_area_y = 240
    text_area_width = block_right - block_left - 2 * (text_area_x - block_left)
    text_area_height = block_bottom - text_area_y - 20

    wrapped_text, fitted_font = fit_text(
        draw, text, FONT_PATH,
        text_area_width, text_area_height,
        max_font_size=40
    )

    with Pilmoji(img, source=GoogleEmojiSource()) as pilmoji:
        pilmoji.text((text_area_x, text_area_y), wrapped_text, font=fitted_font, fill=TEXT_COLOR, spacing=6)

    date_width = font_small.getlength(date)
    date_x = 1175
    date_y = block_bottom + 10
    draw.text((date_x, date_y), date, font=font_small, fill=TEXT_COLOR)

    logo_x = IMAGE_WIDTH - 200
    logo_y = 60
    img.paste(logo, (logo_x, logo_y), logo)

    img.save(filename)
def fit_text(draw, text, font_path, max_width, max_height, max_font_size, min_font_size=20):
    for font_size in range(max_font_size, min_font_size - 1, -2):
        font = ImageFont.truetype(font_path, font_size)
        wrapped = textwrap.fill(text, width=40)
        text_bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=6)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        if text_width <= max_width and text_height <= max_height:
            return wrapped, font
    return textwrap.fill(text, width=40), ImageFont.truetype(font_path, min_font_size)
def check_time_active(data: json):
    now_time = datetime.now(pytz.timezone('Europe/Moscow')).time()

    start_time = dt.time(0, 30) 
    end_time = dt.time(6, 0) 

    if start_time <= now_time <= end_time:
        data["active"] = 0
        with open("replishment_active.json", "w", encoding="utf-8") as file:
            json.dump(data, file)
    else:
        data["active"] = 1
        with open("replishment_active.json", "w", encoding="utf-8") as file:
            json.dump(data, file)  

# Отчет об пополнениях/деньгах

# Получение отчета за день
def get_money_report_for_day():
    data = json.load(open("money_report.json", encoding="utf-8"))
    return data["day_report"]["money"]

# Получение отчета за месяц
def get_money_report_for_month():
    data = json.load(open("money_report.json", encoding="utf-8"))
    return data["month_report"]["money"]

# Обновление отчета за день
def update_money_report_for_day(money=0):
    logging.info("за день")
    data = json.load(open("money_report.json", encoding="utf-8"))
    if data["day_report"]["date"]:
        day_date = datetime.strptime(data["day_report"]["date"], "%Y-%m-%d %H:%M:%S")
        day_delta = dt.timedelta(days=1)
        if datetime.now() >= day_date + day_delta: # если прошел день
            data["day_report"]["date"] = datetime.now().strftime(format="%Y-%m-%d %H:%M:%S")
            data["day_report"]["money"] = money
            with open("money_report.json", "w", encoding="utf-8") as file:
                json.dump(data, file)
        else:
            now_money = data["day_report"]["money"]
            data["day_report"]["money"] = int(now_money) + int(money)
            with open("money_report.json", "w", encoding="utf-8") as file:
                json.dump(data, file)
    else:
        data["day_report"]["date"] = datetime.now().strftime(format="%Y-%m-%d %H:%M:%S")
        data["day_report"]["money"] = money
        with open("money_report.json", "w", encoding="utf-8") as file:
            json.dump(data, file) 
    logging.info(data)

# Обновление отчета за месяц
def update_money_report_for_month(money=0):
    logging.info("за мес")
    data = json.load(open("money_report.json", encoding="utf-8"))
    if data["month_report"]["date"]:
        month_date = datetime.strptime(data["month_report"]["date"], "%Y-%m-%d %H:%M:%S")
        month_delta = dt.timedelta(days=30)
        if datetime.now() >= month_date + month_delta: # если прошел месяц
            data["month_report"]["date"] = datetime.now().strftime(format="%Y-%m-%d %H:%M:%S")
            data["month_report"]["money"] = money
            with open("money_report.json", "w", encoding="utf-8") as file:
                json.dump(data, file)
        else:
            now_money = data["month_report"]["money"]
            data["month_report"]["money"] = int(now_money) + int(money)
            with open("money_report.json", "w", encoding="utf-8") as file:
                json.dump(data, file)
    else:
        data["month_report"]["date"] = datetime.now().strftime(format="%Y-%m-%d %H:%M:%S")
        data["month_report"]["money"] = money
        with open("money_report.json", "w", encoding="utf-8") as file:
            json.dump(data, file) 
    logging.info(data)

def get_bank_from_card(card_number):
    bin_code = card_number.replace(" ", "")[:6]

    url = f"https://data.handyapi.com/bin/{bin_code}"
    headers = {"x-api-key":"HAS-0YFbtNxw9H6pMdTGPm235B0rjz"}

    resp = requests.get(url, headers=headers)

    if resp.status_code != 200:
        return None

    data = resp.json()
    return data.get("Issuer")

#Вывод средств
def withdraw_balance(id, amount):
    update_last_activity(id)
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()

    cursor.execute("SELECT balans FROM users WHERE id = ?", (id,))
    row = cursor.fetchone()
    if row is None:
        db.close()
        return "user_not_found"
    balance = row[0]
    if balance >= amount:
        print(f"DEBUG: amount = {amount}, balans = {balance}")
        new_balance = balance - amount
        cursor.execute(
            "UPDATE users SET balans = ? WHERE id = ?",
            (new_balance, id)
        )
        now = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        cursor.execute(
            'INSERT INTO balance_log (user_id, amount, balance_after, description, created_at) VALUES (?, ?, ?, ?, ?)',
            (id, -amount, new_balance, 'Вывод средств', now)
        )
        db.commit()
        db.close()
        return "success"
    else:
        print(f"DEBUG: amount = {amount}, balance = {balance}")
        db.close()
        return balance


# Реф. система

# Получение баланса юзера
def get_ref_balance(user_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor() 
    cursor.execute(f'SELECT referr_balance FROM users WHERE id = ?', (user_id,))
    data = cursor.fetchone()
    return data[0]

# Получение реферала
def get_ref_user(user_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor() 
    cursor.execute(f'SELECT referr_id FROM users WHERE id = ?', (user_id,))
    data = cursor.fetchone()
    print(data[0])
    return data[0]

# Получение реферальных юзеров
def get_ref_users(user_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor() 
    cursor.execute(f'SELECT COUNT(*) FROM users WHERE referr_id = ?', (user_id,))
    data = cursor.fetchone()
    return data[0]

# Снятие суммы для реферала
def minus_balance_ref(user_id, value):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    value = float(value)
    sql_query = "UPDATE users SET referr_balance = referr_balance - ? WHERE id = ?"
    cursor.execute(sql_query, (value , user_id))
    db.commit()
    db.close()

# Аннулирование реферального баланса пользователя
def reset_ref_balance(user_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute("UPDATE users SET referr_balance = 0 WHERE id = ?", (user_id,))
    db.commit()
    db.close()

# Добавление суммы для реферала
def add_balance_ref(reffered_user_id, value, trans_type):
    referrer_id = get_ref_user(reffered_user_id)
    if not referrer_id:
        return 0
    if not trans_type:
        return 0

    try:
        db = sqlite3.connect('files/users.db')
        cursor = db.cursor()

        user_type = get_user_type(reffered_user_id)
        procents = json.load(open("ref_data.json", encoding="utf-8"))['ref_procent']

        if trans_type not in procents:
            db.close()
            return 0
        if user_type not in procents[trans_type]:
            db.close()
            return 0

        procent = int(procents[trans_type][user_type])
        ref_value = round(float(value) * procent / 100, 2)

        cursor.execute(
            "UPDATE users SET referr_balance = referr_balance + ? WHERE id = ?",
            (ref_value, referrer_id)  # ← ref_value вместо value
        )
        db.commit()
        db.close()
        return ref_value

    except Exception as e:
        print(f"Ошибка add_balance_ref: {e}")
        return 0

# Добавление реферала 
def add_ref(referr_id, user_id):
    regestry(user_id)
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    sql_query = f"UPDATE users SET referr_id = ? WHERE id = ?"
    cursor.execute(sql_query, (referr_id, user_id))
    cursor.execute("UPDATE users SET ref_count = ref_count + 1 WHERE id = ?", (referr_id,))
    db.commit()
    db.close()

# Юмани хелп функции
def get_requisites():
    data = json.load(open("yoomany_requisites.json", encoding="utf-8"))
    if data:
        return data
    return None

# MERCHANT

#Получение ссылки оплаты    
def get_merchant_link(price: str):
    headers = {
        "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiJpYnRyOGx0QjVmZ0FNMjBXRkVIV1RCVlVPMDEzIiwiZGF0ZSI6IjIwMjQtMDctMDNUMTk6MzU6NTUuOTU1WiIsImlhdCI6MTcyMDAzNTM1NX0.gLKOo0JtnmOrYjasAopN1trppfusIo07jarD3-gzvnI",
        "Content-Type": "application/json"
    }
    data = {
        "isPartnerFee": "true",
        "pricing": {
            "local": {
            "amount": f"{price}",
            "currency": "RUB"
            }
        }
    }
    response = requests.post(url="https://api.merchant001.io/v1/transaction/merchant", headers=headers, data=json.dumps(data))
    return response.json()

#Получение ссылки оплаты payok
def get_link(amount: str):
    number = json.load(open("purchase_number.json"))
    payment = str(number["application_number"])
    shop = '12117'
    desc = 'Пополнение баланса'
    secret_key = "bcd206cf2a1c1752ff5a5cfb32269886"
    currency = 'RUB'

    # Формируем данные для подписи
    data = [amount, payment, shop, currency, desc, secret_key]
    sign = md5('|'.join(data).encode('utf-8')).hexdigest()

    # Формируем URL
    url = f'https://payok.io/pay?amount={amount}&payment={payment}&shop={shop}&desc={desc}&sign={sign}'

    # Обновляем номер заявки
    number["application_number"] += 1

    # Сохраняем обновленные данные обратно в JSON файл
    with open("purchase_number.json", "w", encoding="utf-8") as file:
        json.dump(number, file, indent=2, ensure_ascii=False)

    return url

# CRYPTOMUS

# #Получение ссылки оплаты cryptomus
def get_cryptomus_link(data: dict):
    api_key = "gGnc7sHMN3ZFTAauGEskARYSyGnZ928HbkP8nlmdhMdy6rPJaz5Mwari1Z7qieNNxm4Og8Xse8KYaBnAw16uf276upiwloKEYHsDniObrQbcRFFYUEPDXAHQrV8Ytr9j"
    merchant_id = "988f4211-6ec5-4bb0-976e-88dd365d9927"
    encoded_data = base64.b64encode(
        json.dumps(data).encode("utf-8")
    ).decode("utf-8")

    sign = hashlib.md5(f"{encoded_data}{api_key}".encode("utf-8")).hexdigest()

    headers = {
        "merchant": merchant_id,
        "sign": sign    
    }

    response = requests.post(url="https://api.cryptomus.com/v1/payment", json=data, headers=headers)

    return response.json()

# Nicepay
def get_nicepay_link(order_id: str, amount: int, currency: str, customer: str):
    nicepay_config = {
        "merchant_id": "66f9d2e88ae1fc689cdb0f93",
        "secret_key": "StYak-jgSCq-HVw4y-HuRPA-de39U"
    }

    data = {
        "merchant_id": nicepay_config["merchant_id"],
        "secret": nicepay_config["secret_key"],
        "order_id": order_id,
        "amount": amount,
        "currency": currency,
        "customer": customer,
        "success_url": "https://olexandrapi.tw1.ru/nicepay"
    }

    response = requests.post(url="https://nicepay.io/public/api/payment", json=data)
    return response.json()

def check_nicepay_payment(payment_id : str):
    nicepay_config = {
        "merchant_id": "66f9d2e88ae1fc689cdb0f93",
        "secret_key": "StYak-jgSCq-HVw4y-HuRPA-de39U"
    }
    data = {
        "merchant_id": nicepay_config["merchant_id"],
        "secret": nicepay_config["secret_key"],
        "payment": payment_id,
    }
    response = requests.post(url="https://nicepay.io/public/api/h2hConfirmPaid", json=data)
    return response.json()
def get_payment_info(payment_id: str):
    nicepay_config = {
        "merchant_id": "66f9d2e88ae1fc689cdb0f93",
        "secret_key": "StYak-jgSCq-HVw4y-HuRPA-de39U"
    }
    data = {
        "merchant_id": nicepay_config["merchant_id"],
        "secret": nicepay_config["secret_key"],
        "payment": payment_id,
    }
    response = requests.post(url="https://nicepay.io/public/api/h2hPaymentInfo", json=data)
    return response.json()
def get_promocode(chat_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor() 
    cursor.execute(f'SELECT promocode FROM users WHERE id = ?', (chat_id,))
    data = cursor.fetchone()
    if data:
        db.close()
        if data[0] != None:
            try:
                with open("promocode.json", encoding="utf-8") as file:
                    json_data = json.load(file)
                if json_data[data[0]]["procent"]:
                    pass
                return data[0]
            except:
                db = sqlite3.connect('files/users.db')
                cursor = db.cursor()
                cursor.fetchone()
                cursor.execute('UPDATE users SET promocode = ? WHERE id = ?', (None, chat_id,))
                db.commit()
                db.close()
        return None
    else:
        regestry(chat_id)
        return None

def delete_promocode(chat_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute('UPDATE users SET promocode = ? WHERE id = ?', (None, chat_id,))
    db.commit()
    db.close()

def add_promocode(chat_id, promocode):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor() 
    cursor.execute(f'SELECT date,balans FROM users WHERE id = ?', (chat_id,))
    data = cursor.fetchone()
    if data:
        cursor.execute('UPDATE users SET promocode = ? WHERE id = ?', (promocode, chat_id,))
        db.commit()
        db.close()
    else:
        regestry(chat_id)
        cursor.execute('UPDATE users SET promocode = ? WHERE id = ?', (promocode, chat_id,))
        db.commit()
        db.close()

# Проверка наличия пользователя

def check_user(user_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT id FROM users WHERE id = ?', (user_id,))
    data = cursor.fetchone()
    return data


DB_PATH = "files/users.db"
def get_total_spent(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT total_spent FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else 0
def get_donation_rank(user_id):
    try:
        db = sqlite3.connect('files/donations.db')
        cursor = db.cursor()
        cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM donations WHERE user_id = ?', (user_id,))
        total = cursor.fetchone()[0]
        db.close()
    except Exception:
        return ''
    if total < 500:
        return ''
    elif total < 1000:
        return '<tg-emoji emoji-id="5364209244109282901">👑</tg-emoji>'
    elif total < 3000:
        return '<tg-emoji emoji-id="5361664617720325706">👑</tg-emoji>'
    elif total < 5000:
        return '<tg-emoji emoji-id="5361701438474953213">👑</tg-emoji>'
    elif total < 10000:
        return '<tg-emoji emoji-id="5364119608141816446">👑</tg-emoji>'
    else:
        return '<tg-emoji emoji-id="5363918225715243425">👑</tg-emoji>'

def get_user_rank(user_id):
    total = get_total_spent(user_id)
    print(user_id)
    if str(user_id) == "7131879634":
        return "⚙️🛠️"
    if total == 0:
        spent_rank = "❌"
    elif total <= 1000:
        spent_rank = "✅"
    elif total <= 10000:
        spent_rank = "💎"
    elif total <= 100000:
        spent_rank = "🐳"
    else:
        spent_rank = "🕶"
    donation_rank = get_donation_rank(user_id)
    if donation_rank:
        return f"{spent_rank} {donation_rank}"
    return spent_rank
def update_total_spent(user_id, summ):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT total_spent FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return False

    current_spent = row[0] if row[0] is not None else 0
    new_total = current_spent + summ

    cursor.execute(
        "UPDATE users SET total_spent = ? WHERE id = ?",
        (new_total, user_id)
    )

    conn.commit()
    conn.close()
    return True
def get_admin_balance():
    with sqlite3.connect(DB_PATH) as db:
        cursor = db.cursor()
        cursor.execute(
            "SELECT COALESCE(admin_balance, 0) FROM users WHERE id = ?",
            (6732194898,)
        )
        result = cursor.fetchone()
        return result[0] if result else 0
def get_vpn_link(username, device_limit, days_valid):
    url = "http://92.112.125.42:5000/create_user"
    headers = {
        "Authorization": "Bearer tgpayxvpn",
        "Content-Type": "application/json",
    }

    data = {
        "username": username,
        "device_limit": int(device_limit),
        "days_valid": int(days_valid)
    }

    try:
        r = requests.post(url, headers=headers, json=data, timeout=10)
        status = r.status_code

        try:
            result = r.json()
        except Exception:
            return {"error": f"Invalid JSON: {r.text}"}, status

        links = result.get("links") or ([result.get("link")] if result.get("link") else [])
        result["links"] = links

        return result, status

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}, 500

#Пробная подписка впн
def get_trial_vpn(user_id, username):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute("SELECT trial FROM users WHERE id = ?", (user_id,))
    data = cursor.fetchone()
    if data[0] == 0:
        cursor.execute("UPDATE users SET trial = ? WHERE id = ?", (1, user_id))
        db.commit()
        db.close()
        try:
            vpn_data, status = get_vpn_link(username, 1, 2)
            links = vpn_data.get("links") or [vpn_data.get("link")]
            links = [l for l in links if l]
            links_text = "\n\n".join([f"🔗 Ключ {i + 1}:\n`{link}`" for i, link in enumerate(links)])
            return links_text
        except Exception as exc:
            return f"error: {exc}"
    else:
        db.close()
        return "Nah"

#Регистрация
def regestry(chat_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT id FROM users WHERE id = ?', (chat_id,))
    data = cursor.fetchone()
    if not data:
        date = datetime.now().date().strftime('%d.%m.%Y')
        sql_query = f"INSERT INTO users (id,date,balans) VALUES (?,?,?)"
        cursor.execute(sql_query, (
            chat_id,
            date,
            0
            ))
        db.commit()
    db.close()
#Кабинет
def update_balance(chat_id, amount):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()

    cursor.execute('SELECT balans FROM users WHERE id = ?', (chat_id,))
    data = cursor.fetchone()

    if data is not None:
        new_balance = data[0] + amount
        cursor.execute('UPDATE users SET balans = ? WHERE id = ?', (new_balance, chat_id))
        now = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        cursor.execute(
            'INSERT INTO balance_log (user_id, amount, balance_after, description, created_at) VALUES (?, ?, ?, ?, ?)',
            (chat_id, amount, new_balance, 'Изменение баланса', now)
        )
        db.commit()
        db.close()
        return f'Баланс обновлен: {new_balance}₽'
    else:
        db.close()
def get_cabinet(chat_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT date,balans,promocode FROM users WHERE id = ?', (chat_id,))
    data = cursor.fetchone()
    if data:
        db.close()
        spent_rank = get_user_rank(chat_id)
        donation_rank = get_donation_rank(chat_id)
        donation_line = f'{donation_rank}\n' if donation_rank else ''
        rank_line = f'\n🎖 Ранг: {spent_rank}'
        if data[2]:
            kabinet = f"""{rank_line}\n🖥 Кабинет\n🆔 `{chat_id}`\n💵Баланс: {data[1]}₽\n⏱Дата регистрации: {data[0]}\nДействующий промокод: {data[2]}"""
            return kabinet
        else:
            kabinet = f"""{rank_line}\n🖥 Кабинет\n🆔 `{chat_id}`\n💵Баланс: {data[1]}₽\n⏱Дата регистрации: {data[0]}"""
            return kabinet
    else:
        regestry(chat_id)
        cursor.execute(f'SELECT date,balans FROM users WHERE id = ?', (chat_id,))
        data = cursor.fetchone()
        if data:
            db.close()
            spent_rank = get_user_rank(chat_id)
            kabinet = f"""🖥 Кабинет\n🆔 `{chat_id}`\n💵Баланс: {data[1]}₽\n⏱Дата регистрации: {data[0]}\n🎖 Ранг: {spent_rank}"""
            return kabinet
            
#Отзыв в базу
def send_feedback(message):
    db = sqlite3.connect('files/otzivi.db')
    cursor = db.cursor()
    date = datetime.now().date().strftime('%d.%m.%Y')
    sql_query = f"INSERT INTO otzivi (id,date,otziv,name) VALUES (?,?,?,?)"
    cursor.execute(sql_query, (
        message.chat.id,
        date,
        message.text,
        message.chat.first_name
        ))
    db.commit()
    db.close()

#Возвращает все отзывы
def get_feedback(flag=0):
    print('flag', flag)
    db = sqlite3.connect('files/otzivi.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT name,otziv, id FROM otzivi')
    data = cursor.fetchall()
    text = ''
    feeds = []
    n = 1
    for item in reversed(data):
        if flag==0:
            text+=f'<b>{item[0]}</b>\n{item[1]}\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n'
        else:
            text+=f'<b>{item[0]}</b>\n{item[2]}\n{item[1]}\n➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖➖\n'
        if n == 5:
            feeds.append(text)
            text = ''
            n=0
        n+=1
    db.commit()
    db.close()
    return feeds


def send_long_message(chat_id, text, bot):

    # Разбиваем сообщение на части, если оно слишком длинное
    max_length = 4096
    for i in range(0, len(text), max_length):
        part = text[i:i + max_length]
        bot.send_message(chat_id, part, parse_mode='HTML')


def feed(id, all):
    markup = types.InlineKeyboardMarkup(row_width=3)
    if id == 32423:
        pass
    else:
        markup.add(types.InlineKeyboardButton(text='⏪', callback_data=f'feed_dec_{id}'),
                    types.InlineKeyboardButton(text=f'{id}/{all}', callback_data='pass'),
                    types.InlineKeyboardButton(text='⏩', callback_data=f'feed_inc_{id}'))
    return markup
#Получение баланса
def get_balans(chat_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT balans FROM users WHERE id = ?', (chat_id,))
    data = cursor.fetchone()
    if data:
        db.close()
        return data[0]
    else:
        regestry(chat_id)
        cursor.execute(f'SELECT balans FROM users WHERE id = ?', (chat_id,))
        data = cursor.fetchone()
        db.close()
        return data[0]
    
def get_moderator_balans(mod_id, currency='uah'):
    col = 'balans_uah' if currency == 'uah' else 'balans_usd'
    db = sqlite3.connect('files/mods.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT {col} FROM mods WHERE id = ?', (mod_id,))
    row = cursor.fetchone()
    db.close()
    return row[0] if row else None

def add_mod_deposit(mod_id, summ, currency='uah'):
    col = 'balans_uah' if currency == 'uah' else 'balans_usd'
    try:
        db = sqlite3.connect('files/mods.db')
        cursor = db.cursor()
        cursor.execute('INSERT OR IGNORE INTO mods (id) VALUES (?)', (mod_id,))
        cursor.execute(f'UPDATE mods SET {col} = COALESCE({col}, 0) + ? WHERE id = ?', (float(summ), mod_id))
        db.commit()
        db.close()
        return True
    except Exception as e:
        print(f"Ошибка add_mod_deposit: {e}")
        return False

#Работа с балансом
def update_balanse(chat_id, key):
    update_last_activity(chat_id)
    
    # читаем значение из БД вместо JSON файла
    from bot import get_par
    value_str = get_par(key, chat_id)
    
    if value_str is None:
        print(f"Ошибка update_balanse: ключ '{key}' не найден для {chat_id}")
        return False

    try:
        amount = float(value_str)
    except (ValueError, TypeError) as e:
        print(f"Ошибка update_balanse: не удалось конвертировать значение '{value_str}': {e}")
        return False

    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute('SELECT balans FROM users WHERE id = ?', (chat_id,))
    data = cursor.fetchone()
    if data:
        new_balance = data[0] - amount
        cursor.execute('UPDATE users SET balans = ? WHERE id = ?', (new_balance, chat_id))
        db.commit()
        db.close()
        return True
    db.close()
    return False

#Пополнение баланса
def add_deposit(id, summ, description=None):
    update_last_activity(id)
    if str(summ).replace('.', '').replace('-', '').isdigit():
        db = sqlite3.connect('files/users.db')
        cursor = db.cursor()
        cursor.execute(f'SELECT balans FROM users WHERE id = ?', (id,))
        data = cursor.fetchone()
        summ = float(summ)
        if data:
            value=float(summ)+data[0]
            cursor.execute('UPDATE users SET balans = ? WHERE id = ?', (value, id))
            now = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
            if description is None:
                description = 'Пополнение' if summ >= 0 else 'Списание за услугу'
            cursor.execute(
                'INSERT INTO balance_log (user_id, amount, balance_after, description, created_at) VALUES (?, ?, ?, ?, ?)',
                (id, summ, value, description, now)
            )
            db.commit()
            db.close()
            return summ
        else:
            db.close()
            return 'user not found'
    else:
        return False
def change_deposit(id, summ):
    update_last_activity(id)
    if summ.replace('.', '').isdigit():
        db = sqlite3.connect('files/users.db')
        cursor = db.cursor()
        cursor.execute(f'SELECT balans FROM users WHERE id = ?', (id,))
        data = cursor.fetchone()
        if data:
            value = float(summ)
            cursor.execute('UPDATE users SET balans = ? WHERE id = ?', (value, id))
            db.commit()
            db.close()
            return summ
        else:
            db.close()
            return 'user not found'
    else:
        return False
#Архив услуг
def to_arhiv(chat_id, usluga, summ):
    file = 'count.json'
    if os.path.exists('files/'+file):
        with open('files/'+file, encoding='utf-8') as json_file:
            file_data = json.load(json_file)

    db = sqlite3.connect('files/arhive.db')
    cursor = db.cursor()
    date = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    number = file_data['count']
    if number:
        id = number+1
    else:
        id = 100
    file_data['count'] = id
    with open('files/'+file, 'w', encoding='utf-8') as outfile:
        json.dump(file_data, outfile)
    sql_query = f"INSERT INTO uslugi (id,date,usluga,summa,number) VALUES (?,?,?,?,?)"
    cursor.execute(sql_query, (
        chat_id,
        date,
        usluga,
        float(summ),
        id
        ))
    db.commit()
    db.close()

    return id
#Отмена заявки
def cancel_request(text):
    number = text.split('Заявка №')[1].split('\n')[0]
    db = sqlite3.connect('files/arhive.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT number FROM uslugi WHERE number = ?', (int(number),))
    data = cursor.fetchone()
    if data:
        cursor.execute('DELETE FROM uslugi WHERE number = ?', (int(number),))
        db.commit()
        db.close()
        return True
    else:
        db.close()
        return False
#История профиля
def get_balance_history(user_id, limit=20):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute(
        'SELECT amount, balance_after, description, created_at FROM balance_log WHERE user_id = ? ORDER BY id DESC LIMIT ?',
        (user_id, limit)
    )
    rows = cursor.fetchall()
    db.close()
    if not rows:
        return ''
    lines = []
    for amount, balance_after, description, created_at in rows:
        sign = '+' if amount >= 0 else ''
        desc = f' — {description}' if description else ''
        lines.append(f'<b>{created_at}</b>\n{sign}{amount:.2f}₽{desc}\nБаланс: {balance_after:.2f}₽\n➖➖➖➖➖➖➖')
    return '\n'.join(lines)

def get_history(chat_id):
    db = sqlite3.connect('files/arhive.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT date,usluga,summa,number FROM uslugi WHERE id = ?', (chat_id,))
    data = cursor.fetchall()
    text = ''
    for item in reversed(data):
        text+=f'<b>Заказ №{item[3]}</b>\nДата: {item[0]}\nУслуга: {item[1]}\nСумма: {item[2]}\n➖➖➖➖➖➖➖\n'
    db.commit()
    db.close()
    return text

def get_combined_history(user_id, limit=30):
    entries = []

    # Баланс лог
    try:
        db = sqlite3.connect('files/users.db')
        cursor = db.cursor()
        cursor.execute(
            'SELECT amount, balance_after, description, created_at FROM balance_log WHERE user_id = ? ORDER BY id DESC LIMIT ?',
            (user_id, limit)
        )
        for amount, balance_after, description, created_at in cursor.fetchall():
            try:
                dt = datetime.strptime(created_at, '%d.%m.%Y %H:%M:%S')
            except Exception:
                dt = datetime.min
            sign = '+' if amount >= 0 else ''
            desc = f' — {description}' if description else ''
            entries.append((dt, f'<b>{created_at}</b>\n{sign}{amount:.2f}₽{desc}\nБаланс: {balance_after:.2f}₽'))
        db.close()
    except Exception:
        pass

    # Архив заказов
    try:
        db = sqlite3.connect('files/arhive.db')
        cursor = db.cursor()
        cursor.execute('SELECT date, usluga, summa, number FROM uslugi WHERE id = ?', (user_id,))
        for date, usluga, summa, number in cursor.fetchall():
            try:
                dt = datetime.strptime(date, '%d.%m.%Y %H:%M:%S')
            except Exception:
                try:
                    dt = datetime.strptime(date, '%d.%m.%Y')
                except Exception:
                    dt = datetime.min
            entries.append((dt, f'<b>Заказ №{number}</b>\nДата: {date}\nУслуга: {usluga}\nСумма: {summa}₽'))
        db.close()
    except Exception:
        pass

    if not entries:
        return ''

    entries.sort(key=lambda x: x[0], reverse=True)
    return '\n➖➖➖➖➖➖➖\n'.join(e[1] for e in entries[:limit])
#Курс валют
def get_kurs(valuta):
    file = 'valuta.json'
    if os.path.exists('files/'+file):
        with open('files/'+file, encoding='utf-8') as json_file:
            file_data = json.load(json_file)
    if valuta == 'usd':
        return float(file_data[valuta])
    elif valuta == 'eur':
        return float(file_data[valuta])
    elif valuta == 'try':
        return float(file_data[valuta])
    elif valuta == 'uah':
        return float(file_data[valuta])
def get_uah_cost_rate():
    """Получает курс UAH/RUB с Yandex и добавляет 2% (себестоимость)"""
    try:
        import re
        resp = requests.get(
            'https://yandex.ru/finance/currencies/UAH_RUB',
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
            timeout=5
        )
        match = re.search(r'составляет\s+([\d.]+)\s+Российских', resp.text)
        if match:
            rate = float(match.group(1))
            return round(rate * 1.02, 4)
    except:
        pass
    return None

def update_last_activity(user_id, username=None):
    with sqlite3.connect('files/users.db') as db:
        db.execute(
            "UPDATE users SET last_activity = ? WHERE id = ?",
            (datetime.now(), user_id)
        )
        if username:
            db.execute(
                "UPDATE users SET username = ? WHERE id = ?",
                (username, user_id)
            )
#Все юзеры
def get_all_users():
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT id FROM users')
    data = cursor.fetchall()
    db.close()
    chat_ids = []
    for chat_id in data:
        chat_ids.append(chat_id[0])
    print('all_users_taked')
    return chat_ids
#Ротация карт
def get_cards():
    db = sqlite3.connect('files/cards.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT card FROM cards')
    data = cursor.fetchall()
    db.close()
    cards = []
    for card in data:
        cards.append(card[0])
    return cards


def rotaciya():
    file = 'cards.json'

    if os.path.exists('files/' + file):
        with open('files/' + file, encoding='utf-8') as json_file:
            file_data = json.load(json_file)

    cards = get_cards()

    if not cards:
        return "Нет карт для обработки"

    n = file_data.get('nom', 0)

    print(n, cards)
    if n >= len(cards):
        n = 0

    card = cards[n]

    n = (n + 1) % len(cards)

    file_data['nom'] = n
    with open('files/' + file, 'w', encoding='utf-8') as outfile:
        json.dump(file_data, outfile)

    return card

def check_and_get_denomination(code):
    database_name="files/codes.db"
    connection = sqlite3.connect(database_name)
    cursor = connection.cursor()

    # Проверяем наличие кода в базе
    cursor.execute("SELECT denomination FROM codes WHERE code=?", (code,))
    result = cursor.fetchone()

    if result is not None:
        denomination = result[0]
        # Удаляем ваучер из базы
        cursor.execute("DELETE FROM codes WHERE code=?", (code,))
        connection.commit()
        connection.close()
        return denomination
    else:
        connection.close()
        return None

def get_all_users_text():
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute(f'SELECT id, balans FROM users')
    data = cursor.fetchall()
    db.close()
    texts = []
    text = ''
    summ = 0
    count = 0
    for id in data:
        text+=f'{id[0]} - {round(id[1],2)} р.\n'
        summ+=id[1]
        count+=len(text)
        if len(text)>4000:
            texts.append(text)
            text = f'{id[0]} - {round(id[1],2)} р.\n'
            count = 0
    texts.append(text)
    texts.append(f'Общаяя сумма: {round(summ,2)} р.')
    return texts

def get_user_type(user_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute('SELECT last_activity FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    db.close()
    old_date = datetime(2026, 2, 2)

    if not row or not row[0]:
        return 'cold'

    try:
        last = datetime.strptime(str(row[0]), "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        last = datetime.strptime(str(row[0]), "%Y-%m-%d %H:%M:%S")

    if datetime.now() - last > dt.timedelta(days=90) or last.date() == old_date.date():
        return 'warm'
    else:   
        return 'hot'
    
def add_blocked_user(user_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    date = datetime.now().strftime('%d.%m.%Y %H:%M')
    cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    username = row[0] if row and row[0] else None
    cursor.execute('INSERT OR IGNORE INTO blocked_users (id, date, username) VALUES (?, ?, ?)', (user_id, date, username))
    db.commit()
    db.close()
    
def delete_blocked_user(user_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute('DELETE FROM blocked_users WHERE id = ?', (user_id,))
    db.commit()
    db.close()

def update_user_type(user_id):
    user_type = get_user_type(user_id)
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute('UPDATE users SET user_type = ? WHERE id = ?', (user_type, user_id))
    db.commit()
    db.close()

def add_balance_ref_with_type(reffered_user_id, value, trans_type, user_type):
    referrer_id = get_ref_user(reffered_user_id)
    if not referrer_id or not trans_type:
        return 0
    try:
        procents = json.load(open("ref_data.json", encoding="utf-8"))['ref_procent']
        if trans_type not in procents or user_type not in procents[trans_type]:
            return 0
        procent = int(procents[trans_type][user_type])
        ref_value = round(float(value) * procent / 100, 2)
        db = sqlite3.connect('files/users.db')
        cursor = db.cursor()
        cursor.execute(
            "UPDATE users SET referr_balance = referr_balance + ? WHERE id = ?",
            (ref_value, referrer_id)
        )
        db.commit()
        db.close()
        return ref_value
    except Exception as e:
        print(f"Ошибка add_balance_ref_with_type: {e}")
        return 0
    
def export_db_to_excel():
    db = sqlite3.connect('files/users.db')

    users = pd.read_sql_query("SELECT * FROM users", db)
    blocked_users = pd.read_sql_query("SELECT * FROM blocked_users", db)
    inactive_users = pd.read_sql_query("SELECT * FROM inactive_users", db)

    db.close()

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        users.to_excel(writer, sheet_name='users', index=False)
        blocked_users.to_excel(writer, sheet_name='blocked_users', index=False)
        inactive_users.to_excel(writer, sheet_name='inactive_users', index=False)

    buffer.seek(0)
    return buffer

def get_inactive_users():
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute('SELECT id, last_activity FROM users')
    data = cursor.fetchall()
    db.close()

    inactive = []
    old_date = datetime(2026, 2, 2)
    for row in data:
        user_id, last_activity = row
        if not last_activity:
            inactive.append(user_id)
            continue
        try:
            last = datetime.strptime(str(last_activity), "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            last = datetime.strptime(str(last_activity), "%Y-%m-%d %H:%M:%S")
        
        if datetime.now() - last > dt.timedelta(days=90) or last.date() == old_date.date():
            inactive.append(user_id)

    return inactive

def update_inactive_users():
    inactive = get_inactive_users()
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()

    # Стираем таблицу
    cursor.execute('DELETE FROM inactive_users')

    # Записываем заново
    for user_id in inactive:
        cursor.execute('SELECT last_activity, username FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        last_activity = row[0] if row and row[0] else 'Никогда'
        username = row[1] if row and row[1] else None
        cursor.execute(
            'INSERT INTO inactive_users (id, date, username) VALUES (?, ?, ?)',
            (user_id, last_activity, username)
        )
    db.commit()
    db.close()
    return len(inactive)

def get_username(user_id):
    db = sqlite3.connect('files/users.db')
    cursor = db.cursor()
    cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    db.close()
    return row[0] if row else None

    