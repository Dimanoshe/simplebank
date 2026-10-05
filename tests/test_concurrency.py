import threading
from decimal import Decimal

import pytest
from django.db import connection

from bank.services import TransferError, transfer

from .conftest import assert_ledger_is_consistent, balance

# Real commits are needed to test row locks between parallel transactions.
# serialized_rollback brings back the system account after the table flush.
pytestmark = pytest.mark.django_db(transaction=True, serialized_rollback=True)


def run_in_parallel(jobs):
    """Start all jobs at the same moment and return their results."""
    start = threading.Barrier(len(jobs))
    results = []

    def worker(job):
        start.wait()
        try:
            job()
            results.append('ok')
        except TransferError as error:
            results.append(str(error))
        finally:
            connection.close()

    threads = [threading.Thread(target=worker, args=(job,)) for job in jobs]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def test_parallel_transfers_do_not_overdraw(alice, bob):
    # Each transfer costs 1000 + 25 fee, so 10000 is enough for only 9 of them
    job = lambda: transfer(alice, bob.account.number, Decimal('1000'))
    results = run_in_parallel([job] * 20)

    assert results.count('ok') == 9
    assert results.count('Insufficient funds.') == 11
    assert balance(alice) == Decimal('775.00')
    assert balance(bob) == Decimal('19000.00')
    assert_ledger_is_consistent()


def test_opposite_transfers_do_not_deadlock(alice, bob):
    to_bob = lambda: transfer(alice, bob.account.number, Decimal('100'))
    to_alice = lambda: transfer(bob, alice.account.number, Decimal('100'))
    results = run_in_parallel([to_bob, to_alice] * 10)

    assert results == ['ok'] * 20
    # Each side sent 10 x 100 and got 10 x 100 back, paying 10 x 5 fee
    assert balance(alice) == balance(bob) == Decimal('9950.00')
    assert_ledger_is_consistent()
