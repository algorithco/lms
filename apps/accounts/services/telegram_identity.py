"""Canonical Telegram identity lookup and account provisioning."""
from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Profile


class TelegramIdentityUnverified(ValueError):
    """A legacy numeric link exists but its provenance was never recorded."""


def _numeric_telegram_id(value: Any) -> int:
    """Accept only a positive signed 64-bit JSON integer from Telegram."""
    if type(value) is not int or value <= 0 or value > 2**63 - 1:
        raise ValueError("Invalid Telegram user ID.")
    return value


def get_or_create_telegram_user(
    telegram_user: dict[str, Any],
) -> tuple[Any, bool]:
    """Resolve only by signed numeric ID, creating a student when absent.

    Username is deliberately ignored for identity and account linking. Legacy
    numeric links are retained but require explicit ownership verification.
    """
    User = get_user_model()
    telegram_id = _numeric_telegram_id(telegram_user.get("id"))

    with transaction.atomic():
        user = (
            User.objects.select_for_update()
            .filter(telegram_chat_id=telegram_id)
            .first()
        )
        if user is not None:
            if user.telegram_identity_verified_at is None:
                raise TelegramIdentityUnverified(
                    "Telegram hisobining eski bog'lanishi qayta tasdiqlanishi kerak."
                )
            return user, False

        # Numeric IDs are immutable. If a legacy/unlinked row already uses this
        # generated email, use a suffix rather than silently claiming that row.
        base_local = f"tg_{telegram_id}"
        suffix = 0
        while True:
            local = base_local if suffix == 0 else f"{base_local}_{suffix}"
            email = f"{local}@telegram.tma"
            if not User.objects.filter(email=email).exists():
                break
            suffix += 1

        try:
            # A savepoint keeps the outer transaction usable if another
            # request wins the unique Telegram-ID race.
            with transaction.atomic():
                user = User.objects.create_user(
                    email=email,
                    password=None,
                    first_name=str(telegram_user.get("first_name", ""))[:150],
                    last_name=str(telegram_user.get("last_name", ""))[:150],
                    role=User.Role.STUDENT,
                    telegram_chat_id=telegram_id,
                    telegram_identity_verified_at=timezone.now(),
                )
        except IntegrityError:
            # A concurrent signed request may have provisioned the same ID.
            user = User.objects.filter(telegram_chat_id=telegram_id).first()
            if user is None:
                raise
            if user.telegram_identity_verified_at is None:
                raise TelegramIdentityUnverified(
                    "Telegram hisobining eski bog'lanishi qayta tasdiqlanishi kerak."
                )
            return user, False

        Profile.objects.get_or_create(user=user)
        return user, True
