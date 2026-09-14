"""Canonical Telegram identity lookup and account provisioning."""
from __future__ import annotations

import re
from typing import Any

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import Profile


class TelegramIdentityUnverified(ValueError):
    """A legacy numeric link exists but its provenance was never recorded."""


class TelegramAuthConflict(ValueError):
    """The phone number belongs to one account, the Telegram ID to another."""


class TelegramAuthAmbiguous(ValueError):
    """The phone number matches more than one account."""


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


def normalize_phone(value: Any) -> str:
    """Digits only (leading '+' stripped); '' when too short to match on."""
    digits = re.sub(r"\D", "", str(value or ""))
    return digits if len(digits) >= 7 else ""


def find_users_by_phone(clean_phone: str) -> list:
    """All users whose stored profile phone normalizes to *clean_phone*."""
    target = normalize_phone(clean_phone)
    if not target:
        return []
    matched = []
    for profile in (
        Profile.objects.select_related("user")
        .exclude(phone="")
        .exclude(phone__isnull=True)
    ):
        if normalize_phone(profile.phone) == target:
            matched.append(profile.user)
    return matched


def resolve_bot_auth_user(
    telegram_id: int, clean_phone: str
) -> tuple[Any | None, str]:
    """Match a bot-login attempt to an account: Telegram ID first, then phone.

    Returns (user, how) where how is "tg" (verified Telegram link),
    "phone" (found by verified contact number, link attached) or
    ("none", None) when no account exists yet and the caller must ask for
    a name and provision one.

    Raises:
        TelegramIdentityUnverified — legacy numeric link, must re-verify.
        TelegramAuthConflict — phone and Telegram ID point at two accounts.
        TelegramAuthAmbiguous — phone matches several accounts.
        ValueError — matched account is inactive.
    """
    User = get_user_model()
    numeric_id = _numeric_telegram_id(telegram_id)

    with transaction.atomic():
        tg_user = (
            User.objects.select_for_update()
            .filter(telegram_chat_id=numeric_id)
            .first()
        )
        if tg_user is not None and tg_user.telegram_identity_verified_at is None:
            raise TelegramIdentityUnverified(
                "Telegram hisobining eski bog'lanishi qayta tasdiqlanishi kerak."
            )

        phone_users = find_users_by_phone(clean_phone)
        distinct = {u.pk: u for u in phone_users}
        if len(distinct) > 1:
            raise TelegramAuthAmbiguous(
                "Bu telefon raqami bir nechta hisobga bog'langan. "
                "Administratorga murojaat qiling."
            )
        phone_user = next(iter(distinct.values()), None)

        if phone_user is not None and tg_user is not None and tg_user.pk != phone_user.pk:
            raise TelegramAuthConflict(
                "Bu telefon raqami boshqa hisobga, Telegram esa boshqa "
                "hisobga bog'langan. Administratorga murojaat qiling."
            )
        if tg_user is not None:
            if not tg_user.is_active:
                raise ValueError("Hisob faol emas.")
            return tg_user, "tg"
        if phone_user is not None:
            if not phone_user.is_active:
                raise ValueError("Hisob faol emas.")
            try:
                with transaction.atomic():
                    phone_user.telegram_chat_id = numeric_id
                    phone_user.telegram_identity_verified_at = timezone.now()
                    phone_user.save(
                        update_fields=[
                            "telegram_chat_id",
                            "telegram_identity_verified_at",
                        ]
                    )
            except IntegrityError:
                raise TelegramAuthConflict(
                    "Bu Telegram boshqa hisobga bog'langan. "
                    "Administratorga murojaat qiling."
                )
            return phone_user, "phone"
        return None, "none"
