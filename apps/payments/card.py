"""Payment card details come from the environment only.

There is no built-in card number: if ``PAYMENT_CARD_NUMBER`` / ``PAYMENT_CARD_HOLDER``
are not configured, the website and the bot say that payment details are not
available yet and the administrator is told (at most once every six hours).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

UNAVAILABLE_MESSAGE = "To'lov ma'lumoti hozircha mavjud emas."
_ALERT_KEY = "payment_card:missing_alerted"
_ALERT_EVERY = 6 * 60 * 60


@dataclass(frozen=True)
class PaymentCard:
    number: str
    holder: str
    bank: str


def get_payment_card() -> PaymentCard | None:
    """The configured card, or ``None`` when the number or holder is missing."""
    number = str(getattr(settings, "PAYMENT_CARD_NUMBER", "") or "").strip()
    holder = str(getattr(settings, "PAYMENT_CARD_HOLDER", "") or "").strip()
    if not number or not holder:
        return None
    return PaymentCard(number=number, holder=holder, bank=str(getattr(settings, "PAYMENT_CARD_BANK", "") or "").strip())


def notify_admin_card_missing() -> None:
    """Tell the administrator once in a while that payments cannot be shown."""
    try:
        if not cache.add(_ALERT_KEY, 1, _ALERT_EVERY):
            return
    except Exception:  # pragma: no cover - cache outage
        return
    admin_id = getattr(settings, "ADMIN_TELEGRAM_ID", None)
    if not admin_id:
        return
    try:
        from apps.notifications.services.telegram_service import TelegramService

        TelegramService.send_message(
            chat_id=int(admin_id),
            text=(
                "⚠️ <b>To'lov kartasi sozlanmagan</b>\n"
                "Foydalanuvchi to'lov ma'lumotini so'radi, lekin <code>PAYMENT_CARD_NUMBER</code> / "
                "<code>PAYMENT_CARD_HOLDER</code> serverda yo'q. Hozircha «mavjud emas» ko'rsatilmoqda."
            ),
            parse_mode="HTML",
        )
    except Exception:
        logger.warning("Could not tell the admin the payment card is missing", exc_info=True)
