"""
Notifications views — Telegram webhook + Web Push subscription endpoints.
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import threading

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication

logger = logging.getLogger(__name__)

# Global bot application instance (initialized on first request)
_bot_app = None
_bot_init_lock = threading.Lock()

# The shared PTB Application is NOT thread-safe: python-telegram-bot's own
# webhook server processes updates on a single event loop. Concurrent
# webhook POSTs here would each spin up their own asyncio.run() loop and
# race shared handler state (context.user_data, conversation flows), so
# updates are serialized through this lock.
_webhook_lock = threading.Lock()


def _get_bot_app():
    """Get or create the bot Application singleton (thread-safe)."""
    global _bot_app
    if _bot_app is not None:
        return _bot_app

    with _bot_init_lock:
        if _bot_app is not None:
            return _bot_app

        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        if not token:
            return None

        from telegram.ext import ApplicationBuilder

        from apps.notifications.bot.handlers import post_init, setup_handlers

        app = ApplicationBuilder().token(token).post_init(post_init).build()
        setup_handlers(app)

        # Initialize once (job queue, persistence, post_init / command menu)
        # so the application is fully ready before any update is processed.
        try:
            asyncio.run(app.initialize())
        except Exception:
            logger.exception("Bot application initialize failed")

        _bot_app = app
        return app


@csrf_exempt
@require_POST
def telegram_webhook_view(request: HttpRequest) -> HttpResponse:
    """
    Telegram webhook endpoint.

    Receives updates from Telegram and processes them.

    Every request must carry the configured Telegram secret header.
    """
    secret = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
    if not secret:
        logger.error("Webhook rejected: TELEGRAM_WEBHOOK_SECRET is not configured")
        return HttpResponse("Webhook not configured", status=503)

    header = request.META.get("HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN", "")
    if not secrets.compare_digest(header, secret):
        logger.warning("Webhook rejected: bad secret token (ip=%s)", request.META.get("REMOTE_ADDR", "?"))
        return HttpResponse("Unauthorized", status=401)

    # Telegram updates are small; reject oversized authenticated payloads
    # before JSON parsing or bot initialization.
    if len(request.body) > 1024 * 1024:
        return HttpResponse("Update too large", status=413)

    # Authentication happens before expensive bot initialization or parsing.
    app = _get_bot_app()
    if app is None:
        return HttpResponse("Bot not configured", status=503)

    try:
        from telegram import Update

        data = json.loads(request.body)
        update = Update.de_json(data, app.bot)

        # Process update asynchronously — serialized so concurrent webhook
        # POSTs can never mutate shared handler state in parallel.
        with _webhook_lock:
            asyncio.run(app.process_update(update))

        return HttpResponse("OK")
    except Exception as e:
        logger.exception("Telegram webhook error: %s", e)
        return HttpResponse("OK")  # Always return OK to Telegram


# ---------------------------------------------------------------------------
# Web Push Subscription
# ---------------------------------------------------------------------------

@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def push_subscribe_view(request: HttpRequest) -> HttpResponse:
    """
    POST /api/notifications/push/subscribe/

    Save push subscription from browser.

    Request body:
    {
        "endpoint": "https://fcm.googleapis.com/...",
        "p256dh": "...",
        "auth": "..."
    }
    """
    user = request.user

    if not user or not user.is_active:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        data = request.data
        if not isinstance(data, dict):
            return JsonResponse({"error": "Invalid JSON object"}, status=400)
        endpoint = data.get("endpoint", "")
        p256dh = data.get("p256dh", "")
        auth_key = data.get("auth", "")

        if not endpoint or not p256dh or not auth_key:
            return JsonResponse({"error": "Missing fields"}, status=400)

        from apps.notifications.models import PushSubscription

        sub, created = PushSubscription.objects.update_or_create(
            user=user,
            endpoint=endpoint,
            defaults={
                "p256dh": p256dh,
                "auth": auth_key,
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
                "is_active": True,
            },
        )

        logger.info("Push subscription saved: user=%d, created=%s", user.id, created)
        return JsonResponse({"success": True, "created": created})

    except Exception as e:
        logger.error("Push subscribe error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


@api_view(["POST"])
@authentication_classes([JWTAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def push_unsubscribe_view(request: HttpRequest) -> HttpResponse:
    """
    POST /api/notifications/push/unsubscribe/

    Remove push subscription.
    """
    user = request.user

    if not user or not user.is_active:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    try:
        data = request.data
        if not isinstance(data, dict):
            return JsonResponse({"error": "Invalid JSON object"}, status=400)
        endpoint = data.get("endpoint", "")

        from apps.notifications.models import PushSubscription

        if endpoint:
            PushSubscription.objects.filter(user=user, endpoint=endpoint).update(is_active=False)
        else:
            PushSubscription.objects.filter(user=user).update(is_active=False)

        return JsonResponse({"success": True})

    except Exception as e:
        logger.error("Push unsubscribe error: %s", e)
        return JsonResponse({"error": str(e)}, status=500)


def push_vapid_key_view(request: HttpRequest) -> HttpResponse:
    """
    GET /api/notifications/push/vapid-key/

    Return VAPID public key for push subscription.
    """
    vapid_key = getattr(settings, "VAPID_PUBLIC_KEY", "")
    get_token(request)  # browser clients need a CSRF cookie for session writes
    return JsonResponse({"public_key": vapid_key})
