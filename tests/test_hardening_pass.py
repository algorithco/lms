"""Hardening-pass regression tests — minimal, production-safe.

Covers Phase 3-5 fixes without changing product behavior.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase, Client

from apps.accounts.models import User
from apps.core.validators import validate_attachment_upload, validate_image_upload
from apps.courses.models import Course
from apps.tests.models import Choice, Question, Test, TestAttempt
from apps.tests.services import StartAttemptService, SubmitAttemptService


def _make_user(email, role="student"):
    return User.objects.create_user(
        email=email, password="pass12345", role=role, first_name="T", last_name="U"
    )


def _make_test(teacher, **kw):
    course = Course.objects.create(
        teacher=teacher, title="C", description="d", status=Course.Status.PUBLISHED
    )
    params = dict(
        title="T", description="d", course=course, status=Test.Status.PUBLISHED
    )
    params.update(kw)
    return Test.objects.create(**params)


class AttemptRaceTests(TestCase):
    def test_db_blocks_second_in_progress(self):
        teacher = _make_user("t1@e.com", "teacher")
        student = _make_user("s1@e.com")
        test = _make_test(teacher)
        TestAttempt.objects.create(test=test, student=student, status="in_progress")
        with self.assertRaises(IntegrityError):
            TestAttempt.objects.create(test=test, student=student, status="in_progress")

    def test_service_returns_friendly_error_on_race(self):
        teacher = _make_user("t2@e.com", "teacher")
        student = _make_user("s2@e.com")
        test = _make_test(teacher)
        TestAttempt.objects.create(test=test, student=student, status="in_progress")
        with self.assertRaisesMessage(ValueError, "davom etayotgan"):
            StartAttemptService.execute(test_id=test.id, student=student)

    def test_completed_does_not_block_new_start(self):
        teacher = _make_user("t3@e.com", "teacher")
        student = _make_user("s3@e.com")
        test = _make_test(teacher, max_attempts=0)
        TestAttempt.objects.create(test=test, student=student, status="completed")
        a = StartAttemptService.execute(test_id=test.id, student=student)
        self.assertEqual(a.status, "in_progress")


class EssayZeroScoreTests(TestCase):
    def test_zero_stays_zero(self):
        from apps.essays.models import EssaySubmission, EssayTopic

        teacher = _make_user("et@e.com", "teacher")
        student = _make_user("es@e.com")
        topic = EssayTopic.objects.create(
            title="Z", description="d", created_by=teacher, is_active=True
        )
        sub = EssaySubmission.objects.create(
            student=student,
            topic=topic,
            status=EssaySubmission.Status.GRADED,
            total_score=Decimal("0"),
            max_score=24,
        )
        self.assertEqual(sub.effective_score, Decimal("0"))
        self.assertIsNotNone(sub.effective_score)
        self.assertEqual(sub.score_percentage, 0.0)

    def test_topic_less_never_expires(self):
        from apps.essays.models import EssaySubmission

        student = _make_user("es2@e.com")
        sub = EssaySubmission.objects.create(
            student=student,
            topic=None,
            status=EssaySubmission.Status.DRAFT,
            essay_text="hello",
        )
        self.assertFalse(sub.is_expired)


class ArenaRoomCodeTests(TestCase):
    def test_collision_retry(self):
        from apps.arena.models import ArenaRoom

        u1 = _make_user("a1@e.com")
        u2 = _make_user("a2@e.com")
        r1 = ArenaRoom.objects.create(player1=u1, room_code="ABC123")
        self.assertEqual(r1.room_code, "ABC123")
        # Force a collision on first random choice, then succeed.
        import apps.arena.models as m

        orig_choices = __import__("random").choices
        calls = {"n": 0}

        def fake_choices(*a, **k):
            calls["n"] += 1
            if calls["n"] == 1:
                return list("ABC123")
            return orig_choices(*a, **k)

        import random

        random.choices = fake_choices
        try:
            r2 = ArenaRoom.objects.create(player1=u2)
        finally:
            random.choices = orig_choices
        self.assertNotEqual(r2.room_code, "ABC123")
        self.assertEqual(len(r2.room_code), 6)


class ShortCodeTests(TestCase):
    def test_active_short_code_unique(self):
        from apps.notifications.models import TelegramAuthToken

        TelegramAuthToken.objects.create(token="tok1", short_code="123456")
        with self.assertRaises(IntegrityError):
            TelegramAuthToken.objects.create(token="tok2", short_code="123456")

    def test_empty_codes_may_repeat(self):
        from apps.notifications.models import TelegramAuthToken

        TelegramAuthToken.objects.create(token="tok3", short_code="")
        TelegramAuthToken.objects.create(token="tok4", short_code="")
        # no error


class StreakTests(TestCase):
    def test_bonus_goes_to_single_row(self):
        from datetime import timedelta
        from django.utils import timezone
        from apps.games.models import DailyStreak, Game, UserGameScore

        student = _make_user("st@e.com")
        g1 = Game.objects.create(name="G1", slug="imlo_mina", description="d")
        g2 = Game.objects.create(name="G2", slug="gazal_top", description="d")
        s1 = UserGameScore.objects.create(user=student, game=g1)
        s2 = UserGameScore.objects.create(user=student, game=g2)
        streak = DailyStreak.objects.create(
            user=student,
            current_streak=2,
            best_streak=2,
            last_login_date=timezone.now().date() - timedelta(days=1),
        )
        res = streak.update_streak()
        self.assertEqual(res["new_streak"], 3)
        self.assertEqual(res["reward_claimed"], "3_day")
        s1.refresh_from_db()
        s2.refresh_from_db()
        total = (s1.total_xp - 0) + (s2.total_xp - 0)
        # Exactly one row credited with 30 XP, not both.
        self.assertEqual(total, 30)
        self.assertTrue((s1.total_xp == 30) ^ (s2.total_xp == 30))


class GradingTests(TestCase):
    def _setup(self):
        teacher = _make_user("g_t@e.com", "teacher")
        student = _make_user("g_s@e.com")
        test = _make_test(teacher)
        q1 = Question.objects.create(
            test=test, text="1+1?", question_type="single", position=1, points=2
        )
        c1 = Choice.objects.create(question=q1, text="2", is_correct=True, position=1)
        c2 = Choice.objects.create(question=q1, text="3", is_correct=False, position=2)
        q2 = Question.objects.create(
            test=test, text="pick both", question_type="multiple", position=2, points=3
        )
        m1 = Choice.objects.create(question=q2, text="a", is_correct=True, position=1)
        m2 = Choice.objects.create(question=q2, text="b", is_correct=True, position=2)
        m3 = Choice.objects.create(question=q2, text="c", is_correct=False, position=3)
        q3 = Question.objects.create(
            test=test,
            text="capital?",
            question_type="text",
            correct_text="Tashkent",
            position=3,
            points=5,
        )
        return teacher, student, test, (q1, c1, c2), (q2, m1, m2, m3), q3

    def test_single_multiple_text_correct(self):
        from apps.tests.models import StudentAnswer

        _, student, test, (q1, c1, _c2), (q2, m1, m2, _m3), q3 = self._setup()
        attempt = TestAttempt.objects.create(
            test=test, student=student, status="in_progress"
        )
        a1 = StudentAnswer.objects.create(attempt=attempt, question=q1)
        a1.selected_choices.set([c1])
        a2 = StudentAnswer.objects.create(attempt=attempt, question=q2)
        a2.selected_choices.set([m1, m2])
        StudentAnswer.objects.create(
            attempt=attempt, question=q3, text_answer="tashkent"
        )
        # Full submit incl. eager cert+email side-effects; grading itself is a
        # constant query set (questions+gaps+matching prefetches, answers, M2M,
        # through tables, 1 bulk_update, profile get_or_create, result
        # get_or_create+update, per-section update_or_create, 1 milliy EXISTS
        # check in the cert gate). Bound guards N+1.
        with self.assertNumQueries(54):
            outcome = SubmitAttemptService.execute(
                attempt_id=attempt.id, student=student
            )
        self.assertEqual(outcome.correct_answers, 3)
        self.assertEqual(outcome.score, Decimal("10"))

    def test_partial_multiple_gets_zero(self):
        from apps.tests.models import StudentAnswer

        _, student, test, (q1, c1, _), (q2, m1, _m2, _m3), q3 = self._setup()
        attempt = TestAttempt.objects.create(
            test=test, student=student, status="in_progress"
        )
        a1 = StudentAnswer.objects.create(attempt=attempt, question=q1)
        a1.selected_choices.set([c1])
        a2 = StudentAnswer.objects.create(attempt=attempt, question=q2)
        a2.selected_choices.set([m1])  # partial
        StudentAnswer.objects.create(attempt=attempt, question=q3, text_answer="wrong")
        outcome = SubmitAttemptService.execute(attempt_id=attempt.id, student=student)
        self.assertEqual(outcome.correct_answers, 1)
        self.assertEqual(outcome.wrong_answers, 2)


class CertificateDedupTests(TestCase):
    def test_canonical_service_idempotent(self):
        from apps.results.models import Result
        from apps.certificates.services.generation import generate_certificate

        teacher = _make_user("c_t@e.com", "teacher")
        student = _make_user("c_s@e.com")
        student.first_name = "A"
        student.last_name = "B"
        student.save()
        test = _make_test(teacher, pass_percentage=0)
        attempt = TestAttempt.objects.create(
            test=test, student=student, status="completed"
        )
        result = Result.objects.create(
            attempt=attempt,
            student=student,
            test=test,
            course=test.course,
            total_questions=1,
            correct_answers=1,
            wrong_answers=0,
            unanswered=0,
            score=10,
            max_score=10,
            percentage=100,
            is_passed=True,
            time_taken_seconds=60,
        )
        cert1, gen1 = generate_certificate(result)
        cert2, gen2 = generate_certificate(result)
        self.assertEqual(cert1.pk, cert2.pk)
        self.assertTrue(gen1)
        self.assertFalse(gen2)
        self.assertTrue(cert1.fraud_checksum)


class UploadValidatorTests(TestCase):
    def _fake(self, name, size=100):
        class F:
            def __init__(self, n, s):
                self.name = n
                self.size = s

        return F(name, size)

    def test_block_html_svg(self):
        for bad in ("x.html", "x.svg", "x.js", "x.htm"):
            with self.assertRaises(ValidationError, msg=bad):
                validate_image_upload(self._fake(bad))
            with self.assertRaises(ValidationError, msg=bad):
                validate_attachment_upload(self._fake(bad))

    def test_allow_images_and_pdf(self):
        validate_image_upload(self._fake("a.jpg"))
        validate_image_upload(self._fake("b.PNG"))
        validate_attachment_upload(self._fake("doc.pdf"))

    def test_reject_oversize(self):
        with self.assertRaises(ValidationError):
            validate_image_upload(self._fake("a.jpg", size=6 * 1024 * 1024))


class ArenaCsrfTests(TestCase):
    def test_session_post_without_csrf_rejected(self):
        user = _make_user("csrf@e.com")
        c = Client(enforce_csrf_checks=True)
        c.force_login(user)
        resp = c.post("/arena/api/rooms/create/", {})
        # login_required passes (session), CSRF must 403 (not 201/500).
        self.assertEqual(resp.status_code, 403)
