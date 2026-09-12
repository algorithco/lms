"""
Management command: send_push

Send web push notifications to subscribed users.

Usage:
    python manage.py send_push --user 1 --title "Test natijasi" --body "Sizning test natijangiz tayyor!"
    python manage.py send_push --all --title "Yangiliklar" --body "Platformada yangi funksiyalar qo'shildi!"
"""
from __future__ import annotations

import json
import logging

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Web push notification yuborish"

    def add_arguments(self, parser):
        parser.add_argument("--user", type=int, help="Foydalanuvchi ID")
        parser.add_argument("--all", action="store_true", help="Barcha faol obunalarga yuborish")
        parser.add_argument("--title", type=str, required=True, help="Xabar sarlavhasi")
        parser.add_argument("--body", type=str, required=True, help="Xabar matni")
        parser.add_argument("--url", type=str, default="/dashboard/", help="Bosilganda ochiladigan sahifa")
        parser.add_argument("--tag", type=str, default="lms-notification", help="Notification tag")

    def handle(self, *args, **options):
        from apps.notifications.models import PushSubscription

        title = options["title"]
        body = options["body"]
        url = options["url"]
        tag = options["tag"]

        if options["user"]:
            subscriptions = PushSubscription.objects.filter(
                user_id=options["user"], is_active=True,
            )
        elif options["all"]:
            subscriptions = PushSubscription.objects.filter(is_active=True)
        else:
            self.stdout.write(self.style.ERROR("--user yoki --all kerak!"))
            return

        if not subscriptions.exists():
            self.stdout.write(self.style.WARNING("Faol push obunalar topilmadi."))
            return

        self.stdout.write(f"{subscriptions.count()} ta obunaga xabar yuborilmoqda...")

        sent = 0
        failed = 0

        for sub in subscriptions:
            success = self._send_push(sub, title, body, url, tag)
            if success:
                sent += 1
            else:
                failed += 1
                # Deactivate broken subscriptions
                sub.is_active = False
                sub.save(update_fields=["is_active"])

        self.stdout.write(self.style.SUCCESS(
            f"Yuborildi: {sent}, Xatolik: {failed}"
        ))

    def _send_push(self, subscription, title, body, url, tag) -> bool:
        """Send push notification to a single subscription."""
        import pywebpush

        vapid_private_key = getattr(settings, "VAPID_PRIVATE_KEY", "")
        vapid_claims = {"sub": getattr(settings, "VAPID_CLAIM_EMAIL", "mailto:admin@lms-platform.uz")}

        if not vapid_private_key:
            self.stdout.write(self.style.ERROR("VAPID_PRIVATE_KEY sozlanmagan!"))
            return False

        payload = json.dumps({
            "title": title,
            "body": body,
            "data": {"url": url},
            "tag": tag,
        })

        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh,
                "auth": subscription.auth,
            },
        }

        try:
            pywebpush.webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=vapid_private_key,
                vapid_claims=vapid_claims,
            )
            subscription.last_used_at = __import__("django.utils.timezone", fromlist=["now"]).now()
            subscription.save(update_fields=["last_used_at"])
            return True
        except Exception as e:
            logger.error("Push failed: user=%d, error=%s", subscription.user_id, e)
            return False
