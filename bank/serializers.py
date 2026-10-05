from decimal import Decimal

from rest_framework import serializers

from .models import Account, Transaction, Transfer


class MoneyField(serializers.DecimalField):
    default_error_messages = {'float': 'Send the amount as a string, for example "10.50".'}

    def __init__(self, **kwargs):
        super().__init__(max_digits=14, decimal_places=2, **kwargs)

    def to_internal_value(self, data):
        # A float like 0.1 is not exact, so accept only strings and integers
        if isinstance(data, float):
            self.fail('float')
        return super().to_internal_value(data)


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['number', 'balance']


class TransactionSerializer(serializers.ModelSerializer):
    counterparty = serializers.CharField(source='counterparty.number')
    timestamp = serializers.DateTimeField(source='created_at')

    class Meta:
        model = Transaction
        fields = ['id', 'amount', 'type', 'kind', 'counterparty', 'timestamp']


class TransferSerializer(serializers.ModelSerializer):
    to_account = serializers.RegexField(r'^[0-9]{10}$', source='receiver.number')
    amount = MoneyField(min_value=Decimal('0.01'), max_value=Decimal('1000000.00'))
    timestamp = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = Transfer
        fields = ['id', 'to_account', 'amount', 'fee', 'timestamp']
        read_only_fields = ['id', 'fee']


class DateRangeSerializer(serializers.Serializer):
    """Query params ?from=YYYY-MM-DD&to=YYYY-MM-DD, both days are included."""

    def get_fields(self):
        # "from" is a Python keyword, so the fields are declared here
        return {
            'from': serializers.DateField(required=False),
            'to': serializers.DateField(required=False),
        }

    def validate(self, attrs):
        if 'from' in attrs and 'to' in attrs and attrs['from'] > attrs['to']:
            raise serializers.ValidationError('"from" must not be later than "to".')
        return attrs
