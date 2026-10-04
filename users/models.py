from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password):
        # Store email in lower case so it is unique without case
        user = self.model(email=email.lower())
        user.set_password(password)
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, email):
        # Login works with any letter case
        return self.get(email__iexact=email)


class User(AbstractBaseUser):
    email = models.EmailField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    EMAIL_FIELD = 'email'

    def __str__(self):
        return self.email
