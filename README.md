# TGPay

Telegram bot for payment processing, balance management, and digital services (mobile top-ups, eSIM, VPN, GB packages, etc.).

## Stack

- Python 3.10+
- [pyTelegramBotAPI (telebot)](https://github.com/eternnoir/pyTelegramBotAPI)
- SQLite (multiple databases via `sqlite3`)
- Lava.ru Business API (card + SBP payments, polling + webhook)
- Cryptomus (crypto payments)
- NicePay, PayOK, YooMoney (additional payment providers)

## File Structure

```
bot.py          — main file: handlers, callbacks, business logic
help.py         — DB helpers: balances, archive, ranks, history
texts.py        — static message templates
penalties.py    — moderator penalty system
cryptomus.py    — Cryptomus integration
nicepay.py      — NicePay integration
support_bot.py  — separate support bot
yomany_gmail.py — YooMoney monitoring via Gmail

files/          — SQLite databases (not in repo)
  users.db      — users, balances, balance_log, subscriptions
  arhive.db     — completed order archive
  cards.db      — card data for payouts
  penalties.db  — moderator penalties
  donations.db  — developer donations
  referrals.db  — referral system
  mods.db       — moderator balances (UAH/USD)

esim.json           — eSIM operator config (price, description)
promocode.json      — promo codes
lifecell_gb.json    — Lifecell GB packages
analytic_clicks_data.json — section click analytics
```

## Environment Variables

Create a `.env` file in the project root:

```env
BOT_TOKEN=<token from @BotFather>
ADMIN_GROUP=<admin group chat_id (negative)>
ARHIVE_GROUPS=<archive group chat_id>
```

> ⚠️ Never commit `.env` or hardcode tokens in source files.

## Running Locally

```bash
# 1. Clone and enter the directory
git clone https://github.com/grayshark-same/TgPay
cd TgPay

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r librarise.txt

# 4. Create .env (see above)

# 5. Create the database directory
mkdir -p files

# 6. Run
python bot.py
```

All SQLite tables are created automatically on first run.

## Deployment

The bot runs on a remote server. Test bot lives at `/root/test_bot/`, production at `/root/bot/`.

Deploy from test to production via `deploy.sh` (run on the server):

```bash
bash /root/test_bot/deploy.sh
```

The script rsyncs files (excluding databases and `.env`) and restarts `bot.service`.

## Balance Architecture

- User balance is stored in `users.db → users.balans` (RUB, float)
- Every balance change is written to `balance_log` (user_id, amount, balance_after, description, created_at)
- `add_deposit(id, summ, description)` is the single entry point for all balance changes
- `withdraw_balance` and `update_balance` also write to `balance_log`

## Referral System

- Users are linked to a referrer at registration via `referrals.db`
- A percentage of each top-up is credited to the referrer (configurable in `ref_data.json`)
- Accumulated referral balance can be withdrawn via the profile menu

## Lava Payments

1. An invoice is created via `/business/invoice/create` — user receives a payment link
2. The bot polls payment status in a background thread (`poll_lava_payment`) every 5 seconds for up to 1 hour
3. On `paid` status — balance is credited via `add_deposit`

Requests are signed with HMAC-SHA256 using `SECRET_KEY`.

## User Ranks

By total amount spent (`total_spent`):

| Rank | Amount |
|------|--------|
| ❌ | 0 ₽ |
| ✅ | up to 1,000 ₽ |
| 💎 | up to 10,000 ₽ |
| 🐳 | up to 100,000 ₽ |
| 🕶 | 100,000+ ₽ |

By donation amount (`donations.db`):

| Rank | Amount |
|------|--------|
| — | < 500 ₽ |
| 👑 (tier 1) | 500–999 ₽ |
| 👑 (tier 2) | 1,000–2,999 ₽ |
| 👑 (tier 3) | 3,000–4,999 ₽ |
| 👑 (tier 4) | 5,000–9,999 ₽ |
| 👑 (tier 5) | 10,000+ ₽ |
