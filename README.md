# SimpleBank

A small REST API for bank accounts: registration, JWT login, balance,
transaction history and money transfers with a fee.

Stack: Python 3.13, Django 5.2, Django REST Framework, PostgreSQL 18, Docker.

## Run (macOS)

You need [Docker Desktop](https://www.docker.com/products/docker-desktop/) or [OrbStack](https://orbstack.dev).

```bash
cp .env.example .env
docker compose up --build
```

The API is ready at http://localhost:8000. Interactive docs (Swagger): http://localhost:8000/api/docs/

Containers: `db` (PostgreSQL), `migrate` (applies migrations once and exits), `web` (gunicorn).

## Tests

```bash
docker compose run --rm tests
```

Tests run against a real PostgreSQL, because row locks can not be tested on SQLite.
Lint: `docker compose run --rm tests ruff check .`

## API

| Method | URL | Description |
|---|---|---|
| POST | `/api/auth/register/` | Register with email and password. Opens an account with €10,000 |
| POST | `/api/auth/login/` | Get JWT `access` (15 min) and `refresh` (1 day) tokens |
| POST | `/api/auth/refresh/` | Get a new access token |
| GET | `/api/account/` | Account number and balance |
| GET | `/api/account/transactions/?from=&to=` | Transaction history, newest first |
| POST | `/api/transfers/` | Send money to another account |

All endpoints except auth need the header `Authorization: Bearer <access>`.

## Try it

```bash
API=http://localhost:8000/api
JSON='Content-Type: application/json'

# Two users; remember the account number of Bob
curl -s -X POST $API/auth/register/ -H "$JSON" -d '{"email": "alice@example.com", "password": "Str0ng-pass!"}'
curl -s -X POST $API/auth/register/ -H "$JSON" -d '{"email": "bob@example.com", "password": "Str0ng-pass!"}'

# Log in as Alice
TOKEN=$(curl -s -X POST $API/auth/login/ -H "$JSON" \
  -d '{"email": "alice@example.com", "password": "Str0ng-pass!"}' | sed -E 's/.*"access":"([^"]+)".*/\1/')
AUTH="Authorization: Bearer $TOKEN"

curl -s $API/account/ -H "$AUTH"
curl -s -X POST $API/transfers/ -H "$AUTH" -H "$JSON" -d '{"to_account": "<bob number>", "amount": "100.00"}'
curl -s "$API/account/transactions/?from=2026-01-01&to=2026-12-31" -H "$AUTH"
```

## How money is kept safe

- **Atomic operations.** A transfer runs in one database transaction:
  if any step fails, nothing is saved.
- **No race conditions.** Both accounts are locked with `SELECT ... FOR UPDATE`
  and the balance is checked only after the lock. Parallel transfers wait
  for each other, so the same money can not be spent twice.
- **No deadlocks.** Rows are always locked in the same order (by id).
- **Database constraints** as the last line of defence: balance can not go
  below zero, amounts are positive, no transfer to yourself, account number is 10 digits.
- **Exact money.** `Decimal` everywhere, `NUMERIC(14, 2)` in the database.
  The API takes amounts as strings (`"10.50"`) or integers, floats are rejected.
- **Double-entry ledger.** Every money move writes a debit and a credit.
  A system account (`0000000000`) pays the €10,000 deposit and receives fees,
  so the sum of all balances is always zero. Tests check this after parallel transfers.

## Business rules

- Fee: 2.5% of the amount, but at least €5, rounded half up to cents.
  The sender pays it on top: sending €100 costs €105.
- A transfer writes `debit/transfer` for the sender, `credit/transfer`
  for the receiver and `debit/fee` for the sender.
- Amount: from €0.01 to €1,000,000 per transfer.
- `from` and `to` are dates (`YYYY-MM-DD`, UTC), both days are included.
- Rate limits: login 5/min, registration 30/hour, transfers 30/min.

## Project structure

```
config/   settings and root URLs
users/    user model, registration and login
bank/     models, services (money logic), API views
tests/    API, fee, atomicity and concurrency tests
```
