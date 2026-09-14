"""
Accounts app URL configuration.

Endpoints:
    POST /register/          — Ro'yxatdan o'tish
    POST /login/             — JWT token olish (login)
    POST /token/refresh/     — Refresh token yangilash
    POST /logout/            — Token bekor qilish (blacklist)
    GET  /me/                — Profilni ko'rish
    PATCH /me/               — Profilni tahrirlash
    POST /telegram/connect/  — Telegram Chat ID biriktirish
"""
from django.urls import path

from . import views
from . import google_auth as google_auth_views

app_name = "accounts"

urlpatterns = [
    # -- Auth (AllowAny) ------------------------------------------------------
    path(
        "register/",
        views.RegisterView.as_view(),
        name="register",
    ),
    path(
        "login/",
        views.CustomTokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path(
        "token/refresh/",
        views.CustomTokenRefreshView.as_view(),
        name="token_refresh",
    ),

    # -- Auth (Authenticated) -------------------------------------------------
    path(
        "logout/",
        views.LogoutView.as_view(),
        name="logout",
    ),

    # -- Profile --------------------------------------------------------------
    path(
        "me/",
        views.ProfileView.as_view(),
        name="profile",
    ),

    # -- Password reset (JSON, React SPA) ---------------------------------------
    path(
        "password-reset/",
        views.PasswordResetRequestView.as_view(),
        name="password_reset_request",
    ),
    path(
        "password-reset/confirm/",
        views.PasswordResetConfirmAPIView.as_view(),
        name="password_reset_confirm_api",
    ),

    # -- Django session bridge (React SPA: WS + session JSON) -------------------
    path(
        "session/",
        views.SessionLoginView.as_view(),
        name="session_login",
    ),
    path(
        "session/status/",
        views.SessionStatusView.as_view(),
        name="session_status",
    ),
    path(
        "session/logout/",
        views.SessionLogoutView.as_view(),
        name="session_logout",
    ),

    # -- Telegram -------------------------------------------------------------
    path(
        "telegram/connect/",
        views.TelegramConnectView.as_view(),
        name="telegram_connect",
    ),
    path(
        "telegram/connect/status/<str:token>/",
        views.TelegramConnectStatusView.as_view(),
        name="telegram_connect_status",
    ),

    # -- Google OAuth ----------------------------------------------------------
    path(
        "google/",
        google_auth_views.google_auth_start,
        name="google_auth_start",
    ),
    path(
        "google/callback/",
        google_auth_views.google_auth_callback,
        name="google_auth_callback",
    ),
]
