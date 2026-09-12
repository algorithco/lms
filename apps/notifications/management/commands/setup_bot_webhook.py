"""
Management command: setup_bot_webhook

Sets the Telegram bot webhook URL for production deployment.

Usage:
    python manage.py setup_bot_webhook --domain your-domain.com
    python manage.py setup_bot_webhook --remove
"""
from __future__ import annotations

import logging

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Telegram bot webhook URL'sini sozlash yoki o'chirish"

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            type=str,
            default="",
            help="Webhook domeni (masalan: example.com)",
        )
        parser.add_argument(
            "--remove",
            action="store_true",
            help="Webhook'ni o'chirish",
        )

    def handle(self, *args, **options):
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN sozlanmagan!")

        api_base = f"https://api.telegram.org/bot{token}"

        if options["remove"]:
            self._remove_webhook(api_base)
        else:
            domain = options["domain"]
            if not domain:
                raise CommandError("--domain kerak! Masalan: --domain example.com")
            self._set_webhook(api_base, domain)

    def _set_webhook(self, api_base: str, domain: str) -> None:
        # Must match the actual Django route (apps/notifications/urls.py),
        # which is mounted under api/notifications/ in the root urlconf.
        webhook_path = reverse("notifications:telegram-webhook")
        webhook_url = f"https://{domain}{webhook_path}"

        # When TELEGRAM_WEBHOOK_SECRET is configured, register it so Telegram
        # signs every update with X-Telegram-Bot-Api-Secret-Token.
        secret_token = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
        if not secret_token:
            raise CommandError(
                "Webhook o'rnatish uchun TELEGRAM_WEBHOOK_SECRET sozlanishi shart."
            )

        self.stdout.write(f"Webhook o'rnatilmoqda: {webhook_url}")

        try:
            with httpx.Client(timeout=10.0) as client:
                payload = {
                    "url": webhook_url,
                    "allowed_updates": ["message", "callback_query"],
                    "drop_pending_updates": True,
                }
                payload["secret_token"] = secret_token

                resp = client.post(f"{api_base}/setWebhook", json=payload)
                data = resp.json()

                if data.get("ok"):
                    self.stdout.write(self.style.SUCCESS(f"Webhook muvaffaqiyatli o'rnatildi: {webhook_url}"))

                    # Verify (inside the same client session)
                    resp2 = client.get(f"{api_base}/getWebhookInfo")
                    info = resp2.json()
                    if info.get("ok"):
                        wh = info["result"]
                        self.stdout.write(f"  URL: {wh.get('url', 'N/A')}")
                        self.stdout.write(f"  Pending: {wh.get('pending_update_count', 0)}")
                        if wh.get("last_error_date"):
                            self.stdout.write(f"  Last error: {wh.get('last_error_message', 'N/A')}")
                else:
                    self.stdout.write(self.style.ERROR(f"Xatolik: {data.get('description', 'Unknown')}"))

        except Exception as e:
            raise CommandError(f"Webhook o'rnatishda xatolik: {e}")

    def _remove_webhook(self, api_base: str) -> None:
        self.stdout.write("Webhook o'chirilmoqda...")

        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(f"{api_base}/deleteWebhook")
                data = resp.json()

            if data.get("ok"):
                self.stdout.write(self.style.SUCCESS("Webhook muvaffaqiyatli o'chirildi."))
            else:
                self.stdout.write(self.style.ERROR(f"Xatolik: {data.get('description', 'Unknown')}"))

        except Exception as e:
            raise CommandError(f"Webhook o'chirishda xatolik: {e}")
