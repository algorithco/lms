"""
Regression tests for audit fixes (code audit round).

Covers:
    1. Teacher-only essay endpoints reject students (authorization)
    2. Telegram quiz result saving goes through the official attempt pipeline
       and never crashes (previously Result.objects.create was missing
       attempt/course and UserGameScore got an unknown `game_name` kwarg)
"""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.essays.models import EssaySubmission
from apps.results.models import Result

User = get_user_model()


class TeacherAuthorizationTests(TestCase):
    """Students must never reach the teacher essay endpoints."""

    def setUp(self) -> None:
        self.student = User.objects.create_user(
            email="student@test.com",
            password="testpass123",
            first_name="Student",
            last_name="One",
            role="student",
        )
        self.teacher = User.objects.create_user(
            email="teacher@test.com",
            password="testpass123",
            first_name="Teacher",
            last_name="One",
            role="teacher",
        )

    def test_student_blocked_from_teacher_queue(self) -> None:
        self.client.login(email="student@test.com", password="testpass123")
        response = self.client.get(reverse("essays:teacher-queue"))
        self.assertEqual(response.status_code, 403)

    def test_teacher_allowed_into_queue(self) -> None:
        self.client.login(email="teacher@test.com", password="testpass123")
        response = self.client.get("/api/v1/essays/teacher/queue/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("student_requested", response.json())
        self.assertIn("pending", response.json())
        self.assertIn("reviewed", response.json())

    def test_student_blocked_from_review_page(self) -> None:
        sub = EssaySubmission.objects.create(
            student=self.student,
            essay_text="Test essay",
            status=EssaySubmission.Status.PENDING_TEACHER,
        )
        self.client.login(email="student@test.com", password="testpass123")
        response = self.client.get(
            reverse("essays:teacher-review", kwargs={"submission_id": sub.id})
        )
        self.assertEqual(response.status_code, 403)

    def test_student_blocked_from_submitting_review(self) -> None:
        sub = EssaySubmission.objects.create(
            student=self.student,
            essay_text="Test essay",
            status=EssaySubmission.Status.PENDING_TEACHER,
        )
        self.client.login(email="student@test.com", password="testpass123")
        response = self.client.post(
            reverse("essays:teacher-submit-review", kwargs={"submission_id": sub.id}),
            {"score_1": "1.5"},
        )
        self.assertEqual(response.status_code, 403)


class TelegramQuizSaveTests(TestCase):
    """Telegram quiz results must be persisted via the official pipeline."""

    def setUp(self) -> None:
        from apps.courses.models import Category, Course
        from apps.tests.models import Choice, Question, Test

        self.student = User.objects.create_user(
            email="student@test.com",
            password="testpass123",
            first_name="Student",
            last_name="One",
            role="student",
        )
        category = Category.objects.create(name="Onа tili", slug="ona-tili")
        self.course = Course.objects.create(
            title="Ona tili",
            slug="ona-tili",
            description="Test course",
            teacher=self.student,
            category=category,
        )
        self.test = Test.objects.create(
            title="Ona tili Test",
            course=self.course,
            description="Test",
            time_limit_minutes=30,
            pass_percentage=60,
            max_attempts=5,
            is_active=True,
        )
        self.q1 = Question.objects.create(
            test=self.test,
            text="Savol 1?",
            question_type="single",
            points=Decimal("10"),
            position=1,
        )
        self.q1_correct = Choice.objects.create(
            question=self.q1,
            text="To'g'ri",
            is_correct=True,
            position=1,
        )
        Choice.objects.create(
            question=self.q1,
            text="Noto'g'ri",
            is_correct=False,
            position=2,
        )
        self.q2 = Question.objects.create(
            test=self.test,
            text="Savol 2?",
            question_type="multiple",
            points=Decimal("10"),
            position=2,
        )
        self.q2_c1 = Choice.objects.create(
            question=self.q2,
            text="A to'g'ri",
            is_correct=True,
            position=1,
        )
        self.q2_c2 = Choice.objects.create(
            question=self.q2,
            text="B to'g'ri",
            is_correct=True,
            position=2,
        )
        Choice.objects.create(
            question=self.q2,
            text="C xato",
            is_correct=False,
            position=3,
        )
        self.q3 = Question.objects.create(
            test=self.test,
            text="Savol 3?",
            question_type="single",
            points=Decimal("10"),
            position=3,
        )
        self.q3_correct = Choice.objects.create(
            question=self.q3,
            text="To'g'ri",
            is_correct=True,
            position=1,
        )
        Choice.objects.create(
            question=self.q3,
            text="Noto'g'ri",
            is_correct=False,
            position=2,
        )

    def _quiz_state(self) -> dict:
        """Recreate the in-memory quiz dict the bot builds."""
        from apps.tests.models import Choice

        def _choices(question) -> list:
            return [
                {"id": c.id, "text": c.text, "is_correct": c.is_correct}
                for c in Choice.objects.filter(question=question).order_by("position")
            ]

        q1_choices = _choices(self.q1)
        q2_choices = _choices(self.q2)
        q3_choices = _choices(self.q3)

        correct_q1 = next(i for i, c in enumerate(q1_choices) if c["is_correct"])
        correct_q3 = next(i for i, c in enumerate(q3_choices) if c["is_correct"])
        # Multi-choice: only ONE of two correct choices selected → official grade = wrong
        partial_q2 = next(i for i, c in enumerate(q2_choices) if c["is_correct"])

        return {
            "test_id": self.test.id,
            "test_title": self.test.title,
            "questions": [
                {
                    "id": self.q1.id,
                    "text": self.q1.text,
                    "points": "10",
                    "choices": q1_choices,
                },
                {
                    "id": self.q2.id,
                    "text": self.q2.text,
                    "points": "10",
                    "choices": q2_choices,
                },
                {
                    "id": self.q3.id,
                    "text": self.q3.text,
                    "points": "10",
                    "choices": q3_choices,
                },
            ],
            "answers": {0: correct_q1, 1: partial_q2, 2: correct_q3},
            "total_questions": 3,
            "correct_count": 0,
            "current_idx": 0,
        }

    def test_quiz_result_saved_through_official_pipeline(self) -> None:
        from apps.games.models import Game, UserGameScore
        from apps.notifications.bot.quiz import _save_quiz_result_sync
        from apps.tests.models import TestAttempt

        quiz = self._quiz_state()
        saved = _save_quiz_result_sync(self.student, quiz)

        self.assertIsNotNone(saved)
        # Official grading: Q1 + Q3 correct; Q2 (multi) wrong → 2/3
        self.assertEqual(saved["correct"], 2)
        self.assertEqual(saved["total"], 3)
        self.assertTrue(saved["is_passed"])

        # A real attempt + Result exist
        attempt = TestAttempt.objects.filter(
            test=self.test, student=self.student
        ).first()
        self.assertIsNotNone(attempt)
        self.assertEqual(attempt.status, TestAttempt.Status.COMPLETED)
        result = Result.objects.get(attempt=attempt)
        self.assertEqual(result.correct_answers, 2)
        self.assertEqual(result.test, self.test)
        self.assertEqual(result.course, self.course)

        # XP awarded through a real Game row (no `game_name` crash)
        game = Game.objects.get(slug="telegram_quiz")
        score = UserGameScore.objects.get(user=self.student, game=game)
        self.assertEqual(score.total_xp, 20)  # 2 correct * 10 XP
        self.assertEqual(score.games_played, 1)

    def test_quiz_save_none_when_test_missing(self) -> None:
        from apps.notifications.bot.quiz import _save_quiz_result_sync

        quiz = self._quiz_state()
        quiz["test_id"] = 999999
        self.assertIsNone(_save_quiz_result_sync(self.student, quiz))


class AuditWorkflowSecurityTests(TestCase):
    """Regression tests for audit security & RBAC isolation."""

    def setUp(self) -> None:
        self.student = User.objects.create_user(
            email="audit_student@test.com",
            password="testpass123",
            first_name="Audit",
            last_name="Student",
            role="student",
        )
        self.teacher1 = User.objects.create_user(
            email="audit_teacher1@test.com",
            password="testpass123",
            first_name="Audit",
            last_name="Teacher1",
            role="teacher",
        )
        self.teacher2 = User.objects.create_user(
            email="audit_teacher2@test.com",
            password="testpass123",
            first_name="Audit",
            last_name="Teacher2",
            role="teacher",
        )
        from apps.courses.models import StudentGroup
        self.group1 = StudentGroup.objects.create(
            teacher=self.teacher1,
            name="Teacher 1 Group",
            subject="uzbek",
        )
        self.group1.students.add(self.student)

    def test_student_blocked_from_enterprise_views(self) -> None:
        self.client.login(email="audit_student@test.com", password="testpass123")
        r1 = self.client.get("/api/v1/enterprise/dashboard/")
        self.assertEqual(r1.status_code, 403)

        r2 = self.client.post("/api/v1/enterprise/students/bulk-import/", {})
        self.assertEqual(r2.status_code, 403)

        r3 = self.client.get("/api/v1/enterprise/report/download/")
        self.assertEqual(r3.status_code, 403)

        r4 = self.client.get("/api/v1/organizations/branding/")
        self.assertEqual(r4.status_code, 403)

    def test_monthly_report_pdf_blocked_for_other_teacher(self) -> None:
        self.client.login(email="audit_teacher2@test.com", password="testpass123")
        res = self.client.get(f"/api/v1/school/groups/{self.group1.id}/export/monthly-report-pdf/")
        self.assertEqual(res.status_code, 403)

    def test_speaking_submission_detail_isolation(self) -> None:
        from apps.speaking.models import SpeakingTopic, SpeakingSubmission
        topic = SpeakingTopic.objects.create(
            title="Audit Test Topic",
            prompt="Describe something.",
            part="part1",
        )
        sub = SpeakingSubmission.objects.create(
            user=self.student,
            topic=topic,
            transcript="Hello world",
        )
        # Teacher 2 (not managing student) gets 404/not found
        self.client.login(email="audit_teacher2@test.com", password="testpass123")
        res = self.client.get(f"/api/v1/speaking/submissions/{sub.id}/")
        self.assertEqual(res.status_code, 404)

        # Teacher 1 (manages student) gets 200 OK
        self.client.login(email="audit_teacher1@test.com", password="testpass123")
        res = self.client.get(f"/api/v1/speaking/submissions/{sub.id}/")
        self.assertEqual(res.status_code, 200)

    def test_essay_safe_render_partial_json_fallback(self) -> None:
        from django.test import RequestFactory
        from apps.essays.views import _safe_render_partial
        rf = RequestFactory()
        req = rf.get("/essays/fake/")
        resp = _safe_render_partial(req, "essays/nonexistent_template.html", {"status": "ok", "foo": "bar"}, status=200)
        self.assertEqual(resp.status_code, 200)
        import json
        data = json.loads(resp.content)
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("foo"), "bar")
