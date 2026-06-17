"""
Тесты get_combined_history: сортировка, форматирование, оба источника.
"""
import sqlite3
from datetime import datetime
import pytest
from tests.conftest import add_user
import help


def add_balance_log(user_id, amount, balance_after, description, created_at):
    db = sqlite3.connect("files/users.db")
    db.execute(
        "INSERT INTO balance_log (user_id, amount, balance_after, description, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, balance_after, description, created_at)
    )
    db.commit()
    db.close()


def add_archive_entry(user_id, date, usluga, summa, number):
    db = sqlite3.connect("files/arhive.db")
    db.execute(
        "INSERT INTO uslugi (id, date, usluga, summa, number) VALUES (?, ?, ?, ?, ?)",
        (user_id, date, usluga, summa, number)
    )
    db.commit()
    db.close()


class TestCombinedHistory:
    def test_empty_history_returns_empty_string(self, tgpay_env):
        assert help.get_combined_history(8001) == ""

    def test_balance_log_entry_appears(self, tgpay_env):
        add_user(8002)
        add_balance_log(8002, 500.0, 500.0, "Пополнение", "15.06.2026 12:00:00")
        result = help.get_combined_history(8002)
        assert "+500.00₽" in result
        assert "Пополнение" in result

    def test_archive_entry_appears(self, tgpay_env):
        add_user(8003)
        add_archive_entry(8003, "15.06.2026 13:00:00", "eSIM Турция", 990.0, 201)
        result = help.get_combined_history(8003)
        assert "eSIM Турция" in result
        assert "Заказ №201" in result

    def test_entries_sorted_newest_first(self, tgpay_env):
        add_user(8004)
        add_balance_log(8004, 100.0, 100.0, "Пополнение", "14.06.2026 10:00:00")
        add_archive_entry(8004, "15.06.2026 11:00:00", "VPN 30 дней", 500.0, 202)
        result = help.get_combined_history(8004)
        pos_order = result.index("Заказ №202")
        pos_deposit = result.index("100.00₽")
        assert pos_order < pos_deposit

    def test_negative_amount_shows_minus_sign(self, tgpay_env):
        add_user(8005)
        add_balance_log(8005, -200.0, 300.0, "Списание за услугу", "15.06.2026 09:00:00")
        result = help.get_combined_history(8005)
        assert "-200.00₽" in result

    def test_old_date_format_in_archive(self, tgpay_env):
        """Архив с датой без времени (старый формат) не ломает историю."""
        add_user(8006)
        add_balance_log(8006, 50.0, 50.0, "Тест", "15.06.2026 10:00:00")
        add_archive_entry(8006, "10.06.2026", "GB пакет", 100.0, 203)
        result = help.get_combined_history(8006)
        assert "GB пакет" in result
        assert "50.00₽" in result
