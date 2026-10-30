"""
Receipt Verifier & Anti-Fraud Engine (Module 2, 3, 4).
Performs AI Vision OCR (Gemini Flash Vision) on payment receipts (Click, Payme, Uzum, Bank),
detects duplicate/fake receipts, applies Fraud Strikes, auto-bans fraudulent users,
and automatically activates Starter, PRO, or PREMIUM subscriptions for authentic receipts.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.subscriptions.models import FraudLog, PaymentReceipt

logger = logging.getLogger(__name__)

# Plan price standards
PLAN_PRICES: dict[str, Decimal] = {
    "starter": Decimal("7000"),
    "pro": Decimal("15000"),
    "premium": Decimal("27000"),
}


def compute_receipt_hash(image_bytes: bytes) -> str:
    """Compute standard SHA-256 hash of receipt image bytes."""
    return hashlib.sha256(image_bytes).hexdigest()


def parse_receipt_text_heuristics(text: str) -> Dict[str, Any]:
    """
    Regex/Heuristic fallback parser for receipt texts (Click, Payme, Uzum).
    """
    clean_text = text.replace("\xa0", " ").replace("&nbsp;", " ")

    # 1. Amount
    amount = None
    amount_match = re.search(
        r"(?:jami|summa|oplata|amount|itogo|to['`]?langan|to'lov)[\s:]*([0-9\s.,]+)(?:so['`]?m|uzs|sum)?",
        clean_text,
        re.IGNORECASE,
    )
    if amount_match:
        raw_amt = amount_match.group(1).replace(" ", "").replace(",", "").strip()
        try:
            val = Decimal(raw_amt)
            if 5000 <= val <= 50000000:
                amount = float(val)
        except Exception:
            pass

    if not amount:
        gen_match = re.search(
            r"([0-9]{1,3}(?:[\s.,][0-9]{3})+)\s*(?:so['`]?m|uzs|sum)",
            clean_text,
            re.IGNORECASE,
        )
        if gen_match:
            raw_amt = (
                gen_match.group(1)
                .replace(" ", "")
                .replace(",", "")
                .replace(".", "")
                .strip()
            )
            try:
                amount = float(raw_amt)
            except Exception:
                pass

    # 2. Transaction ID
    trans_id = ""
    mpo_match = re.search(
        r"(?:^|[\s:#№])([A-Z]{2,6}[0-9]{6,18})(?:$|[\s\.,])", clean_text, re.IGNORECASE
    )
    if mpo_match:
        trans_id = mpo_match.group(1).strip()
    else:
        trans_match = re.search(
            r"(?:trans(?:action)?[\s_]?id|chek\s*raqami|tranzaksiya|kod\s*tranzaksii|nomer\s*kvitantsii)[\s:#№]*([A-Z0-9_-]{6,32})",
            clean_text,
            re.IGNORECASE,
        )
        if trans_match:
            trans_id = trans_match.group(1).strip()

    # 3. Provider
    provider = PaymentReceipt.PaymentSystem.UNKNOWN
    lower = clean_text.lower()
    if "click" in lower:
        provider = PaymentReceipt.PaymentSystem.CLICK
    elif "payme" in lower:
        provider = PaymentReceipt.PaymentSystem.PAYME
    elif "uzum" in lower:
        provider = PaymentReceipt.PaymentSystem.UZUM
    elif "bank" in lower or "karta" in lower:
        provider = PaymentReceipt.PaymentSystem.BANK_CARD

    # 4. Success marker
    is_success = any(
        w in lower
        for w in (
            "bajarildi",
            "o'tkazildi",
            "muvaffaqiyatli",
            "uspeshno",
            "успешно",
            "oplacheno",
            "оплачено",
            "success",
            "completed",
        )
    )

    # 5. Date
    date_str = ""
    date_match = re.search(
        r"\b(\d{2}[./-]\d{2}[./-]\d{4}(?:\s+\d{2}:\d{2}(?::\d{2})?)?)\b", clean_text
    )
    if date_match:
        date_str = date_match.group(1)

    is_valid = bool(amount and (trans_id or is_success))

    return {
        "is_valid": is_valid,
        "amount": amount or 0.0,
        "transaction_id": trans_id,
        "payment_system": provider,
        "is_success": is_success,
        "date_str": date_str,
        "recipient": "GRAND EDUCATION",
        "method": "heuristic",
    }


def scan_receipt_vision(image_bytes: bytes) -> Dict[str, Any]:
    """
    Scans a receipt screenshot using Gemini Flash Vision or fallback.
    """
    # Allow mock mode for testing
    if getattr(settings, "RECEIPT_AI_MOCK_MODE", False):
        # In mock mode, check if image_bytes contains simulated receipt text
        try:
            decoded = image_bytes.decode("utf-8", errors="ignore")
            if "mock_receipt" in decoded or "amount" in decoded:
                return parse_receipt_text_heuristics(decoded)
        except Exception:
            pass

    api_key = (
        getattr(settings, "GEMINI_API_KEY", "")
        or getattr(settings, "OPENROUTER_API_KEY", "")
        or os.environ.get("GEMINI_API_KEY", "")
        or os.environ.get("OPENROUTER_API_KEY", "")
    )

    if api_key:
        try:
            import requests

            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            prompt = (
                "You are an expert Uzbek payment receipt OCR engine. "
                "Analyze this payment receipt screenshot (Click, Payme, Uzum, Bank). "
                "Extract and output strictly valid JSON with these fields: "
                '{"amount": <number in UZS>, "transaction_id": "<string>", '
                '"payment_system": "click|payme|uzum|bank_card|unknown", '
                '"date_str": "<YYYY-MM-DD HH:MM:SS or string>", '
                '"recipient": "<string>", "is_success": true|false, "is_valid": true|false}. '
                "If not an authentic payment receipt or image is blurry/unreadable, set is_valid: false."
            )

            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "google/gemini-2.0-flash-001",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{b64_img}"
                                    },
                                },
                            ],
                        }
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.1,
                },
                timeout=15,
            )
            if response.status_code == 200:
                res_json = response.json()
                content = res_json["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                ps = parsed.get("payment_system", "unknown").lower()
                if ps not in [
                    PaymentReceipt.PaymentSystem.CLICK,
                    PaymentReceipt.PaymentSystem.PAYME,
                    PaymentReceipt.PaymentSystem.UZUM,
                    PaymentReceipt.PaymentSystem.BANK_CARD,
                ]:
                    ps = PaymentReceipt.PaymentSystem.UNKNOWN

                return {
                    "is_valid": bool(
                        parsed.get("is_valid", True) and parsed.get("amount")
                    ),
                    "amount": float(parsed.get("amount", 0)),
                    "transaction_id": str(parsed.get("transaction_id", "")).strip(),
                    "payment_system": ps,
                    "date_str": str(parsed.get("date_str", "")),
                    "recipient": str(parsed.get("recipient", "")),
                    "is_success": bool(parsed.get("is_success", True)),
                    "method": "vision_ai",
                }
        except Exception as e:
            logger.warning(
                "Vision AI receipt scan failed: %s; falling back to heuristic OCR.", e
            )

    # OCR Fallback via pytesseract or text parser
    try:
        import io
        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        ocr_text = pytesseract.image_to_string(img, lang="eng+uzb")
        return parse_receipt_text_heuristics(ocr_text)
    except Exception:
        # If image cannot be read
        return {
            "is_valid": False,
            "amount": 0.0,
            "transaction_id": "",
            "payment_system": PaymentReceipt.PaymentSystem.UNKNOWN,
            "is_success": False,
            "date_str": "",
            "recipient": "",
            "method": "fallback_failed",
        }


def is_receipt_date_recent(date_str: str) -> bool:
    """
    Check if receipt timestamp is within the last 24 hours.
    Returns True if valid / recent, False if definitely older than 24h.
    """
    if not date_str:
        return True  # If date not legible, don't reject purely on date

    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%d.%m.%Y %H:%M:%S",
        "%d.%m.%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d",
        "%d.%m.%Y",
    ]
    now = timezone.now()
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str[:19].strip(), fmt)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.get_current_timezone())
            diff = (now - dt).total_seconds()
            # Must be within last 24 hours (86400s) + allow small clock skew up to 1 hour ahead
            if diff > 86400:
                return False
            return True
        except Exception:
            continue
    return True


def apply_fraud_strike(
    user: Any,
    reason: str,
    transaction_id: str = "",
    receipt_hash: str = "",
    force_ban: bool = False,
    metadata: Optional[dict] = None,
) -> Tuple[int, bool]:
    """
    Increments user fraud strikes. If strikes >= 2 or force_ban (duplicate transaction ID),
    bans the user account across Web and Telegram.
    Returns (strike_count: int, is_banned: bool).
    """
    user.fraud_strikes = getattr(user, "fraud_strikes", 0) + 1
    banned = False

    if force_ban or user.fraud_strikes >= 2:
        user.is_banned = True
        user.ban_reason = "Qalbaki to'lov cheki yuklash orqali firibgarlik"
        user.banned_at = timezone.now()
        banned = True

    user.save(update_fields=["fraud_strikes", "is_banned", "ban_reason", "banned_at"])

    # Log into FraudLog
    try:
        FraudLog.objects.create(
            user=user,
            receipt_hash=receipt_hash or "",
            transaction_id=transaction_id or "",
            reason=reason,
            strike_count=user.fraud_strikes,
            banned=banned,
            metadata=metadata or {},
        )
    except Exception as e:
        logger.error("Failed to write to FraudLog: %s", e)

    # Notify Admin if banned
    if banned:
        notify_admin_fraud(user, reason=reason, transaction_id=transaction_id)

    return user.fraud_strikes, banned


def notify_admin_fraud(user: Any, reason: str, transaction_id: str = ""):
    """Send fraud alert to admin channel/telegram."""
    tg_id = getattr(user, "telegram_chat_id", None) or "Noma'lum"
    username = (
        getattr(user, "telegram_username", None)
        or getattr(user, "username", "")
        or "Mavjud emas"
    )
    full_name = f"{user.first_name} {user.last_name}".strip() or str(user.email)
    msg = (
        "🚨 <b>FIRIBGARLIK ANIQLANDI VA BLOKLANDI!</b>\n\n"
        f"👤 Foydalanuvchi: {full_name} (@{username}, ID: {tg_id})\n"
        f"⚠️ Sabab: {reason} ({transaction_id or 'TX-N/A'})\n"
        f"🕒 Vaqt: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    try:
        from apps.webapi.views_crm import send_telegram_message_safe

        admin_chat_id = getattr(settings, "PAYMENT_ADMIN_CHAT_ID", None)
        if admin_chat_id:
            send_telegram_message_safe(int(admin_chat_id), msg)
    except Exception as e:
        logger.warning("Failed to dispatch admin fraud alert: %s", e)


class ReceiptVerifier:
    """
    Main verification pipeline for payment receipt screenshots.
    """

    @classmethod
    def verify_receipt(
        cls,
        user: Any,
        image_bytes: bytes,
        plan_type: str = "starter",
        filename: str = "receipt.jpg",
    ) -> Dict[str, Any]:
        """
        Processes receipt image bytes:
        - Checks SHA-256 hash for duplicate images (deliberate fraud)
        - Runs Vision OCR
        - Checks Transaction ID for reuse / theft (deliberate fraud)
        - Checks Amount & Date (24h)
        - Auto-activates subscription or applies fraud strikes / auto-ban
        """
        # If user is already banned, reject immediately
        if getattr(user, "is_banned", False):
            return {
                "success": False,
                "is_banned": True,
                "strike_count": user.fraud_strikes,
                "message": (
                    "🚫 <b>Hisobingiz bloklandi!</b> Siz tomonidan qalbaki to'lov kvitansiyasi aniqlandi. "
                    "Tizimdan foydalanish huquqingiz cheklandi. Savollar bo'yicha: @grandec_admin"
                ),
                "ban_reason": user.ban_reason,
            }

        # Validate bytes
        if not image_bytes or len(image_bytes) < 10:
            return {
                "success": False,
                "message": "⚠️ Chek tasdiqlanmadi. Iltimos, Click/Payme ilovasidan to'lov muvaffaqiyatli o'tgan rasmiy kvitansiyani yuboring.",
                "is_banned": False,
            }

        # 1. SHA-256 Hash Check (Image integrity)
        receipt_hash = compute_receipt_hash(image_bytes)
        duplicate_hash_receipt = PaymentReceipt.objects.filter(
            receipt_hash=receipt_hash
        ).first()
        if duplicate_hash_receipt:
            # Reusing same receipt image = deliberate fraud!
            strikes, banned = apply_fraud_strike(
                user=user,
                reason="Bir xil chek rasmini qayta yuklash (SHA-256 xesh duplikati)",
                receipt_hash=receipt_hash,
                force_ban=True,
                metadata={"duplicate_receipt_id": duplicate_hash_receipt.id},
            )
            return {
                "success": False,
                "is_banned": banned,
                "strike_count": strikes,
                "message": (
                    "🚫 <b>Hisobingiz bloklandi!</b> Siz tomonidan qalbaki to'lov kvitansiyasi aniqlandi. "
                    "Tizimdan foydalanish huquqingiz cheklandi. Savollar bo'yicha: @grandec_admin"
                    if banned
                    else "⛔ QALBAKI CHEK ANIQLANDI! Tizimga soxta yoki takroriy chek yuklash qat'iyan man etiladi. Keyingi urinishda hisobingiz butunlay bloklanadi!"
                ),
            }

        # 2. Vision OCR Analysis
        scan_res = scan_receipt_vision(image_bytes)
        if not scan_res.get("is_valid"):
            # 1-darajali xatolik: tushunarsiz rasm, xira skrinshot, to'lov kvitansiyasi emas
            return {
                "success": False,
                "message": "⚠️ Chek tasdiqlanmadi. Iltimos, Click/Payme ilovasidan to'lov muvaffaqiyatli o'tgan rasmiy kvitansiyani yuboring.",
                "is_banned": False,
            }

        amount = Decimal(str(scan_res.get("amount", 0)))
        transaction_id = str(scan_res.get("transaction_id", "")).strip()
        payment_system = scan_res.get(
            "payment_system", PaymentReceipt.PaymentSystem.UNKNOWN
        )
        date_str = scan_res.get("date_str", "")

        # Fallback transaction id if legitimate receipt had no text trans_id
        if not transaction_id:
            transaction_id = f"TX-{receipt_hash[:12].upper()}"

        # 3. Transaction ID Uniqueness Check
        duplicate_tx = PaymentReceipt.objects.filter(
            transaction_id=transaction_id
        ).first()
        if duplicate_tx:
            # Reusing someone else's or previous transaction ID = deliberate fraud & auto-ban!
            strikes, banned = apply_fraud_strike(
                user=user,
                reason=f"Takroriy/qalbaki tranzaksiya ID ({transaction_id})",
                transaction_id=transaction_id,
                receipt_hash=receipt_hash,
                force_ban=True,
                metadata={"duplicate_tx_id": duplicate_tx.id},
            )
            return {
                "success": False,
                "is_banned": banned,
                "strike_count": strikes,
                "message": (
                    "🚫 <b>Hisobingiz bloklandi!</b> Siz tomonidan qalbaki to'lov kvitansiyasi aniqlandi. "
                    "Tizimdan foydalanish huquqingiz cheklandi. Savollar bo'yicha: @grandec_admin"
                ),
            }

        # 4. Plan and Amount Match Check
        clean_plan = (plan_type or "starter").lower().strip()
        if clean_plan not in PLAN_PRICES:
            clean_plan = "starter"
        required_price = PLAN_PRICES[clean_plan]

        if amount < required_price:
            # Level 1 error (Underpaid / incorrect plan selected)
            return {
                "success": False,
                "message": (
                    f"⚠️ To'lov summasi yetarli emas. Chekdagi summa: {int(amount):,} so'm. "
                    f"{clean_plan.upper()} tarifi narxi: {int(required_price):,} so'm. "
                    "Iltimos, to'liq to'lov chekini yuboring."
                ),
                "is_banned": False,
            }

        # 5. Date freshness check (last 24 hours)
        if not is_receipt_date_recent(date_str):
            return {
                "success": False,
                "message": (
                    "⚠️ Chek muddati eskirgan. Faqat oxirgi 24 soat ichida amalga oshirilgan "
                    "to'lov cheklari qabul qilinadi."
                ),
                "is_banned": False,
            }

        # 6. Success Flow — Save verified PaymentReceipt & Activate Subscription
        content_file = ContentFile(
            image_bytes, name=f"receipt_{user.id}_{transaction_id}.jpg"
        )
        receipt = PaymentReceipt.objects.create(
            user=user,
            plan_type=clean_plan,
            amount=amount,
            payment_system=payment_system,
            transaction_id=transaction_id,
            receipt_image=content_file,
            receipt_hash=receipt_hash,
            is_verified=True,
            admin_note="Avtomatik Vision AI tekshiruvidan muvaffaqiyatli o'tdi",
        )

        # 7. Activate plan
        cls._activate_user_plan(user, clean_plan, receipt)

        plan_display = clean_plan.upper()
        return {
            "success": True,
            "receipt_id": receipt.id,
            "plan_type": clean_plan,
            "amount": float(amount),
            "transaction_id": transaction_id,
            "is_banned": False,
            "message": (
                f"🎉 <b>To'lovingiz qabul qilindi!</b>\n\n"
                f"Sizning <b>{plan_display}</b> tarifingiz muvaffaqiyatli faollashtirildi.\n"
                "Imkoniyatlaringiz yangilandi. Bilim olishda omad tilaymiz!"
            ),
        }

    @classmethod
    def _activate_user_plan(
        cls, user: Any, plan_type: str, receipt: PaymentReceipt
    ) -> None:
        """Activates Starter, PRO, or PREMIUM plan for user."""
        try:
            from apps.payments.services import _get_or_create_plan_for_receipt
            from apps.payments.subscriptions import grant_subscription
            from apps.payments.models import UserSubscription

            plan_obj = _get_or_create_plan_for_receipt(plan_type)
            grant_subscription(
                user=user,
                plan=plan_obj,
                source=UserSubscription.Source.WEBSITE,
                payment_method="card",
                payment_reference=f"verified_receipt:{receipt.id}:{receipt.transaction_id}",
                grant_source="automated_receipt_verification",
                days=30,
            )
        except Exception as e:
            logger.error(
                "Failed to grant subscription for receipt #%s: %s", receipt.id, e
            )

        # Update profile plan field
        try:
            profile = getattr(user, "profile", None)
            if profile:
                profile.plan = plan_type
                profile.save(update_fields=["plan"])
        except Exception as e:
            logger.warning("Failed to update profile plan for user #%s: %s", user.id, e)
