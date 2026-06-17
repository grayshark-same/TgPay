"""
Тесты реферальной системы: add_balance_ref_with_type.
"""
import sqlite3
import pytest
from tests.conftest import add_user
import help


def set_referrer(user_id, referrer_id):
    db = sqlite3.connect("files/users.db")
    db.execute("UPDATE users SET referr_id = ? WHERE id = ?", (referrer_id, user_id))
    db.commit()
    db.close()


class TestRefBalance:
    def test_hot_user_gets_5_percent(self, tgpay_env):
        add_user(7001, balance=0)  # referrer
        add_user(7002, balance=0)  # referred
        set_referrer(7002, 7001)

        earned = help.add_balance_ref_with_type(7002, 1000, "lava", "hot")
        assert earned == 50.0

        db = sqlite3.connect("files/users.db")
        row = db.execute("SELECT referr_balance FROM users WHERE id = ?", (7001,)).fetchone()
        db.close()
        assert row[0] == 50.0

    def test_warm_user_gets_3_percent(self, tgpay_env):
        add_user(7003, balance=0)
        add_user(7004, balance=0)
        set_referrer(7004, 7003)

        earned = help.add_balance_ref_with_type(7004, 1000, "lava", "warm")
        assert earned == 30.0

    def test_cold_user_gets_1_percent(self, tgpay_env):
        add_user(7005, balance=0)
        add_user(7006, balance=0)
        set_referrer(7006, 7005)

        earned = help.add_balance_ref_with_type(7006, 1000, "lava", "cold")
        assert earned == 10.0

    def test_no_referrer_returns_zero(self, tgpay_env):
        add_user(7007, balance=0)
        earned = help.add_balance_ref_with_type(7007, 1000, "lava", "hot")
        assert earned == 0

    def test_unknown_trans_type_returns_zero(self, tgpay_env):
        add_user(7008, balance=0)
        add_user(7009, balance=0)
        set_referrer(7009, 7008)

        earned = help.add_balance_ref_with_type(7009, 1000, "unknown_type", "hot")
        assert earned == 0

    def test_rounding_to_2_decimal_places(self, tgpay_env):
        add_user(7010, balance=0)
        add_user(7011, balance=0)
        set_referrer(7011, 7010)

        # 5% от 333 = 16.65
        earned = help.add_balance_ref_with_type(7011, 333, "lava", "hot")
        assert earned == 16.65
