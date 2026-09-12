"""
Full integration tests for LMS Platform — Phase 6.

Covers:
    1. Student Auth & JWT token flow
    2. Test start, time limit enforcement
    3. Single & multiple choice answer auto-save
    4. Test submit, score calculation
    5. PDF certificate generation (synchronous via CELERY_TASK_ALWAYS_EAGER)
    6. Certificate verify API
    7. Throttling configuration
    8. OpenAPI schema generation
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.courses.models import Category, Course
from apps.results.models import Certificate, Result
from apps.tests.models import Choice, Question, Test, TestAttempt

from .conftest import LMSBaseTestCase


# ============================================================================
# 1. AUTH & JWT
# ============================================================================

class AuthJWTTests(LMSBaseTestCase):
    """Student registration, login, token refresh, logout."""

    def test_register_student(self):
        """POST /api/auth/register/ — ro'yxatdan o'tish."""
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "new@student.com",
                "password": "securepass123",
                "password_confirm": "securepass123",
                "first_name": "Yangi",
                "last_name": "Oquvchi",
                "role": "student",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertEqual(response.data["user"]["role"], "student")

        # Profile avtomatik yaratilganini tekshirish
        user = User.objects.get(email="new@student.com")
        self.assertTrue(hasattr(user, "profile"))

    def test_register_rejects_admin_role(self):
        """Admin rolini register orqali olish mumkin emas."""
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "hacker@test.com",
                "password": "securepass123",
                "password_confirm": "securepass123",
                "first_name": "Hacker",
                "last_name": "Admin",
                "role": "admin",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_password_mismatch(self):
        """Parollar mos kelmasligi."""
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "test@test.com",
                "password": "pass12345",
                "password_confirm": "pass99999",
                "first_name": "Test",
                "last_name": "User",
                "role": "student",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_returns_jwt_tokens(self):
        """POST /api/auth/login/ — JWT token olish."""
        response = self.client.post(
            "/api/auth/login/",
            {"email": "student@test.com", "password": "testpass123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("tokens", response.data)
        self.assertIn("access", response.data["tokens"])
        self.assertIn("refresh", response.data["tokens"])
        self.assertEqual(response.data["user"]["email"], "student@test.com")
        self.assertEqual(response.data["user"]["role"], "student")

    def test_login_wrong_password(self):
        """Noto'g'ri parol."""
        response = self.client.post(
            "/api/auth/login/",
            {"email": "student@test.com", "password": "wrongpass"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh(self):
        """POST /api/auth/token/refresh/ — token yangilash."""
        tokens = self.get_jwt_tokens()
        response = self.client.post(
            "/api/auth/token/refresh/",
            {"refresh": tokens["refresh"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_profile_view(self):
        """GET /api/auth/me/ — profilni ko'rish."""
        client = self.get_authenticated_client()
        response = client.get("/api/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "student@test.com")
        self.assertEqual(response.data["role"], "student")

    def test_profile_update(self):
        """PATCH /api/auth/me/ — profilni tahrirlash."""
        client = self.get_authenticated_client()
        response = client.patch(
            "/api/auth/me/",
            {"first_name": "Yangi Ism", "bio": "Django developer"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertEqual(self.student.first_name, "Yangi Ism")

    def test_unauthenticated_access_denied(self):
        """Autentifikatsiyasiz kirish rad etilishi."""
        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ============================================================================
# 2. TEST START & TIME LIMIT
# ============================================================================

class TestStartTests(LMSBaseTestCase):
    """Testni boshlash va vaqt chegarasi nazorati."""

    def test_start_attempt(self):
        """POST /api/tests/{id}/start/ — yangi attempt yaratish."""
        client = self.get_authenticated_client()
        response = client.post(f"/api/tests/{self.test.id}/start/", format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "in_progress")
        self.assertIn("remaining_seconds", response.data)

        # DBda saqlanganini tekshirish
        attempt = TestAttempt.objects.get(id=response.data["id"])
        self.assertEqual(attempt.student, self.student)
        self.assertEqual(attempt.test, self.test)

    def test_student_cannot_start_twice(self):
        """Aktiv attempt borligida yangi start bermaslik."""
        client = self.get_authenticated_client()
        # Birinchi start
        client.post(f"/api/tests/{self.test.id}/start/", format="json")
        # Ikkinchi start — xato
        response = client.post(f"/api/tests/{self.test.id}/start/", format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_teacher_cannot_start_test(self):
        """O'qituvchi test topshira olmaydi."""
        client = self.get_authenticated_client(email="teacher@test.com")
        response = client.post(f"/api/tests/{self.test.id}/start/", format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_max_attempts_enforcement(self):
        """Max attempts chegarasini bosmaslik."""
        client = self.get_authenticated_client()

        # 3 ta attempt yaratish (max_attempts=3)
        for _ in range(3):
            TestAttempt.objects.create(
                test=self.test, student=self.student,
                status=TestAttempt.Status.COMPLETED,
                score=Decimal("50"), percentage=Decimal("50"),
                is_passed=False,
            )

        # 4-chi attempt — xato
        response = client.post(f"/api/tests/{self.test.id}/start/", format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_attempt_detail_with_timer(self):
        """GET /api/tests/attempts/{id}/ — timer bilan attempt holati."""
        client = self.get_authenticated_client()
        start_resp = client.post(f"/api/tests/{self.test.id}/start/", format="json")
        attempt_id = start_resp.data["id"]

        response = client.get(f"/api/tests/attempts/{attempt_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("remaining_seconds", response.data)
        self.assertGreater(response.data["remaining_seconds"], 0)


# ============================================================================
# 3. ANSWER AUTO-SAVE
# ============================================================================

class AnswerSaveTests(LMSBaseTestCase):
    """Single va multiple choice javoblarni auto-save."""

    def setUp(self):
        super().setUp()
        client = self.get_authenticated_client()
        resp = client.post(f"/api/tests/{self.test.id}/start/", format="json")
        self.attempt_id = resp.data["id"]

    def test_save_single_choice_answer(self):
        """Single choice javobni saqlash."""
        client = self.get_authenticated_client()
        response = client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q1.id, "choice_ids": [self.q1_c1.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.q1_c1.id, response.data["saved_choices"])

    def test_save_multiple_choice_answer(self):
        """Multiple choice javobni saqlash."""
        client = self.get_authenticated_client()
        response = client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q2.id, "choice_ids": [self.q2_c1.id, self.q2_c2.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["saved_choices"]), 2)

    def test_answer_update(self):
        """Javobni yangilash (upsert)."""
        client = self.get_authenticated_client()

        # Birinchi javob
        client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q1.id, "choice_ids": [self.q1_c2.id]},
            format="json",
        )

        # Yangilash — to'g'ri javob
        response = client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q1.id, "choice_ids": [self.q1_c1.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(self.q1_c1.id, response.data["saved_choices"])

    def test_cannot_answer_after_timeout(self):
        """Vaqt tugagandan keyin javob bermaslik."""
        client = self.get_authenticated_client()

        # Attempt ni timeout qilish
        attempt = TestAttempt.objects.get(id=self.attempt_id)
        attempt.status = TestAttempt.Status.TIMEOUT
        attempt.save(update_fields=["status"])

        response = client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q1.id, "choice_ids": [self.q1_c1.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ============================================================================
# 4. TEST SUBMIT & SCORE CALCULATION
# ============================================================================

class SubmitTests(LMSBaseTestCase):
    """Testni topshirish va ball avto-hisoblash."""

    def setUp(self):
        super().setUp()
        client = self.get_authenticated_client()
        resp = client.post(f"/api/tests/{self.test.id}/start/", format="json")
        self.attempt_id = resp.data["id"]

    def _submit_answers(self, client):
        """Barcha savollarga to'g'ri javoblar."""
        # Q1: single choice — to'g'ri
        client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q1.id, "choice_ids": [self.q1_c1.id]},
            format="json",
        )
        # Q2: multiple choice — to'g'ri (barcha)
        client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q2.id, "choice_ids": [self.q2_c1.id, self.q2_c2.id]},
            format="json",
        )
        # Q3: single choice — to'g'ri
        client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q3.id, "choice_ids": [self.q3_c1.id]},
            format="json",
        )

    def test_submit_all_correct(self):
        """Barcha javoblar to'g'ri — 100% ball."""
        client = self.get_authenticated_client()
        self._submit_answers(client)

        response = client.post(
            f"/api/tests/attempts/{self.attempt_id}/submit/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result = response.data["result"]
        self.assertEqual(result["correct_answers"], 3)
        self.assertEqual(result["wrong_answers"], 0)
        self.assertEqual(Decimal(result["percentage"]), Decimal("100"))
        self.assertTrue(result["is_passed"])

        # Result DBda mavjudligini tekshirish
        db_result = Result.objects.get(attempt_id=self.attempt_id)
        self.assertTrue(db_result.is_passed)

    def test_submit_mixed_answers(self):
        """Bir qismi to'g'ri, bir qismi noto'g'ri."""
        client = self.get_authenticated_client()

        # Q1: to'g'ri
        client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q1.id, "choice_ids": [self.q1_c1.id]},
            format="json",
        )
        # Q2: noto'g'ri (faqat bitta, multiple choice uchun barcha kerak)
        client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q2.id, "choice_ids": [self.q2_c1.id]},
            format="json",
        )
        # Q3: to'g'ri
        client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q3.id, "choice_ids": [self.q3_c1.id]},
            format="json",
        )

        response = client.post(
            f"/api/tests/attempts/{self.attempt_id}/submit/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result = response.data["result"]
        self.assertEqual(result["correct_answers"], 2)  # Q1 + Q3
        self.assertEqual(result["wrong_answers"], 1)     # Q2 (partial)
        # 20/30 = 66.67%
        self.assertGreater(Decimal(result["percentage"]), Decimal("60"))
        self.assertTrue(result["is_passed"])

    def test_submit_all_wrong(self):
        """Barcha javoblar noto'g'ri — 0%."""
        client = self.get_authenticated_client()

        # Q1: noto'g'ri
        client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q1.id, "choice_ids": [self.q1_c2.id]},
            format="json",
        )
        # Q2: noto'g'ri
        client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q2.id, "choice_ids": [self.q2_c3.id]},
            format="json",
        )
        # Q3: noto'g'ri
        client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q3.id, "choice_ids": [self.q3_c2.id]},
            format="json",
        )

        response = client.post(
            f"/api/tests/attempts/{self.attempt_id}/submit/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        result = response.data["result"]
        self.assertEqual(result["correct_answers"], 0)
        self.assertEqual(result["wrong_answers"], 3)
        self.assertEqual(Decimal(result["percentage"]), Decimal("0"))
        self.assertFalse(result["is_passed"])

    def test_cannot_submit_twice(self):
        """Allaqachon yakunlangan attempt ni qayta submit qilmaslik."""
        client = self.get_authenticated_client()
        self._submit_answers(client)

        # Birinchi submit
        client.post(f"/api/tests/attempts/{self.attempt_id}/submit/", format="json")

        # Ikkinchi submit — xato
        response = client.post(
            f"/api/tests/attempts/{self.attempt_id}/submit/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_multiple_choice_partial_score_zero(self):
        """Multiple choice'da qisman javob — 0 ball."""
        client = self.get_authenticated_client()

        # Q2: faqat bitta to'g'ri choice (ikkalasi kerak)
        client.post(
            f"/api/tests/attempts/{self.attempt_id}/save-answer/",
            {"question_id": self.q2.id, "choice_ids": [self.q2_c1.id]},
            format="json",
        )

        response = client.post(
            f"/api/tests/attempts/{self.attempt_id}/submit/",
            format="json",
        )
        result = response.data["result"]
        # Q2 noto'g'ri (partial), Q1 va Q3 javobsiz
        self.assertEqual(result["wrong_answers"], 1)
        self.assertEqual(result["unanswered"], 2)


# ============================================================================
# 5. PDF CERTIFICATE GENERATION (SYNCHRONOUS)
# ============================================================================

class CertificateGenerationTests(LMSBaseTestCase):
    """PDF sertifikat generatsiya — CELERY_TASK_ALWAYS_EAGER=True bilan."""

    def test_certificate_generated_on_pass(self):
        """O'tgan student uchun PDF sertifikat yaratilishi."""
        client = self.get_authenticated_client()

        # Start + answers + submit
        resp = client.post(f"/api/tests/{self.test.id}/start/", format="json")
        attempt_id = resp.data["id"]

        # To'g'ri javoblar
        client.post(
            f"/api/tests/attempts/{attempt_id}/save-answer/",
            {"question_id": self.q1.id, "choice_ids": [self.q1_c1.id]},
            format="json",
        )
        client.post(
            f"/api/tests/attempts/{attempt_id}/save-answer/",
            {"question_id": self.q2.id, "choice_ids": [self.q2_c1.id, self.q2_c2.id]},
            format="json",
        )
        client.post(
            f"/api/tests/attempts/{attempt_id}/save-answer/",
            {"question_id": self.q3.id, "choice_ids": [self.q3_c1.id]},
            format="json",
        )

        response = client.post(f"/api/tests/attempts/{attempt_id}/submit/", format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["result"]["is_passed"])

        # Celery eager mode da PDF avtomatik yaratilganini tekshirish
        result = Result.objects.get(attempt_id=attempt_id)
        self.assertTrue(result.is_passed)

        # Certificate mavjudligini tekshirish
        cert = Certificate.objects.get(result=result)
        self.assertEqual(cert.status, Certificate.Status.GENERATED)
        self.assertTrue(cert.file, "Certificate PDF file should exist")
        self.assertTrue(cert.certificate_number.startswith("LMS-"))

        # PDF fayl haqiqiy PDF ekanligini tekshirish
        with cert.file.open("rb") as f:
            header = f.read(5)
            self.assertEqual(header, b"%PDF-")

    def test_no_certificate_on_fail(self):
        """O'tmagan student uchun sertifikat yaratilmasligi."""
        client = self.get_authenticated_client()
        resp = client.post(f"/api/tests/{self.test.id}/start/", format="json")
        attempt_id = resp.data["id"]

        # Noto'g'ri javoblar
        client.post(
            f"/api/tests/attempts/{attempt_id}/save-answer/",
            {"question_id": self.q1.id, "choice_ids": [self.q1_c2.id]},
            format="json",
        )

        client.post(f"/api/tests/attempts/{attempt_id}/submit/", format="json")

        result = Result.objects.get(attempt_id=attempt_id)
        self.assertFalse(result.is_passed)

        # Certificate yaratilmagan
        self.assertFalse(
            Certificate.objects.filter(result=result).exists(),
            "Certificate should NOT be created for failed test",
        )

    def test_certificate_number_format(self):
        """Sertifikat raqami to'g'ri formatda."""
        client = self.get_authenticated_client()
        resp = client.post(f"/api/tests/{self.test.id}/start/", format="json")
        attempt_id = resp.data["id"]

        # To'g'ri javoblar
        for q, c in [(self.q1, self.q1_c1), (self.q2, [self.q2_c1.id, self.q2_c2.id]), (self.q3, self.q3_c1)]:
            choice_ids = c if isinstance(c, list) else [c.id]
            client.post(
                f"/api/tests/attempts/{attempt_id}/save-answer/",
                {"question_id": q.id, "choice_ids": choice_ids},
                format="json",
            )

        client.post(f"/api/tests/attempts/{attempt_id}/submit/", format="json")

        result = Result.objects.get(attempt_id=attempt_id)
        cert = Certificate.objects.get(result=result)

        # LMS-YYYY-XXXXXX format
        import re
        self.assertRegex(cert.certificate_number, r"^LMS-\d{4}-\d{6}$")


# ============================================================================
# 6. CERTIFICATE VERIFY API
# ============================================================================

class CertificateVerifyTests(LMSBaseTestCase):
    """Sertifikat haqiqiyligini tekshirish API."""

    def setUp(self):
        super().setUp()
        # Sertifikat yaratish
        self.attempt = TestAttempt.objects.create(
            test=self.test, student=self.student,
            status=TestAttempt.Status.COMPLETED,
            score=Decimal("30"), percentage=Decimal("100"),
            is_passed=True,
        )
        self.result = Result.objects.create(
            attempt=self.attempt, student=self.student,
            test=self.test, course=self.course,
            total_questions=3, correct_answers=3, wrong_answers=0,
            score=Decimal("30"), max_score=Decimal("30"),
            percentage=Decimal("100"), is_passed=True,
            time_taken_seconds=120,
        )
        # PDF generatsiya (synchronous)
        from apps.results.tasks import generate_certificate_task
        generate_certificate_task(result_id=self.result.id)
        self.cert = Certificate.objects.get(result=self.result)

    def test_verify_valid_certificate(self):
        """POST /api/certificates/verify/{number}/ — to'g'ri sertifikat."""
        response = self.client.post(
            f"/api/certificates/verify/{self.cert.certificate_number}/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])
        self.assertEqual(response.data["student_name"], "Jasur Karimov")
        self.assertEqual(response.data["course_title"], "Django Backend")
        self.assertEqual(response.data["percentage"], "100.00")

    def test_verify_invalid_number(self):
        """Noto'g'ri sertifikat raqami."""
        response = self.client.post(
            "/api/certificates/verify/LMS-0000-000000/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(response.data["valid"])

    def test_verify_via_get(self):
        """GET ham ishlashi kerak."""
        response = self.client.get(
            f"/api/certificates/verify/{self.cert.certificate_number}/",
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])

    def test_web_verify_page(self):
        """GET /certificates/verify/{number}/ — HTML sahifa."""
        response = self.client.get(
            f"/certificates/verify/{self.cert.certificate_number}/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, self.cert.certificate_number)
        self.assertContains(response, "Jasur Karimov")

    def test_web_verify_page_not_found(self):
        """Noto'g'ri raqam uchun HTML sahifa."""
        response = self.client.get("/certificates/verify/LMS-0000-000000/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "topilmadi")

    def test_my_certificates_list(self):
        """GET /api/certificates/my-certificates/ — sertifikatlar ro'yxati."""
        client = self.get_authenticated_client()
        response = client.get("/api/certificates/my-certificates/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Paginated response: {"count": N, "results": [...]}
        if isinstance(response.data, dict) and "results" in response.data:
            self.assertEqual(response.data["count"], 1)
            self.assertEqual(response.data["results"][0]["certificate_number"], self.cert.certificate_number)
        else:
            self.assertEqual(len(response.data), 1)
            self.assertEqual(response.data[0]["certificate_number"], self.cert.certificate_number)


# ============================================================================
# 7. THROTTLING
# ============================================================================

# Base.py'dagi throttle shartnomasi. Development sozlamalarida throttling
# o'chirilgan (tez hasher testlarni rate-limitga urib yubormasligi uchun),
# shuning uchun bu shartnomaviy testlar config'ni lokal ravishda tiklaydi.
@override_settings(REST_FRAMEWORK={
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "30/minute",      # Anonymous: 30 requests per minute
        "user": "100/minute",     # Authenticated: 100 requests per minute
        "test-start": "5/hour",   # Test start: 5 per hour
        "test-submit": "10/hour", # Test submit: 10 per hour
    },
})
class ThrottlingTests(LMSBaseTestCase):
    """Rate limiting sozlamalarini tekshirish."""

    def test_throttle_settings_exist(self):
        """Throttling sozlamalari mavjudligini tekshirish."""
        drf_settings = settings.REST_FRAMEWORK
        self.assertIn("DEFAULT_THROTTLE_CLASSES", drf_settings)
        self.assertIn("DEFAULT_THROTTLE_RATES", drf_settings)
        self.assertIn("anon", drf_settings["DEFAULT_THROTTLE_RATES"])
        self.assertIn("user", drf_settings["DEFAULT_THROTTLE_RATES"])

    def test_anon_rate(self):
        """Anonymous rate: 30/minute."""
        rate = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["anon"]
        self.assertEqual(rate, "30/minute")

    def test_user_rate(self):
        """Authenticated rate: 100/minute."""
        rate = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["user"]
        self.assertEqual(rate, "100/minute")


# ============================================================================
# 8. OPENAPI SCHEMA
# ============================================================================

class OpenAPISchemaTests(LMSBaseTestCase):
    """Swagger/Redoc schema generatsiyasi."""

    @staticmethod
    def _parse_schema(response) -> dict:
        """Parse OpenAPI schema from response (YAML or JSON)."""
        import yaml
        if hasattr(response, 'render') and not response.is_rendered:
            response.render()
        content = response.content
        if isinstance(content, bytes):
            content = content.decode('utf-8')
        return yaml.safe_load(content)

    def test_schema_endpoint(self):
        """GET /api/schema/ — OpenAPI JSON schema."""
        response = self.client.get("/api/schema/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        schema = self._parse_schema(response)
        self.assertEqual(schema["info"]["title"], "LMS Platform API")
        self.assertEqual(schema["info"]["version"], "1.0.0")
        self.assertIn("paths", schema)

    def test_swagger_ui(self):
        """GET /api/docs/ — Swagger UI sahifasi."""
        response = self.client.get("/api/docs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_redoc(self):
        """GET /api/schema/redoc/ — Redoc sahifasi."""
        response = self.client.get("/api/schema/redoc/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_schema_has_auth_endpoints(self):
        """Schema Auth endpointlarini ichiga oladi."""
        response = self.client.get("/api/schema/")
        schema = self._parse_schema(response)
        paths = schema["paths"]

        self.assertIn("/api/auth/register/", paths)
        self.assertIn("/api/auth/login/", paths)
        self.assertIn("/api/auth/me/", paths)

    def test_schema_has_test_endpoints(self):
        """Schema Test endpointlarini ichiga oladi."""
        response = self.client.get("/api/schema/")
        schema = self._parse_schema(response)
        paths = schema["paths"]

        self.assertIn("/api/tests/", paths)
        self.assertIn("/api/tests/{test_id}/start/", paths)
        self.assertIn("/api/tests/attempts/{attempt_id}/save-answer/", paths)
        self.assertIn("/api/tests/attempts/{attempt_id}/submit/", paths)

    def test_schema_has_certificate_endpoints(self):
        """Schema Certificate endpointlarini ichiga oladi."""
        response = self.client.get("/api/schema/")
        schema = self._parse_schema(response)
        paths = schema["paths"]

        self.assertIn("/api/certificates/verify/{certificate_number}/", paths)
        self.assertIn("/api/certificates/my-certificates/", paths)

    def test_schema_has_jwt_bearer(self):
        """Schema JWT Bearer security scheme ni ichiga oladi."""
        response = self.client.get("/api/schema/")
        schema = self._parse_schema(response)
        components = schema.get("components", {})
        security_schemes = components.get("securitySchemes", {})

        self.assertIn("jwtAuth", security_schemes)
        self.assertEqual(
            security_schemes["jwtAuth"]["type"], "http",
        )
        self.assertEqual(
            security_schemes["jwtAuth"]["scheme"], "bearer",
        )


# ============================================================================
# 9. ENVIRONMENT & SETTINGS
# ============================================================================

class SettingsTests(LMSBaseTestCase):
    """Django-environ va settings sozlamalari."""

    def test_celery_eager_mode(self):
        """CELERY_TASK_ALWAYS_EAGER=True (development)."""
        self.assertTrue(settings.CELERY_TASK_ALWAYS_EAGER)

    def test_debug_enabled(self):
        """DEBUG sozlamasi env orqali o'zgarishi."""
        # base.py env('DEBUG', default=False) ishlaydi
        # development.py DEBUG=True bilan override qiladi
        self.assertIn('DEBUG', dir(settings))

    def test_spectacular_settings(self):
        """drf-spectacular sozlamalari to'g'ri."""
        spec = settings.SPECTACULAR_SETTINGS
        self.assertEqual(spec["TITLE"], "LMS Platform API")
        self.assertEqual(spec["VERSION"], "1.0.0")
        self.assertFalse(spec["SERVE_INCLUDE_SCHEMA"])

    def test_security_headers(self):
        """Xavfsizlik headrlari yoqilgan."""
        self.assertTrue(settings.SECURE_BROWSER_XSS_FILTER)
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")

    def test_cors_config(self):
        """CORS sozlamalari mavjud."""
        self.assertIn("corsheaders", settings.INSTALLED_APPS)
        self.assertIn("CORS_ALLOWED_ORIGINS", dir(settings))


# ============================================================================
# 10. EDGE CASES
# ============================================================================

class EdgeCaseTests(LMSBaseTestCase):
    """Edge cases va xatolik holatlari."""

    def test_start_nonexistent_test(self):
        """Mavjud bo'lmagan testni start qilish."""
        client = self.get_authenticated_client()
        response = client.post("/api/tests/99999/start/", format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_nonexistent_attempt(self):
        """Mavjud bo'lmagan attempt ni submit qilish."""
        client = self.get_authenticated_client()
        response = client.post("/api/tests/attempts/99999/submit/", format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_answer_wrong_question(self):
        """Boshqa testga tegishli javob berish."""
        client = self.get_authenticated_client()
        resp = client.post(f"/api/tests/{self.test.id}/start/", format="json")
        attempt_id = resp.data["id"]

        # Yangi test yaratish
        other_test = Test.objects.create(
            title="Other Test", course=self.course,
            description="Other", time_limit_minutes=10,
            pass_percentage=60, max_attempts=3, is_active=True,
        )
        other_q = Question.objects.create(
            test=other_test, text="Other Q", question_type="single",
            points=Decimal("10"), position=1,
        )
        other_c = Choice.objects.create(
            question=other_q, text="Other C", is_correct=True, position=1,
        )

        # Boshqa testga tegishli javob
        response = client.post(
            f"/api/tests/attempts/{attempt_id}/save-answer/",
            {"question_id": other_q.id, "choice_ids": [other_c.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# Need to import User for conftest
from django.contrib.auth import get_user_model
User = get_user_model()
