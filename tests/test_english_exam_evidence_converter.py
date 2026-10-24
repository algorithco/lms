from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase

from apps.courses.models import Course
from apps.tests.models import (
    Choice,
    Question,
    ReadingPassage,
    Test,
    TestAttempt,
)
from apps.tests.score_converter import (
    calculate_overall_cefr_level,
    calculate_overall_ielts_band,
    convert_test_score_to_english_band,
    generate_digital_certificate_payload,
    ielts_band_to_cefr,
    raw_to_cefr_multilevel,
    raw_to_ielts_band,
)
from apps.tests.evidence_feedback import (
    generate_reading_listening_evidence,
    grade_ielts_writing_deductive,
    grade_multilevel_writing_bmb,
)
from apps.tests.services import StartAttemptService, SubmitAttemptService

User = get_user_model()


class ScoreConverterUnitTests(APITestCase):
    """Unit tests for the automated score converter and Cambridge/BMB rounding scales."""

    def test_raw_to_ielts_band_all_bands(self):
        # 39–40: Band 9.0
        self.assertEqual(raw_to_ielts_band(40), Decimal("9.0"))
        self.assertEqual(raw_to_ielts_band(39), Decimal("9.0"))

        # 37–38: Band 8.5
        self.assertEqual(raw_to_ielts_band(38), Decimal("8.5"))
        self.assertEqual(raw_to_ielts_band(37), Decimal("8.5"))

        # 35–36: Band 8.0
        self.assertEqual(raw_to_ielts_band(36), Decimal("8.0"))
        self.assertEqual(raw_to_ielts_band(35), Decimal("8.0"))

        # 32–34: Band 7.5
        self.assertEqual(raw_to_ielts_band(34), Decimal("7.5"))
        self.assertEqual(raw_to_ielts_band(32), Decimal("7.5"))

        # 30–31: Band 7.0
        self.assertEqual(raw_to_ielts_band(31), Decimal("7.0"))
        self.assertEqual(raw_to_ielts_band(30), Decimal("7.0"))

        # 26–29: Band 6.5
        self.assertEqual(raw_to_ielts_band(29), Decimal("6.5"))
        self.assertEqual(raw_to_ielts_band(26), Decimal("6.5"))

        # 23–25: Band 6.0
        self.assertEqual(raw_to_ielts_band(25), Decimal("6.0"))
        self.assertEqual(raw_to_ielts_band(23), Decimal("6.0"))

        # 19–22: Band 5.5
        self.assertEqual(raw_to_ielts_band(22), Decimal("5.5"))
        self.assertEqual(raw_to_ielts_band(19), Decimal("5.5"))

        # 15–18: Band 5.0
        self.assertEqual(raw_to_ielts_band(18), Decimal("5.0"))
        self.assertEqual(raw_to_ielts_band(15), Decimal("5.0"))

        # 13–14: Band 4.5
        self.assertEqual(raw_to_ielts_band(14), Decimal("4.5"))
        self.assertEqual(raw_to_ielts_band(13), Decimal("4.5"))

        # 10–12: Band 4.0
        self.assertEqual(raw_to_ielts_band(12), Decimal("4.0"))
        self.assertEqual(raw_to_ielts_band(10), Decimal("4.0"))

        # 0–9: Band 3.5 and below
        self.assertLessEqual(raw_to_ielts_band(9), Decimal("3.5"))
        self.assertLessEqual(raw_to_ielts_band(4), Decimal("3.0"))

    def test_raw_to_cefr_multilevel_scale(self):
        # 65–75: C1
        c1_level, score1 = raw_to_cefr_multilevel(70, max_score=75)
        self.assertEqual(c1_level, "C1")
        self.assertEqual(score1, Decimal("70.0"))

        # 51–64: B2
        b2_level, _ = raw_to_cefr_multilevel(60, max_score=75)
        self.assertEqual(b2_level, "B2")

        # 36–50: B1
        b1_level, _ = raw_to_cefr_multilevel(45, max_score=75)
        self.assertEqual(b1_level, "B1")

        # <= 35: A2 (no certificate)
        a2_level, _ = raw_to_cefr_multilevel(30, max_score=75)
        self.assertEqual(a2_level, "A2")

    def test_cambridge_half_band_rounding(self):
        # e.g. average = 6.25 -> rounds up to 6.5
        self.assertEqual(
            calculate_overall_ielts_band(6.5, 6.5, 6.0, 6.0),
            Decimal("6.5"),
        )
        # e.g. average = 6.75 -> rounds up to 7.0
        self.assertEqual(
            calculate_overall_ielts_band(7.0, 7.0, 6.5, 6.5),
            Decimal("7.0"),
        )
        # e.g. average = 6.125 -> rounds down to 6.0
        self.assertEqual(
            calculate_overall_ielts_band(6.0, 6.0, 6.0, 6.5),
            Decimal("6.0"),
        )

    def test_ielts_band_to_cefr(self):
        self.assertEqual(ielts_band_to_cefr(8.5), "C2")
        self.assertEqual(ielts_band_to_cefr(7.5), "C1")
        self.assertEqual(ielts_band_to_cefr(6.0), "B2")
        self.assertEqual(ielts_band_to_cefr(4.5), "B1")
        self.assertEqual(ielts_band_to_cefr(3.0), "A2")

    def test_digital_certificate_payload_generation(self):
        score_info = {
            "ielts_band": 7.5,
            "cefr_level": "C1",
            "has_certificate": True,
            "sections": {
                "listening": {"band": 8.0, "cefr": "C1"},
                "reading": {"band": 7.5, "cefr": "C1"},
                "writing": {"band": 7.0, "cefr": "C1"},
                "speaking": {"band": 7.5, "cefr": "C1"},
            },
        }
        cert = generate_digital_certificate_payload(
            student_name="Komiljon Roziyev",
            exam_title="IELTS Academic Mock Examination",
            exam_type="IELTS Academic",
            score_info=score_info,
        )
        self.assertEqual(cert["candidate_name"], "Komiljon Roziyev")
        self.assertEqual(cert["overall_band"], 7.5)
        self.assertEqual(cert["overall_cefr"], "C1")
        self.assertTrue(cert["is_valid"])
        self.assertIn("verify-certificate", cert["qr_verification_url"])


class EvidenceFeedbackUnitTests(APITestCase):
    """Unit tests for Reading/Listening evidence extraction & writing evaluators."""

    def test_reading_listening_evidence_fallback(self):
        passage = "The primary objective of the conservation program is to protect endangered species from habitat destruction."
        res = generate_reading_listening_evidence(
            question_text="What is the main goal of the conservation effort?",
            selected_answer="Economic development",
            correct_answer="Protect endangered species",
            passage_text=passage,
            question_explanation="Directly stated in line 1.",
        )
        self.assertIn("direct_quote", res)
        self.assertIn("why_wrong", res)
        self.assertIn("synonym_matching", res)
        self.assertIn("correct_rule", res)
        self.assertIn("protect endangered species", res["direct_quote"].lower())

    def test_multilevel_writing_bmb(self):
        text = "In modern society, education plays a vital and paramount role in fostering human capabilities and developing national economy. Furthermore, continuous learning facilitates innovation."
        res = grade_multilevel_writing_bmb(text, topic_title="Role of Education")
        self.assertIn("content_score", res)
        self.assertIn("communicative_score", res)
        self.assertIn("organisation_score", res)
        self.assertIn("language_score", res)
        self.assertIn("total_score", res)
        self.assertIn("cefr_level", res)
        self.assertIn("word_upgrades", res)
        self.assertGreaterEqual(res["total_score"], 15)
        self.assertLessEqual(res["total_score"], 75)

    def test_ielts_writing_deductive(self):
        text = "It is often argued whether modern technology brings more advantages or disadvantages to contemporary students. In my perspective, digital tools substantially accelerate academic research."
        res = grade_ielts_writing_deductive(text, topic_title="Technology in Education")
        self.assertIn("task_response", res)
        self.assertIn("coherence_cohesion", res)
        self.assertIn("lexical_resource", res)
        self.assertIn("grammatical_accuracy", res)
        self.assertIn("overall_band", res)
        self.assertIn("model_paragraph_rewrite", res)
        self.assertGreaterEqual(res["overall_band"], 1.0)
        self.assertLessEqual(res["overall_band"], 9.0)


class EnglishExamIntegrationTests(APITestCase):
    """Integration test suite for Strict vs Practice exam flows and API endpoints."""

    def setUp(self):
        self.user = User.objects.create_user(
            email="ielts_student@example.com",
            password="SecurePassword123!",
            role="student",
        )
        self.teacher = User.objects.create_user(
            email="ielts_teacher@example.com",
            password="SecurePassword123!",
            role="teacher",
        )
        self.course = Course.objects.create(
            title="IELTS Academic Preparation",
            slug="ielts-academic-prep",
            teacher=self.teacher,
        )
        self.test = Test.objects.create(
            course=self.course,
            title="IELTS Academic Full Mock 1",
            subject="english",
            exam_type=Test.ExamType.IELTS_ACADEMIC,
            is_strict_mode=True,
            time_limit_minutes=60,
            max_attempts=0,
        )
        self.passage = ReadingPassage.objects.create(
            test=self.test,
            title="The Renewable Energy Transition",
            content="Solar power harnesses radiant light and heat from the Sun using a range of ever-evolving technologies.",
            order=1,
        )
        self.q1 = Question.objects.create(
            test=self.test,
            reading_passage=self.passage,
            text="What does solar power harness?",
            question_type=Question.QuestionType.SINGLE_CHOICE,
            points=1,
            position=1,
        )
        self.c1 = Choice.objects.create(
            question=self.q1, text="Radiant light and heat", is_correct=True, position=1
        )
        self.c2 = Choice.objects.create(
            question=self.q1,
            text="Nuclear fission energy",
            is_correct=False,
            position=2,
        )

    def test_start_attempt_strict_and_practice_modes(self):
        # Strict mode start
        attempt_strict = StartAttemptService.execute(
            test_id=self.test.id,
            student=self.user,
            mode="strict",
        )
        self.assertEqual(attempt_strict.mode, TestAttempt.Mode.STRICT)

        # Complete attempt
        SubmitAttemptService.execute(attempt_strict.id, self.user)

        # Practice mode start
        attempt_practice = StartAttemptService.execute(
            test_id=self.test.id,
            student=self.user,
            mode="practice",
        )
        self.assertEqual(attempt_practice.mode, TestAttempt.Mode.PRACTICE)

    def test_anti_cheat_violation_and_auto_termination(self):
        attempt = StartAttemptService.execute(
            test_id=self.test.id,
            student=self.user,
            mode="strict",
        )
        self.client.force_authenticate(user=self.user)

        # 1st violation
        resp1 = self.client.post(
            f"/api/tests/attempts/{attempt.id}/report-violation/",
            {"type": "tab_switch"},
            format="json",
        )
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(resp1.data["violation_count"], 1)
        self.assertFalse(resp1.data["terminated"])

        # 2nd violation
        resp2 = self.client.post(
            f"/api/tests/attempts/{attempt.id}/report-violation/",
            {"type": "window_blur"},
            format="json",
        )
        self.assertEqual(resp2.data["violation_count"], 2)
        self.assertFalse(resp2.data["terminated"])

        # 3rd violation -> automatic termination
        resp3 = self.client.post(
            f"/api/tests/attempts/{attempt.id}/report-violation/",
            {"type": "tab_switch"},
            format="json",
        )
        self.assertEqual(resp3.data["violation_count"], 3)
        self.assertTrue(resp3.data["terminated"])
        self.assertTrue(resp3.data["cheating_detected"])

        attempt.refresh_from_db()
        self.assertIn(
            attempt.status,
            [TestAttempt.Status.COMPLETED, TestAttempt.Status.TIMEOUT],
        )

    from unittest.mock import patch

    @patch("apps.payments.ai_quota.check_and_consume_ai_quota", return_value=(True, ""))
    def test_explain_mistake_endpoint_with_evidence(self, _mock_quota):
        attempt = StartAttemptService.execute(
            test_id=self.test.id,
            student=self.user,
            mode="practice",
        )
        self.client.force_authenticate(user=self.user)

        resp = self.client.post(
            f"/api/tests/questions/{self.q1.id}/explain-mistake/",
            {
                "selected_choice_id": self.c2.id,
                "attempt_id": attempt.id,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("direct_quote", resp.data)
        self.assertIn("why_wrong", resp.data)
        self.assertIn("synonym_matching", resp.data)

    def test_evaluate_writing_endpoint(self):
        self.client.force_authenticate(user=self.user)
        payload = {
            "essay_text": "In recent decades, environmental degradation has escalated to alarming proportions across the globe. Consequently, international cooperation is imperative to mitigate climate change.",
            "topic_title": "Global Environmental Challenges",
            "exam_type": "ielts",
            "task_type": "task2",
        }
        resp = self.client.post("/api/tests/writing/evaluate/", payload, format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("overall_band", resp.data)
        self.assertIn("model_paragraph_rewrite", resp.data)

    def test_certificate_card_endpoint(self):
        attempt = StartAttemptService.execute(
            test_id=self.test.id,
            student=self.user,
            mode="strict",
        )
        # Select correct answer
        self.client.force_authenticate(user=self.user)
        self.client.post(
            f"/api/tests/attempts/{attempt.id}/save-answer/",
            {"question_id": self.q1.id, "choice_ids": [self.c1.id]},
            format="json",
        )
        self.client.post(f"/api/tests/attempts/{attempt.id}/submit/", format="json")

        resp = self.client.get(f"/api/tests/attempts/{attempt.id}/certificate-card/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("certificate_number", resp.data)
        self.assertIn("overall_band", resp.data)
        self.assertIn("overall_cefr", resp.data)
