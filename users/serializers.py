from django.contrib.auth import password_validation
from rest_framework import serializers

from .models import User


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    # Limit length to protect the slow hasher from huge inputs
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate(self, attrs):
        password_validation.validate_password(attrs['password'], User(email=attrs['email']))
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

