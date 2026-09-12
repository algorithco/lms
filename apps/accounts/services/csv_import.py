"""
CSV Import Service — Talabalarni CSV fayldan to'plamda qo'shish.

Supports:
    - CSV with columns: email, first_name, last_name, phone (optional)
    - Duplicate detection (skip existing emails)
    - Password generation for new students
    - Welcome email sending
    - Import summary with success/error counts
"""
from __future__ import annotations

import csv
import io
import logging
import secrets
from typing import Any

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)
User = get_user_model()


class CSVImportService:
    """
    CSV fayldan talabalarni import qilish xizmati.

    CSV format:
        email,first_name,last_name,phone
        student1@example.com,Ali,Valiyev,+998901234567
        student2@example.com,Vali,Hasanov,+998907654321
    """

    REQUIRED_COLUMNS = {"email", "first_name", "last_name"}
    OPTIONAL_COLUMNS = {"phone"}
    VALID_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS

    @classmethod
    def import_students(
        cls,
        csv_content: str | bytes,
        created_by: Any = None,
        send_welcome: bool = True,
    ) -> dict[str, Any]:
        """
        CSV dan talabalarni import qilish.

        Args:
            csv_content: CSV faylning matn/kontenti.
            created_by: Kim tomonidan yaratilgan (teacher/admin).
            send_welcome: Welcome email yuborilsinmi?

        Returns:
            {
                "total": int,
                "created": int,
                "skipped": int,
                "errors": list[dict],
                "created_users": list[User],
            }
        """
        if isinstance(csv_content, bytes):
            csv_content = csv_content.decode("utf-8-sig")

        reader = csv.DictReader(io.StringIO(csv_content))

        # Validate columns
        if not reader.fieldnames:
            return {"total": 0, "created": 0, "skipped": 0, "errors": [{"row": 0, "error": "CSV fayl bo'sh"}], "created_users": []}

        missing = cls.REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            return {
                "total": 0,
                "created": 0,
                "skipped": 0,
                "errors": [{"row": 0, "error": f"Kerakli ustunlar yo'q: {', '.join(missing)}"}],
                "created_users": [],
            }

        created = 0
        skipped = 0
        errors = []
        created_users = []

        for i, row in enumerate(reader, start=2):  # start=2 because row 1 is header
            try:
                email = row.get("email", "").strip().lower()
                first_name = row.get("first_name", "").strip()
                last_name = row.get("last_name", "").strip()
                phone = row.get("phone", "").strip()

                # Validate required fields
                if not email:
                    errors.append({"row": i, "error": "Email bo'sh"})
                    continue
                if not first_name:
                    errors.append({"row": i, "error": "Ism bo'sh"})
                    continue
                if not last_name:
                    errors.append({"row": i, "error": "Familiya bo'sh"})
                    continue

                # Check duplicate
                if User.objects.filter(email=email).exists():
                    skipped += 1
                    continue

                # Generate password
                password = secrets.token_urlsafe(12)

                # Create user
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    role="student",
                )

                # Update phone in profile if provided
                if phone:
                    from apps.accounts.models import Profile
                    profile, _ = Profile.objects.get_or_create(user=user)
                    profile.phone = phone
                    profile.save(update_fields=["phone"])

                created += 1
                created_users.append(user)

                # Send welcome email
                if send_welcome:
                    try:
                        cls._send_welcome_email(user, password)
                    except Exception as e:
                        logger.warning("Welcome email failed for %s: %s", email, e)

            except Exception as e:
                errors.append({"row": i, "error": str(e)})

        logger.info(
            "CSV import completed: total=%d, created=%d, skipped=%d, errors=%d",
            created + skipped, created, skipped, len(errors),
        )

        return {
            "total": created + skipped + len(errors),
            "created": created,
            "skipped": skipped,
            "errors": errors,
            "created_users": created_users,
        }

    @classmethod
    def _send_welcome_email(cls, user: Any, password: str) -> None:
        """Welcome email yuborish — parol bilan birga."""
        subject = "Ona Tili & Adabiyot platformasiga xush kelibsiz!"
        context = {
            "user": user,
            "password": password,
            "site_url": "http://localhost:8000",
        }
        html_message = render_to_string("emails/welcome_with_password.html", context)
        plain_message = strip_tags(html_message)

        send_mail(
            subject=subject,
            message=plain_message,
            from_email="Ona Tili & Adabiyot <noreply@lms-platform.uz>",
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )

    @classmethod
    def validate_csv(cls, csv_content: str | bytes) -> dict[str, Any]:
        """
        CSV faylni tekshirish (import qilmasdan).

        Returns:
            {"valid": bool, "errors": list, "row_count": int, "columns": list}
        """
        if isinstance(csv_content, bytes):
            csv_content = csv_content.decode("utf-8-sig")

        reader = csv.DictReader(io.StringIO(csv_content))

        if not reader.fieldnames:
            return {"valid": False, "errors": ["CSV fayl bo'sh"], "row_count": 0, "columns": []}

        missing = cls.REQUIRED_COLUMNS - set(reader.fieldnames)
        if missing:
            return {
                "valid": False,
                "errors": [f"Kerakli ustunlar yo'q: {', '.join(missing)}"],
                "row_count": 0,
                "columns": list(reader.fieldnames),
            }

        rows = list(reader)
        errors = []
        for i, row in enumerate(rows, start=2):
            if not row.get("email", "").strip():
                errors.append(f"{i}-qator: Email bo'sh")
            if not row.get("first_name", "").strip():
                errors.append(f"{i}-qator: Ism bo'sh")
            if not row.get("last_name", "").strip():
                errors.append(f"{i}-qator: Familiya bo'sh")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "row_count": len(rows),
            "columns": list(reader.fieldnames),
        }
