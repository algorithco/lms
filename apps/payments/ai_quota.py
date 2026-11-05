"""
AI Quota and Rate Limiting Service.

Quotas:
  - Free users: 1 request / day
  - Starter subscribers: 10 requests / day
  - Premium subscribers: unlimited
"""

from __future__ import annotations

import logging
from typing import Any
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

DAILY_QUOTA_MAP = {
    "free": 1,
    "starter": 10,
    "pro": 50,
    "premium": None,  # Unlimited
}


def get_user_plan_tier(user: Any) -> str:
    """Return user's tier: 'free', 'starter', 'pro', or 'premium'."""
    if not user or not getattr(user, "is_authenticated", False):
        return "free"

    # Superusers, platform staff, teachers and admins have unlimited access
    if (
        getattr(user, "is_superuser", False)
        or getattr(user, "role", None) in ("admin", "center_admin", "teacher")
    ):
        return "premium"

    # Single source: the effective entitlement (an active, unexpired
    # subscription or an approved teacher sponsorship). Profile.plan strings,
    # group membership and old receipts never grant a tier.
    from apps.payments.entitlements import SOURCE_SPONSORED, get_effective_entitlement

    entitlement = get_effective_entitlement(user)
    plan_type = (entitlement.plan_type or "").lower()
    if plan_type in ("premium", "family"):
        return "premium"
    if plan_type == "pro" or entitlement.source == SOURCE_SPONSORED:
        return "pro"
    if plan_type in ("starter", "start"):
        return "starter"
    return "free"


def get_display_tier(user: Any) -> tuple[str, bool]:
    """``(tier, custom_limit)`` for labels. Quotas keep using :func:`get_user_plan_tier`.

    A manual limit override must not turn a PRO student into "FREE" on screen:
    the tier is read from their subscription and the override is flagged apart.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return "free", False
    if getattr(user, "is_superuser", False) or getattr(user, "role", None) in ("admin", "center_admin", "teacher"):
        return "premium", False
    from apps.payments.entitlements import display_plan, get_effective_entitlement

    plan_type, _name, custom = display_plan(user, get_effective_entitlement(user))
    if custom:
        return (plan_type or "free").lower(), True
    return get_user_plan_tier(user), False


def get_user_ai_quota(user: Any) -> dict[str, Any]:
    """Get user's AI quota and usage for today."""
    if user and (
        getattr(user, "is_superuser", False)
        or getattr(user, "role", "") in ("admin", "center_admin")
    ):
        return {
            "tier": "admin",
            "limit": None,
            "used": 0,
            "remaining": None,
            "allowed": True,
        }

    tier = get_user_plan_tier(user)
    limit = DAILY_QUOTA_MAP.get(tier, 1)

    if not user or not getattr(user, "is_authenticated", False):
        return {
            "tier": "free",
            "limit": 1,
            "used": 1,
            "remaining": 0,
            "allowed": False,
        }

    date_str = timezone.now().strftime("%Y-%m-%d")
    cache_key = f"ai_daily_usage:{user.id}:{date_str}"
    used = int(cache.get(cache_key, 0))

    if limit is None:
        remaining = None
        allowed = True
    else:
        remaining = max(0, limit - used)
        allowed = used < limit

    return {
        "tier": tier,
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "allowed": allowed,
    }


def check_and_consume_ai_quota(user: Any) -> tuple[bool, str]:
    """
    Check if user has remaining AI quota today and consume 1 request if allowed.
    Returns (allowed: bool, error_message: str).
    """
    if user and (
        getattr(user, "is_superuser", False)
        or getattr(user, "role", "") in ("admin", "center_admin")
    ):
        return True, ""

    quota_info = get_user_ai_quota(user)
    if not quota_info["allowed"]:
        tier = quota_info["tier"]
        if tier == "free":
            msg = "Sizning bugungi bepul AI limitingiz tugadi. Cheksiz foydalanish uchun tarifingizni yangilang!"
        else:
            msg = f"Sizning bugungi {tier.capitalize()} AI limitingiz tugadi. Cheksiz foydalanish uchun Premium tarifiga o'ting!"
        return False, msg

    limit = quota_info["limit"]
    if limit is not None and getattr(user, "id", None):
        date_str = timezone.now().strftime("%Y-%m-%d")
        cache_key = f"ai_daily_usage:{user.id}:{date_str}"
        try:
            cache.set(cache_key, quota_info["used"] + 1, timeout=86400 * 2)
            quota_info["used"] += 1
            quota_info["remaining"] = max(0, limit - quota_info["used"])
        except Exception as exc:
            logger.warning("Failed to increment AI quota in cache: %s", exc)

    return True, ""


# ---------------------------------------------------------------------------
# Per-feature daily caps (paid AI calls that have no essay/test allowance)
# ---------------------------------------------------------------------------
#: Calls per day by tier. ``0`` means the feature is not part of the tier,
#: ``None`` unlimited. Teachers resolve to the "premium" tier and administrators
#: are exempt. Override any entry with ``settings.AI_FEATURE_DAILY_CAPS``.
FEATURE_DAILY_CAPS: dict[str, dict[str, int | None]] = {
    # Handwriting OCR for photo essays (the essay itself is charged separately).
    # Whether the plan includes photo essays at all is decided by its entitlement
    # (see essay_ocr_view); this is only the daily ceiling on top of it.
    "ocr": {"free": 0, "starter": 5, "pro": 5, "premium": 20},
    # AI Speaking evaluation (transcription + 4-criteria grading).
    "speaking": {"free": 1, "starter": 3, "pro": 10, "premium": 30},
    # Teacher document -> test converter (vision / text LLM).
    "converter": {"free": 0, "starter": 0, "pro": 0, "premium": 20},
    # OMR answer-sheet scan (one vision call per photo; grading is a normal attempt).
    "omr": {"free": 3, "starter": 10, "pro": 20, "premium": 40},
    # Teacher vocabulary generator.
    "vocab": {"free": 0, "starter": 0, "pro": 0, "premium": 20},
}


def feature_cap_for(user: Any, feature: str) -> int | None:
    """Daily limit of ``feature`` for this user (``None`` = unlimited)."""
    from django.conf import settings

    if user and (
        getattr(user, "is_superuser", False)
        or getattr(user, "role", "") in ("admin", "center_admin")
    ):
        return None
    caps = dict(FEATURE_DAILY_CAPS.get(feature, {}))
    caps.update((getattr(settings, "AI_FEATURE_DAILY_CAPS", {}) or {}).get(feature, {}))
    return caps.get(get_user_plan_tier(user), 0)


def _feature_cap_key(user: Any, feature: str) -> str:
    from zoneinfo import ZoneInfo

    day = timezone.now().astimezone(ZoneInfo("Asia/Tashkent")).strftime("%Y-%m-%d")
    return f"ai_feature:{feature}:{user.id}:{day}"


def consume_feature_cap(user: Any, feature: str) -> tuple[bool, int | None]:
    """Take one call of today's cap. Returns ``(allowed, limit)``.

    Atomic (cache ``incr``); call :func:`refund_feature_cap` when the AI call
    produced no result so a provider failure never costs the user a call.
    """
    limit = feature_cap_for(user, feature)
    if limit is None:
        return True, None
    if limit <= 0 or not getattr(user, "id", None):
        return False, limit
    key = _feature_cap_key(user, feature)
    cache.add(key, 0, 86400 * 2)
    used = cache.incr(key)
    if used > limit:
        cache.decr(key)
        return False, limit
    return True, limit


def refund_feature_cap(user: Any, feature: str) -> None:
    if feature_cap_for(user, feature) is None or not getattr(user, "id", None):
        return
    key = _feature_cap_key(user, feature)
    try:
        if int(cache.get(key, 0)) > 0:
            cache.decr(key)
    except Exception:  # pragma: no cover
        logger.warning("Could not refund %s cap for user %s", feature, user.id, exc_info=True)
