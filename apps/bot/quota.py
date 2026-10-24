"""
Bot Quota Enforcement (Module 2).
Enforces free 1-essay/day rules and Starter/PRO tier checks for Telegram Bot updates.
"""

from __future__ import annotations

from typing import Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from apps.subscriptions.services import QuotaService


def get_essay_denied_keyboard(site_url: str = "https://grandec.uz") -> InlineKeyboardMarkup:
    """Generate the exact quota upgrade keyboard requested in Module 2."""
    clean_site = site_url.rstrip("/")
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⚡ Starter (5 000 so'm)", callback_data="cb_plan_starter"),
                InlineKeyboardButton("🔥 PRO tarifiga o'tish", callback_data="cb_plan_pro"),
            ],
            [
                InlineKeyboardButton("🌐 Saytga o'tish", url=f"{clean_site}/subscribe"),
            ],
        ]
    )


def check_bot_essay_quota(user: Any, site_url: str = "https://grandec.uz") -> tuple[bool, str, InlineKeyboardMarkup | None]:
    """
    Check if the user is allowed to submit an essay via bot.
    Returns (is_allowed: bool, message: str, keyboard: InlineKeyboardMarkup | None).
    """
    allowed, message, details = QuotaService.check_essay_quota(user)
    if not allowed:
        keyboard = get_essay_denied_keyboard(site_url)
        return False, message, keyboard

    return True, "", None


def record_bot_essay_consumption(user: Any, kind: str = "text_essay", idempotency_key: str | None = None) -> bool:
    """Record consumption of one essay quota."""
    return QuotaService.consume_essay_quota(user, kind=kind, idempotency_key=idempotency_key, source="telegram_bot")
