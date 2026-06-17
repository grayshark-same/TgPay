import json
import os
import sqlite3
import pytest


def create_users_db(path):
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            date TEXT,
            balans REAL DEFAULT 0,
            referr_id INTEGER,
            referr_balance REAL DEFAULT 0,
            ref_count INTEGER DEFAULT 0,
            promocode TEXT,
            total_spent REAL DEFAULT 0,
            trial INTEGER DEFAULT 0,
            last_activity TEXT,
            username TEXT,
            user_type TEXT,
            admin_balance REAL DEFAULT 0
        );
        CREATE TABLE balance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            balance_after REAL NOT NULL,
            description TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS blocked_users (
            id INTEGER PRIMARY KEY,
            date TEXT,
            username TEXT
        );
        CREATE TABLE IF NOT EXISTS inactive_users (
            id INTEGER PRIMARY KEY,
            date TEXT,
            username TEXT
        );
    """)
    db.commit()
    db.close()


def create_donations_db(path):
    db = sqlite3.connect(path)
    db.execute("""
        CREATE TABLE donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            amount REAL NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()
    db.close()


def create_arhive_db(path):
    db = sqlite3.connect(path)
    db.execute("""
        CREATE TABLE uslugi (
            id INTEGER,
            date TEXT,
            usluga TEXT,
            summa REAL,
            number INTEGER
        )
    """)
    db.commit()
    db.close()


@pytest.fixture
def tgpay_env(tmp_path, monkeypatch):
    """Временная рабочая директория с нужными БД и файлами."""
    files_dir = tmp_path / "files"
    files_dir.mkdir()

    create_users_db(str(files_dir / "users.db"))
    create_donations_db(str(files_dir / "donations.db"))
    create_arhive_db(str(files_dir / "arhive.db"))

    # ref_data.json нужен для реферальной системы
    ref_data = {
        "ref_procent": {
            "lava": {
                "hot": "5",
                "warm": "3",
                "cold": "1"
            }
        }
    }
    (tmp_path / "ref_data.json").write_text(
        json.dumps(ref_data), encoding="utf-8"
    )

    # count.json нужен для to_arhiv
    (files_dir / "count.json").write_text(
        json.dumps({"count": 100}), encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)

    return tmp_path


def add_user(user_id, balance=0.0):
    """Добавить пользователя напрямую в тестовую БД."""
    from datetime import datetime
    db = sqlite3.connect("files/users.db")
    db.execute(
        "INSERT INTO users (id, date, balans, last_activity) VALUES (?, ?, ?, ?)",
        (user_id, "01.01.2026", balance, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    db.commit()
    db.close()
