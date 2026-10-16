"""
Payments services: Receipt approval, rejection, notifications, and subscription activation.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.notifications.services.telegram_service import TelegramService
from .models import (
    PaymentHistory,
    PaymentReceipt,
    SubscriptionPlan,
    UserSubscription,
)
from .subscriptions import grant_subscription

logger = logging.getLogger(__name__)


def _get_or_create_plan_for_receipt(plan_key: str) -> SubscriptionPlan:
    """Ensure canonical Starter or Premium SubscriptionPlan exists."""
    clean_key = plan_key.lower().strip()
    if clean_key in ("starter", "start"):
        canonical_type = SubscriptionPlan.PlanType.STARTER
        name = "Starter"
        price_uzs = getattr(settings, "PLAN_STARTER_PRICE", 49000)
        desc = "Milliy sertifikatga tayyorgarlik uchun Starter tarifi."
        kwargs = {
            "image_essay_weekly_limit": 5,
            "text_essay_weekly_limit": 10,
            "test_limit": 30,
            "text_essay_cooldown_hours": 2,
            "is_unlimited_image_essays": False,
            "is_unlimited_text_essays": False,
            "is_unlimited_tests": False,
        }
    else:
        canonical_type = SubscriptionPlan.PlanType.PREMIUM
        name = "Premium"
        price_uzs = getattr(settings, "PLAN_PREMIUM_PRICE", 99000)
        desc = "Barcha imkoniyatlar cheksiz — AI esse, Fast CBT va ELO Arena."
        kwargs = {
            "image_essay_weekly_limit": None,
            "text_essay_weekly_limit": None,
            "test_limit": None,
            "text_essay_cooldown_hours": 0,
            "is_unlimited_image_essays": True,
            "is_unlimited_text_essays": True,
            "is_unlimited_tests": True,
            "detailed_analytics": True,
            "pdf_certificate": True,
            "priority_support": True,
        }

    plan = SubscriptionPlan.objects.filter(plan_type=canonical_type).first()
    if plan is None:
        plan = SubscriptionPlan.objects.create(
            name=name,
            plan_type=canonical_type,
            description=desc,
            price_monthly=Decimal(price_uzs),
            price_yearly=Decimal(price_uzs * 10),
            duration_days=30,
            is_active=True,
            is_public=True,
            **kwargs,
        )
    return plan


@transaction.atomic
def approve_payment_receipt(receipt: PaymentReceipt, admin_user=None) -> UserSubscription:
    """
    To'lov chekini tasdiqlash:
    - Status 'approved' qilinadi.
    - UserSubscription faollashtiriladi / +30 kunga uzaytiriladi.
    - User Profile plan maydoni yangilanadi ('starter' yoki 'premium').
    - PaymentHistory yozuvi saqlanadi.
    - Agar foydalanuvchi Telegram bog'lagan bo'lsa, xabarnoma yuboriladi.
    """
    receipt.status = PaymentReceipt.Status.APPROVED
    receipt.save(update_fields=["status", "updated_at"])

    # 1. Resolve or create appropriate SubscriptionPlan
    plan = _get_or_create_plan_for_receipt(receipt.plan)

    # 2. Grant / extend subscription by 30 days
    source = (
        UserSubscription.Source.TELEGRAM_BOT
        if receipt.source == PaymentReceipt.Source.BOT
        else UserSubscription.Source.WEBSITE
    )
    sub = grant_subscription(
        user=receipt.user,
        plan=plan,
        source=source,
        payment_method="card",
        payment_reference=f"receipt:{receipt.id}",
        grant_source="admin_card_receipt",
        days=30,
        actor=admin_user,
        reason=f"Payment receipt #{receipt.id} approved ({receipt.plan})",
    )

    # 3. Update user profile plan
    if hasattr(receipt.user, "profile"):
        receipt.user.profile.plan = receipt.plan
        receipt.user.profile.save(update_fields=["plan"])

    # 4. Create PaymentHistory record
    PaymentHistory.objects.create(
        user=receipt.user,
        plan=plan,
        amount=receipt.amount,
        currency="UZS",
        payment_method="card",
        payment_id=f"RECEIPT-{receipt.id}",
        status=PaymentHistory.PaymentStatus.COMPLETED,
        description=f"Karta orqali to'lov cheki (#{receipt.id}) tasdiqlandi",
        completed_at=timezone.now(),
    )

    # 5. Send Telegram notification if user has linked Telegram
    telegram_id = getattr(receipt.user, "telegram_chat_id", None)
    if telegram_id:
        try:
            plan_title = receipt.plan.capitalize()
            msg = (
                f"🎉 <b>To'lovingiz muvaffaqiyatli tasdiqlandi!</b>\n\n"
                f"📦 Tarif: <b>{plan_title}</b> (30 kun)\n"
                f"💰 Summa: <b>{int(receipt.amount):,} so'm</b>\n\n"
                f"Sizning hisobingizda <b>{plan_title}</b> obunasi faollashtirildi. "
                f"Endi barcha AI esse tekshiruvlari va milliy sertifikat testlaridan to'liq foydalanishingiz mumkin!\n\n"
                f"🚀 Boshlash: https://grandec.uz/dashboard/"
            )
            TelegramService.send_general_notification(
                chat_id=telegram_id,
                text=msg,
                title="To'lov tasdiqlandi",
                recipient=receipt.user,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning("Failed to notify user via Telegram: %s", e)

    return sub


@transaction.atomic
def reject_payment_receipt(receipt: PaymentReceipt, note: str = "", admin_user=None) -> None:
    """
    To'lov chekini rad etish:
    - Status 'rejected' qilinadi.
    - Admin izohi (admin_note) saqlanadi.
    - Agar Telegram ulangan bo'lsa, xabarnoma yuboriladi.
    """
    receipt.status = PaymentReceipt.Status.REJECTED
    receipt.admin_note = note
    receipt.save(update_fields=["status", "admin_note", "updated_at"])

    telegram_id = getattr(receipt.user, "telegram_chat_id", None)
    if telegram_id:
        try:
            reason_text = f"Sabab: <i>{note}</i>" if note else "Iltimos, to'lov ma'lumotlarini tekshirib qaytadan urinib ko'ring."
            msg = (
                f"⚠️ <b>To'lov chekingiz rad etildi</b>\n\n"
                f"📦 Tarif: <b>{receipt.plan.capitalize()}</b>\n"
                f"{reason_text}\n\n"
                f"Qo'shimcha savollar bo'yicha @grandec_admin bilan bog'lanishingiz mumkin."
            )
            TelegramService.send_general_notification(
                chat_id=telegram_id,
                text=msg,
                title="To'lov rad etildi",
                recipient=receipt.user,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning("Failed to notify user via Telegram: %s", e)
