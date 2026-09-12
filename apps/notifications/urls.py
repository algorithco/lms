"""Notifications app URL configuration."""
from django.urls import path

from . import views
from . import telegram_auth

app_name = "notifications"

urlpatterns = [
    # Telegram webhook (production)
    path("telegram/webhook/", views.telegram_webhook_view, name="telegram-webhook"),

    # Telegram Auth (web login via bot)
    path("telegram/auth/start/", telegram_auth.telegram_auth_start, name="tg-auth-start"),
    path("telegram/auth/<str:token>/status/", telegram_auth.telegram_auth_status, name="tg-auth-status"),
    # NOTE: "code/login/" MUST precede "<str:token>/login/" — otherwise the
    # literal path "code" is captured by <str:token> and code login 405s.
    path("telegram/auth/code/login/", telegram_auth.telegram_auth_code_login, name="tg-auth-code-login"),
    path("telegram/auth/<str:token>/login/", telegram_auth.telegram_auth_login, name="tg-auth-login"),

    # Web Push
    path("push/subscribe/", views.push_subscribe_view, name="push-subscribe"),
    path("push/unsubscribe/", views.push_unsubscribe_view, name="push-unsubscribe"),
    path("push/vapid-key/", views.push_vapid_key_view, name="push-vapid-key"),
]
