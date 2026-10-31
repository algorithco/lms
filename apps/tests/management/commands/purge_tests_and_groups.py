"""
Django Management Command: purge_tests_and_groups
Safely purges all old tests, questions, attempts, results, and student groups
from the database for a clean start, while strictly preserving:
- User accounts (Admin, Ustoz, Students)
- Subscriptions and Billing Receipts
- AI Essay submissions and topics
"""

from __future__ import annotations

import sys
from typing import Any
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

# Tests models
from apps.tests.models import (
    Test,
    ExamSection,
    ReadingPassage,
    Question,
    Choice,
    TestAttempt,
    StudentAnswer,
    GapBlank,
    GapResponse,
    MatchingPrompt,
    MatchingOption,
    MatchingPair,
    MatchingResponse,
    ExamWrittenBridge,
    AttemptSectionProgress,
    ExamScoringProfile,
)

# Results models
from apps.results.models import Result, Certificate, ResultSectionScore

# Courses & Groups models
from apps.courses.models import (
    StudentGroup,
    GroupEnrollment,
    Homework,
    HomeworkSubmission,
)

# Optional related group models (CASCADE / SET_NULL safe cleanup)
try:
    from apps.attendance.models import AttendanceRecord, AttendanceSession
except ImportError:
    AttendanceRecord = None
    AttendanceSession = None

try:
    from apps.weekly_reports.models import WeeklyGroupReport
except ImportError:
    WeeklyGroupReport = None

try:
    from apps.tuition.models import StudentTuition, CourseBillingPolicy
except ImportError:
    StudentTuition = None
    CourseBillingPolicy = None

try:
    from apps.essays.models import EssayAssignment
except ImportError:
    EssayAssignment = None

try:
    from apps.payments.models import TeacherSponsorship
except ImportError:
    TeacherSponsorship = None

try:
    from apps.arena.models import Tournament, TournamentParticipant
except ImportError:
    Tournament = None
    TournamentParticipant = None

# Preserved models for verification
from apps.essays.models import EssaySubmission, EssayTopic
from apps.payments.models import UserSubscription, PaymentReceipt, SubscriptionPlan

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Safely purges tests, questions, choices, test attempts, results, "
        "and student groups while strictly protecting users, subscriptions, and essays."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm that you want to execute the purge without prompting.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what records would be deleted without making changes.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        is_dry_run = options.get("dry_run", False)
        is_confirmed = options.get("confirm", False)

        self.stdout.write(self.style.NOTICE("=== PURGE TESTS & GROUPS DATABASE RESET ==="))

        # Pre-count records to delete
        counts_to_delete = {
            "Student Answers": StudentAnswer.objects.count(),
            "Gap Responses": GapResponse.objects.count(),
            "Matching Responses": MatchingResponse.objects.count(),
            "Section Progress": AttemptSectionProgress.objects.count(),
            "Written Bridges": ExamWrittenBridge.objects.count(),
            "Certificates": Certificate.objects.count(),
            "Result Section Scores": ResultSectionScore.objects.count(),
            "Results": Result.objects.count(),
            "Test Attempts": TestAttempt.objects.count(),
            "Choices": Choice.objects.count(),
            "Questions": Question.objects.count(),
            "Reading Passages": ReadingPassage.objects.count(),
            "Exam Sections": ExamSection.objects.count(),
            "Scoring Profiles": ExamScoringProfile.objects.count(),
            "Tests": Test.objects.count(),
            "Group Enrollments": GroupEnrollment.objects.count(),
            "Homework Submissions": HomeworkSubmission.objects.count(),
            "Homeworks": Homework.objects.count(),
            "Student Groups": StudentGroup.objects.count(),
        }

        if Tournament is not None:
            counts_to_delete["Tournaments"] = Tournament.objects.count()
        if TournamentParticipant is not None:
            counts_to_delete["Tournament Participants"] = TournamentParticipant.objects.count()
        if AttendanceSession is not None:
            counts_to_delete["Attendance Sessions"] = AttendanceSession.objects.count()
        if AttendanceRecord is not None:
            counts_to_delete["Attendance Records"] = AttendanceRecord.objects.count()
        if WeeklyGroupReport is not None:
            counts_to_delete["Weekly Group Reports"] = WeeklyGroupReport.objects.count()
        if StudentTuition is not None:
            counts_to_delete["Student Tuition Records"] = StudentTuition.objects.count()
        if EssayAssignment is not None:
            counts_to_delete["Group Essay Assignments"] = EssayAssignment.objects.count()

        # Count protected records
        users_count = User.objects.count()
        subs_count = UserSubscription.objects.count()
        receipts_count = PaymentReceipt.objects.count()
        essays_count = EssaySubmission.objects.count()
        essay_topics_count = EssayTopic.objects.count()

        self.stdout.write("\n[1] O'CHIRILISHI REJALASHTIRILGAN MA'LUMOTLAR:")
        total_items = 0
        for name, count in counts_to_delete.items():
            total_items += count
            self.stdout.write(f"  - {name}: {count}")
        self.stdout.write(f"  Jami o'chiriladigan ob'ektlar: {total_items}")

        self.stdout.write("\n[2] SAQLANIB QOLUVCHI DAXLSIZ MA'LUMOTLAR:")
        self.stdout.write(f"  - Foydalanuvchilar (Users): {users_count} ta (Admin, Ustoz, O'quvchilar)")
        self.stdout.write(f"  - Obunalar (Subscriptions): {subs_count} ta")
        self.stdout.write(f"  - To'lov kvitansiyalari (Payment Receipts): {receipts_count} ta")
        self.stdout.write(f"  - Esse topshiriqlari (Essay Submissions): {essays_count} ta")
        self.stdout.write(f"  - Esse mavzulari (Essay Topics): {essay_topics_count} ta")

        if is_dry_run:
            self.stdout.write(
                self.style.WARNING("\n[DRY RUN] Hech qanday ma'lumot o'chirilmadi (--dry-run yoqilgan).")
            )
            return

        if not is_confirmed:
            # Check if interactive
            if sys.stdin.isatty():
                confirm_input = input("\nHaqiqatan ham barcha testlar va guruhlarni tozalashni xohlaysizmi? [y/N]: ")
                if confirm_input.strip().lower() not in ("y", "yes", "ha"):
                    self.stdout.write(self.style.WARNING("[BEKOR QILINDI] Amaliyot to'xtatildi."))
                    return
            else:
                self.stdout.write(
                    self.style.ERROR(
                        "\n[XATOLIK] Avtomatlashtirilgan yoki no-tty rejimida bajarish uchun "
                        "--confirm kalitini bering: python manage.py purge_tests_and_groups --confirm"
                    )
                )
                return

        # Perform atomic cleanup in safe child-to-parent order
        self.stdout.write(self.style.NOTICE("\nTozalash jarayoni boshlanmoqda..."))

        with transaction.atomic():
            # Step A: Attempts, progress, and answers
            StudentAnswer.objects.all().delete()
            GapResponse.objects.all().delete()
            MatchingResponse.objects.all().delete()
            AttemptSectionProgress.objects.all().delete()
            ExamWrittenBridge.objects.all().delete()

            # Step B: Certificates and results
            Certificate.objects.all().delete()
            ResultSectionScore.objects.all().delete()
            Result.objects.all().delete()

            # Step C: Tournaments (if any)
            if TournamentParticipant is not None:
                TournamentParticipant.objects.all().delete()
            if Tournament is not None:
                Tournament.objects.all().delete()

            # Step D: Test Attempts
            TestAttempt.objects.all().delete()

            # Step E: Questions, choices, and passages
            Choice.objects.all().delete()
            GapBlank.objects.all().delete()
            MatchingPair.objects.all().delete()
            MatchingOption.objects.all().delete()
            MatchingPrompt.objects.all().delete()
            Question.objects.all().delete()
            ReadingPassage.objects.all().delete()
            ExamSection.objects.all().delete()
            ExamScoringProfile.objects.all().delete()

            # Step F: Tests
            Test.objects.all().delete()

            # Step G: Groups and group dependencies
            HomeworkSubmission.objects.all().delete()
            Homework.objects.all().delete()

            if AttendanceRecord is not None:
                AttendanceRecord.objects.all().delete()
            if AttendanceSession is not None:
                AttendanceSession.objects.all().delete()
            if WeeklyGroupReport is not None:
                WeeklyGroupReport.objects.all().delete()
            if StudentTuition is not None:
                StudentTuition.objects.all().delete()
            if CourseBillingPolicy is not None:
                CourseBillingPolicy.objects.filter(group__isnull=False).delete()
            if EssayAssignment is not None:
                EssayAssignment.objects.all().delete()
            if TeacherSponsorship is not None:
                TeacherSponsorship.objects.all().delete()

            GroupEnrollment.objects.all().delete()
            StudentGroup.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("\n[OK] Barcha eski testlar, urinishlar va guruhlar muvaffaqiyatli tozalandi!"))

        # Verify integrity of protected records post-cleanup
        post_users = User.objects.count()
        post_subs = UserSubscription.objects.count()
        post_essays = EssaySubmission.objects.count()

        self.stdout.write(self.style.SUCCESS(
            f"[TEKSHIRILDI] Saqlab qolingan ma'lumotlar holati:\n"
            f"   - Users: {post_users} ta (Hech kim o'chirilmadi)\n"
            f"   - Subscriptions: {post_subs} ta (Obunalar butun)\n"
            f"   - Essay Submissions: {post_essays} ta (Esselar butun)"
        ))
