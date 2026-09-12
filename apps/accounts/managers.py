"""
Custom UserManager — handles user creation with role-based defaults.

Extends BaseUserManager to support email-as-username and role assignment.
"""
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager["User"]):
    """
    Custom manager where email is the unique identifier for authentication.

    Usage:
        User.objects.create_user(email="a@b.com", password="pass", role="student")
        User.objects.create_superuser(email="admin@b.com", password="pass")
    """

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields,
    ) -> "User":
        if not email:
            raise ValueError("Email kiritilishi shart.")
        email = self.normalize_email(email)
        extra_fields.setdefault("is_active", True)

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields,
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser is_staff=True bo'lishi kerak.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser is_superuser=True bo'lishi kerak.")

        return self.create_user(email, password, **extra_fields)
