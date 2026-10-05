from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError

from .models import Transaction
from .serializers import (
    AccountSerializer,
    DateRangeSerializer,
    TransactionSerializer,
    TransferSerializer,
)
from .services import TransferError, transfer


class AccountView(generics.RetrieveAPIView):
    serializer_class = AccountSerializer

    def get_object(self):
        return self.request.user.account


@extend_schema(parameters=[DateRangeSerializer])
class TransactionListView(generics.ListAPIView):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        params = DateRangeSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        dates = params.validated_data

        queryset = Transaction.objects.filter(account__user=self.request.user)
        if 'from' in dates:
            queryset = queryset.filter(created_at__date__gte=dates['from'])
        if 'to' in dates:
            queryset = queryset.filter(created_at__date__lte=dates['to'])
        return queryset.select_related('counterparty').order_by('-created_at', '-id')


class TransferView(generics.CreateAPIView):
    serializer_class = TransferSerializer
    throttle_scope = 'transfer'

    def perform_create(self, serializer):
        data = serializer.validated_data
        try:
            serializer.instance = transfer(
                self.request.user, data['receiver']['number'], data['amount']
            )
        except TransferError as error:
            raise ValidationError({'detail': str(error)})
