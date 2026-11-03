"""
Billing Celery Tasks — Subscription lifecycle, renewal warnings, and automated checks.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="billing.check_expiring_subscriptions")
def check_and_notify_expiring_subscriptions() -> dict[str, Any]:
    """
    Check all active subscriptions expiring within 5 days and send Telegram alerts.
    Excludes platform admins and already notified subscriptions.
    """
    from apps.notifications.services.telegram_service import TelegramService
    from apps.payments.models import UserSubscription

    now = timezone.now()
    five_days_from_now = now + timedelta(days=5)

    # Active subscriptions expiring in (now, now + 5 days]
    expiring_subs = UserSubscription.objects.filter(
        status=UserSubscription.Status.ACTIVE,
        expires_at__gt=now,
        expires_at__lte=five_days_from_now,
    ).select_related("user", "plan")

    notified_count = 0
    site_url = getattr(settings, "FRONTEND_URL", None) or getattr(settings, "SITE_URL", "https://grandec.uz")
    subscribe_url = f"{site_url.rstrip('/')}/subscribe"

    for sub in expiring_subs:
        user = sub.user
        if not user or not user.is_active:
            continue
        # Platform admins have unlimited access — no warnings needed
        if getattr(user, "is_superuser", False) or getattr(user, "role", "") in ("admin", "center_admin"):
            continue

        chat_id = getattr(user, "telegram_chat_id", None)
        if not chat_id:
            continue

        days_left = max(1, (sub.expires_at - now).days)
        plan_name = sub.plan.name if sub.plan else "PRO"

        text = (
            f"⚠️ *Diqqat: Sizning {plan_name} obunangiz tugashiga {days_left} kun qoldi!*\n\n"
            f"📅 Tugash vaqti: *{sub.expires_at.strftime('%d.%m.%Y')}*\n\n"
            "Platformadagi barcha premium imkoniyatlar (AI esse tekshiruvi, rasmiy milliy sertifikat testlari, "
            "Cambridge CBT)dan uzluksiz foydalanish uchun obunani yangilang!"
        )

        buttons = [
            [{"text": "💳 Obunani yangilash", "url": subscribe_url}]
        ]

        try:
            TelegramService.send_message_with_keyboard(
                chat_id=chat_id,
                text=text,
                buttons=buttons,
                parse_mode="Markdown",
                notification_type="subscription_expiring",
                recipient=user,
                title="Obuna tugash ogohlantirishi",
            )
            notified_count += 1
            logger.info("Sent expiring subscription warning to user_id=%s (days_left=%s)", user.pk, days_left)
        except Exception as e:
            logger.warning("Failed to send subscription warning to user_id=%s: %s", user.pk, e)

    return {"status": "ok", "notified": notified_count}
