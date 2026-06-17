"""
Тесты системы рангов: get_donation_rank, get_user_rank.
"""
import sqlite3
import pytest
from tests.conftest import add_user
import help


def add_donation(user_id, amount):
    db = sqlite3.connect("files/donations.db")
    db.execute(
        "INSERT INTO donations (user_id, amount) VALUES (?, ?)",
        (user_id, amount)
    )
    db.commit()
    db.close()


class TestDonationRank:
    def test_no_donations_returns_empty(self, tgpay_env):
        assert help.get_donation_rank(5001) == ""

    def test_below_500_returns_empty(self, tgpay_env):
        add_donation(5002, 499.99)
        assert help.get_donation_rank(5002) == ""

    def test_exactly_500_returns_first_tier(self, tgpay_env):
        add_donation(5003, 500)
        rank = help.get_donation_rank(5003)
        assert "5364209244109282901" in rank

    def test_999_returns_first_tier(self, tgpay_env):
        add_donation(5004, 999)
        rank = help.get_donation_rank(5004)
        assert "5364209244109282901" in rank

    def test_1000_returns_second_tier(self, tgpay_env):
        add_donation(5005, 1000)
        rank = help.get_donation_rank(5005)
        assert "5361664617720325706" in rank

    def test_3000_returns_third_tier(self, tgpay_env):
        add_donation(5006, 3000)
        rank = help.get_donation_rank(5006)
        assert "5361701438474953213" in rank

    def test_5000_returns_fourth_tier(self, tgpay_env):
        add_donation(5007, 5000)
        rank = help.get_donation_rank(5007)
        assert "5364119608141816446" in rank

    def test_10000_returns_top_tier(self, tgpay_env):
        add_donation(5008, 10000)
        rank = help.get_donation_rank(5008)
        assert "5363918225715243425" in rank

    def test_multiple_donations_summed(self, tgpay_env):
        add_donation(5009, 300)
        add_donation(5009, 300)
        # 600 >= 500 → первый тир
        rank = help.get_donation_rank(5009)
        assert "5364209244109282901" in rank


class TestUserRank:
    def test_zero_spent_rank(self, tgpay_env):
        add_user(6001, balance=0)
        rank = help.get_user_rank(6001)
        assert rank == "❌"

    def test_1000_spent_rank(self, tgpay_env):
        add_user(6002, balance=0)
        db = sqlite3.connect("files/users.db")
        db.execute("UPDATE users SET total_spent = 1000 WHERE id = ?", (6002,))
        db.commit()
        db.close()
        rank = help.get_user_rank(6002)
        assert rank == "✅"

    def test_donation_rank_appended(self, tgpay_env):
        add_user(6003, balance=0)
        add_donation(6003, 500)
        rank = help.get_user_rank(6003)
        assert "❌" in rank
        assert "5364209244109282901" in rank
