"""Two-channel Telegram account linking."""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import TelegramLinkChallenge
from .telegram_identity import _numeric_telegram_id

CHALLENGE_LIFETIME = timedelta(minutes=10)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_link_challenge(user) -> str:
    if not user.is_authenticated or not user.is_active:
        raise ValueError("Active web login required.")
    token = secrets.token_urlsafe(32)
    with transaction.atomic():
        # Only the newest challenge can be completed.
        TelegramLinkChallenge.objects.filter(
            user=user, confirmed_at__isnull=True,
        ).update(confirmed_at=timezone.now())
        TelegramLinkChallenge.objects.create(user=user, token_hash=_token_hash(token))
    return token


def confirm_link_challenge(token: str, telegram_id: int) -> str:
    """Consume one challenge using the numeric sender ID from a Telegram update."""
    try:
        numeric_id = _numeric_telegram_id(telegram_id)
    except ValueError:
        return "invalid"
    User = get_user_model()
    try:
        return _confirm_link_challenge_atomic(token, numeric_id, User)
    except IntegrityError:
        # Another confirmation may have claimed the unique Telegram ID.
        return "conflict"


@transaction.atomic
def _confirm_link_challenge_atomic(token: str, numeric_id: int, User) -> str:
    challenge = (
        TelegramLinkChallenge.objects.select_for_update()
        .select_related("user")
        .filter(token_hash=_token_hash(token))
        .first()
    )
    if challenge is None or challenge.confirmed_at is not None:
        return "invalid"
    if timezone.now() > challenge.created_at + CHALLENGE_LIFETIME:
        return "expired"
    user = User.objects.select_for_update().get(pk=challenge.user_id)
    if not user.is_active:
        return "invalid"
    if User.objects.filter(telegram_chat_id=numeric_id).exclude(pk=user.pk).exists():
        return "conflict"
    user.telegram_chat_id = numeric_id
    user.telegram_identity_verified_at = timezone.now()
    user.save(update_fields=[
        "telegram_chat_id", "telegram_identity_verified_at",
    ])
    challenge.telegram_id = numeric_id
    challenge.confirmed_at = timezone.now()
    challenge.save(update_fields=["telegram_id", "confirmed_at"])
    return "confirmed"


def link_challenge_status(user, token: str) -> str:
    challenge = TelegramLinkChallenge.objects.filter(
        user=user, token_hash=_token_hash(token),
    ).first()
    if challenge is None:
        return "invalid"
    if challenge.confirmed_at is not None:
        return "confirmed" if challenge.telegram_id else "invalid"
    if timezone.now() > challenge.created_at + CHALLENGE_LIFETIME:
        return "expired"
    return "pending"
