"""
Accounts serializers — Register, JWT Login, Profile, Telegram connection.

Architecture:
    - CustomTokenObtainPairSerializer overrides the default SimpleJWT
      serializer to inject extra claims (role, full_name) into the token.
    - RegisterSerializer handles user creation with role validation.
    - ProfileReadSerializer / ProfileUpdateSerializer follow the
      read vs. write serializer separation principle.
"""
from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken

from .models import Profile

User = get_user_model()


# ---------------------------------------------------------------------------
# JWT Serializers
# ---------------------------------------------------------------------------

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Custom JWT login serializer.

    Extends the default to add:
        - `user_id`  — integer PK
        - `email`    — login identifier
        - `role`     — student | teacher | admin
        - `full_name` — first + last name

    These claims are embedded in the access token payload so the
    frontend can display role-based UI without an extra API call.
    """

    @classmethod
    def get_token(cls, user: Any) -> dict[str, Any]:
        """
        Generate JWT token with custom claims.

        Args:
            user: Authenticated User instance.

        Returns:
            Token dict with standard + custom claims.
        """
        token = super().get_token(user)

        # Custom claims — payload ga qo'shiladi
        token["user_id"] = user.pk
        token["email"] = user.email
        token["role"] = user.role
        token["full_name"] = user.get_full_name()

        return token


# ---------------------------------------------------------------------------
# Register Serializer
# ---------------------------------------------------------------------------

class RegisterSerializer(serializers.ModelSerializer):
    """
    User registration serializer.

    Public registration always creates a student. Privileged roles are managed
    only through the administrator panel.

    Validations:
        - Password must pass Django's password validators.
        - The role is never accepted from public input.
    """

    password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={"input_type": "password"},
        help_text="Kamida 8 ta belgi bo'lishi kerak.",
    )
    password_confirm = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
        help_text="Parolni qaytadan kiriting.",
    )

    class Meta:
        model = User
        fields = [
            "id", "email", "password", "password_confirm",
            "first_name", "last_name", "role",
        ]
        read_only_fields = ["id", "role"]

    def validate_email(self, value: str) -> str:
        """Case-insensitive uniqueness check — friendly 400 before DB constraint."""
        email = (value or "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Bu email allaqachon ro'yxatdan o'tgan.")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Parollar mos ekanligini tekshirish."""
        requested_role = self.initial_data.get("role")
        if requested_role and requested_role != User.Role.STUDENT:
            raise serializers.ValidationError({
                "role": "Imtiyozli rollarni faqat administrator tayinlaydi.",
            })
        password = attrs.get("password")
        password_confirm = attrs.get("password_confirm")

        if password != password_confirm:
            raise serializers.ValidationError(
                {"password_confirm": "Parollar mos kelmaydi."}
            )

        # Django password validators ni ishga tushirish
        try:
            validate_password(
                password,
                user=User(**{k: v for k, v in attrs.items() if k != "password_confirm"}),
            )
        except DjangoValidationError as e:
            raise serializers.ValidationError(
                {"password": list(e.messages)}
            )

        return attrs

    def create(self, validated_data: dict[str, Any]) -> Any:
        """Yangi User yaratish."""
        # password_confirm ni olib tashlash (User modelda yo'q)
        validated_data.pop("password_confirm", None)

        password = validated_data.pop("password")

        # Never honor a role supplied by an untrusted caller, even if this
        # serializer is instantiated indirectly with pre-validated data.
        validated_data.pop("role", None)
        user = User(role=User.Role.STUDENT, **validated_data)
        user.set_password(password)
        user.save()

        return user


# ---------------------------------------------------------------------------
# Profile Serializers
# ---------------------------------------------------------------------------

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Read-only profile serializer — profile sahifasi uchun.

    User va Profile ma'lumotlarini birlashtirib chiqaradi.
    """

    # Profile maydonlari — nested
    phone = serializers.CharField(source="profile.phone", read_only=True)
    bio = serializers.CharField(source="profile.bio", read_only=True)
    avatar = serializers.ImageField(source="profile.avatar", read_only=True)
    date_of_birth = serializers.DateField(
        source="profile.date_of_birth", read_only=True,
    )
    is_platform_admin = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name",
            "role", "phone", "bio", "avatar", "date_of_birth",
            "created_at",
            "language", "is_staff", "is_superuser", "is_platform_admin",
        ]
        read_only_fields = fields  # Hammasi read-only

    def get_is_platform_admin(self, obj: Any) -> bool:
        from apps.accounts.access import is_platform_admin
        return is_platform_admin(obj)


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Write serializer — profile ma'lumotlarini tahrirlash.

    User modelning o'zini (first_name, last_name) va
    Profile modelni (phone, bio, avatar, date_of_birth) yangilaydi.
    """

    # Profile maydonlari
    phone = serializers.CharField(
        source="profile.phone", required=False, allow_blank=True,
    )
    bio = serializers.CharField(
        source="profile.bio", required=False, allow_blank=True,
    )
    avatar = serializers.ImageField(
        source="profile.avatar", required=False, allow_null=True,
    )
    date_of_birth = serializers.DateField(
        source="profile.date_of_birth", required=False, allow_null=True,
    )

    class Meta:
        model = User
        fields = [
            "first_name", "last_name", "language",
            "phone", "bio", "avatar", "date_of_birth",
        ]

    def update(self, instance: Any, validated_data: dict[str, Any]) -> Any:
        """
        User va Profile ni birgalikda yangilash.

        Nested profile maydonlarini ajratib, alohida saqlash.
        """
        profile_data = validated_data.pop("profile", {})

        # User maydonlarini yangilash
        instance.first_name = validated_data.get(
            "first_name", instance.first_name,
        )
        instance.last_name = validated_data.get(
            "last_name", instance.last_name,
        )
        if "language" in validated_data:
            instance.language = validated_data["language"]
        instance.save()

        # Profile maydonlarini yangilash
        profile = instance.profile
        for attr, value in profile_data.items():
            setattr(profile, attr, value)
        profile.save()

        return instance


# ---------------------------------------------------------------------------
# Telegram Connection Serializer
# ---------------------------------------------------------------------------

class ConnectTelegramSerializer(serializers.Serializer):
    """No raw Telegram ID is accepted from the web client."""

    chat_id = serializers.IntegerField(
        required=False,
        help_text="Deprecated; start a two-channel challenge instead.",
    )

    def validate_chat_id(self, value: int) -> int:
        """
        Chat ID ni tekshirish:
        - Musbat son bo'lishi kerak.
        - Boshqa foydalanuvchiga tegishli bo'lmasligi kerak.
        """
        raise serializers.ValidationError(
            "Telegram ID ni qo'lda bog'lab bo'lmaydi. "
            "Telegram botdagi tasdiqlangan bog'lash oqimidan foydalaning."
        )


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """Ensure inactive users cannot refresh — defense-in-depth beyond SIMPLE_JWT."""

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        data = super().validate(attrs)
        try:
            refresh = JWTRefreshToken(attrs["refresh"])
            user_id = refresh.payload.get("user_id") or refresh.payload.get("userId")
            if user_id is not None:
                try:
                    u = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    pass
                else:
                    if not u.is_active:
                        from rest_framework_simplejwt.exceptions import InvalidToken
                        raise InvalidToken("No active account found with the given credentials")
        except Exception as e:
            from rest_framework_simplejwt.exceptions import InvalidToken as _Invalid
            if isinstance(e, _Invalid):
                raise
            # let super()'s error surface — ignore decode errors here
            pass
        return data
