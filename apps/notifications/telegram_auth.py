"""
Telegram Auth Views — web login via Telegram bot.

Flow:
    1. POST /api/telegram/auth/start/  → creates token, returns deep link
    2. GET  /api/telegram/auth/<token>/status/  → polls verification status
    3. POST /api/telegram/auth/<token>/login/   → consumes token and logs user in
"""
from __future__ import annotations

import logging
import secrets
import hashlib

from django.conf import settings
from django.contrib.auth import login
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import TelegramAuthToken

logger = logging.getLogger(__name__)

# Single source of truth: settings.TELEGRAM_BOT_NAME (env-configurable,
# defaults to uz_essaygrader_bot). Kept as a module-level alias so existing
# imports keep working.
BOT_USERNAME = getattr(settings, "TELEGRAM_BOT_NAME", "uz_essaygrader_bot")


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _get_client_ip(request: HttpRequest) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _is_pending_for_session(request: HttpRequest, token: str) -> bool:
    return _token_digest(token) in request.session.get("telegram_auth_pending", [])


def _forget_pending(request: HttpRequest, token: str) -> None:
    digest = _token_digest(token)
    request.session["telegram_auth_pending"] = [
        value for value in request.session.get("telegram_auth_pending", []) if value != digest
    ]


@require_POST
def telegram_auth_start(request: HttpRequest) -> JsonResponse:
    """
    Generate a new Telegram auth token and return the deep link URL.

    POST /api/telegram/auth/start/
    Response: {"token": "...", "deep_link": "https://t.me/uz_essaygrader_bot?start=auth_...", "expires_in": 600}
    """
    from django.core.cache import cache

    # Clean up old tokens for this IP/session (prevent spam)
    ip = _get_client_ip(request)
    TelegramAuthToken.objects.filter(
        is_verified=False,
        user__isnull=True,
    ).filter(
        # Tokens older than 5 minutes that are not verified
        created_at__lt=timezone.now() - timezone.timedelta(minutes=5),
    ).delete()

    # Rate limit token creation (per IP, rolling 10 minutes)
    throttle_key = f"tgauth-start:{ip}"
    attempts = cache.get(throttle_key, 0)
    if attempts >= 10:
        logger.warning("Telegram auth start throttled")
        return JsonResponse(
            {"error": "Juda ko'p so'rov. Bir ozdan keyin qayta urinib ko'ring."},
            status=429,
        )
    cache.set(throttle_key, attempts + 1, timeout=600)

    # Generate new token
    token = secrets.token_urlsafe(32)
    TelegramAuthToken.objects.create(token=token)
    pending = request.session.get("telegram_auth_pending", [])
    request.session["telegram_auth_pending"] = (pending + [_token_digest(token)])[-3:]

    deep_link = f"https://t.me/{BOT_USERNAME}?start=auth_{token}"

    logger.info("Telegram auth token created")

    return JsonResponse({
        "token": token,
        "deep_link": deep_link,
        "expires_in": 600,  # 10 minutes
    })


@require_POST
def telegram_auth_code_login(request: HttpRequest) -> JsonResponse:
    """
    Login via 6-digit short code.

    POST /api/telegram/auth/code/login/
    Body: {"code": "123456"}
    Response: {"status": "ok", "redirect": "/dashboard/"}

    Flow:
        1. User enters 6-digit code from Telegram bot
        2. We find the matching TelegramAuthToken
        3. If verified & not expired → login and redirect
    """
    import json
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Noto'g'ri JSON"}, status=400)

    code = body.get("code", "")
    if not isinstance(code, str):
        return JsonResponse({"error": "Noto'g'ri kod formati."}, status=400)
    code = code.strip()
    if not code or len(code) != 6 or not code.isdigit():
        return JsonResponse({"error": "Noto'g'ri kod formati. 6 ta raqam kiriting."}, status=400)

    # Brute-force protection: the 6-digit codes have only 10^6 combinations,
    # so failed attempts must be throttled per client (5 minutes window).
    from django.core.cache import cache

    ip = _get_client_ip(request)
    throttle_key = f"tgauth-code:{ip}"
    attempts = cache.get(throttle_key, 0)
    if attempts >= 15:
        logger.warning("Telegram auth code login throttled")
        return JsonResponse(
            {"error": "Juda ko'p urinish. 5 daqiqadan keyin qayta urinib ko'ring."},
            status=429,
        )
    cache.set(throttle_key, attempts + 1, timeout=300)

    # Find token by short_code
    with transaction.atomic():
        matches = list(TelegramAuthToken.objects.select_for_update().filter(
            short_code=code, is_verified=True, consumed_at__isnull=True,
        )[:2])
        # Legacy duplicate short codes are ambiguous and must never select an
        # arbitrary account.
        if len(matches) != 1:
            return JsonResponse({"error": "Noto'g'ri kod yoki kod hali tasdiqlanmagan."}, status=404)
        auth_token = matches[0]
        # Session binding — code must belong to a token started in this browser session
        # This prevents shoulder-surfed code reuse from a different browser/IP.
        if request.session.get("telegram_auth_pending") and not _is_pending_for_session(request, auth_token.token):
            return JsonResponse({"error": "Kod bu sessiyaga tegishli emas."}, status=403)
        if auth_token.is_expired or not auth_token.user or not auth_token.user.is_active:
            return JsonResponse({"error": "Kod muddati tugagan yoki hisob faol emas."}, status=400)
        if not TelegramAuthToken.objects.filter(
            pk=auth_token.pk, short_code=code, consumed_at__isnull=True,
        ).update(consumed_at=timezone.now(), short_code=""):
            return JsonResponse({"error": "Kod allaqachon ishlatilgan."}, status=400)

    login(request, auth_token.user)
    request.session.set_expiry(60 * 60 * 24 * 30)
    _forget_pending(request, auth_token.token)
    logger.info("Telegram code login: user_id=%s, phone_verified=%s", auth_token.user_id, getattr(auth_token, "phone_verified", False))

    return JsonResponse({
        "status": "ok",
        "redirect": "/dashboard/",
        "user_name": auth_token.user.get_full_name(),
    })


@require_GET
def telegram_auth_status(request: HttpRequest, token: str) -> JsonResponse:
    """
    Poll the verification status of a Telegram auth token.

    GET /api/telegram/auth/<token>/status/
    Response: {"status": "pending"|"verified"|"expired", "user_id": ..., "login_url": ...}
    """
    from django.core.cache import cache

    ip = _get_client_ip(request)
    skey = f"tgauth-status:{ip}"
    cnt = cache.get(skey, 0)
    if cnt >= 60:
        return JsonResponse({"status": "throttled", "error": "Juda ko'p so'rov"}, status=429)
    cache.set(skey, cnt + 1, timeout=60)

    if not _is_pending_for_session(request, token):
        return JsonResponse({"status": "invalid"}, status=404)
    try:
        auth_token = TelegramAuthToken.objects.get(token=token)
    except TelegramAuthToken.DoesNotExist:
        return JsonResponse({"status": "invalid", "error": "Token topilmadi"}, status=404)

    if auth_token.consumed_at:
        return JsonResponse({"status": "expired"})
    if auth_token.is_expired:
        return JsonResponse({"status": "expired", "error": "Token muddati tugadi"})

    if auth_token.is_verified and auth_token.user:
        login_url = reverse("notifications:tg-auth-login", args=[token])
        return JsonResponse({
            "status": "verified",
            "user_id": auth_token.user.id,
            "user_name": auth_token.user.get_full_name(),
            "login_url": login_url,
        })

    return JsonResponse({"status": "pending"})


@require_POST
def telegram_auth_login(request: HttpRequest, token: str) -> JsonResponse:
    """
    Log in the user after Telegram verification.

    POST /api/telegram/auth/<token>/login/
    If verified → login and redirect to dashboard
    If not verified → return error
    """
    if not _is_pending_for_session(request, token):
        return JsonResponse({"status": "error"}, status=404)
    with transaction.atomic():
        try:
            auth_token = TelegramAuthToken.objects.select_for_update().get(token=token)
        except TelegramAuthToken.DoesNotExist:
            return JsonResponse({"status": "error"}, status=404)
        if (auth_token.consumed_at or auth_token.is_expired or not auth_token.is_verified
                or not auth_token.user or not auth_token.user.is_active):
            return JsonResponse({"status": "error"}, status=400)
        if not TelegramAuthToken.objects.filter(
            pk=auth_token.pk, consumed_at__isnull=True,
        ).update(consumed_at=timezone.now(), short_code=""):
            return JsonResponse({"status": "error"}, status=400)

    _forget_pending(request, token)
    login(request, auth_token.user)

    # Set session expiry (30 days like "remember me")
    request.session.set_expiry(60 * 60 * 24 * 30)

    logger.info("Telegram token login: user_id=%s", auth_token.user_id)

    return JsonResponse({
        "status": "ok",
        "redirect": "/dashboard/",
        "user_name": auth_token.user.get_full_name(),
    })
