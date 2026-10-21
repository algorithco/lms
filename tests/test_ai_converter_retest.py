"""
Tests for:
1. Teacher AI Document-to-Test Converter (apps/tests/ai_converter.py & views_converter.py)
2. Student Adaptive Re-Test Engine (apps/tests/views_mistakes.py)
"""

from __future__ import annotations

import io
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.courses.models import Course
from apps.tests.models import Choice, Question, StudentAnswer, Test, TestAttempt

User = get_user_model()


class AiConverterAndRetestTests(TestCase):
    def setUp(self) -> None:
        self.teacher = User.objects.create_user(
            email="converter_teacher@test.com",
            password="testpass123",
            first_name="Ustoz",
            last_name="Test",
            role="teacher",
        )
        self.student = User.objects.create_user(
            email="retest_student@test.com",
            password="testpass123",
            first_name="Talaba",
            last_name="Test",
            role="student",
        )
        self.course = Course.objects.create(
            teacher=self.teacher,
            title="Ona tili kursi",
            subject="uzbek",
        )
        self.test = Test.objects.create(
            course=self.course,
            title="Ona tili diagnostikasi",
            subject="uzbek",
            time_limit_minutes=30,
            status=Test.Status.PUBLISHED,
        )

        # 3 ta savol yaratamiz
        self.q1 = Question.objects.create(
            test=self.test,
            text="Fonetika nimani o'rganadi?",
            position=1,
            points=1,
            explanation="Fonetika nutq tovushlarini o'rganadi.",
        )
        Choice.objects.create(
            question=self.q1, text="Nutq tovushlarini", is_correct=True, position=1
        )
        Choice.objects.create(
            question=self.q1, text="So'z ma'nolarini", is_correct=False, position=2
        )

        self.q2 = Question.objects.create(
            test=self.test,
            text="Morfologiya nimani o'rganadi?",
            position=2,
            points=1,
            explanation="Morfologiya so'z turkumlarini o'rganadi.",
        )
        Choice.objects.create(
            question=self.q2, text="So'z turkumlarini", is_correct=True, position=1
        )
        Choice.objects.create(
            question=self.q2, text="Gap bo'laklarini", is_correct=False, position=2
        )

    def test_student_blocked_from_ai_converter(self) -> None:
        self.client.login(email="retest_student@test.com", password="testpass123")
        dummy_file = SimpleUploadedFile(
            "test.png", b"fake_image_content", content_type="image/png"
        )
        res = self.client.post(
            "/api/v1/tests/ai-convert-document/",
            {"file": dummy_file, "subject": "uzbek"},
        )
        self.assertEqual(res.status_code, 403)

    def test_teacher_ai_convert_document_success(self) -> None:
        self.client.login(email="converter_teacher@test.com", password="testpass123")
        dummy_file = SimpleUploadedFile(
            "sample_test.png", b"fake_png_data", content_type="image/png"
        )
        res = self.client.post(
            "/api/v1/tests/ai-convert-document/",
            {"file": dummy_file, "subject": "uzbek"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertIn("questions", data.get("data", {}))
        self.assertGreaterEqual(len(data["data"]["questions"]), 1)

    def test_teacher_ai_save_converted_test(self) -> None:
        self.client.login(email="converter_teacher@test.com", password="testpass123")
        payload = {
            "test_title": "AI Yangi Mock Test 2026",
            "subject": "uzbek",
            "time_limit_minutes": 45,
            "reading_passage": "Alisher Navoiy ijodi haqida umumiy matn.",
            "questions": [
                {
                    "order": 1,
                    "text": "Navoiy 'Xamsa'sini necha yoshida yozib tugatgan?",
                    "choices": [
                        {"code": "A", "text": "44 yoshida"},
                        {"code": "B", "text": "30 yoshida"},
                        {"code": "C", "text": "50 yoshida"},
                        {"code": "D", "text": "25 yoshida"},
                    ],
                    "correct_answer": "A",
                    "explanation": "Alisher Navoiy 1483-1485 yillarda 'Xamsa'ni yozgan (42-44 yoshlarida).",
                }
            ],
        }
        res = self.client.post(
            "/api/v1/tests/ai-save-converted/", payload, content_type="application/json"
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertIn("mock_code", data)
        self.assertTrue(data["mock_code"].startswith("#MOCK-"))

        # Test bazada haqiqatan yaratilganini tekshiramiz
        saved_test = Test.objects.get(id=data["test_id"])
        self.assertEqual(saved_test.title, "AI Yangi Mock Test 2026")
        self.assertEqual(saved_test.questions.count(), 1)
        self.assertEqual(saved_test.passages.count(), 1)

    def test_adaptive_retest_generation(self) -> None:
        # Talaba urinish qiladi va 1 ta to'g'ri, 1 ta xato ishlaydi
        attempt = TestAttempt.objects.create(
            test=self.test,
            student=self.student,
            status=TestAttempt.Status.COMPLETED,
        )

        c1 = self.q1.choices.filter(is_correct=True).first()
        ans1 = StudentAnswer.objects.create(
            attempt=attempt, question=self.q1, is_correct=True
        )
        ans1.selected_choices.add(c1)

        c2_wrong = self.q2.choices.filter(is_correct=False).first()
        ans2 = StudentAnswer.objects.create(
            attempt=attempt, question=self.q2, is_correct=False
        )
        ans2.selected_choices.add(c2_wrong)

        self.client.login(email="retest_student@test.com", password="testpass123")
        res = self.client.post(f"/api/v1/tests/attempts/{attempt.id}/generate-retest/")
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertTrue(data.get("has_mistakes"))
        self.assertIn("retest_test_id", data)
        self.assertIn("attempt_id", data)

        # Yangi retest attempt holati
        retest_attempt = TestAttempt.objects.get(id=data["attempt_id"])
        self.assertEqual(retest_attempt.student, self.student)
        self.assertEqual(retest_attempt.status, TestAttempt.Status.IN_PROGRESS)
        self.assertTrue("Xatolar ustida mashq" in retest_attempt.test.title)

    def test_mistake_vault_api(self) -> None:
        attempt = TestAttempt.objects.create(
            test=self.test,
            student=self.student,
            status=TestAttempt.Status.COMPLETED,
        )
        c2_wrong = self.q2.choices.filter(is_correct=False).first()
        ans2 = StudentAnswer.objects.create(
            attempt=attempt, question=self.q2, is_correct=False
        )
        ans2.selected_choices.add(c2_wrong)

        self.client.login(email="retest_student@test.com", password="testpass123")
        res = self.client.get("/api/v1/tests/mistake-vault/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertGreaterEqual(data.get("unresolved_count", 0), 1)
        self.assertIn("weak_topics", data)
        self.assertIn("recent_mistakes", data)
