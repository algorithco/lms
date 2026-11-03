"""Seed QA accounts into a LOCAL development database. Never runs in production.

    python manage.py seed_qa_accounts [--out PATH] [--tokens]

Creates (idempotently): a platform admin, a teacher, a FREE student, a paid
(PRO) student and one teacher group holding both students. Passwords are
random, never printed: they are written to ``--out`` (default
``.qa_accounts.local.json``, git-ignored) together with the user ids and, with
``--tokens``, ready-to-use JWTs for driving the browser without typing a
password. The PRO student's plan is granted through the audited
``grant_subscription`` gate (kind="admin"), exactly like a real admin grant.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

User = get_user_model()

ACCOUNTS = {
    "admin": {"email": "qa_admin@example.test", "first_name": "QA", "last_name": "Admin", "role": "admin"},
    "teacher": {"email": "qa_teacher@example.test", "first_name": "QA", "last_name": "Teacher", "role": "teacher"},
    "free": {"email": "qa_free@example.test", "first_name": "QA", "last_name": "Free", "role": "student"},
    "paid": {"email": "qa_paid@example.test", "first_name": "QA", "last_name": "Paid", "role": "student"},
}


def _is_local_dev() -> bool:
    engine = settings.DATABASES["default"].get("ENGINE", "")
    return bool(settings.DEBUG or engine.endswith("sqlite3"))


class Command(BaseCommand):
    help = "Seed QA admin/teacher/FREE/paid accounts into a local dev database (refuses elsewhere)."

    def add_arguments(self, parser):
        parser.add_argument("--out", default=".qa_accounts.local.json", help="Where credentials are written.")
        parser.add_argument("--tokens", action="store_true", help="Also write JWT access/refresh per account.")

    @transaction.atomic
    def handle(self, *args, **opts):
        if not _is_local_dev():
            raise CommandError("seed_qa_accounts only runs against a local development database.")

        from apps.accounts.models import Profile, TeacherProfile
        from apps.courses.models import StudentGroup
        from apps.payments.models import SubscriptionPlan, UserSubscription
        from apps.payments.subscriptions import grant_subscription

        creds: dict[str, dict] = {}
        users = {}
        for key, spec in ACCOUNTS.items():
            password = secrets.token_urlsafe(18)
            user, _created = User.objects.get_or_create(
                email=spec["email"],
                defaults={"first_name": spec["first_name"], "last_name": spec["last_name"], "role": spec["role"]},
            )
            user.role = spec["role"]
            user.is_active = True
            user.is_superuser = key == "admin"
            user.is_staff = key == "admin"
            if key == "teacher":
                user.can_create_test = True
                user.can_create_essay_topic = True
            user.set_password(password)
            user.save()
            Profile.objects.get_or_create(user=user)
            if key == "teacher":
                TeacherProfile.objects.get_or_create(teacher=user)
            users[key] = user
            creds[key] = {"id": user.id, "email": spec["email"], "password": password}

        group, _ = StudentGroup.objects.get_or_create(teacher=users["teacher"], name="QA group")
        group.students.add(users["free"], users["paid"])

        pro, _ = SubscriptionPlan.objects.get_or_create(
            plan_type=SubscriptionPlan.PlanType.PRO,
            defaults={"name": "Pro", "price_monthly": 15000, "test_limit": 30},
        )
        if not UserSubscription.objects.filter(user=users["paid"], status="active").exists():
            grant_subscription(
                users["paid"], pro, kind="admin", actor=users["admin"], days=30,
                source=UserSubscription.Source.ADMIN, payment_method="admin_grant",
                reason="QA seed: paid student fixture",
            )

        if opts["tokens"]:
            from rest_framework_simplejwt.tokens import RefreshToken

            for key, user in users.items():
                refresh = RefreshToken.for_user(user)
                creds[key]["access"] = str(refresh.access_token)
                creds[key]["refresh"] = str(refresh)

        out = Path(opts["out"])
        out.write_text(json.dumps(creds, indent=2), encoding="utf-8")
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(creds)} QA accounts (ids: "
                + ", ".join(f"{k}={v['id']}" for k, v in creds.items())
                + f"). Credentials written to {out} (not printed)."
            )
        )
