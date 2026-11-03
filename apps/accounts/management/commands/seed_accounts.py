"""
Django Management Command: seed_accounts
Provisions a root admin and a verified teacher (with a sample group) for local RBAC testing.

SAFETY
- Refuses to run unless DEBUG is on, the database is SQLite, or --allow-production is given.
- No password is stored in code. Each comes from SEED_ADMIN_PASSWORD / SEED_TEACHER_PASSWORD, or is
  generated randomly and shown once on this console.
- An existing account keeps its password unless --reset-passwords is given.
"""

import os
import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.accounts.models import Profile, TeacherProfile
from apps.courses.models import StudentGroup

User = get_user_model()


class Command(BaseCommand):
    help = "Seed 1 Admin and 1 Verified Teacher account for RBAC testing (local databases only)."

    def add_arguments(self, parser):
        parser.add_argument("--allow-production", action="store_true", help="Run against a non-local database.")
        parser.add_argument("--reset-passwords", action="store_true", help="Also reset the password of existing accounts.")

    @staticmethod
    def _password(env_name: str) -> tuple[str, bool]:
        """(password, generated): from the environment, else random."""
        value = os.environ.get(env_name, "")
        return (value, False) if value else (secrets.token_urlsafe(16), True)

    @transaction.atomic
    def handle(self, *args, **options):
        engine = settings.DATABASES["default"].get("ENGINE", "")
        if not (settings.DEBUG or engine.endswith("sqlite3") or options["allow_production"]):
            raise CommandError(
                "seed_accounts creates privileged accounts and only runs on a local database "
                "(DEBUG or SQLite). Pass --allow-production only if you really mean it."
            )
        reset = options["reset_passwords"]
        self.stdout.write(self.style.NOTICE("=== SEEDING RBAC ACCOUNTS ==="))

        # ---------------------------------------------------------------------
        # 1. BOSH ADMINISTRATOR (Root Admin)
        # ---------------------------------------------------------------------
        admin_email = "admin.grandec@gmail.com"
        admin_password, admin_generated = self._password("SEED_ADMIN_PASSWORD")

        admin_user, admin_created = User.objects.get_or_create(
            email=admin_email,
            defaults={
                "first_name": "Grandec",
                "last_name": "Superadmin",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
                "can_create_test": True,
                "can_create_essay_topic": True,
            },
        )

        admin_user.first_name = "Grandec"
        admin_user.last_name = "Superadmin"
        admin_user.role = User.Role.ADMIN
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.is_active = True
        admin_user.can_create_test = True
        admin_user.can_create_essay_topic = True
        set_admin_password = admin_created or reset
        if set_admin_password:
            admin_user.set_password(admin_password)
        admin_user.save()

        # Profile for Admin
        admin_profile, _ = Profile.objects.get_or_create(user=admin_user)
        admin_profile.phone = "+998901234567"
        admin_profile.bio = "Grand Education LMS Bosh Tizim Administratori (Root Access)"
        admin_profile.active_subject = "uzbek"
        admin_profile.onboarding_completed = True
        admin_profile.plan = "ADMIN_UNLIMITED"
        admin_profile.save()

        # TeacherProfile for Admin (enables quota management)
        admin_tp, _ = TeacherProfile.objects.get_or_create(teacher=admin_user)
        admin_tp.pro_quota_balance = 9999
        admin_tp.premium_quota_balance = 9999
        admin_tp.save()

        status_admin = "yaratildi" if admin_created else "yangilandi"
        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] [ADMIN] {admin_user.email} muvaffaqiyatli {status_admin}!\n"
                f"   Rol: {admin_user.role} | is_staff: {admin_user.is_staff} | is_superuser: {admin_user.is_superuser}"
            )
        )
        if set_admin_password and admin_generated:
            self.stdout.write(self.style.WARNING(f"   Admin password (shown once, not stored): {admin_password}"))
        elif not set_admin_password:
            self.stdout.write("   Existing account: password left unchanged.")

        # ---------------------------------------------------------------------
        # 2. TASDIQLANGAN USTOZ (Verified Teacher)
        # ---------------------------------------------------------------------
        teacher_email = "ustoz.grandec@gmail.com"
        teacher_password, teacher_generated = self._password("SEED_TEACHER_PASSWORD")

        teacher_user, teacher_created = User.objects.get_or_create(
            email=teacher_email,
            defaults={
                "first_name": "Hamid",
                "last_name": "Olimjon",
                "role": User.Role.TEACHER,
                "is_staff": False,
                "is_superuser": False,
                "is_active": True,
                "can_create_test": True,
                "can_create_essay_topic": True,
            },
        )

        teacher_user.first_name = "Hamid"
        teacher_user.last_name = "Olimjon"
        teacher_user.role = User.Role.TEACHER
        teacher_user.is_staff = False
        teacher_user.is_superuser = False
        teacher_user.is_active = True
        teacher_user.can_create_test = True
        teacher_user.can_create_essay_topic = True
        set_teacher_password = teacher_created or reset
        if set_teacher_password:
            teacher_user.set_password(teacher_password)
        teacher_user.save()

        # Profile for Teacher
        teacher_profile, _ = Profile.objects.get_or_create(user=teacher_user)
        teacher_profile.phone = "+998907654321"
        teacher_profile.bio = "Ona tili va adabiyot fani oliy toifali ustozi, BMB eksperti"
        teacher_profile.active_subject = "uzbek"
        teacher_profile.onboarding_completed = True
        teacher_profile.plan = "PRO"
        teacher_profile.save()

        # TeacherProfile with quota balances
        teacher_tp, _ = TeacherProfile.objects.get_or_create(teacher=teacher_user)
        teacher_tp.pro_quota_balance = max(teacher_tp.pro_quota_balance, 50)
        teacher_tp.premium_quota_balance = max(teacher_tp.premium_quota_balance, 10)
        teacher_tp.save()

        # ---------------------------------------------------------------------
        # 3. NAMUNAVIY FAOL SINF / GURUH (11-A Ona tili guruhi)
        # ---------------------------------------------------------------------
        sample_group_code = "GR-11A"
        sample_group, group_created = StudentGroup.objects.get_or_create(
            invite_code=sample_group_code,
            defaults={
                "teacher": teacher_user,
                "name": "11-A Ona tili guruhi",
                "description": "11-sinf o'quvchilari uchun Ona tili va Milliy sertifikatga tayyorgarlik sinfi",
                "subject": "uzbek",
                "invite_token": secrets.token_hex(32),
                "monthly_fee": 450000,
            },
        )

        sample_group.teacher = teacher_user
        sample_group.name = "11-A Ona tili guruhi"
        sample_group.description = "11-sinf o'quvchilari uchun Ona tili va Milliy sertifikatga tayyorgarlik sinfi"
        sample_group.subject = "uzbek"
        if not sample_group.invite_token:
            sample_group.invite_token = secrets.token_hex(32)
        sample_group.monthly_fee = 450000
        sample_group.save()

        status_teacher = "yaratildi" if teacher_created else "yangilandi"
        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] [USTOZ] {teacher_user.email} muvaffaqiyatli {status_teacher}!\n"
                f"   Rol: {teacher_user.role} | F.I.Sh: {teacher_user.get_full_name()}\n"
                f"   Biriktirilgan guruh: {sample_group.name} (Kod: {sample_group.invite_code}, Token: {sample_group.invite_token[:12]}...)"
            )
        )

        if set_teacher_password and teacher_generated:
            self.stdout.write(self.style.WARNING(f"   Teacher password (shown once, not stored): {teacher_password}"))
        elif not set_teacher_password:
            self.stdout.write("   Existing account: password left unchanged.")

        self.stdout.write(self.style.SUCCESS("\n[DONE] Barcha akkauntlar muvaffaqiyatli tayyorlandi!"))
