"""
Payments services: Receipt approval, rejection, notifications, and subscription activation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from decimal import Decimal
from io import BytesIO
from typing import Any

import requests
from PIL import Image

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

MAX_RECEIPT_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def validate_and_hash_receipt_image(file_or_bytes: Any) -> tuple[str, bytes]:
    """
    Validates uploaded payment receipt image:
    1. Size must not exceed 5MB.
    2. Validates format via magic bytes (JPG/PNG/WEBP).
    3. Calculates SHA-256 hash.
    4. Anti-fraud check: Checks if another receipt with same hash is pending or approved.

    Returns (image_hash, raw_bytes).
    Raises ValueError on validation failure.
    """
    if hasattr(file_or_bytes, "read"):
        raw_bytes = file_or_bytes.read()
        if hasattr(file_or_bytes, "seek"):
            file_or_bytes.seek(0)
    elif isinstance(file_or_bytes, (bytes, bytearray)):
        raw_bytes = bytes(file_or_bytes)
    else:
        raise ValueError("Rasm formati noto'g'ri.")

    if not raw_bytes:
        raise ValueError("To'lov cheki fayli bo'sh bo'lishi mumkin emas.")

    if len(raw_bytes) > MAX_RECEIPT_FILE_SIZE:
        raise ValueError("Fayl hajmi 5MB dan oshmasligi kerak.")

    # Magic bytes verification:
    # JPEG: starts with \xff\xd8\xff
    # PNG: starts with \x89PNG\r\n\x1a\n
    # WEBP: starts with RIFF and WEBP at bytes 8..12
    is_jpeg = raw_bytes[:3] == b"\xff\xd8\xff"
    is_png = raw_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    is_webp = (
        raw_bytes[:4] == b"RIFF" and len(raw_bytes) > 12 and raw_bytes[8:12] == b"WEBP"
    )

    if not (is_jpeg or is_png or is_webp):
        # Also try opening with Pillow as verification
        try:
            with Image.open(BytesIO(raw_bytes)) as img:
                fmt = (img.format or "").upper()
                if fmt not in ("JPEG", "JPG", "PNG", "WEBP"):
                    raise ValueError(
                        "Faqat JPG, PNG yoki WEBP formatidagi cheklar qabul qilinadi."
                    )
        except Exception:
            raise ValueError(
                "Faqat JPG, PNG yoki WEBP formatidagi cheklar qabul qilinadi."
            )

    image_hash = hashlib.sha256(raw_bytes).hexdigest()

    # Anti-fraud duplicate detection
    duplicate = PaymentReceipt.objects.filter(
        image_hash=image_hash,
        status__in=[PaymentReceipt.Status.PENDING, PaymentReceipt.Status.APPROVED],
    ).exists()

    if duplicate:
        raise ValueError(
            "⚠️ Ushbu to'lov cheki avval tizimga yuklangan! Qayta ishlatish taqiqlanadi."
        )

    return image_hash, raw_bytes


def notify_admin_new_receipt(receipt: PaymentReceipt) -> None:
    """Send alert to superadmin Telegram with photo and inline action buttons."""
    bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
    admin_id = getattr(settings, "ADMIN_TELEGRAM_ID", None) or 5582178765

    user = receipt.user
    user_name = user.get_full_name() or user.email
    tg_handle = f"@{user.telegram_username}" if getattr(user, "telegram_username", None) else f"ID: {user.id}"
    plan_name = receipt.plan.upper()
    created_str = (
        receipt.created_at.strftime("%d.%m.%Y, %H:%M")
        if receipt.created_at
        else timezone.now().strftime("%d.%m.%Y, %H:%M")
    )

    caption = (
        "🧾 <b>Yangi to'lov cheki!</b>\n"
        f"👤 <b>Foydalanuvchi:</b> {user_name} ({tg_handle})\n"
        f"📦 <b>Tanlangan tarif:</b> {plan_name} ({int(receipt.amount):,} so'm)\n"
        f"📅 <b>Sana:</b> {created_str}"
    )

    reply_markup = {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Tasdiqlash va faollashtirish",
                    "callback_data": f"approve_receipt_{receipt.id}",
                },
                {"text": "❌ Rad etish", "callback_data": f"reject_receipt_{receipt.id}"},
            ]
        ]
    }

    if not bot_token:
        logger.warning(
            "TELEGRAM_BOT_TOKEN not configured; cannot notify admin of receipt #%s",
            receipt.id,
        )
        return

    # Try sending photo if receipt_image exists
    try:
        if receipt.receipt_image:
            image_path = getattr(receipt.receipt_image, "path", None)
            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as photo_file:
                    resp = requests.post(
                        f"https://api.telegram.org/bot{bot_token}/sendPhoto",
                        data={
                            "chat_id": admin_id,
                            "caption": caption,
                            "parse_mode": "HTML",
                            "reply_markup": json.dumps(reply_markup),
                        },
                        files={"photo": photo_file},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        return
    except Exception as exc:
        logger.warning("Failed to send receipt photo to admin: %s", exc)

    # Fallback to text message if photo file is not on disk or failed
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={
                "chat_id": admin_id,
                "text": caption,
                "parse_mode": "HTML",
                "reply_markup": reply_markup,
            },
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Failed to send receipt text message to admin: %s", exc)


def _get_or_create_plan_for_receipt(plan_key: str) -> SubscriptionPlan:
    """Ensure canonical Starter, Pro, or Premium SubscriptionPlan exists."""
    clean_key = plan_key.lower().strip()
    if clean_key in ("starter", "start"):
        canonical_type = SubscriptionPlan.PlanType.STARTER
        name = "Starter"
        price_uzs = getattr(settings, "PLAN_STARTER_PRICE", 7000)
        desc = "5 ta to'liq test, haftasiga 3 ta esse tekshirish matnli, xatolar va zaif mavzular tahlili."
        kwargs = {
            "image_essay_weekly_limit": 5,
            "text_essay_weekly_limit": 3,
            "test_limit": 30,
            "text_essay_cooldown_hours": 2,
            "is_unlimited_image_essays": False,
            "is_unlimited_text_essays": False,
            "is_unlimited_tests": False,
        }
    elif clean_key == "pro":
        canonical_type = SubscriptionPlan.PlanType.PRO
        name = "Pro"
        price_uzs = getattr(settings, "PLAN_PRO_PRICE", 15000)
        desc = "Haftasiga 15 ta esse rasmli/matnli, kunlik rasmiy Mock testlar, CBT testlar va AI repetitor."
        kwargs = {
            "image_essay_weekly_limit": 15,
            "text_essay_weekly_limit": 15,
            "test_limit": 100,
            "text_essay_cooldown_hours": 1,
            "is_unlimited_image_essays": False,
            "is_unlimited_text_essays": False,
            "is_unlimited_tests": False,
            "detailed_analytics": True,
            "pdf_certificate": True,
        }
    else:
        canonical_type = SubscriptionPlan.PlanType.PREMIUM
        name = "Premium"
        price_uzs = getattr(settings, "PLAN_PREMIUM_PRICE", 27000)
        desc = "Cheksiz esse 12 mezon, cheksiz Mock testlar va 1v1 Arena, ustoz tekshiruvi va rasmiy PDF sertifikat."
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
    else:
        plan.name = name
        plan.price_monthly = Decimal(price_uzs)
        plan.price_yearly = Decimal(price_uzs * 10)
        plan.description = desc
        for k, v in kwargs.items():
            setattr(plan, k, v)
        plan.save()
    return plan


@transaction.atomic
def approve_payment_receipt(
    receipt: PaymentReceipt, admin_user=None
) -> UserSubscription:
    """
    To'lov chekini tasdiqlash:
    - Status 'approved' qilinadi.
    - UserSubscription faollashtiriladi / +30 kunga uzaytiriladi.
    - User Profile plan maydoni yangilanadi ('starter' yoki 'premium').
    - PaymentHistory yozuvi saqlanadi.
    - Agar foydalanuvchi Telegram bog'lagan bo'lsa, xabarnoma yuboriladi.
    """
    receipt.status = PaymentReceipt.Status.APPROVED
    receipt.reviewed_at = timezone.now()
    if admin_user and getattr(admin_user, "is_authenticated", False):
        receipt.reviewed_by = admin_user
    receipt.save(update_fields=["status", "reviewed_at", "reviewed_by", "updated_at"])

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
        is_trial=False,
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
                f"🎉 <b>To'lovingiz tasdiqlandi! Sizda {plan_title} faollashtirildi.</b>\n\n"
                f"📦 Tarif: <b>{plan_title}</b> (30 kun)\n"
                f"💰 Summa: <b>{int(receipt.amount):,} so'm</b>\n\n"
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
def reject_payment_receipt(
    receipt: PaymentReceipt, note: str = "", admin_user=None
) -> None:
    """
    To'lov chekini rad etish:
    - Status 'rejected' qilinadi.
    - Admin izohi (admin_note) saqlanadi.
    - Agar Telegram ulangan bo'lsa, xabarnoma yuboriladi.
    """
    receipt.status = PaymentReceipt.Status.REJECTED
    receipt.admin_note = note
    receipt.reviewed_at = timezone.now()
    if admin_user and getattr(admin_user, "is_authenticated", False):
        receipt.reviewed_by = admin_user
    receipt.save(update_fields=["status", "admin_note", "reviewed_at", "reviewed_by", "updated_at"])

    # Revert trial immediately back to FREE upon rejection
    user = receipt.user
    sub = getattr(user, "subscription", None)
    if sub and (
        getattr(sub, "is_trial", False)
        or getattr(sub, "grant_source", "") == "receipt_trial"
        or getattr(sub, "payment_reference", "") == f"receipt_trial:{receipt.id}"
    ):
        sub.status = UserSubscription.Status.REVOKED
        sub.is_trial = False
        sub.save(update_fields=["status", "is_trial", "updated_at"])
        if hasattr(user, "profile"):
            user.profile.plan = "free"
            user.profile.save(update_fields=["plan"])
        logger.info("Reverted 24h trial to FREE for user %s after receipt #%s rejection", user.id, receipt.id)

    telegram_id = getattr(receipt.user, "telegram_chat_id", None)
    if telegram_id:
        try:
            reason_text = (
                f"Sabab: <i>{note}</i>"
                if note
                else "Iltimos, to'lov ma'lumotlarini tekshirib qaytadan urinib ko'ring."
            )
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
