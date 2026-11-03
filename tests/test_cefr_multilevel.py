"""CEFR Multi-level estimated scoring: anchor table, level boundaries,
incomplete results and the certificate-card payload (no IELTS band)."""

from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.tests import cefr_multilevel as cm
from apps.tests.models import Choice, ExamSection, Question, Test, TestAttempt
from apps.tests.scoring import QuestionScore
from apps.tests.services import StartAttemptService

User = get_user_model()


def objective(code: str, correct: int, total: int = 35) -> list[QuestionScore]:
    return [
        QuestionScore(question_id=i, earned=Decimal(int(i < correct)), maximum=Decimal(1),
                      is_correct=i < correct, section_code=code)
        for i in range(total)
    ]


def rated(code: str, earned: float | None, maximum: float = 10) -> list[QuestionScore]:
    """One graded (or pending when earned is None) writing/speaking item."""
    return [
        QuestionScore(question_id=999, earned=Decimal(str(earned or 0)), maximum=Decimal(str(maximum)),
                      is_correct=None if earned is None else True, section_code=code, kind="written")
    ]


def section_map(score: float) -> dict:
    return {c: {"status": cm.SCORED, "score": score} for c in ("LISTENING", "READING", "WRITING", "SPEAKING")}


class RawToScaledTests(SimpleTestCase):
    def test_anchor_points_per_section(self):
        expected = {0: (0, "BELOW_B1"), 9: (37, "BELOW_B1"), 10: (38, "B1"), 17: (50, "B1"),
                    18: (51, "B2"), 27: (64, "B2"), 28: (65, "C1"), 35: (75, "C1")}
        for raw, (score, level) in expected.items():
            with self.subTest(raw=raw):
                scaled = cm.raw_to_scaled(raw, 35)
                self.assertEqual(scaled, Decimal(score))
                self.assertEqual(cm.level_for(scaled), level)

    def test_linear_interpolation_between_anchors(self):
        # 18 → 51, 27 → 64: 22 is 4/9 of the way → 51 + 13*4/9 = 56.8
        self.assertEqual(cm.raw_to_scaled(22, 35), Decimal("56.8"))

    def test_non_standard_question_count_is_normalised(self):
        self.assertEqual(cm.raw_to_scaled(40, 40), Decimal(75))
        self.assertEqual(cm.raw_to_scaled(0, 40), Decimal(0))

    def test_rated_sections_scaled_to_75(self):
        self.assertEqual(cm.rated_to_scaled(10, 10), Decimal(75))
        self.assertEqual(cm.rated_to_scaled(5, 10), Decimal("37.5"))
        self.assertEqual(cm.rated_to_scaled(0, 0), Decimal(0))


class OverallLevelTests(SimpleTestCase):
    def test_average_boundaries(self):
        cases = {37.9: "BELOW_B1", 38: "B1", 50: "B1", 51: "B2", 64: "B2", 65: "C1"}
        for avg, level in cases.items():
            with self.subTest(avg=avg):
                summary = cm.summarize(section_map(avg))
                self.assertEqual(summary["overall"]["level"], level)
                self.assertEqual(summary["has_certificate"], level != "BELOW_B1")

    def test_full_score(self):
        scores = objective("LISTENING", 35) + objective("READING", 35) + rated("WRITING", 10) + rated("SPEAKING", 10)
        summary = cm.compute(scores)
        self.assertEqual(summary["overall"], {"score": Decimal(75), "level": "C1"})
        self.assertTrue(summary["has_certificate"])
        self.assertTrue(summary["is_estimate"])

    def test_one_section_not_taken(self):
        scores = objective("LISTENING", 20) + objective("READING", 20) + rated("WRITING", 6)
        summary = cm.compute(scores)
        self.assertIsNone(summary["overall"])
        self.assertEqual(summary["missing_sections"], ["SPEAKING"])
        self.assertFalse(summary["has_certificate"])
        by_code = {s["code"]: s for s in summary["sections"]}
        self.assertEqual(by_code["LISTENING"]["level"], "B2")
        self.assertEqual(by_code["SPEAKING"]["status"], cm.MISSING)

    def test_listening_and_reading_only(self):
        summary = cm.compute(objective("LISTENING", 30) + objective("READING", 12))
        self.assertIsNone(summary["overall"])
        self.assertEqual(summary["missing_sections"], ["WRITING", "SPEAKING"])

    def test_pending_writing_blocks_overall(self):
        scores = objective("LISTENING", 30) + objective("READING", 30) + rated("WRITING", None) + rated("SPEAKING", 8)
        summary = cm.compute(scores)
        self.assertIsNone(summary["overall"])
        self.assertEqual({s["code"]: s["status"] for s in summary["sections"]}["WRITING"], cm.PENDING)

    def test_blank_section_counts_as_missing(self):
        blank = [QuestionScore(question_id=i, maximum=Decimal(1), is_correct=False, answered=False,
                               section_code="READING") for i in range(35)]
        summary = cm.compute(objective("LISTENING", 20) + blank)
        self.assertIn("READING", summary["missing_sections"])

    def test_no_ielts_band_in_result(self):
        summary = cm.compute(objective("LISTENING", 35) + objective("READING", 35))
        flat = repr(summary).lower()
        self.assertNotIn("band", flat)
        self.assertNotIn("ielts", flat)


class CefrCertificateCardTests(APITestCase):
    def setUp(self):
        self.student = User.objects.create_user(email="ml_student@example.com", password="x-Pass-123!", role="student")
        teacher = User.objects.create_user(email="ml_teacher@example.com", password="x-Pass-123!", role="teacher")
        course = Course.objects.create(title="Multi-level", slug="multi-level", teacher=teacher)
        self.test = Test.objects.create(
            course=course, title="Multi-level Mock", subject="english",
            exam_type=Test.ExamType.CEFR_MULTILEVEL, time_limit_minutes=60, max_attempts=0,
        )
        self.questions = {}
        for order, code in enumerate(("LISTENING", "READING"), start=1):
            section = ExamSection.objects.create(test=self.test, name=code.capitalize(), code=code, order=order)
            q = Question.objects.create(test=self.test, section=section, text=f"{code} q",
                                        question_type=Question.QuestionType.SINGLE_CHOICE, points=1, position=order)
            right = Choice.objects.create(question=q, text="right", is_correct=True, position=1)
            Choice.objects.create(question=q, text="wrong", is_correct=False, position=2)
            self.questions[code] = (q, right)

    def test_certificate_card_is_cefr_only(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student, mode="practice")
        self.client.force_authenticate(user=self.student)
        for q, right in self.questions.values():
            self.client.post(f"/api/tests/attempts/{attempt.id}/save-answer/",
                             {"question_id": q.id, "choice_ids": [right.id]}, format="json")
        self.client.post(f"/api/tests/attempts/{attempt.id}/submit/", format="json")

        attempt.refresh_from_db()
        self.assertIsNone(attempt.band_score)
        self.assertEqual(attempt.cefr_level, "")  # Writing/Speaking missing → no overall level
        self.assertEqual(attempt.section_scores["LISTENING"]["level"], "C1")

        resp = self.client.get(f"/api/tests/attempts/{attempt.id}/certificate-card/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["scale"], "cefr_multilevel")
        self.assertNotIn("overall_band", resp.data)
        self.assertNotIn("ielts_band", resp.data)
        self.assertIsNone(resp.data["overall"])
        self.assertEqual(resp.data["missing_sections"], ["WRITING", "SPEAKING"])
        self.assertFalse(resp.data["is_valid"])

    def test_recalc_command_dry_run_does_not_write(self):
        attempt = StartAttemptService.execute(test_id=self.test.id, student=self.student, mode="practice")
        self.client.force_authenticate(user=self.student)
        self.client.post(f"/api/tests/attempts/{attempt.id}/submit/", format="json")
        # Simulate a legacy row scored with the old 40-question IELTS table.
        TestAttempt.objects.filter(id=attempt.id).update(band_score=Decimal("6.5"), cefr_level="B2", section_scores={})

        out = StringIO()
        call_command("recalc_cefr_scores", "--dry-run", stdout=out)
        attempt.refresh_from_db()
        self.assertEqual(attempt.band_score, Decimal("6.5"))
        self.assertIn("o'zgaradi: 1", out.getvalue())

        call_command("recalc_cefr_scores", stdout=StringIO())
        attempt.refresh_from_db()
        self.assertIsNone(attempt.band_score)
        self.assertEqual(attempt.cefr_level, "")
        self.assertEqual(set(attempt.section_scores), {"LISTENING", "READING"})
