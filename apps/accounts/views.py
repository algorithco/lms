"""
Accounts views — Register, JWT Login, Profile, Telegram connection.

All views use DRF's generic views and mixins for clean, reusable code.
JWT endpoints (login, refresh, logout) are provided by SimpleJWT views
with our custom serializer for extra token claims.
"""
from typing import Any

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .permissions import IsOwnerOrReadOnly
from .serializers import (
    ConnectTelegramSerializer,
    CustomTokenObtainPairSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    UserProfileSerializer,
)

import django.contrib.auth as auth

User = auth.get_user_model()


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — Yangi foydalanuvchi ro'yxatdan o'tkazish."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Ro'yxatdan o'tish",
        description=(
            "Yangi foydalanuvchi yaratish.\n\n"
            "Public registration always creates a student account. "
            "Teachers are promoted by an administrator.\n\n"
            "Muvaffaqiyatli ro'yxatdan o'tgandan keyin JWT token qaytariladi."
        ),
        request=RegisterSerializer,
        responses={
            201: {
                "description": "Muvaffaqiyatli ro'yxatdan o'tildi",
                "examples": [{
                    "user": {"id": 1, "email": "user@example.com", "role": "student"},
                    "tokens": {"access": "eyJ...", "refresh": "eyJ..."},
                    "message": "Muvaffaqiyatli ro'yxatdan o'tdingiz!",
                }],
            },
            400: {"description": "Validation xatoligi"},
        },
        tags=["Auth"],
    )
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Ro'yxatdan o'tish va token bilan qaytarish."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "user": UserProfileSerializer(user).data,
                "tokens": {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                "message": "Muvaffaqiyatli ro'yxatdan o'tdingiz!",
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# JWT Login (Custom)
# ---------------------------------------------------------------------------
class CustomTokenObtainPairView(TokenObtainPairView):
    """POST /api/auth/login/ — Email + password orqali JWT token olish."""

    serializer_class = CustomTokenObtainPairSerializer

    @extend_schema(
        summary="Tizimga kirish (JWT)",
        description=(
            "Email va parol orqali JWT token olish.\n\n"
            "Token payload'iga qo'shimcha ma'lumotlar qo'shiladi:\n"
            "- `user_id`, `email`, `role`, `full_name`, `is_active`\n\n"
            "**Access token** API so'rovlarida ishlatiladi.\n"
            "**Refresh token** access token muddati tugaganda yangilash uchun."
        ),
        request=CustomTokenObtainPairSerializer,
        responses={
            200: {
                "description": "Muvaffaqiyatli kirildi",
                "examples": [{
                    "tokens": {"access": "eyJ...", "refresh": "eyJ..."},
                    "user": {"id": 1, "email": "user@example.com", "role": "student", "full_name": "Jasur Karimov"},
                }],
            },
            401: {"description": "Noto'g'ri email yoki parol"},
        },
        tags=["Auth"],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Login — access va refresh token olish."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        tokens = serializer.validated_data
        user = serializer.user

        return Response(
            {
                "tokens": {
                    "access": str(tokens["access"]),
                    "refresh": str(tokens["refresh"]),
                },
                "user": {
                    "id": user.pk,
                    "email": user.email,
                    "role": user.role,
                    "full_name": user.get_full_name(),
                    "is_active": user.is_active,
                },
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Token Refresh
# ---------------------------------------------------------------------------
class CustomTokenRefreshView(TokenRefreshView):
    """POST /api/auth/token/refresh/ — Refresh token yangilash."""

    @extend_schema(
        summary="Token yangilash",
        description=(
            "Refresh token orqali yangi access token olish.\n\n"
            "`ROTATE_REFRESH_TOKENS=True` bo'lgani uchun, "
            "har safar yangi refresh token ham qaytariladi."
        ),
        responses={
            200: {"description": "Yangi tokenlar"},
            401: {"description": "Noto'g'ri yoki muddati tugagan token"},
        },
        tags=["Auth"],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        return super().post(request, *args, **kwargs)


# ---------------------------------------------------------------------------
# Logout (Blacklist refresh token)
# ---------------------------------------------------------------------------
class LogoutView(APIView):
    """POST /api/auth/logout/ — Refresh token'ni blacklist'ga qo'shish."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Tizimdan chiqish",
        description=(
            "Refresh token'ni blacklist'ga qo'shish.\n\n"
            "Token bekor qilinadi va qayta ishlatib bo'lmaydi."
        ),
        request={"refresh": "eyJ..."},
        responses={
            200: {"description": "Muvaffaqiyatli chiqildi"},
            400: {"description": "Noto'g'ri token"},
        },
        tags=["Auth"],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Refresh token'ni blacklist'ga qo'shish."""
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response(
                {"error": "Refresh token kiritilishi shart."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response(
                {"error": "Noto'g'ri yoki muddati tugagan token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"message": "Muvaffaqiyatli chiqdingiz!"},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Profile (Read & Update)
# ---------------------------------------------------------------------------
@extend_schema_view(
    get=extend_schema(
        summary="Profilni ko'rish",
        description="Foydalanuvchining to'liq profil ma'lumotlari.",
        responses={200: UserProfileSerializer},
        tags=["Auth"],
    ),
    patch=extend_schema(
        summary="Profilni tahrirlash",
        description="Profil ma'lumotlarini qisman yangilash (PATCH).",
        request=ProfileUpdateSerializer,
        responses={200: UserProfileSerializer},
        tags=["Auth"],
    ),
)
class ProfileView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/me/ — Profilni ko'rish va tahrirlash."""

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return ProfileUpdateSerializer
        return UserProfileSerializer

    def get_object(self):
        return self.request.user


# ---------------------------------------------------------------------------
# Telegram Connect
# ---------------------------------------------------------------------------
class TelegramConnectView(APIView):
    """POST /api/auth/telegram/connect/ — start a verified link challenge."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Telegram bog'lash",
        description=(
            "Returns a short-lived bot deep link. The signed Telegram update "
            "confirms the numeric ID before the account is linked."
        ),
        request=ConnectTelegramSerializer,
        responses={
            200: {"description": "Telegram bog'landi"},
            400: {"description": "Validation xatoligi"},
        },
        tags=["Auth"],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a challenge; never trust a caller-provided chat ID."""
        serializer = ConnectTelegramSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        from django.conf import settings
        from .services.telegram_link import create_link_challenge
        token = create_link_challenge(request.user)
        bot_name = getattr(settings, "TELEGRAM_BOT_NAME", "uz_essaygrader_bot")

        return Response(
            {
                "message": "Telegram botda bog'lashni tasdiqlang.",
                "deep_link": f"https://t.me/{bot_name}?start=link_{token}",
                "token": token,
                "expires_in": 600,
            },
            status=status.HTTP_200_OK,
        )


class TelegramConnectStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, token: str) -> Response:
        from .services.telegram_link import link_challenge_status
        state = link_challenge_status(request.user, token)
        return Response({"status": state})
