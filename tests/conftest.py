import pytest
from django.core.cache import cache
from django.db.models import Q, Sum
from rest_framework.test import APIClient

from bank.models import Account
from bank.services import open_account
from users.models import User

PASSWORD = 'Str0ng-pass!'


@pytest.fixture(autouse=True)
def fresh_cache(settings):
    # Throttle counters live in the cache, so every test starts from zero
    settings.CACHES = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
    cache.clear()


@pytest.fixture
def make_user(db):
    def make(email):
        user = User.objects.create_user(email, PASSWORD)
        open_account(user)
        return user

    return make


@pytest.fixture
def alice(make_user):
    return make_user('alice@example.com')


@pytest.fixture
def bob(make_user):
    return make_user('bob@example.com')


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def alice_api(api, alice):
    api.force_authenticate(alice)
    return api


def balance(user):
    return Account.objects.get(user=user).balance


def assert_ledger_is_consistent():
    # Money is never created or lost: all balances together are zero
    assert Account.objects.aggregate(total=Sum('balance'))['total'] == 0
    for account in Account.objects.all():
        sums = account.transactions.aggregate(
            credit=Sum('amount', filter=Q(type='credit'), default=0),
            debit=Sum('amount', filter=Q(type='debit'), default=0),
        )
        assert account.balance == sums['credit'] - sums['debit']
