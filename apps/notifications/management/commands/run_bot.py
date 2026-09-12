"""
Management command: run_bot

Starts the Telegram bot with long polling.

Usage:
    python manage.py run_bot
    python manage.py run_bot --webhook --domain your-domain.com
"""
from __future__ import annotations

import logging
import os
import sys

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Telegram bot'ni ishga tushirish (polling yoki webhook)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--webhook",
            action="store_true",
            help="Webhook rejimida ishga tushirish (production uchun)",
        )
        parser.add_argument(
            "--domain",
            type=str,
            default="",
            help="Webhook domeni (masalan: example.com)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=8443,
            help="Webhook port (default: 8443)",
        )

    def handle(self, *args, **options):
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")

        if not token:
            raise CommandError(
                "TELEGRAM_BOT_TOKEN sozlanmagan!\n"
                ".env fayliga qo'shing yoki settings.py da o'rnating."
            )

        self.stdout.write(self.style.SUCCESS(f"Bot token topildi: ...{token[-8:]}"))

        try:
            from telegram.ext import ApplicationBuilder

            from apps.notifications.bot.handlers import post_init, setup_handlers

            # Build application with extended timeouts
            app = (
                ApplicationBuilder()
                .token(token)
                .post_init(post_init)
                .connect_timeout(30)
                .read_timeout(30)
                .build()
            )

            # Register handlers
            setup_handlers(app)

            if options["webhook"]:
                self._run_webhook(app, options)
            else:
                self._run_polling(app)

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nBot to'xtatildi."))
        except Exception as e:
            raise CommandError(f"Bot ishga tushmadi: {e}")

    def _run_polling(self, app):
        """Run bot with long polling (development)."""
        self.stdout.write(self.style.SUCCESS("Bot polling rejimda ishga tushdi..."))
        self.stdout.write(self.style.SUCCESS("To'xtatish uchun: Ctrl+C"))
        self.stdout.write(self.style.SUCCESS("Bot: @uz_essaygrader_bot"))

        app.run_polling(
            drop_pending_updates=False,
            allowed_updates=[
                "message",
                "callback_query",
                "inline_query",
            ],
        )

    def _run_webhook(self, app, options):
        """Run bot with webhook (production)."""
        domain = options["domain"]
        port = options["port"]

        if not domain:
            raise CommandError("Webhook rejimda --domain kerak!")

        webhook_url = f"https://{domain}/telegram/webhook/"
        secret_token = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
        if not secret_token:
            raise CommandError(
                "Webhook rejimida TELEGRAM_WEBHOOK_SECRET sozlanishi shart."
            )

        self.stdout.write(self.style.SUCCESS(f"Webhook URL: {webhook_url}"))
        self.stdout.write(self.style.SUCCESS(f"Port: {port}"))

        kwargs = dict(
            listen="0.0.0.0",
            port=port,
            url_path="telegram/webhook/",
            webhook_url=webhook_url,
            drop_pending_updates=True,
        )
        kwargs["secret_token"] = secret_token

        app.run_webhook(**kwargs)
