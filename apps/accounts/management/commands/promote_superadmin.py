"""
Django Management Command: promote_superadmin

Promotes or provisions a user to full Superadmin on the platform:
- is_superuser = True
- is_staff = True
- role = User.Role.ADMIN ('admin')
- telegram_chat_id = <telegram_id>
- telegram_identity_verified_at = now()
- profile.plan = 'pro'
"""

from __future__ import annotations

from typing import Any
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Profile

User = get_user_model()


class Command(BaseCommand):
    help = "Promote or provision a user to full Superadmin (is_superuser=True, is_staff=True, role='admin')."

    def add_arguments(self, parser):
        parser.add_argument(
            "--telegram-id",
            type=int,
            default=5582178765,
            help="Numeric Telegram Chat ID (default: 5582178765).",
        )
        parser.add_argument(
            "--email",
            type=str,
            default=None,
            help="Optional email address to associate with the superadmin account.",
        )
        parser.add_argument(
            "--name",
            type=str,
            default="Grand Admin",
            help="Full name or display name for the account.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        telegram_id: int = options["telegram_id"]
        email_arg: str | None = options.get("email")
        name_arg: str = options.get("name") or "Grand Admin"

        self.stdout.write(
            self.style.NOTICE(
                f"Promoting Telegram ID: {telegram_id} to full Superadmin..."
            )
        )

        user = User.objects.filter(telegram_chat_id=telegram_id).first()

        # If not found by telegram_chat_id, check by email if provided
        if not user and email_arg:
            user = User.objects.filter(email=email_arg).first()

        created = False
        if not user:
            # Create new user
            email = email_arg or f"admin_{telegram_id}@grandec.uz"
            first_name, *last_parts = name_arg.split(" ", 1)
            last_name = last_parts[0] if last_parts else ""

            user = User.objects.create(
                email=email,
                first_name=first_name,
                last_name=last_name,
                telegram_chat_id=telegram_id,
                telegram_identity_verified_at=timezone.now(),
                role=User.Role.ADMIN,
                is_superuser=True,
                is_staff=True,
                is_active=True,
            )
            user.set_unusable_password()
            user.save()
            created = True
        else:
            # Update existing user to full Superadmin
            user.is_superuser = True
            user.is_staff = True
            user.role = User.Role.ADMIN
            user.is_active = True
            if not user.telegram_chat_id:
                user.telegram_chat_id = telegram_id
            if not user.telegram_identity_verified_at:
                user.telegram_identity_verified_at = timezone.now()
            if email_arg and user.email != email_arg:
                user.email = email_arg
            user.save()

        # Ensure Profile exists and has pro access
        profile, _ = Profile.objects.get_or_create(user=user)
        if profile.plan != "pro":
            profile.plan = "pro"
            profile.save(update_fields=["plan"])

        action = "Created & promoted" if created else "Successfully promoted"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} Superadmin:\n"
                f"  - User ID: {user.pk}\n"
                f"  - Email: {user.email}\n"
                f"  - Role: {user.role}\n"
                f"  - is_superuser: {user.is_superuser}\n"
                f"  - is_staff: {user.is_staff}\n"
                f"  - telegram_chat_id: {user.telegram_chat_id}\n"
                f"  - Profile Plan: {profile.plan}"
            )
        )
