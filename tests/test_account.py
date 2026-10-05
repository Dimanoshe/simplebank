from datetime import datetime, timezone

import pytest

from bank.models import Transaction

URL = '/api/account/transactions/'


def test_balance(alice_api, alice):
    response = alice_api.get('/api/account/')

    assert response.status_code == 200
    assert response.data == {'number': alice.account.number, 'balance': '10000.00'}


def test_history_shows_only_own_transactions(alice_api, alice, bob):
    alice_api.post('/api/transfers/', {'to_account': bob.account.number, 'amount': '50'})

    results = alice_api.get(URL).data['results']

    assert [(r['type'], r['kind'], r['amount']) for r in results] == [
        ('debit', 'fee', '5.00'),
        ('debit', 'transfer', '50.00'),
        ('credit', 'deposit', '10000.00'),
    ]
    assert results[1]['counterparty'] == bob.account.number
    assert set(results[0]) == {'id', 'amount', 'type', 'kind', 'counterparty', 'timestamp'}


@pytest.fixture
def dated_history(alice):
    # Three entries on 1, 2 and 3 March
    deposit = alice.account.transactions.get()
    for day in (1, 2, 3):
        entry = Transaction.objects.create(
            account=alice.account,
            counterparty=deposit.counterparty,
            type='credit',
            kind='deposit',
            amount=day,
        )
        entry.created_at = datetime(2026, 3, day, 23, 59, tzinfo=timezone.utc)
        entry.save(update_fields=['created_at'])
    deposit.delete()


@pytest.mark.usefixtures('dated_history')
@pytest.mark.parametrize(
    'query, amounts',
    [
        ('', ['3.00', '2.00', '1.00']),
        ('?from=2026-03-02', ['3.00', '2.00']),
        ('?to=2026-03-02', ['2.00', '1.00']),
        ('?from=2026-03-02&to=2026-03-02', ['2.00']),
        ('?from=2026-04-01', []),
    ],
)
def test_history_date_filter(alice_api, query, amounts):
    response = alice_api.get(URL + query)

    assert response.status_code == 200
    assert [r['amount'] for r in response.data['results']] == amounts


@pytest.mark.parametrize('query', ['?from=abc', '?to=2026-13-01', '?from=2026-03-03&to=2026-03-01'])
def test_history_invalid_dates(alice_api, query):
    assert alice_api.get(URL + query).status_code == 400
