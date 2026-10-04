from django.db import IntegrityError
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import RegisterSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = 'register'

    def perform_create(self, serializer):
        # Two parallel requests with the same email can pass validation
        try:
            serializer.save()
        except IntegrityError:
            raise ValidationError({'email': ['A user with this email already exists.']})


class LoginView(TokenObtainPairView):
    throttle_scope = 'login'
