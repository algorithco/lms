from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Profile, User
from apps.courses.models import Course, StudentGroup
from apps.organizations.models import CenterBranch, LearningCenter
from apps.tests.models import Test


class Command(BaseCommand):
    help = "Seed branches (kursxonalar), teachers, and groups for Biology, Chemistry, and Law."

    def handle(self, *args, **options):
        self.stdout.write("Seeding educational branches, teachers, and groups...")
        with transaction.atomic():
            # 1. Main Center
            owner, _ = User.objects.get_or_create(
                email="admin@grandec.uz",
                defaults={
                    "first_name": "Komiljon",
                    "last_name": "Roziyev",
                    "role": "admin",
                    "is_staff": True,
                    "is_superuser": True,
                },
            )
            center, _ = LearningCenter.objects.get_or_create(
                slug="grand-education",
                defaults={
                    "name": "Grand Education Birlashgan O'quv Markazi",
                    "owner": owner,
                    "student_seat_limit": 1000,
                },
            )

            # 2. Branches
            b_sam, _ = CenterBranch.objects.get_or_create(
                branch_code="SAM-01",
                defaults={
                    "center": center,
                    "name": "Grand Education — Samarqand Markaziy Filiali",
                    "region": "Samarqand viloyati",
                    "address": "Registon ko'chasi, 14-uy",
                    "phone": "+998 66 233 44 55",
                    "telegram_channel": "@grandec_samarkand",
                    "subjects_offered": ["biology", "chemistry", "law", "uzbek", "english"],
                    "max_teachers_limit": 25,
                    "max_students_limit": 600,
                    "is_active": True,
                },
            )

            b_tas, _ = CenterBranch.objects.get_or_create(
                branch_code="TAS-01",
                defaults={
                    "center": center,
                    "name": "Grand Education — Toshkent Chilonzor Filiali",
                    "region": "Toshkent shahri",
                    "address": "Chilonzor 9-mavze, Qatortol 21-bino",
                    "phone": "+998 71 200 11 22",
                    "telegram_channel": "@grandec_toshkent",
                    "subjects_offered": ["biology", "chemistry", "law", "uzbek", "english"],
                    "max_teachers_limit": 30,
                    "max_students_limit": 800,
                    "is_active": True,
                },
            )

            b_bux, _ = CenterBranch.objects.get_or_create(
                branch_code="BUX-01",
                defaults={
                    "center": center,
                    "name": "Registon Kursxonasi — Buxoro Filiali",
                    "region": "Buxoro viloyati",
                    "address": "B. Naqshbandiy shohko'chasi, 8-uy",
                    "phone": "+998 65 220 33 44",
                    "telegram_channel": "@registon_buxoro",
                    "subjects_offered": ["biology", "chemistry", "law"],
                    "max_teachers_limit": 15,
                    "max_students_limit": 350,
                    "is_active": True,
                },
            )

            # 3. Teachers
            teachers_spec = [
                {
                    "email": "ustoz_biologiya@grandec.uz",
                    "name": "Zafar Qodirov",
                    "subject": "biology",
                    "branch": b_sam,
                    "phone": "+998 90 111 22 33",
                },
                {
                    "email": "ustoz_kimyo@grandec.uz",
                    "name": "Dilshod Rahimov",
                    "subject": "chemistry",
                    "branch": b_tas,
                    "phone": "+998 90 222 33 44",
                },
                {
                    "email": "ustoz_huquq@grandec.uz",
                    "name": "Shahnoza Umarova",
                    "subject": "law",
                    "branch": b_bux,
                    "phone": "+998 90 333 44 55",
                },
            ]

            created_teachers = {}
            for spec in teachers_spec:
                t_user = User.objects.filter(email=spec["email"]).first()
                parts = spec["name"].split()
                first = parts[0]
                last = " ".join(parts[1:])
                if not t_user:
                    t_user = User.objects.create_user(
                        email=spec["email"],
                        password="GrandTeacher2026!",
                        first_name=first,
                        last_name=last,
                        role="teacher",
                        branch=spec["branch"],
                        learning_center=center,
                        can_create_test=True,
                        can_create_essay_topic=True,
                        is_active=True,
                    )
                else:
                    t_user.role = "teacher"
                    t_user.branch = spec["branch"]
                    t_user.learning_center = center
                    t_user.can_create_test = True
                    t_user.save()

                prof, _ = Profile.objects.get_or_create(user=t_user)
                prof.active_subject = spec["subject"]
                prof.phone = spec["phone"]
                prof.save()
                created_teachers[spec["subject"]] = t_user

            # 4. Courses & Groups
            groups_spec = [
                {
                    "subject": "biology",
                    "name": "Biologiya BMB Milliy Sertifikat 104-Guruh",
                    "code": "BIO-104",
                    "branch": b_sam,
                    "teacher": created_teachers["biology"],
                    "test_code": "#MOCK-BIO-01",
                },
                {
                    "subject": "chemistry",
                    "name": "Kimyo DTM va Masalalar 205-Guruh",
                    "code": "KIM-205",
                    "branch": b_tas,
                    "teacher": created_teachers["chemistry"],
                    "test_code": "#MOCK-CHEM-01",
                },
                {
                    "subject": "law",
                    "name": "Huquqshunoslik Kazus & Konstitutsiya 301-Guruh",
                    "code": "HUQ-301",
                    "branch": b_bux,
                    "teacher": created_teachers["law"],
                    "test_code": "#MOCK-LAW-01",
                },
            ]

            for g_spec in groups_spec:
                course, _ = Course.objects.get_or_create(
                    slug=f"{g_spec['subject']}-group-course",
                    defaults={
                        "title": f"{g_spec['subject'].capitalize()} Kursi",
                        "teacher": g_spec["teacher"],
                        "subject": g_spec["subject"],
                    },
                )
                group, _ = StudentGroup.objects.get_or_create(
                    invite_code=g_spec["code"],
                    defaults={
                        "teacher": g_spec["teacher"],
                        "branch": g_spec["branch"],
                        "name": g_spec["name"],
                        "subject": g_spec["subject"],
                        "description": f"{g_spec['branch'].name} qoshidagi rasmiy guruh.",
                    },
                )
                if not group.branch:
                    group.branch = g_spec["branch"]
                    group.save(update_fields=["branch"])

                # Link mock test if exists
                mock_test = Test.objects.filter(mock_code=g_spec["test_code"]).first()
                if mock_test and not mock_test.assigned_group:
                    mock_test.assigned_group = group
                    mock_test.save(update_fields=["assigned_group"])

        self.stdout.write(self.style.SUCCESS("Branches, teachers, and groups seeded successfully!"))
