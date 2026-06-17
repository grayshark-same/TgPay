"""
Тесты денежной логики: add_deposit, withdraw_balance, update_balance, balance_log.
"""
import sqlite3
import pytest
from tests.conftest import add_user
import help


class TestAddDeposit:
    def test_positive_deposit_increases_balance(self, tgpay_env):
        add_user(1001, balance=100.0)
        result = help.add_deposit(1001, 50.0, description="Пополнение")
        assert result == 50.0
        db = sqlite3.connect("files/users.db")
        row = db.execute("SELECT balans FROM users WHERE id = ?", (1001,)).fetchone()
        db.close()
        assert row[0] == 150.0

    def test_negative_deposit_decreases_balance(self, tgpay_env):
        add_user(1002, balance=200.0)
        result = help.add_deposit(1002, -80.0, description="Списание за услугу")
        assert result == -80.0
        db = sqlite3.connect("files/users.db")
        row = db.execute("SELECT balans FROM users WHERE id = ?", (1002,)).fetchone()
        db.close()
        assert row[0] == 120.0

    def test_deposit_writes_to_balance_log(self, tgpay_env):
        add_user(1003, balance=0.0)
        help.add_deposit(1003, 300.0, description="Пополнение через Lava")
        db = sqlite3.connect("files/users.db")
        row = db.execute(
            "SELECT amount, balance_after, description FROM balance_log WHERE user_id = ?",
            (1003,)
        ).fetchone()
        db.close()
        assert row[0] == 300.0
        assert row[1] == 300.0
        assert row[2] == "Пополнение через Lava"

    def test_deposit_default_description_positive(self, tgpay_env):
        add_user(1004, balance=0.0)
        help.add_deposit(1004, 100.0)
        db = sqlite3.connect("files/users.db")
        row = db.execute(
            "SELECT description FROM balance_log WHERE user_id = ?", (1004,)
        ).fetchone()
        db.close()
        assert row[0] == "Пополнение"

    def test_deposit_default_description_negative(self, tgpay_env):
        add_user(1005, balance=500.0)
        help.add_deposit(1005, -50.0)
        db = sqlite3.connect("files/users.db")
        row = db.execute(
            "SELECT description FROM balance_log WHERE user_id = ?", (1005,)
        ).fetchone()
        db.close()
        assert row[0] == "Списание за услугу"

    def test_deposit_user_not_found(self, tgpay_env):
        result = help.add_deposit(9999, 100.0)
        assert result == "user not found"

    def test_deposit_invalid_summ(self, tgpay_env):
        add_user(1006, balance=0.0)
        result = help.add_deposit(1006, "abc")
        assert result is False

    def test_multiple_deposits_accumulate(self, tgpay_env):
        add_user(1007, balance=0.0)
        help.add_deposit(1007, 100.0)
        help.add_deposit(1007, 200.0)
        help.add_deposit(1007, -50.0)
        db = sqlite3.connect("files/users.db")
        row = db.execute("SELECT balans FROM users WHERE id = ?", (1007,)).fetchone()
        count = db.execute(
            "SELECT COUNT(*) FROM balance_log WHERE user_id = ?", (1007,)
        ).fetchone()[0]
        db.close()
        assert row[0] == 250.0
        assert count == 3


class TestWithdrawBalance:
    def test_withdraw_success(self, tgpay_env):
        add_user(2001, balance=500.0)
        result = help.withdraw_balance(2001, 200.0)
        assert result == "success"
        db = sqlite3.connect("files/users.db")
        row = db.execute("SELECT balans FROM users WHERE id = ?", (2001,)).fetchone()
        db.close()
        assert row[0] == 300.0

    def test_withdraw_writes_to_balance_log(self, tgpay_env):
        add_user(2002, balance=1000.0)
        help.withdraw_balance(2002, 400.0)
        db = sqlite3.connect("files/users.db")
        row = db.execute(
            "SELECT amount, balance_after, description FROM balance_log WHERE user_id = ?",
            (2002,)
        ).fetchone()
        db.close()
        assert row[0] == -400.0
        assert row[1] == 600.0
        assert row[2] == "Вывод средств"

    def test_withdraw_insufficient_funds_returns_balance(self, tgpay_env):
        add_user(2003, balance=100.0)
        result = help.withdraw_balance(2003, 500.0)
        # Возвращает текущий баланс, не строку
        assert result == 100.0

    def test_withdraw_exact_balance(self, tgpay_env):
        add_user(2004, balance=250.0)
        result = help.withdraw_balance(2004, 250.0)
        assert result == "success"
        db = sqlite3.connect("files/users.db")
        row = db.execute("SELECT balans FROM users WHERE id = ?", (2004,)).fetchone()
        db.close()
        assert row[0] == 0.0

    def test_withdraw_user_not_found(self, tgpay_env):
        result = help.withdraw_balance(9999, 100.0)
        assert result == "user_not_found"

    def test_withdraw_does_not_log_on_insufficient(self, tgpay_env):
        add_user(2005, balance=50.0)
        help.withdraw_balance(2005, 100.0)
        db = sqlite3.connect("files/users.db")
        count = db.execute(
            "SELECT COUNT(*) FROM balance_log WHERE user_id = ?", (2005,)
        ).fetchone()[0]
        db.close()
        assert count == 0


class TestUpdateBalance:
    def test_update_balance_adds_amount(self, tgpay_env):
        add_user(3001, balance=100.0)
        help.update_balance(3001, 50.0)
        db = sqlite3.connect("files/users.db")
        row = db.execute("SELECT balans FROM users WHERE id = ?", (3001,)).fetchone()
        db.close()
        assert row[0] == 150.0

    def test_update_balance_writes_to_log(self, tgpay_env):
        add_user(3002, balance=200.0)
        help.update_balance(3002, -30.0)
        db = sqlite3.connect("files/users.db")
        row = db.execute(
            "SELECT amount, balance_after, description FROM balance_log WHERE user_id = ?",
            (3002,)
        ).fetchone()
        db.close()
        assert row[0] == -30.0
        assert row[1] == 170.0
        assert row[2] == "Изменение баланса"
