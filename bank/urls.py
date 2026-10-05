from django.urls import path

from .views import AccountView, TransactionListView, TransferView

urlpatterns = [
    path('account/', AccountView.as_view(), name='account'),
    path('account/transactions/', TransactionListView.as_view(), name='transactions'),
    path('transfers/', TransferView.as_view(), name='transfers'),
]
