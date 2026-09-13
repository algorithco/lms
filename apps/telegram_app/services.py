"""
Telegram Mini App — HMAC-SHA256 validation service.

Telegram WebApp initData validation:
    1. Parse initData string (URL-encoded key=value pairs)
    2. Extract 'hash' field
    3. Build data-check-string: sorted key=value pairs joined by newlines
    4. Compute HMAC-SHA256 using bot_token as secret key
    5. Compare computed hash with provided hash

Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any
from urllib.parse import parse_qsl

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# TMA data validity period — 10 minutes (Telegram recommends 24h max, but 10m
# limits replay window for stolen initData). Must match cache replay TTL.
TMA_DATA_MAX_AGE = 600
TMA_REPLAY_CACHE_PREFIX = "tma:hash:"


class TelegramMiniAppService:
    """
    Telegram Mini App initData validation.

    Validates that the data came from Telegram and hasn't been tampered with.
    """

    @classmethod
    def validate_init_data(cls, init_data: str, bot_token: str = "") -> dict[str, Any] | None:
        """
        Validate Telegram WebApp initData.

        Args:
            init_data: Raw initData string from Telegram WebApp.
            bot_token: Telegram bot token. Falls back to settings.

        Returns:
            Parsed user data dict if valid, None if invalid.
        """
        if not bot_token:
            bot_token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
            if not bot_token:
                logger.error("TELEGRAM_BOT_TOKEN not configured")
                return None

        if not init_data:
            logger.warning("Empty init_data received")
            return None

        try:
            return cls._validate(init_data, bot_token)
        except Exception as e:
            logger.error("TMA validation error: %s", e)
            return None

    @classmethod
    def _validate(cls, init_data: str, bot_token: str) -> dict[str, Any] | None:
        """Internal validation logic."""
        # Parse the initData string
        parsed = cls._parse_init_data(init_data)

        # Extract hash
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            logger.warning("No hash in init_data")
            return None

        # Build data-check-string
        data_check_string = cls._build_data_check_string(parsed)

        # Compute secret key
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode(),
            hashlib.sha256,
        ).digest()

        # Compute HMAC
        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Compare
        if not hmac.compare_digest(computed_hash, received_hash):
            logger.warning("Hash mismatch: computed=%s, received=%s", computed_hash, received_hash)
            return None

        # Check auth_date (not too old, not from future)
        try:
            auth_date = int(parsed.get("auth_date", 0))
        except (ValueError, TypeError):
            logger.warning("Invalid auth_date in init_data")
            return None
        age = time.time() - auth_date
        if auth_date <= 0 or age < -60 or age > TMA_DATA_MAX_AGE:
            logger.warning("initData expired: auth_date=%d, now=%d", auth_date, time.time())
            return None

        # Replay protection — hash may be reused only once per TTL window
        replay_key = f"{TMA_REPLAY_CACHE_PREFIX}{received_hash}"
        if cache.get(replay_key):
            logger.warning("Replay detected for initData hash=%s", received_hash[:8])
            return None

        # Parse user data
        user_data = cls._parse_user(parsed)
        if not user_data.get("id"):
            logger.warning("Missing user id in init_data")
            return None

        cache.set(replay_key, 1, timeout=TMA_DATA_MAX_AGE)
        logger.info("TMA validated: user_id=%s", user_data.get("id"))
        return user_data

    @classmethod
    def _parse_init_data(cls, init_data: str) -> dict[str, str]:
        """Parse URL-encoded initData into dict (Telegram uses x-www-form-urlencoded)."""
        # parse_qsl handles unquote_plus and duplicate keys (last wins) correctly
        try:
            pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
        except ValueError:
            logger.warning("Failed to parse init_data")
            return {}
        result: dict[str, str] = {}
        for key, value in pairs:
            result[key] = value
        return result

    @classmethod
    def _build_data_check_string(cls, data: dict[str, str]) -> str:
        """
        Build data-check-string from parsed data.

        Rules:
            - Sort keys alphabetically
            - Join key=value pairs with newlines
            - Exclude 'hash' key
        """
        sorted_pairs = sorted(data.items())
        return "\n".join(f"{k}={v}" for k, v in sorted_pairs)

    @classmethod
    def _parse_user(cls, parsed: dict[str, str]) -> dict[str, Any]:
        """
        Parse Telegram user data from init_data.

        The 'user' field is a JSON string:
        {"id": 12345, "first_name": "John", "last_name": "Doe", "username": "johndoe", "language_code": "en"}
        """
        import json

        user_json = parsed.get("user", "{}")
        try:
            user_data = json.loads(user_json)
        except json.JSONDecodeError:
            logger.warning("Invalid user JSON in init_data")
            return {}

        return {
            "id": user_data.get("id"),
            "first_name": user_data.get("first_name", ""),
            "last_name": user_data.get("last_name", ""),
            "username": user_data.get("username", ""),
            "language_code": user_data.get("language_code", "uz"),
            "auth_date": int(parsed.get("auth_date", 0)),
            "is_premium": user_data.get("is_premium", False),
        }
