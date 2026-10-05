import pytest

from bank.models import SYSTEM_ACCOUNT_NUMBER, Transaction
from users.models import User

from .conftest import PASSWORD, assert_ledger_is_consistent, balance

REGISTER = '/api/auth/register/'
LOGIN = '/api/auth/login/'


@pytest.mark.django_db
def test_register_opens_account_with_deposit(api):
    response = api.post(REGISTER, {'email': 'New@Example.com', 'password': PASSWORD})

    assert response.status_code == 201
    user = User.objects.get(email='new@example.com')
    number = response.data['account_number']
    assert number == user.account.number
    assert len(number) == 10 and number.isdigit()
    assert balance(user) == 10000

    deposit = user.account.transactions.get()
    assert deposit.type == Transaction.Type.CREDIT
    assert deposit.kind == Transaction.Kind.DEPOSIT
    assert deposit.counterparty.number == SYSTEM_ACCOUNT_NUMBER
    assert_ledger_is_consistent()


def test_register_duplicate_email_ignores_case(api, alice):
    response = api.post(REGISTER, {'email': 'ALICE@example.com', 'password': PASSWORD})

    assert response.status_code == 400
    assert 'email' in response.data


@pytest.mark.django_db
def test_register_rejects_weak_password(api):
    response = api.post(REGISTER, {'email': 'weak@example.com', 'password': '12345678'})

    assert response.status_code == 400
    assert not User.objects.exists()


@pytest.mark.django_db
def test_register_is_atomic(api, monkeypatch):
    def broken(user):
        raise RuntimeError

    monkeypatch.setattr('users.serializers.open_account', broken)

    with pytest.raises(RuntimeError):
        api.post(REGISTER, {'email': 'new@example.com', 'password': PASSWORD})
    # User without an account must not stay in the database
    assert not User.objects.exists()


def test_account_number_collision_is_retried(make_user, monkeypatch):
    numbers = iter([111111111, 111111111, 222222222])
    monkeypatch.setattr('bank.services.secrets.randbelow', lambda _: next(numbers))

    first = make_user('first@example.com')
    second = make_user('second@example.com')

    assert first.account.number == '1111111111'
    assert second.account.number == '1222222222'


def test_login_returns_working_token(api, alice):
    response = api.post(LOGIN, {'email': 'ALICE@example.com', 'password': PASSWORD})

    assert response.status_code == 200
    api.credentials(HTTP_AUTHORIZATION=f'Bearer {response.data["access"]}')
    assert api.get('/api/account/').status_code == 200


def test_login_wrong_password(api, alice):
    response = api.post(LOGIN, {'email': 'alice@example.com', 'password': 'wrong'})

    assert response.status_code == 401
    assert 'access' not in response.data


def test_login_is_throttled(api, alice):
    for _ in range(5):
        api.post(LOGIN, {'email': 'alice@example.com', 'password': 'wrong'})

    response = api.post(LOGIN, {'email': 'alice@example.com', 'password': PASSWORD})
    assert response.status_code == 429


@pytest.mark.django_db
@pytest.mark.parametrize('url', ['/api/account/', '/api/account/transactions/', '/api/transfers/'])
def test_endpoints_require_auth(api, url):
    assert api.get(url).status_code == 401
