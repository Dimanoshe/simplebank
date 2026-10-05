from decimal import Decimal

import pytest

from bank.models import SYSTEM_ACCOUNT_NUMBER, Transfer
from bank.services import calculate_fee

from .conftest import assert_ledger_is_consistent, balance

URL = '/api/transfers/'


@pytest.mark.parametrize(
    'amount, fee',
    [
        ('0.01', '5.00'),
        ('200.00', '5.00'),
        ('200.01', '5.00'),
        ('300.19', '7.50'),
        ('300.20', '7.51'),
        ('1000.00', '25.00'),
    ],
)
def test_fee_is_2_5_percent_but_at_least_5(amount, fee):
    assert calculate_fee(Decimal(amount)) == Decimal(fee)


def test_transfer(alice_api, alice, bob):
    response = alice_api.post(URL, {'to_account': bob.account.number, 'amount': '100.00'})

    assert response.status_code == 201
    assert response.data['amount'] == '100.00'
    assert response.data['fee'] == '5.00'
    assert balance(alice) == Decimal('9895.00')
    assert balance(bob) == Decimal('10100.00')

    transfer = Transfer.objects.get()
    entries = {(e.account.number, e.type, e.kind) for e in transfer.transactions.all()}
    assert entries == {
        (alice.account.number, 'debit', 'transfer'),
        (bob.account.number, 'credit', 'transfer'),
        (alice.account.number, 'debit', 'fee'),
        (SYSTEM_ACCOUNT_NUMBER, 'credit', 'fee'),
    }
    assert_ledger_is_consistent()


def test_transfer_whole_balance_with_fee(alice_api, alice, bob):
    # 9756.10 + 243.90 fee = 10000.00
    response = alice_api.post(URL, {'to_account': bob.account.number, 'amount': '9756.10'})

    assert response.status_code == 201
    assert balance(alice) == 0


def test_transfer_insufficient_funds(alice_api, alice, bob):
    # 9756.11 + 243.90 fee = 10000.01, one cent more than the balance
    response = alice_api.post(URL, {'to_account': bob.account.number, 'amount': '9756.11'})

    assert response.status_code == 400
    assert response.data['detail'] == 'Insufficient funds.'
    assert balance(alice) == 10000
    assert not Transfer.objects.exists()


@pytest.mark.parametrize(
    'to_account, error',
    [
        ('9999999999', 'Receiver account not found.'),
        (SYSTEM_ACCOUNT_NUMBER, 'Receiver account not found.'),
    ],
)
def test_transfer_to_unknown_account(alice_api, to_account, error):
    response = alice_api.post(URL, {'to_account': to_account, 'amount': '10'})

    assert response.status_code == 400
    assert response.data['detail'] == error


def test_transfer_to_own_account(alice_api, alice):
    response = alice_api.post(URL, {'to_account': alice.account.number, 'amount': '10'})

    assert response.status_code == 400
    assert response.data['detail'] == 'Cannot transfer to your own account.'


@pytest.mark.parametrize(
    'amount', [0.1, '0', '-5', '1.001', 'NaN', 'abc', '1000000.01', None]
)
def test_transfer_invalid_amount(alice_api, alice, bob, amount):
    response = alice_api.post(URL, {'to_account': bob.account.number, 'amount': amount})

    assert response.status_code == 400
    assert 'amount' in response.data
    assert balance(alice) == 10000


@pytest.mark.parametrize('to_account', ['123', '12345678901', '12345abcde', ''])
def test_transfer_invalid_account_number(alice_api, to_account):
    response = alice_api.post(URL, {'to_account': to_account, 'amount': '10'})

    assert response.status_code == 400
    assert 'to_account' in response.data


def test_integer_amount_is_accepted(alice_api, bob):
    response = alice_api.post(URL, {'to_account': bob.account.number, 'amount': 10})

    assert response.status_code == 201
    assert response.data['amount'] == '10.00'

