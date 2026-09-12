"""Explicitly verify a retained legacy Telegram identity after checking proof."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.services.telegram_identity import _numeric_telegram_id


class Command(BaseCommand):
    help = (
        "List unverified legacy Telegram links, or verify one existing mapping "
        "after the operator has independently checked ownership."
    )

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int)
        parser.add_argument("--telegram-id", type=int)
        parser.add_argument("--evidence", help="Operator's auditable proof reference")
        parser.add_argument("--list", action="store_true", help="List legacy links requiring verification")

    def handle(self, *args, **options):
        User = get_user_model()
        if options["user_id"] is None and options["telegram_id"] is None and not options["evidence"]:
            pending = User.objects.filter(
                telegram_chat_id__isnull=False,
                telegram_identity_verified_at__isnull=True,
            )
            self.stdout.write(f"Unverified legacy Telegram links: {pending.count()}")
            if options["list"]:
                for user in pending.only("id", "email", "telegram_chat_id").iterator():
                    self.stdout.write(
                        f"user_id={user.pk} email={user.email} telegram_id={user.telegram_chat_id}"
                    )
            return
        if options["list"]:
            raise CommandError("--list cannot be combined with verification options.")
        if not all((options["user_id"], options["telegram_id"], options["evidence"])):
            raise CommandError("--user-id, --telegram-id and --evidence are required together.")
        try:
            telegram_id = _numeric_telegram_id(options["telegram_id"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        with transaction.atomic():
            user = User.objects.select_for_update().filter(pk=options["user_id"]).first()
            if user is None or user.telegram_chat_id != telegram_id:
                raise CommandError("The supplied user and existing Telegram ID do not match.")
            if user.telegram_identity_verified_at:
                raise CommandError("This Telegram link is already verified.")
            user.telegram_identity_verified_at = timezone.now()
            user.save(update_fields=["telegram_identity_verified_at"])
        self.stdout.write(
            f"Verified legacy mapping for user {user.pk}, Telegram ID {telegram_id}. "
            f"Evidence reference: {options['evidence']}"
        )
