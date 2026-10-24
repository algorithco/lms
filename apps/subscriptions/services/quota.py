"""
Subscriptions & Quota Service (Module 2).
Enforces unified quota rules across Web and Telegram Bot:
  - Free users: 1 essay / day (strictly blocked when limit reached)
  - Starter subscribers: 3 essays / period (and 5 tests)
  - PRO / Premium / Teachers / Admins: full access according to tier
"""

from __future__ import annotations

import logging
from typing import Any
from django.core.cache import cache
from django.utils import timezone

from apps.payments.models import SubscriptionUsage
from apps.payments.ai_quota import get_user_plan_tier

logger = logging.getLogger(__name__)


class QuotaService:
    """Unified quota enforcement service for Web and Telegram Bot."""

    FREE_DAILY_ESSAY_LIMIT = 1
    STARTER_ESSAY_LIMIT = 3
    STARTER_TEST_LIMIT = 5

    @classmethod
    def get_user_tier(cls, user: Any) -> str:
        """Return 'free', 'starter', 'pro', or 'premium'."""
        return get_user_plan_tier(user)

    @classmethod
    def check_essay_quota(cls, user: Any) -> tuple[bool, str, dict[str, Any]]:
        """
        Check if user is allowed to submit an essay today.
        Returns (is_allowed: bool, user_message: str, details: dict).
        """
        if not user or not getattr(user, "is_authenticated", False):
            msg = (
                "⚠️ <b>Kvotangiz tugadi!</b> Siz bugungi 1 ta bepul esse tekshirish imkoniyatingizdan foydalandingiz.\n\n"
                "Cheklovlarsiz ishlash uchun 5 000 so'mlik <b>Starter</b> yoki <b>PRO</b> tarifiga o'ting!"
            )
            return (
                False,
                msg,
                {
                    "tier": "free",
                    "limit": 1,
                    "used": 1,
                    "remaining": 0,
                    "allowed": False,
                },
            )

        tier = cls.get_user_tier(user)

        # Teachers, Admins, Superusers, PRO and Premium have full access
        if tier in ("premium", "pro"):
            return (
                True,
                "",
                {
                    "tier": tier,
                    "limit": None,
                    "used": 0,
                    "remaining": 999,
                    "allowed": True,
                },
            )

        today = timezone.localdate()
        date_str = today.strftime("%Y-%m-%d")

        # 1. Bepul foydalanuvchi: kunlik 1 ta esse
        if tier == "free":
            # Check DB submissions today
            from apps.essays.models import EssaySubmission

            db_sub_count = EssaySubmission.objects.filter(
                student=user,
                submitted_at__date=today,
            ).count()

            # Check SubscriptionUsage today
            usage_count = SubscriptionUsage.objects.filter(
                user=user,
                created_at__date=today,
                kind__in=[
                    SubscriptionUsage.Kind.TEXT_ESSAY,
                    SubscriptionUsage.Kind.IMAGE_ESSAY,
                ],
            ).count()

            # Check cache usage
            cache_key = f"ai_daily_usage:{user.id}:{date_str}"
            cache_used = int(cache.get(cache_key, 0))

            used = max(db_sub_count, usage_count, cache_used)

            if used >= cls.FREE_DAILY_ESSAY_LIMIT:
                msg = (
                    "⚠️ <b>Kvotangiz tugadi!</b> Siz bugungi 1 ta bepul esse tekshirish imkoniyatingizdan foydalandingiz.\n\n"
                    "Cheklovlarsiz ishlash uchun 5 000 so'mlik <b>Starter</b> yoki <b>PRO</b> tarifiga o'ting!"
                )
                return (
                    False,
                    msg,
                    {
                        "tier": "free",
                        "limit": cls.FREE_DAILY_ESSAY_LIMIT,
                        "used": used,
                        "remaining": 0,
                        "allowed": False,
                    },
                )

            return (
                True,
                "",
                {
                    "tier": "free",
                    "limit": cls.FREE_DAILY_ESSAY_LIMIT,
                    "used": used,
                    "remaining": cls.FREE_DAILY_ESSAY_LIMIT - used,
                    "allowed": True,
                },
            )

        # 2. Starter tarifi: 3 ta esse
        if tier == "starter":
            from apps.payments.entitlements import get_active_subscription
            from apps.essays.models import EssaySubmission

            sub = get_active_subscription(user)
            start_date = getattr(sub, "start_date", today - timezone.timedelta(days=30))
            if hasattr(start_date, "date"):
                start_date = start_date.date()

            period_used = EssaySubmission.objects.filter(
                student=user,
                submitted_at__date__gte=start_date,
            ).count()

            if period_used >= cls.STARTER_ESSAY_LIMIT:
                msg = (
                    "⚠️ <b>Starter tarifidagi esse kvotangiz tugadi!</b>\n"
                    f"Sizga ajratilgan {cls.STARTER_ESSAY_LIMIT} ta esse tekshiruvidan foydalandingiz.\n\n"
                    "Cheksiz tekshiruvlar uchun <b>PRO</b> tarifiga o'ting!"
                )
                return (
                    False,
                    msg,
                    {
                        "tier": "starter",
                        "limit": cls.STARTER_ESSAY_LIMIT,
                        "used": period_used,
                        "remaining": 0,
                        "allowed": False,
                    },
                )

            return (
                True,
                "",
                {
                    "tier": "starter",
                    "limit": cls.STARTER_ESSAY_LIMIT,
                    "used": period_used,
                    "remaining": cls.STARTER_ESSAY_LIMIT - period_used,
                    "allowed": True,
                },
            )

        return (
            True,
            "",
            {"tier": tier, "limit": None, "used": 0, "remaining": 999, "allowed": True},
        )

    @classmethod
    def consume_essay_quota(
        cls,
        user: Any,
        kind: str = SubscriptionUsage.Kind.TEXT_ESSAY,
        idempotency_key: str | None = None,
        source: str = "telegram_bot",
    ) -> bool:
        """Record essay quota consumption in DB and cache."""
        if not user or not getattr(user, "is_authenticated", False):
            return False

        today = timezone.localdate()
        date_str = today.strftime("%Y-%m-%d")

        # 1. Update cache counter
        cache_key = f"ai_daily_usage:{user.id}:{date_str}"
        try:
            curr = int(cache.get(cache_key, 0))
            cache.set(cache_key, curr + 1, timeout=86400 * 2)
        except Exception as e:
            logger.warning("Failed to update cache quota for user %s: %s", user.id, e)

        # 2. Update SubscriptionUsage in DB
        try:
            from apps.payments.models import SubscriptionUsage
            from apps.payments.entitlements import quota_period_start

            if (
                idempotency_key
                and SubscriptionUsage.objects.filter(
                    idempotency_key=idempotency_key
                ).exists()
            ):
                return True

            SubscriptionUsage.objects.create(
                user=user,
                kind=kind,
                status=SubscriptionUsage.Status.COMMITTED,
                period_start=quota_period_start(),
                idempotency_key=idempotency_key
                or f"quota:{user.id}:{kind}:{timezone.now().timestamp()}",
            )
            return True
        except Exception as e:
            logger.warning("SubscriptionUsage record creation warning: %s", e)
            return True

    @classmethod
    def check_test_quota(cls, user: Any) -> tuple[bool, str, dict[str, Any]]:
        """Check test quota for user."""
        tier = cls.get_user_tier(user)
        if tier in ("premium", "pro"):
            return True, "", {"tier": tier, "allowed": True, "remaining": 999}

        if tier == "starter":
            from apps.tests.models import TestAttempt

            today = timezone.localdate()
            used_tests = TestAttempt.objects.filter(
                student=user,
                started_at__date__gte=today - timezone.timedelta(days=30),
            ).count()
            if used_tests >= cls.STARTER_TEST_LIMIT:
                return (
                    False,
                    f"Starter tarifi bo'yicha {cls.STARTER_TEST_LIMIT} ta test limitingiz tugadi.",
                    {
                        "tier": "starter",
                        "limit": cls.STARTER_TEST_LIMIT,
                        "used": used_tests,
                        "remaining": 0,
                        "allowed": False,
                    },
                )
            return (
                True,
                "",
                {
                    "tier": "starter",
                    "limit": cls.STARTER_TEST_LIMIT,
                    "used": used_tests,
                    "remaining": cls.STARTER_TEST_LIMIT - used_tests,
                    "allowed": True,
                },
            )

        return True, "", {"tier": "free", "allowed": True, "remaining": 1}
