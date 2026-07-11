# -*- coding: utf-8 -*-
"""Бэкап БД: локальный снапшот + (опц.) отправка users.db в архив-группы.

Использование:
    python backup.py          # снапшот файлов БД в backups/<timestamp>/
    python backup.py send     # снапшот + отправка users.db в ARHIVE_GROUPS
"""
import os
import sys
import sqlite3
import shutil
from datetime import datetime

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

DB_FILES = [
    'files/users.db', 'files/arhive.db', 'files/user_data.db', 'files/mods.db',
    'files/otzivi.db', 'files/penalties.db', 'files/cards.db', 'files/codes.db',
]
KEEP = 30  # сколько последних снапшотов хранить


def backup_db_file(src, dest):
    """Консистентный снапшот sqlite-файла через Online Backup API — в отличие от
    простого copy2 корректно работает с WAL (не теряет ещё не закечкпоинченные
    записи из *-wal и не ловит 'database is locked' на живой БД)."""
    src_conn = sqlite3.connect(src)
    dest_conn = sqlite3.connect(dest)
    try:
        src_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        src_conn.close()


def snapshot():
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = os.path.join('backups', ts)
    os.makedirs(dest, exist_ok=True)
    copied = []
    for f in DB_FILES:
        if os.path.exists(f):
            backup_db_file(f, os.path.join(dest, os.path.basename(f)))
            copied.append(os.path.basename(f))
    print(f'snapshot -> {dest} ({len(copied)} файлов: {", ".join(copied)})')
    _rotate()
    return dest


def _rotate():
    root = 'backups'
    if not os.path.isdir(root):
        return
    dirs = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    for d in dirs[:-KEEP]:
        shutil.rmtree(os.path.join(root, d), ignore_errors=True)


def send_to_archives():
    import tempfile
    import telebot
    import pytz
    from dotenv import load_dotenv
    load_dotenv()
    bot = telebot.TeleBot(os.environ['BOT_TOKEN'])
    groups = [int(x) for x in os.environ['ARHIVE_GROUPS'].split(',')]
    cap = '🗄 Бэкап БД ' + datetime.now(pytz.timezone('Europe/Moscow')).strftime('%d.%m.%Y %H:%M МСК')
    with tempfile.TemporaryDirectory() as tmp:
        tmp_db = os.path.join(tmp, 'users.db')
        backup_db_file('files/users.db', tmp_db)
        with open(tmp_db, 'rb') as f:
            data = f.read()
    for gid in groups:
        try:
            bot.send_document(gid, data, visible_file_name='users.db', caption=cap)
            print(f'  {gid}: SENT')
        except Exception as e:
            print(f'  {gid}: ERROR {e}')


if __name__ == '__main__':
    snapshot()
    if len(sys.argv) > 1 and sys.argv[1] == 'send':
        send_to_archives()
