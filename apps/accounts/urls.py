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
