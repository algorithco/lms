"""Honest AI failures: one exception, one failure counter, one admin alert.

When the AI provider is missing, slow or returns something we cannot parse,
a feature must say "not graded" and give the allowance back. It must never
invent a score, a band, a transcript or an answer key. The helpers here are
shared by every AI call site (essays, speaking, OCR, vocabulary, explain).
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

#: Consecutive failures of one feature before the admin is told.
ALERT_AFTER = 3
#: At most one alert per feature in this window (seconds).
ALERT_COOLDOWN = 30 * 60
_FAIL_TTL = 60 * 60


class AIUnavailable(Exception):
    """The AI could not produce a real result. Nothing was invented."""

    #: Shown to the student; no provider, key or stack detail.
    user_message = "Baholash hozircha amalga oshmadi. Limitingiz qaytarildi, birozdan so'ng qayta urinib ko'ring."

    def __init__(self, detail: str = "", *, feature: str = "ai"):
        super().__init__(detail or self.user_message)
        self.detail = detail
        self.feature = feature


def _fail_key(feature: str) -> str:
    return f"ai_health:fail:{feature}"


def _alert_key(feature: str) -> str:
    return f"ai_health:alerted:{feature}"


def record_ai_success(feature: str) -> None:
    try:
        cache.delete(_fail_key(feature))
    except Exception:  # pragma: no cover - cache outage must not break grading
        logger.debug("ai_health: cache unavailable on success", exc_info=True)


def record_ai_failure(feature: str, exc: BaseException | str = "") -> int:
    """Count a failure; alert the admin on Telegram after ``ALERT_AFTER`` in a row.

    Returns the current consecutive-failure count (0 if the cache is down).
    """
    try:
        key = _fail_key(feature)
        try:
            count = cache.incr(key)
        except ValueError:
            cache.set(key, 1, _FAIL_TTL)
            count = 1
        if count >= ALERT_AFTER and cache.add(_alert_key(feature), 1, ALERT_COOLDOWN):
            _alert_admin(feature, count, exc)
        return count
    except Exception:  # pragma: no cover
        logger.warning("ai_health: could not record failure for %s", feature, exc_info=True)
        return 0


def _alert_admin(feature: str, count: int, exc: BaseException | str) -> None:
    admin_id = getattr(settings, "ADMIN_TELEGRAM_ID", None)
    if not admin_id:
        return
    reason = str(exc)[:160].replace("<", "‹").replace(">", "›") if exc else ""
    text = (
        "⚠️ <b>AI baholash ishlamayapti</b>\n"
        f"🔧 Funksiya: <code>{feature}</code>\n"
        f"🔁 Ketma-ket xato: {count}\n"
        + (f"📄 Sabab: {reason}\n" if reason else "")
        + "Foydalanuvchilarga «baholanmadi» ko'rsatilmoqda va limiti qaytarilmoqda."
    )
    try:
        from apps.notifications.services.telegram_service import TelegramService

        TelegramService.send_message(chat_id=int(admin_id), text=text, parse_mode="HTML")
    except Exception:
        logger.warning("ai_health: admin alert failed for %s", feature, exc_info=True)
