"""
Management command: run_all

Starts both Django web server AND Telegram bot simultaneously.

Usage:
    python manage.py run_all
    python manage.py run_all --port 8000
    python manage.py run_all --no-bot          # faqat web server
    python manage.py run_all --no-web          # faqat bot
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Web server + Telegram bot — bir paytda ishga tushirish"

    def add_arguments(self, parser):
        parser.add_argument(
            "--port", type=int, default=8000,
            help="Web server porti (default: 8000)",
        )
        parser.add_argument(
            "--no-bot", action="store_true",
            help="Faqat web server (botni ishga tushirmaydi)",
        )
        parser.add_argument(
            "--no-web", action="store_true",
            help="Faqat Telegram bot (web serverni ishga tushirmaydi)",
        )
        parser.add_argument(
            "--noreload", action="store_true",
            help="Fayl o'zgarishlarini kuzatmaslik (production uchun)",
        )

    def handle(self, *args, **options):
        port = options["port"]
        run_web = not options["no_web"]
        run_bot = not options["no_bot"]

        if not run_web and not run_bot:
            raise CommandError("Hech narsa ishga tushirilmaydi! --no-bot yoki --no-web ni olib tashlang.")

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("  🚀 LMS Platform — bir paytda ishga tushirilmoqda"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        threads = []
        stop_event = threading.Event()

        # --- Web Server ---
        if run_web:
            web_thread = threading.Thread(
                target=self._run_web_server,
                args=(port, options["noreload"], stop_event),
                daemon=True,
                name="web-server",
            )
            threads.append(web_thread)
            self.stdout.write(self.style.SUCCESS(f"  🌐 Web server: http://127.0.0.1:{port}/"))

        # --- Telegram Bot ---
        if run_bot:
            token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
            if not token:
                self.stdout.write(self.style.WARNING(
                    "  ⚠️  TELEGRAM_BOT_TOKEN sozlanmagan — bot ishga tushmaydi"
                ))
            else:
                bot_thread = threading.Thread(
                    target=self._run_telegram_bot,
                    args=(token, stop_event),
                    daemon=True,
                    name="telegram-bot",
                )
                threads.append(bot_thread)
                self.stdout.write(self.style.SUCCESS(
                    f"  🤖 Telegram bot: @uz_essaygrader_bot"
                ))

        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("  To'xtatish uchun: Ctrl+C"))
        self.stdout.write(self.style.SUCCESS("=" * 60))

        # Barcha thread'larni ishga tushirish
        for t in threads:
            t.start()

        # Signal handler — Ctrl+C bosilganda tozalab to'xtatish
        def signal_handler(sig, frame):
            self.stdout.write(self.style.WARNING("\n⏸  To'xtatilmoqda..."))
            stop_event.set()
            # Bot thread'ni majburiy to'xtatish
            for t in threads:
                if t.is_alive():
                    t.join(timeout=5)
            self.stdout.write(self.style.SUCCESS("✅ Hammasi to'xtatildi!"))
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Asosiy thread'ni ushlab turish
        try:
            while not stop_event.is_set():
                time.sleep(1)
                # O'lik thread'larni tekshirish
                for t in threads:
                    if not t.is_alive() and not stop_event.is_set():
                        self.stdout.write(self.style.WARNING(
                            f"  ⚠️  {t.name} to'xtadi — qayta ishga tushirilmoqda..."
                        ))
                        if t.name == "web-server":
                            t_new = threading.Thread(
                                target=self._run_web_server,
                                args=(port, options["noreload"], stop_event),
                                daemon=True,
                                name="web-server",
                            )
                            t_new.start()
                            threads = [t_new if x is t else x for x in threads]
                        elif t.name == "telegram-bot":
                            token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
                            if token:
                                t_new = threading.Thread(
                                    target=self._run_telegram_bot,
                                    args=(token, stop_event),
                                    daemon=True,
                                    name="telegram-bot",
                                )
                                t_new.start()
                                threads = [t_new if x is t else x for x in threads]
        except KeyboardInterrupt:
            stop_event.set()
            self.stdout.write(self.style.SUCCESS("\n✅ Hammasi to'xtatildi!"))

    def _run_web_server(self, port: int, noreload: bool, stop_event: threading.Event) -> None:
        """Web serverni alohida thread'da ishga tushirish."""
        try:
            # Django settings ni this thread uchun tayyorlash
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

            from django.core.management import execute_from_command_line

            args = ["manage.py", "runserver", f"0.0.0.0:{port}"]
            if noreload:
                args.append("--noreload")

            # runserver blocking call — to'xtash kerak
            execute_from_command_line(args)
        except SystemExit:
            pass
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ❌ Web server xatosi: {e}"))
            if not stop_event.is_set():
                time.sleep(2)
                self._run_web_server(port, noreload, stop_event)

    def _run_telegram_bot(self, token: str, stop_event: threading.Event) -> None:
        """Telegram bot'ni alohida thread'da ishga tushirish."""
        try:
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

            # Django setup — har bir thread uchun kerak
            import django
            django.setup()

            from telegram.ext import ApplicationBuilder
            from apps.notifications.bot.handlers import post_init, setup_handlers

            app = (
                ApplicationBuilder()
                .token(token)
                .post_init(post_init)
                .connect_timeout(30)
                .read_timeout(30)
                .build()
            )

            setup_handlers(app)

            # run_polling blocking call — stop_event ni tekshirib turish uchun
            # thread da ishlaydi, shuning uchun drop_pending_updates=False
            app.run_polling(
                drop_pending_updates=False,
                allowed_updates=["message", "callback_query", "inline_query"],
            )
        except SystemExit:
            pass
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ❌ Bot xatosi: {e}"))
            if not stop_event.is_set():
                time.sleep(3)
                self._run_telegram_bot(token, stop_event)
