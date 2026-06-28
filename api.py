import hashlib
import hmac
import json
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Optional

import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import os

load_dotenv()

app = FastAPI(title="TGPay API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
JWT_SECRET = os.getenv("JWT_SECRET", BOT_TOKEN)
JWT_EXPIRE_DAYS = 30
USERS_DB = "files/users.db"
ARCHIVE_DB = "files/arhive.db"
VPN_BOT_DB = os.getenv("VPN_BOT_DB", "/root/vpn_bot/data/users.db")

security = HTTPBearer()


# ── Auth helpers ─────────────────────────────────────────────────────────────

class TelegramAuthData(BaseModel):
    id: int
    first_name: str = ""
    last_name: str = ""
    username: str = ""
    photo_url: str = ""
    auth_date: int
    hash: str


def _verify_telegram_hash(data: TelegramAuthData) -> bool:
    fields = {
        "id": str(data.id),
        "first_name": data.first_name,
        "last_name": data.last_name,
        "username": data.username,
        "photo_url": data.photo_url,
        "auth_date": str(data.auth_date),
    }
    check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(fields.items()) if v
    )
    secret = hashlib.sha256(BOT_TOKEN.encode()).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, data.hash)


def _get_or_create_user(tg_id: int, username: str) -> dict:
    with sqlite3.connect(USERS_DB) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM users WHERE id = ?", (tg_id,)).fetchone()
        if row is None:
            date = datetime.now().strftime("%d.%m.%Y")
            db.execute(
                "INSERT INTO users (id, date, balans, username) VALUES (?, ?, 0, ?)",
                (tg_id, date, username),
            )
            row = db.execute("SELECT * FROM users WHERE id = ?", (tg_id,)).fetchone()
        else:
            if username and row["username"] != username:
                db.execute("UPDATE users SET username = ? WHERE id = ?", (username, tg_id))
        return dict(row)


def _make_token(tg_id: int) -> str:
    payload = {
        "sub": tg_id,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def _get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")


def _user_to_dict(user: dict) -> dict:
    return {
        "id": user["id"],
        "username": user.get("username"),
        "balance": round(user.get("balans") or 0, 2),
        "ref_balance": round(user.get("ref_balance") or 0, 2),
        "total_spent": round(user.get("total_spent") or 0, 2),
        "ref_count": user.get("ref_count") or 0,
        "promocode": user.get("promocode"),
        "date": user.get("date"),
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/auth/telegram")
def auth_telegram(data: TelegramAuthData):
    if time.time() - data.auth_date > 3600:
        raise HTTPException(status_code=401, detail="auth_date expired")
    if not _verify_telegram_hash(data):
        raise HTTPException(status_code=401, detail="invalid hash")

    user = _get_or_create_user(data.id, data.username)
    return {
        "token": _make_token(data.id),
        "user": _user_to_dict(user),
    }


@app.get("/me")
def get_me(tg_id: int = Depends(_get_current_user)):
    with sqlite3.connect(USERS_DB) as db:
        db.row_factory = sqlite3.Row
        row = db.execute("SELECT * FROM users WHERE id = ?", (tg_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="user not found")
    return _user_to_dict(dict(row))


@app.get("/history")
def get_history(limit: int = 30, tg_id: int = Depends(_get_current_user)):
    entries = []

    # balance_log
    try:
        with sqlite3.connect(USERS_DB) as db:
            rows = db.execute(
                "SELECT amount, balance_after, description, created_at FROM balance_log "
                "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (tg_id, limit),
            ).fetchall()
        for amount, balance_after, description, created_at in rows:
            try:
                dt = datetime.strptime(created_at, "%d.%m.%Y %H:%M:%S")
            except Exception:
                dt = datetime.min
            entries.append({
                "type": "balance",
                "amount": round(amount, 2),
                "balance_after": round(balance_after, 2),
                "description": description,
                "date": created_at,
                "_dt": dt,
            })
    except Exception:
        pass

    # archive orders
    try:
        with sqlite3.connect(ARCHIVE_DB) as db:
            rows = db.execute(
                "SELECT date, usluga, summa, number FROM uslugi WHERE id = ? ORDER BY number DESC LIMIT ?",
                (tg_id, limit),
            ).fetchall()
        for date, usluga, summa, number in rows:
            try:
                dt = datetime.strptime(date, "%d.%m.%Y %H:%M:%S")
            except Exception:
                try:
                    dt = datetime.strptime(date, "%d.%m.%Y")
                except Exception:
                    dt = datetime.min
            entries.append({
                "type": "order",
                "order_number": number,
                "service": usluga,
                "amount": -round(float(summa), 2),
                "date": date,
                "_dt": dt,
            })
    except Exception:
        pass

    entries.sort(key=lambda x: x.pop("_dt"), reverse=True)
    return entries[:limit]


@app.get("/vpn/status")
def get_vpn_status(tg_id: int = Depends(_get_current_user)):
    try:
        with sqlite3.connect(VPN_BOT_DB) as db:
            row = db.execute(
                "SELECT end_of_sub FROM users WHERE tg_id = ?", (tg_id,)
            ).fetchone()
        if not row or not row[0]:
            return {"active": False, "end_date": None, "days_left": None}
        end_date = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
        is_active = end_date > datetime.now()
        days_left = max((end_date - datetime.now()).days, 0) if is_active else 0
        return {
            "active": is_active,
            "end_date": end_date.strftime("%d.%m.%Y"),
            "days_left": days_left,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"vpn db unavailable: {e}")


@app.get("/referral")
def get_referral(tg_id: int = Depends(_get_current_user)):
    with sqlite3.connect(USERS_DB) as db:
        db.row_factory = sqlite3.Row
        row = db.execute(
            "SELECT ref_balance, ref_count FROM users WHERE id = ?", (tg_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="user not found")
    return {
        "ref_balance": round(row["ref_balance"] or 0, 2),
        "ref_count": row["ref_count"] or 0,
        "ref_link": f"https://t.me/TGPayBot?start={tg_id}",
    }


# ── Catalog ───────────────────────────────────────────────────────────────────

_GB_INFO = {
    "gb_10":   ("🛜 Пополнение ГБ (10 ГБ)",  990),
    "gb_100":  ("🛜 Пополнение ГБ (100 ГБ)", 1690),
    "roum_15": ("🌍 Роуминг (15 ГБ)",         990),
    "roum_40": ("🌍 Роуминг (40 ГБ)",        2099),
}

_SVC_INFO = {
    "svyaz":  ("📶 Настройка связи",             899),
    "sim":    ("💳 Настройка SIM / eSIM",        899),
    "phone":  ("📲 Настройка телефона",          899),
    "gaming": ("🎮 Настройка игровых аккаунтов", 990),
    "region": ("🌍 Смена региона аккаунтов",    1490),
}

_VPN_PLANS = {1: 360, 3: 960, 6: 1790, 12: 2990}
_VPN_PLAN_NAMES = {1: "1 месяц", 3: "3 месяца", 6: "6 месяцев", 12: "12 месяцев"}
_VPN_PLAN_DAYS = {1: 30, 3: 90, 6: 180, 12: 365}


@app.get("/catalog")
def get_catalog():
    esim = {}
    try:
        with open("esim.json", encoding="utf-8") as f:
            raw = json.load(f)
        esim = {op: {"name": op, "price": int(v["price"])} for op, v in raw.items()}
    except Exception:
        pass

    return {
        "vpn": [
            {"id": str(m), "name": _VPN_PLAN_NAMES[m], "price": p}
            for m, p in _VPN_PLANS.items()
        ],
        "gb": [
            {"id": k, "name": name, "price": price}
            for k, (name, price) in _GB_INFO.items()
        ],
        "services": [
            {"id": k, "name": name, "price": price}
            for k, (name, price) in _SVC_INFO.items()
        ],
        "esim": list(esim.values()),
    }


# ── Purchase helpers ──────────────────────────────────────────────────────────

def _deduct(tg_id: int, price: float, description: str):
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    with sqlite3.connect(USERS_DB) as db:
        row = db.execute("SELECT balans FROM users WHERE id = ?", (tg_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="user not found")
        balance = float(row[0] or 0)
        if balance < price:
            raise HTTPException(status_code=402, detail="insufficient balance")
        new_balance = balance - price
        db.execute("UPDATE users SET balans = ? WHERE id = ?", (new_balance, tg_id))
        db.execute(
            "INSERT INTO balance_log (user_id, amount, balance_after, description, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (tg_id, -price, new_balance, description, now),
        )
    return new_balance


def _to_archive(tg_id: int, service_name: str, price: float) -> int:
    count_file = "files/count.json"
    try:
        with open(count_file, encoding="utf-8") as f:
            data = json.load(f)
        order_num = (data.get("count") or 99) + 1
    except Exception:
        order_num = 100
    try:
        with open(count_file, "w", encoding="utf-8") as f:
            json.dump({"count": order_num}, f)
    except Exception:
        pass
    date = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    with sqlite3.connect(ARCHIVE_DB) as db:
        db.execute(
            "INSERT INTO uslugi (id, date, usluga, summa, number) VALUES (?, ?, ?, ?, ?)",
            (tg_id, date, service_name, float(price), order_num),
        )
    return order_num


def _update_total_spent(tg_id: int, amount: float):
    with sqlite3.connect(USERS_DB) as db:
        db.execute(
            "UPDATE users SET total_spent = COALESCE(total_spent, 0) + ? WHERE id = ?",
            (amount, tg_id),
        )


# ── Purchase endpoints ────────────────────────────────────────────────────────

class VpnPurchaseRequest(BaseModel):
    months: int


class GbPurchaseRequest(BaseModel):
    package: str


class ServicePurchaseRequest(BaseModel):
    service: str
    phone: Optional[str] = None


class EsimPurchaseRequest(BaseModel):
    operator: str


@app.post("/purchase/vpn")
def purchase_vpn(body: VpnPurchaseRequest, tg_id: int = Depends(_get_current_user)):
    if body.months not in _VPN_PLANS:
        raise HTTPException(status_code=400, detail="invalid plan, choose from 1/3/6/12")
    price = _VPN_PLANS[body.months]
    plan_name = _VPN_PLAN_NAMES[body.months]
    days = _VPN_PLAN_DAYS[body.months]
    service_label = f"🛡 VPN TGPay — {plan_name}"

    new_balance = _deduct(tg_id, price, service_label)
    order_num = _to_archive(tg_id, service_label, price)
    _update_total_spent(tg_id, price)

    # extend VPN subscription
    end_date = None
    try:
        with sqlite3.connect(VPN_BOT_DB) as db:
            row = db.execute("SELECT end_of_sub FROM users WHERE tg_id = ?", (tg_id,)).fetchone()
            if row is None:
                end_date = datetime.now() + timedelta(days=days)
                db.execute(
                    "INSERT INTO users (tg_id, end_of_sub) VALUES (?, ?)",
                    (tg_id, end_date.strftime("%Y-%m-%d %H:%M:%S")),
                )
            else:
                current_end = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S") if row[0] else None
                base = current_end if current_end and current_end > datetime.now() else datetime.now()
                end_date = base + timedelta(days=days)
                db.execute(
                    "UPDATE users SET end_of_sub = ? WHERE tg_id = ?",
                    (end_date.strftime("%Y-%m-%d %H:%M:%S"), tg_id),
                )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"vpn db error: {e}")

    return {
        "order_number": order_num,
        "service": service_label,
        "price": price,
        "balance_after": round(new_balance, 2),
        "vpn_end_date": end_date.strftime("%d.%m.%Y") if end_date else None,
    }


@app.post("/purchase/gb")
def purchase_gb(body: GbPurchaseRequest, tg_id: int = Depends(_get_current_user)):
    if body.package not in _GB_INFO:
        raise HTTPException(status_code=400, detail=f"invalid package, choose from {list(_GB_INFO)}")
    name, price = _GB_INFO[body.package]

    new_balance = _deduct(tg_id, price, name)
    order_num = _to_archive(tg_id, name, price)
    _update_total_spent(tg_id, price)

    return {
        "order_number": order_num,
        "service": name,
        "price": price,
        "balance_after": round(new_balance, 2),
    }


@app.post("/purchase/service")
def purchase_service(body: ServicePurchaseRequest, tg_id: int = Depends(_get_current_user)):
    if body.service not in _SVC_INFO:
        raise HTTPException(status_code=400, detail=f"invalid service, choose from {list(_SVC_INFO)}")
    name, price = _SVC_INFO[body.service]

    new_balance = _deduct(tg_id, price, name)
    order_num = _to_archive(tg_id, name, price)
    _update_total_spent(tg_id, price)

    return {
        "order_number": order_num,
        "service": name,
        "price": price,
        "balance_after": round(new_balance, 2),
        "note": "Заявка принята. Ожидайте выполнения.",
    }


@app.post("/purchase/esim")
def purchase_esim(body: EsimPurchaseRequest, tg_id: int = Depends(_get_current_user)):
    try:
        with open("esim.json", encoding="utf-8") as f:
            catalog = json.load(f)
    except Exception:
        raise HTTPException(status_code=503, detail="esim catalog unavailable")

    if body.operator not in catalog:
        raise HTTPException(status_code=400, detail=f"unknown operator: {body.operator}")

    entry = catalog[body.operator]
    price = int(entry["price"])
    name = f"eSIM — {body.operator}"

    new_balance = _deduct(tg_id, price, name)
    order_num = _to_archive(tg_id, name, price)
    _update_total_spent(tg_id, price)

    return {
        "order_number": order_num,
        "service": name,
        "price": price,
        "balance_after": round(new_balance, 2),
        "note": "Заявка принята. Ожидайте выполнения.",
    }


@app.get("/tg-auth", response_class=HTMLResponse)
async def tg_auth():
    html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TGPay</title>
  <style>
    body { margin:0; min-height:100vh; display:flex;
           align-items:center; justify-content:center; background:#0D0D1A; }
  </style>
</head>
<body>
  <script async src="https://telegram.org/js/telegram-widget.js?22"
    data-telegram-login="PayTelekom_bot"
    data-size="large"
    data-radius="12"
    data-onauth="onAuth(user)"
    data-request-access="write">
  </script>
  <script>
    function onAuth(user) {
      var p = new URLSearchParams();
      for (var k in user) { if (user[k] != null) p.set(k, user[k]); }
      window.location.href = 'tgpapp://auth?' + p.toString();
    }
  </script>
</body>
</html>"""
    return HTMLResponse(content=html)