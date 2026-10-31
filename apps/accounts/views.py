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
    # JWT-only public endpoint: never enforce SessionAuthentication/CSRF here.
    # Otherwise a stale `sessionid` cookie (admin login, arena bridge, 2nd
    # user in same browser) triggers 403 "CSRF Failed" on registration.
    authentication_classes: list = []
    throttle_scope = "login"

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
                "examples": [
                    {
                        "user": {
                            "id": 1,
                            "email": "user@example.com",
                            "role": "student",
                        },
                        "tokens": {"access": "eyJ...", "refresh": "eyJ..."},
                        "message": "Muvaffaqiyatli ro'yxatdan o'tdingiz!",
                    }
                ],
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
    throttle_scope = "login"

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
                "examples": [
                    {
                        "tokens": {"access": "eyJ...", "refresh": "eyJ..."},
                        "user": {
                            "id": 1,
                            "email": "user@example.com",
                            "role": "student",
                            "full_name": "Jasur Karimov",
                        },
                    }
                ],
            },
            401: {"description": "Noto'g'ri email yoki parol"},
        },
        tags=["Auth"],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Login — access va refresh token olish."""
        from apps.accounts.access import is_platform_admin

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
                    "language": getattr(user, "language", "uz"),
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                    "is_platform_admin": is_platform_admin(user),
                    "plan": UserProfileSerializer(user).get_plan(user),
                    "tariff": UserProfileSerializer(user).get_tariff(user),
                    "is_paid": UserProfileSerializer(user).get_is_paid(user),
                    "is_premium": UserProfileSerializer(user).get_is_premium(user),
                    "has_pro_access": UserProfileSerializer(user).get_has_pro_access(user),
                },
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Token Refresh
# ---------------------------------------------------------------------------
class CustomTokenRefreshView(TokenRefreshView):
    """POST /api/auth/token/refresh/ — Refresh token yangilash."""

    from .serializers import CustomTokenRefreshSerializer

    serializer_class = CustomTokenRefreshSerializer  # type: ignore[assignment]

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


class DirectTelegramLinkView(APIView):
    """POST /api/auth/telegram/direct-link/
    Allows an authenticated user to bind or update their telegram_chat_id directly.
    Payload: { "telegram_chat_id": 5582178765 }
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Telegram ID to'g'ridan-to'g'ri bog'lash",
        description="Foydalanuvchi hisobiga telegram_chat_id ni saqlaydi va bildirishnomalarni faollashtiradi.",
        responses={
            200: {"description": "Telegram bog'landi"},
            400: {"description": "Xatolik"},
        },
        tags=["Auth"],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        from django.utils import timezone

        chat_id_raw = request.data.get("telegram_chat_id")
        if not chat_id_raw:
            return Response(
                {"error": "Telegram ID kiritilishi shart."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            chat_id = int(str(chat_id_raw).strip())
            if chat_id <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            return Response(
                {"error": "Telegram ID musbat butun son bo'lishi kerak."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        existing = (
            User.objects.filter(telegram_chat_id=chat_id)
            .exclude(id=request.user.id)
            .first()
        )
        if existing:
            if (
                request.user.is_superuser
                or request.user.is_staff
                or getattr(request.user, "role", "") == "admin"
            ):
                existing.telegram_chat_id = None
                existing.save(update_fields=["telegram_chat_id"])
            else:
                return Response(
                    {
                        "error": "Ushbu Telegram ID allaqachon boshqa hisobga bog'langan."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        user = request.user
        user.telegram_chat_id = chat_id
        user.telegram_identity_verified_at = timezone.now()
        user.save(update_fields=["telegram_chat_id", "telegram_identity_verified_at"])

        try:
            from apps.attendance.models import NotificationPreference

            pref, _ = NotificationPreference.objects.get_or_create(user=user)
            pref.telegram_enabled = True
            pref.save(update_fields=["telegram_enabled"])
        except Exception:
            pass

        return Response(
            {
                "ok": True,
                "telegram_chat_id": user.telegram_chat_id,
                "message": f"Telegram ID ({chat_id}) muvaffaqiyatli bog'landi! Bildirishnomalar va to'lov kvitansiyalari ushbu akkauntga yo'naltiriladi.",
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Django Session Bridge (for React SPA: WS arena + session-only JSON views)
# ---------------------------------------------------------------------------
# The arena WebSocket consumer uses AuthMiddlewareStack (session cookie only —
# a JWT in a header cannot authenticate a WebSocket). The old server-rendered
# /login/ page is gone, so the SPA establishes the Django session through
# these JSON endpoints instead (same-origin, cookies incl. CSRF).
class SessionLoginView(APIView):
    """POST /api/auth/session/ — {email, password} → Django session login."""

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "login"

    @extend_schema(
        summary="Django session ochish (SPA bridge)",
        description=(
            "Email va parol orqali Django session (cookie) ochish. "
            "Arena WebSocket va session-only JSON endpointlar uchun."
        ),
        request={"email": "user@example.com", "password": "secret"},
        responses={200: {"description": "Session ochildi"}},
        tags=["Auth"],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        from django.contrib.auth import authenticate
        from django.contrib.auth import login as django_login
        from django.middleware.csrf import get_token

        email = str(request.data.get("email", "")).strip().lower()
        password = str(request.data.get("password", ""))

        if not email or not password:
            return Response(
                {"detail": "Email va parol kiritilishi shart."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(request, username=email, password=password)
        if user is None or not user.is_active:
            return Response(
                {"detail": "Noto'g'ri email yoki parol."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        django_login(request, user)
        # Force the csrftoken cookie so sessionApi() can POST session views.
        get_token(request)

        return Response(
            {
                "ok": True,
                "user": {
                    "id": user.pk,
                    "email": user.email,
                    "role": user.role,
                },
            },
            status=status.HTTP_200_OK,
        )


class SessionStatusView(APIView):
    """GET /api/auth/session/status/ — Django session holatini tekshirish."""

    permission_classes = [AllowAny]

    def get(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        user = request.user
        authed = bool(user and user.is_authenticated)
        tokens = None
        user_data = None
        if authed:
            from rest_framework_simplejwt.tokens import RefreshToken
            from apps.accounts.access import is_platform_admin

            refresh = RefreshToken.for_user(user)
            tokens = {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            }
            user_data = {
                "id": user.pk,
                "email": user.email,
                "role": user.role,
                "full_name": user.get_full_name(),
                "is_active": user.is_active,
                "language": getattr(user, "language", "uz"),
                "is_staff": user.is_staff,
                "is_superuser": user.is_superuser,
                "is_platform_admin": is_platform_admin(user),
            }

        return Response(
            {
                "authenticated": authed,
                "user": user_data,
                "tokens": tokens,
            },
            status=status.HTTP_200_OK,
        )


class SessionLogoutView(APIView):
    """POST /api/auth/session/logout/ — Django session'ni yopish."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        from django.contrib.auth import logout as django_logout

        django_logout(request)
        return Response({"ok": True}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Password Reset (JSON, for React SPA)
# ---------------------------------------------------------------------------
# The emailed link points at the SPA route /password-reset/confirm/<uid>/<token>/
# (see registration/password_reset_email.* templates). Same-origin with the SPA
# after cutover, so {{ protocol }}://{{ domain }} stays correct.
class PasswordResetRequestView(APIView):
    """POST /api/auth/password-reset/ — reset havolasini emailga yuborish."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        summary="Parolni tiklash havolasini yuborish",
        description="Emailga parol tiklash havolasi yuborish (har doim 200).",
        request={"email": "user@example.com"},
        responses={200: {"description": "Havola yuborildi (agar email mavjud bo'lsa)"}},
        tags=["Auth"],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        from django.conf import settings
        from django.contrib.auth.forms import PasswordResetForm
        from django.contrib.auth.tokens import default_token_generator
        from django.core.cache import cache
        from django.core.exceptions import ImproperlyConfigured
        from django.utils.crypto import salted_hmac
        from urllib.parse import urlsplit

        from apps.core.translations import get_user_language

        email = str(request.data.get("email", "")).strip().casefold()

        # Same per-IP / per-email throttle as SecurePasswordResetView.
        ip = request.META.get("REMOTE_ADDR", "unknown")
        throttled = False
        for kind, value, limit in (("ip", ip, 20), ("email", email, 3)):
            digest = salted_hmac("password-reset-rate", f"{kind}:{value}").hexdigest()
            key = f"password-reset:{kind}:{digest}"
            if cache.add(key, 1, timeout=3600):
                count = 1
            else:
                count = cache.incr(key)
            throttled |= count > limit

        if email and not throttled:
            form = PasswordResetForm({"email": email})
            if form.is_valid():
                options = {
                    "use_https": request.is_secure() or not settings.DEBUG,
                    "token_generator": default_token_generator,
                    "email_template_name": "registration/password_reset_email.txt",
                    "subject_template_name": "registration/password_reset_subject.txt",
                    "html_email_template_name": "registration/password_reset_email.html",
                    "request": request,
                    "extra_email_context": {
                        "lang": get_user_language(request),
                    },
                }
                if not settings.DEBUG:
                    site = urlsplit(settings.SITE_URL)
                    if (
                        site.scheme != "https"
                        or not site.netloc
                        or site.path not in ("", "/")
                    ):
                        raise ImproperlyConfigured(
                            "SITE_URL must be an HTTPS origin for password reset."
                        )
                    options["domain_override"] = site.netloc
                form.save(**options)

        # Generic response — never reveal whether the email exists.
        return Response(
            {"ok": True, "message": "Agar email ro'yxatda bo'lsa, havola yuborildi."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmAPIView(APIView):
    """POST /api/auth/password-reset/confirm/ — yangi parolni saqlash."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        summary="Yangi parolni saqlash",
        description="uid + token tekshirib, yangi parolni saqlash.",
        request={
            "uid": "MQ",
            "token": "cx...",
            "new_password1": "secret123",
            "new_password2": "secret123",
        },
        responses={
            200: {"description": "Parol yangilandi"},
            400: {"description": "Havola yaroqsiz yoki parol xato"},
        },
        tags=["Auth"],
    )
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        from django.contrib.auth.password_validation import (
            validate_password as django_validate_password,
        )
        from django.contrib.auth.tokens import default_token_generator
        from django.core.exceptions import ValidationError as DjangoValidationError
        from django.utils.encoding import force_str
        from django.utils.http import urlsafe_base64_decode

        uid = str(request.data.get("uid", ""))
        token = str(request.data.get("token", ""))
        p1 = str(request.data.get("new_password1", ""))
        p2 = str(request.data.get("new_password2", ""))

        user = None
        try:
            pk = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=pk)
        except Exception:
            user = None

        if user is None or not default_token_generator.check_token(user, token):
            return Response(
                {"detail": "Havola yaroqsiz yoki muddati tugagan."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not p1 or p1 != p2:
            return Response(
                {"new_password2": ["Parollar mos kelmaydi."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            django_validate_password(p1, user=user)
        except DjangoValidationError as e:
            return Response(
                {"new_password1": list(e.messages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(p1)
        user.save(update_fields=["password"])
        return Response(
            {"ok": True, "message": "Parol muvaffaqiyatli yangilandi."},
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Telegram Official Login Widget / 1-Click OAuth
# ---------------------------------------------------------------------------
class TelegramWidgetAuthView(APIView):
    """
    POST /api/auth/telegram/widget/
    Official Telegram Login Widget (1-Click Auth).

    Payload:
    {
        "id": 12345678,
        "first_name": "...",
        "last_name": "...",
        "username": "...",
        "photo_url": "...",
        "auth_date": 1718000000,
        "hash": "..."
    }
    """

    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_scope = "login"

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        import hashlib
        import hmac
        import time
        from django.conf import settings
        from django.contrib.auth import login
        from apps.accounts.access import is_platform_admin
        from apps.accounts.services.telegram_identity import (
            TelegramIdentityUnverified,
            get_or_create_telegram_user,
        )

        data = request.data
        if not isinstance(data, dict):
            return Response(
                {"error": "Noto'g'ri so'rov formati."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        if not bot_token:
            return Response(
                {"error": "Telegram bot tokeni sozlanmagan."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        received_hash = data.get("hash")
        if not received_hash or not isinstance(received_hash, str):
            return Response(
                {"error": "Hash parametri topilmadi."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            auth_date = int(data.get("auth_date", 0))
            if abs(time.time() - auth_date) > 86400:
                return Response(
                    {"error": "Avtorizatsiya muddati tugagan (24 soat)."},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
        except (ValueError, TypeError):
            return Response(
                {"error": "Noto'g'ri auth_date parametri."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        check_items = []
        for k in sorted(data.keys()):
            if k != "hash" and data[k] is not None:
                check_items.append(f"{k}={data[k]}")
        data_check_string = "\n".join(check_items)

        secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
        computed_hash = hmac.new(
            secret_key, data_check_string.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(computed_hash, received_hash):
            return Response(
                {"error": "Telegram ma'lumotlari tasdiqlanmadi."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            tg_id = int(data.get("id"))
        except (ValueError, TypeError):
            return Response(
                {"error": "Noto'g'ri Telegram ID."}, status=status.HTTP_400_BAD_REQUEST
            )

        first_name = str(data.get("first_name", "") or "")
        last_name = str(data.get("last_name", "") or "")
        username = str(data.get("username", "") or "")
        photo_url = str(data.get("photo_url", "") or "")

        try:
            user, is_new_user = get_or_create_telegram_user(
                {
                    "id": tg_id,
                    "first_name": first_name,
                    "last_name": last_name,
                    "username": username,
                }
            )
        except TelegramIdentityUnverified as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not user.is_active:
            return Response(
                {"error": "Hisob faol emas."}, status=status.HTTP_403_FORBIDDEN
            )

        if (
            photo_url
            and hasattr(user, "profile")
            and not getattr(user.profile, "picture_url", "")
        ):
            user.profile.picture_url = photo_url
            user.profile.save(update_fields=["picture_url"])

        login(request, user)
        request.session.set_expiry(60 * 60 * 24 * 30)

        refresh = RefreshToken.for_user(user)

        is_admin = is_platform_admin(user)
        return Response(
            {
                "status": "ok",
                "redirect": "/panel" if is_admin else "/dashboard",
                "user": {
                    "id": user.pk,
                    "email": user.email,
                    "role": getattr(user, "role", "student"),
                    "full_name": user.get_full_name(),
                    "is_active": user.is_active,
                    "language": getattr(user, "language", "uz"),
                    "is_staff": user.is_staff,
                    "is_superuser": user.is_superuser,
                    "is_platform_admin": is_admin,
                    "avatar": photo_url or getattr(user.profile, "picture_url", ""),
                },
                "tokens": {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
            },
            status=status.HTTP_200_OK,
        )
