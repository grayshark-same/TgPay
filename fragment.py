# -*- coding: utf-8 -*-
"""Покупка Telegram Stars/Premium через Wizard API (api.wizard-bot.com).

Заказ создаётся синхронно (POST /orders/create) и получает order_id, но
доставка асинхронна — статус нужно опрашивать через GET /orders/get/{id}
(см. bot.py: _sp_poll_loop). Итоговые статусы: success (успех) / failed
(провал, требуется возврат денег).
"""
import os
import requests

WIZARD_API_KEY = os.getenv('WIZARD_API_KEY')
WIZARD_BASE = 'https://api.wizard-bot.com/v1'


def is_configured():
    return bool(WIZARD_API_KEY)


def _headers():
    return {'X-API-KEY': WIZARD_API_KEY}


def get_balance():
    """Текущий баланс аккаунта Wizard API (строка) или None при ошибке."""
    try:
        r = requests.get(f'{WIZARD_BASE}/user/profile', headers=_headers(), timeout=15)
        if r.status_code != 200:
            return None
        return r.json().get('data', {}).get('balance')
    except Exception:
        return None


def create_order(category, recipient, quantity):
    """category: 'stars' | 'premium'. Возвращает (ok, order_id_или_текст_ошибки)."""
    if not is_configured():
        return False, 'not_configured'
    try:
        r = requests.post(f'{WIZARD_BASE}/orders/create', headers=_headers(),
                          json={'recipient': recipient.lstrip('@'),
                                'quantity': int(quantity), 'category': category},
                          timeout=15)
        data = r.json()
        if r.status_code != 201 or not data.get('data', {}).get('id'):
            err = data.get('error') or f'HTTP {r.status_code}'
            if r.status_code == 402:
                bal = get_balance()
                err = f'{err} (баланс wizard-bot: {bal})' if bal is not None else err
            return False, err
        return True, data['data']['id']
    except Exception as e:
        return False, str(e)


def get_order(order_id):
    """Возвращает dict с полями status/category/recipient/quantity/price, либо None при ошибке."""
    try:
        r = requests.get(f'{WIZARD_BASE}/orders/get/{order_id}', headers=_headers(), timeout=15)
        if r.status_code != 200:
            return None
        return r.json().get('data')
    except Exception:
        return None


def create_deposit(amount, method='TON'):
    """Пополнение баланса Wizard API. Возвращает (ok, dict_с_реквизитами_или_ошибкой)."""
    if not is_configured():
        return False, 'not_configured'
    try:
        r = requests.post(f'{WIZARD_BASE}/deposits/create', headers=_headers(),
                          json={'amount': str(amount), 'method': method}, timeout=15)
        data = r.json()
        if r.status_code not in (200, 201):
            return False, data.get('error') or f'HTTP {r.status_code}'
        return True, data['data']
    except Exception as e:
        return False, str(e)
