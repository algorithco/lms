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



def _plans_text() -> str:
    """'Starter (7 000 so'm) yoki PRO (15 000 so'm)' from the configured prices."""
    from django.conf import settings

    def fmt(n: int) -> str:
        return f"{int(n):,}".replace(",", " ")

    return (
        f"Starter ({fmt(settings.PLAN_STARTER_PRICE)} so'm) yoki "
        f"PRO ({fmt(settings.PLAN_PRO_PRICE)} so'm)"
    )

class QuotaService:
    """Unified quota enforcement service for Web and Telegram Bot."""

    FREE_ESSAY_LIMIT = 1
    FREE_TEST_LIMIT = 1
    FREE_ARENA_DAILY_LIMIT = 3
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
        if user and (
            getattr(user, "is_superuser", False)
            or getattr(user, "role", "") in ("admin", "center_admin")
        ):
            return True, "", {"tier": "admin", "allowed": True, "remaining": 999999, "limit": None}

        if not user or not getattr(user, "is_authenticated", False):
            msg = (
                "⚠️ <b>Kvotangiz tugadi!</b> Siz bugungi 1 ta bepul esse tekshirish imkoniyatingizdan foydalandingiz.\n\n"
                f"Cheklovlarsiz ishlash uchun {_plans_text()} tarifiga o'ting!"
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

        # 1. Bepul foydalanuvchi: jami 1 ta matnli esse sinovi (rasmli esse esa mutlaqo taqiqlangan)
        if tier == "free":
            from apps.essays.models import EssaySubmission

            db_sub_count = EssaySubmission.objects.filter(
                student=user,
                status__in=[
                    EssaySubmission.Status.GRADED,
                    EssaySubmission.Status.PENDING,
                    EssaySubmission.Status.PENDING_TEACHER,
                ],
            ).count()

            usage_count = SubscriptionUsage.objects.filter(
                user=user,
                kind__in=[
                    SubscriptionUsage.Kind.TEXT_ESSAY,
                    SubscriptionUsage.Kind.IMAGE_ESSAY,
                ],
            ).count()

            used = max(db_sub_count, usage_count)
            bonus_essays = getattr(user, "bonus_essays", 0)
            effective_limit = cls.FREE_ESSAY_LIMIT + bonus_essays

            if used >= effective_limit:
                msg = (
                    "⚠️ Kvotangiz tugadi! Siz 1 ta bepul esse sinovidan foydalandingiz. "
                    f"Davom ettirish uchun {_plans_text()} tarifiga o'ting!"
                )
                return (
                    False,
                    msg,
                    {
                        "tier": "free",
                        "limit": effective_limit,
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
                    "limit": effective_limit,
                    "used": used,
                    "remaining": effective_limit - used,
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
        if (
            getattr(user, "is_superuser", False)
            or getattr(user, "role", "") in ("admin", "center_admin")
        ):
            return True

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
    def check_test_quota(cls, user: Any, test_id: int | None = None) -> tuple[bool, str, dict[str, Any]]:
        """Check test quota for user (Free tier: exactly 1 test trial, locked mocks require plan).

        Admins and teachers are never limited: StartAttemptService runs
        their attempts as previews that stay out of stats and ratings.
        """
        if user and (
            getattr(user, "is_superuser", False)
            or getattr(user, "role", "") in ("admin", "center_admin", "teacher")
        ):
            return True, "", {"tier": "admin", "allowed": True, "remaining": 999999, "limit": None}

        # One rule for display and enforcement: the effective entitlement
        # (plan row limit per period; free tier = lifetime limit + bonus).
        from apps.payments.entitlements import can_start_test

        tier = cls.get_user_tier(user)
        allowed, _reason, remaining = can_start_test(user)
        bucket = remaining["test"]
        details = {
            "tier": tier,
            "limit": bucket["limit"],
            "used": bucket["used"],
            "remaining": bucket["remaining"],
            "allowed": allowed,
        }
        if not allowed:
            if tier == "free":
                msg = f"⚠️ Bepul sinov test limitingiz tugadi. Boshqa to'liq testlar uchun {_plans_text()} tarifiga o'ting."
            else:
                msg = f"{tier.capitalize()} tarifi bo'yicha {bucket['limit']} ta test limitingiz tugadi."
            return False, msg, details

        # Locked mocks stay paid-only for free users without referral bonus tests.
        if tier == "free" and test_id and not getattr(user, "bonus_tests", 0):
            from apps.tests.models import Test

            t_obj = Test.objects.filter(id=test_id).only("title").first()
            title_lower = (getattr(t_obj, "title", "") or "").lower()
            if "#mock" in title_lower and not ("diagnostic" in title_lower or "bepul" in title_lower):
                return (
                    False,
                    f"🔒 Ushbu to'liq mock test tarif bilan ochiladi: {_plans_text()}.",
                    {**details, "allowed": False, "is_locked_mock": True},
                )

        return True, "", details

    @classmethod
    def check_arena_quota(cls, user: Any) -> tuple[bool, str, dict[str, Any]]:
        """Check 1v1 Arena match quota (Free users: max 3 matches / day)."""
        if user and (
            getattr(user, "is_superuser", False)
            or getattr(user, "role", "") in ("admin", "center_admin")
        ):
            return True, "", {"tier": "admin", "allowed": True, "remaining": 999999, "limit": None}

        tier = cls.get_user_tier(user)
        if tier in ("premium", "pro"):
            return True, "", {"tier": tier, "allowed": True, "remaining": 999}

        today = timezone.localdate()
        from apps.arena.models import ArenaPlayer

        played_today = ArenaPlayer.objects.filter(
            player=user,
            room__created_at__date=today,
        ).count()

        if tier == "free" and played_today >= cls.FREE_ARENA_DAILY_LIMIT:
            return (
                False,
                f"⚠️ Bugungi bepul 1v1 Arena limitingiz tugadi (kuniga 3 ta o'yin). Cheksiz janglar uchun {_plans_text()} tarifiga o'ting!",
                {
                    "tier": "free",
                    "limit": cls.FREE_ARENA_DAILY_LIMIT,
                    "used": played_today,
                    "remaining": 0,
                    "allowed": False,
                },
            )

        remaining = max(0, cls.FREE_ARENA_DAILY_LIMIT - played_today)
        return (
            True,
            "",
            {
                "tier": tier,
                "limit": cls.FREE_ARENA_DAILY_LIMIT,
                "used": played_today,
                "remaining": remaining,
                "allowed": True,
            },
        )
