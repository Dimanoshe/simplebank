from django.conf import settings
from django.db import models
from django.db.models import F, Q

MONEY = {'max_digits': 14, 'decimal_places': 2}
# User accounts never start with 0, so this number is free
SYSTEM_ACCOUNT_NUMBER = '0000000000'


class Account(models.Model):
    # Only the system account has no user: it funds deposits and collects fees
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name='account'
    )
    number = models.CharField(max_length=10, unique=True)
    balance = models.DecimalField(**MONEY, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(number__regex=r'^[0-9]{10}$'), name='account_number_10_digits'
            ),
            models.CheckConstraint(
                condition=Q(balance__gte=0) | Q(number=SYSTEM_ACCOUNT_NUMBER),
                name='account_balance_non_negative',
            ),
            models.CheckConstraint(
                condition=Q(user__isnull=False) | Q(number=SYSTEM_ACCOUNT_NUMBER),
                name='account_has_user',
            ),
        ]

    def __str__(self):
        return self.number


class Transfer(models.Model):
    sender = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name='sent_transfers'
    )
    receiver = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name='received_transfers'
    )
    amount = models.DecimalField(**MONEY)
    fee = models.DecimalField(**MONEY)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name='transfer_amount_positive'),
            models.CheckConstraint(condition=Q(fee__gte=0), name='transfer_fee_non_negative'),
            models.CheckConstraint(condition=~Q(sender=F('receiver')), name='transfer_not_to_self'),
        ]


class Transaction(models.Model):
    """One ledger entry. Every money move writes a debit and a credit."""

    class Type(models.TextChoices):
        CREDIT = 'credit'
        DEBIT = 'debit'

    class Kind(models.TextChoices):
        DEPOSIT = 'deposit'
        TRANSFER = 'transfer'
        FEE = 'fee'

    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='transactions')
    counterparty = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='+')
    transfer = models.ForeignKey(
        Transfer, on_delete=models.PROTECT, null=True, related_name='transactions'
    )
    type = models.CharField(max_length=6, choices=Type)
    kind = models.CharField(max_length=8, choices=Kind)
    amount = models.DecimalField(**MONEY)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['account', '-created_at'])]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name='transaction_amount_positive'),
        ]
