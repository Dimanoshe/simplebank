from django.contrib.auth import password_validation
from django.db import transaction
from rest_framework import serializers

from bank.services import open_account

from .models import User


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    # Limit length to protect the slow hasher from huge inputs
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)
    account_number = serializers.CharField(source='account.number', read_only=True)

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate(self, attrs):
        password_validation.validate_password(attrs['password'], User(email=attrs['email']))
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        open_account(user)
        return user
