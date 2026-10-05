#!/usr/bin/env bash
# Manual check of the running API: every step prints the expected and the real result.
# Usage: ./scripts/check.sh   (needs curl and jq, the app must run on localhost:8000)

API=${API:-http://localhost:8000/api}
JSON='Content-Type: application/json'
RUN=$(date +%s)   # new emails on every run
PASS='Str0ng-pass!'

step() { echo; echo "=== $1  (expected: $2)"; }
call() { curl -s -w '\n-> HTTP %{http_code}\n' "$@"; }

# ---------- 1. Registration ----------
step "Register Alice" 201
call -X POST $API/auth/register/ -H "$JSON" -d "{\"email\": \"alice$RUN@example.com\", \"password\": \"$PASS\"}"

step "Register Bob" 201
BOB=$(curl -s -X POST $API/auth/register/ -H "$JSON" -d "{\"email\": \"bob$RUN@example.com\", \"password\": \"$PASS\"}" | jq -r .account_number)
echo "Bob's account: $BOB"

step "Same email again" 400
call -X POST $API/auth/register/ -H "$JSON" -d "{\"email\": \"alice$RUN@example.com\", \"password\": \"$PASS\"}"

step "Weak password" 400
call -X POST $API/auth/register/ -H "$JSON" -d "{\"email\": \"weak$RUN@example.com\", \"password\": \"123\"}"

# ---------- 2. Login ----------
step "Wrong password" 401
call -X POST $API/auth/login/ -H "$JSON" -d "{\"email\": \"alice$RUN@example.com\", \"password\": \"wrong\"}"

ALICE_TOKEN=$(curl -s -X POST $API/auth/login/ -H "$JSON" -d "{\"email\": \"alice$RUN@example.com\", \"password\": \"$PASS\"}" | jq -r .access)
BOB_TOKEN=$(curl -s -X POST $API/auth/login/ -H "$JSON" -d "{\"email\": \"bob$RUN@example.com\", \"password\": \"$PASS\"}" | jq -r .access)
if [ "$BOB" = null ] || [ "$ALICE_TOKEN" = null ] || [ "$BOB_TOKEN" = null ]; then
    echo; echo "Setup failed, most likely a rate limit (HTTP 429 above). See README and try later."
    exit 1
fi
A="Authorization: Bearer $ALICE_TOKEN"
B="Authorization: Bearer $BOB_TOKEN"
ALICE=$(curl -s $API/account/ -H "$A" | jq -r .number)

# ---------- 3. Access without a token ----------
step "Balance without a token" 401
call $API/account/

step "Balance with a fake token" 401
call $API/account/ -H "Authorization: Bearer fake.token.here"

# ---------- 4. Start balances ----------
step "Alice's balance" "200, 10000.00"
call $API/account/ -H "$A"

step "Bob's balance" "200, 10000.00"
call $API/account/ -H "$B"

# ---------- 5. Successful transfer ----------
step "Alice -> Bob 100.00" "201, fee 5.00 (minimum)"
call -X POST $API/transfers/ -H "$A" -H "$JSON" -d "{\"to_account\": \"$BOB\", \"amount\": \"100.00\"}"

step "Alice's balance" "9895.00 = 10000 - 100 - 5"
call $API/account/ -H "$A"

step "Bob's balance" "10100.00"
call $API/account/ -H "$B"

# ---------- 6. Transfers that must fail ----------
step "More than the balance: 10000.00" "400, Insufficient funds"
call -X POST $API/transfers/ -H "$A" -H "$JSON" -d "{\"to_account\": \"$BOB\", \"amount\": \"10000.00\"}"

step "Unknown account" "400, Receiver account not found"
call -X POST $API/transfers/ -H "$A" -H "$JSON" -d '{"to_account": "9999999999", "amount": "10.00"}'

step "To yourself" "400, Cannot transfer to your own account"
call -X POST $API/transfers/ -H "$A" -H "$JSON" -d "{\"to_account\": \"$ALICE\", \"amount\": \"10.00\"}"

step "To the system account 0000000000" "400, Receiver account not found"
call -X POST $API/transfers/ -H "$A" -H "$JSON" -d '{"to_account": "0000000000", "amount": "10.00"}'

step "Amount 0" 400
call -X POST $API/transfers/ -H "$A" -H "$JSON" -d "{\"to_account\": \"$BOB\", \"amount\": \"0\"}"

step "Negative amount" 400
call -X POST $API/transfers/ -H "$A" -H "$JSON" -d "{\"to_account\": \"$BOB\", \"amount\": \"-50.00\"}"

step "Over the 1,000,000 limit" 400
call -X POST $API/transfers/ -H "$A" -H "$JSON" -d "{\"to_account\": \"$BOB\", \"amount\": \"1000000.01\"}"

step "Three decimal places" 400
call -X POST $API/transfers/ -H "$A" -H "$JSON" -d "{\"to_account\": \"$BOB\", \"amount\": \"10.005\"}"

step "Amount as a float" 400
call -X POST $API/transfers/ -H "$A" -H "$JSON" -d "{\"to_account\": \"$BOB\", \"amount\": 10.5}"

step "Wrong account number format" 400
call -X POST $API/transfers/ -H "$A" -H "$JSON" -d '{"to_account": "123", "amount": "10.00"}'

step "Transfer without a token" 401
call -X POST $API/transfers/ -H "$JSON" -d "{\"to_account\": \"$BOB\", \"amount\": \"10.00\"}"

step "Alice's balance did not change after the errors" "9895.00"
call $API/account/ -H "$A"

# ---------- 7. Send the whole balance ----------
# 9653.66 + 2.5% fee (241.34) = 9895.00
step "Alice -> Bob 9653.66, the whole balance with the fee" "201, fee 241.34"
call -X POST $API/transfers/ -H "$A" -H "$JSON" -d "{\"to_account\": \"$BOB\", \"amount\": \"9653.66\"}"

step "Alice's balance" "0.00"
call $API/account/ -H "$A"

step "0.01 more from a zero balance" "400, Insufficient funds"
call -X POST $API/transfers/ -H "$A" -H "$JSON" -d "{\"to_account\": \"$BOB\", \"amount\": \"0.01\"}"

step "Bob's balance" "19753.66 = 10000 + 100 + 9653.66"
call $API/account/ -H "$B"

# ---------- 8. History ----------
step "Alice's history" "deposit + 2 transfers + 2 fees"
call $API/account/transactions/ -H "$A"

step "Bob's history for today" "deposit + 2 incoming transfers"
TODAY=$(date -u +%F)
call "$API/account/transactions/?from=$TODAY&to=$TODAY" -H "$B"

step "History: from is later than to" 400
call "$API/account/transactions/?from=2026-12-31&to=2026-01-01" -H "$A"

step "History: wrong date" 400
call "$API/account/transactions/?from=abc" -H "$A"

# ---------- 9. Token refresh ----------
REFRESH=$(curl -s -X POST $API/auth/login/ -H "$JSON" -d "{\"email\": \"bob$RUN@example.com\", \"password\": \"$PASS\"}" | jq -r .refresh)
step "New access token from refresh" 200
call -X POST $API/auth/refresh/ -H "$JSON" -d "{\"refresh\": \"$REFRESH\"}"

step "Fake refresh token" 401
call -X POST $API/auth/refresh/ -H "$JSON" -d '{"refresh": "fake"}'
