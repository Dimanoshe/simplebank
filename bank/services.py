import secrets
from decimal import ROUND_HALF_UP, Decimal

from django.db import IntegrityError, transaction

from .models import SYSTEM_ACCOUNT_NUMBER, Account, Transaction, Transfer

START_DEPOSIT = Decimal('10000.00')
FEE_RATE = Decimal('0.025')
MIN_FEE = Decimal('5.00')
CENT = Decimal('0.01')


class TransferError(Exception):
    pass


def calculate_fee(amount):
    return max((amount * FEE_RATE).quantize(CENT, ROUND_HALF_UP), MIN_FEE)


@transaction.atomic
def open_account(user):
    """Create an account for a new user and deposit the start amount."""
    account = _create_account(user)
    _move(_lock_system_account(), account, START_DEPOSIT, Transaction.Kind.DEPOSIT)
    return account


@transaction.atomic
def transfer(user, to_number, amount):
    """Send money to another account. The sender also pays the fee."""
    sender = Account.objects.get(user=user)
    receiver = Account.objects.filter(number=to_number, user__isnull=False).first()
    if receiver is None:
        raise TransferError('Receiver account not found.')
    if receiver.pk == sender.pk:
        raise TransferError('Cannot transfer to your own account.')

    # Lock rows always in the same order, so two transfers can not deadlock
    locked = Account.objects.select_for_update().filter(pk__in=[sender.pk, receiver.pk])
    accounts = {account.pk: account for account in locked.order_by('pk')}
    sender, receiver = accounts[sender.pk], accounts[receiver.pk]

    # Check only after the lock, so no other transfer can change the balance
    fee = calculate_fee(amount)
    if sender.balance < amount + fee:
        raise TransferError('Insufficient funds.')

    record = Transfer.objects.create(sender=sender, receiver=receiver, amount=amount, fee=fee)
    _move(sender, receiver, amount, Transaction.Kind.TRANSFER, record)
    _move(sender, _lock_system_account(), fee, Transaction.Kind.FEE, record)
    return record


def _create_account(user, attempts=5):
    for _ in range(attempts):
        # First digit is never 0, so the number never matches the system account
        number = str(secrets.randbelow(9 * 10**9) + 10**9)
        try:
            # Savepoint: a number collision must not break the outer transaction
            with transaction.atomic():
                return Account.objects.create(user=user, number=number)
        except IntegrityError:
            continue
    raise RuntimeError('Could not create a unique account number.')


def _lock_system_account():
    # The system row is shared by all operations, so lock it last and hold it short
    return Account.objects.select_for_update().get(number=SYSTEM_ACCOUNT_NUMBER)


def _move(source, target, amount, kind, transfer=None):
    """Move money between two locked accounts and write both ledger entries."""
    source.balance -= amount
    target.balance += amount
    source.save(update_fields=['balance'])
    target.save(update_fields=['balance'])

    entry = {'kind': kind, 'amount': amount, 'transfer': transfer}
    Transaction.objects.bulk_create(
        [
            Transaction(account=source, counterparty=target, type=Transaction.Type.DEBIT, **entry),
            Transaction(account=target, counterparty=source, type=Transaction.Type.CREDIT, **entry),
        ]
    )
