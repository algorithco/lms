"""
AI Quota and Rate Limiting Service.

Quotas:
  - Free users: 1 request / day
  - Starter subscribers: 20 requests / day
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
    "starter": 20,
    "pro": 50,
    "premium": None,  # Unlimited
}


def get_user_plan_tier(user: Any) -> str:
    """Return user's tier: 'free', 'starter', 'pro', or 'premium'."""
    if not user or not getattr(user, "is_authenticated", False):
        return "free"

    # Superusers, platform staff, teachers and admins have unlimited access
    if getattr(user, "is_superuser", False) or getattr(user, "role", None) in ("admin", "teacher"):
        return "premium"

    sub = getattr(user, "subscription", None)
    if sub and getattr(sub, "is_active", False):
        plan_type = getattr(sub.plan, "plan_type", "").lower()
        if plan_type in ("premium", "family"):
            return "premium"
        if plan_type == "pro":
            return "pro"
        if plan_type in ("starter", "start"):
            return "starter"

    profile = getattr(user, "profile", None)
    if profile:
        profile_plan = getattr(profile, "plan", "").lower()
        if profile_plan in ("premium", "family"):
            return "premium"
        if profile_plan == "pro":
            return "pro"
        if profile_plan in ("starter", "start"):
            return "starter"

    return "free"


def get_user_ai_quota(user: Any) -> dict[str, Any]:
    """Get user's AI quota and usage for today."""
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
