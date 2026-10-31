"""Referral and viral growth service."""

from __future__ import annotations

import logging
from django.db import transaction
from apps.accounts.models import ReferralHistory, User

logger = logging.getLogger(__name__)


def apply_referral_reward(new_user: User, referral_code: str) -> tuple[bool, str]:
    """
    Applies referral code to a new user.
    Awards +1 test and +1 essay bonus to both referrer and new user.
    """
    if not referral_code:
        return False, "Referal kodi kiritilmadi."

    clean_code = referral_code.strip()

    # Check if this user already received a referral reward
    if ReferralHistory.objects.filter(referred_user=new_user).exists():
        return False, "Siz allaqachon taklif bonusi olgansiz."

    referrer = (
        User.objects.filter(referral_code__iexact=clean_code).first()
        or User.objects.filter(referral_code__iexact=f"ref_{clean_code}").first()
    )
    if not referrer:
        return False, "Bunday referal kodi topilmadi."

    if referrer.id == new_user.id:
        return False, "O'zingizning referal kodingizdan foydalana olmaysiz."

    with transaction.atomic():
        # Reward both parties
        referrer.bonus_tests = (referrer.bonus_tests or 0) + 1
        referrer.bonus_essays = (referrer.bonus_essays or 0) + 1
        referrer.save(update_fields=["bonus_tests", "bonus_essays"])

        new_user.bonus_tests = (new_user.bonus_tests or 0) + 1
        new_user.bonus_essays = (new_user.bonus_essays or 0) + 1
        new_user.save(update_fields=["bonus_tests", "bonus_essays"])

        ReferralHistory.objects.create(
            referrer=referrer,
            referred_user=new_user,
            referral_code=clean_code,
            reward_given=True,
            referrer_bonus_tests=1,
            referred_bonus_tests=1,
            referrer_bonus_essays=1,
            referred_bonus_essays=1,
        )

        logger.info(
            "Referral reward applied: Referrer %s, New User %s, Code %s",
            referrer.id,
            new_user.id,
            clean_code,
        )

    # Send Telegram alert to referrer if linked
    if referrer.telegram_chat_id:
        try:
            from apps.notifications.services.telegram_service import TelegramService

            friend_name = new_user.get_full_name() or new_user.email
            total_invited = ReferralHistory.objects.filter(referrer=referrer).count()
            TelegramService.send_message(
                chat_id=int(referrer.telegram_chat_id),
                text=(
                    f"🎁 <b>Tabriklaymiz! Do'stingiz qo'shildi!</b>\n\n"
                    f"👤 <b>{friend_name}</b> sizning taklifingiz bilan platformaga qo'shildi.\n"
                    f"⭐ Hisobingizga <b>+1 ta rasmiy Mock Test</b> va <b>+1 ta AI Esse tekshiruvi</b> bonusi qo'shildi!\n\n"
                    f"Jami taklif qilingan do'stlaringiz: <b>{total_invited} ta</b>"
                ),
            )
        except Exception as e:
            logger.warning("Could not send Telegram referral alert: %s", e)

    return (
        True,
        "Referal bonusi muvaffaqiyatli faollashtirildi! Sizga +1 ta test va +1 ta esse qo'shildi.",
    )
