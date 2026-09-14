"""
SPA contract tests — JSON endpoints built for the React frontend.

Covers:
    1. Django session bridge (/api/auth/session/*) for WS arena + session views
    2. Auth identity flags (is_staff / is_superuser / is_platform_admin / language)
    3. Teacher essay review JSON API (/api/v1/essays/teacher/*)
"""
from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.courses.models import StudentGroup
from apps.essays.models import EssayCriterionScore, EssaySubmission, EssayTopic

User = get_user_model()


class SessionBridgeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="bridge@test.com", password="testpass123",
            first_name="Bridge", last_name="User", role="student",
        )
        self.login_url = reverse("accounts:session_login")
        self.status_url = reverse("accounts:session_status")
        self.logout_url = reverse("accounts:session_logout")

    def test_status_anonymous_is_false(self):
        data = self.client.get(self.status_url).json()
        self.assertFalse(data["authenticated"])
        self.assertIsNone(data["user"])

    def test_login_opens_session_and_status_turns_true(self):
        response = self.client.post(
            self.login_url,
            {"email": "bridge@test.com", "password": "testpass123"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        # Django session cookie + CSRF cookie are set for sessionApi/WS use.
        self.assertIn("sessionid", response.cookies)
        self.assertIn("csrftoken", response.cookies)

        status = self.client.get(self.status_url).json()
        self.assertTrue(status["authenticated"])
        self.assertEqual(status["user"]["email"], "bridge@test.com")

    def test_login_rejects_bad_credentials(self):
        response = self.client.post(
            self.login_url,
            {"email": "bridge@test.com", "password": "wrong"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(self.client.get(self.status_url).json()["authenticated"])

    def test_login_requires_both_fields(self):
        response = self.client.post(
            self.login_url, {"email": "bridge@test.com"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_logout_closes_session(self):
        self.client.post(
            self.login_url,
            {"email": "bridge@test.com", "password": "testpass123"},
            content_type="application/json",
        )
        self.assertTrue(self.client.get(self.status_url).json()["authenticated"])
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(self.client.get(self.status_url).json()["authenticated"])

    def test_session_logout_requires_auth(self):
        from rest_framework.test import APIClient
        response = APIClient().post(self.logout_url)
        self.assertIn(response.status_code, (401, 403))


class AuthIdentityFlagTests(TestCase):
    def test_login_and_me_expose_platform_flags(self):
        user = User.objects.create_user(
            email="flags@test.com", password="testpass123", role="teacher",
        )
        response = self.client.post(
            reverse("accounts:token_obtain_pair"),
            {"email": "flags@test.com", "password": "testpass123"},
            content_type="application/json",
        )
        user_data = response.json()["user"]
        self.assertEqual(user_data["role"], "teacher")
        self.assertFalse(user_data["is_platform_admin"])
        self.assertFalse(user_data["is_superuser"])
        self.assertIn(user_data["language"], ("uz", "ru", "en"))

        # JWT login sets no Django session — authenticate explicitly for me.
        self.client.force_login(user)
        me = self.client.get(reverse("accounts:profile")).json()
        self.assertEqual(me["role"], "teacher")
        self.assertFalse(me["is_platform_admin"])
        self.assertIn(me["language"], ("uz", "ru", "en"))

    def test_superuser_student_role_is_platform_admin(self):
        su = User.objects.create_superuser(
            email="su@test.com", password="testpass123",
        )
        su.role = "student"
        su.save(update_fields=["role"])
        self.client.force_login(su)
        me = self.client.get(reverse("accounts:profile")).json()
        self.assertTrue(me["is_superuser"])
        self.assertTrue(me["is_platform_admin"])


class TeacherEssaysApiTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="essay-student@test.com", password="testpass123", role="student",
        )
        self.teacher = User.objects.create_user(
            email="essay-teacher@test.com", password="testpass123", role="teacher",
        )
        self.topic = EssayTopic.objects.create(
            title="Mavzu", description="Tavsif", created_by=self.teacher,
        )
        group = StudentGroup.objects.create(teacher=self.teacher, name="9-A")
        group.students.add(self.student)
        self.sub = EssaySubmission.objects.create(
            student=self.student,
            topic=self.topic,
            essay_text="Esse matni " * 30,
            status=EssaySubmission.Status.PENDING_TEACHER,
            total_score=Decimal("18.0"),
            max_score=24,
            teacher_review_requested=True,
        )
        for i in range(1, 13):
            EssayCriterionScore.objects.create(
                submission=self.sub, criterion_id=i,
                name=f"Mezon {i}", score=Decimal("1.5"),
            )
        self.queue_url = reverse("webapi:essays-teacher-queue")

    def test_student_forbidden_from_queue(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.queue_url).status_code, 403)

    def test_teacher_queue_lists_requested(self):
        self.client.force_login(self.teacher)
        data = self.client.get(self.queue_url).json()
        ids = [s["id"] for s in data["student_requested"]]
        self.assertIn(self.sub.id, ids)
        self.assertEqual(data["pending"], [])

    def test_detail_contains_criteria(self):
        self.client.force_login(self.teacher)
        url = reverse("webapi:essays-teacher-detail", args=[self.sub.id])
        data = self.client.get(url).json()
        self.assertEqual(data["submission"]["id"], self.sub.id)
        self.assertIn("Esse matni", data["submission"]["essay_text"])
        self.assertEqual(len(data["ai_criteria"]), 12)
        self.assertIsNone(data["existing_review"])

    def test_submit_review_finalizes(self):
        self.client.force_login(self.teacher)
        url = reverse("webapi:essays-teacher-review", args=[self.sub.id])
        response = self.client.post(
            url,
            {
                "criteria_scores": {str(i): 1.5 for i in range(1, 13)},
                "teacher_comments": "Yaxshi ish!",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["final_score"], 18.0)
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.status, EssaySubmission.Status.TEACHER_REVIEWED)

    def test_submit_review_rejects_invalid_scores(self):
        self.client.force_login(self.teacher)
        url = reverse("webapi:essays-teacher-review", args=[self.sub.id])
        response = self.client.post(
            url,
            {"criteria_scores": {str(i): 1.3 for i in range(1, 13)}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_student_cannot_submit_review(self):
        self.client.force_login(self.student)
        url = reverse("webapi:essays-teacher-review", args=[self.sub.id])
        response = self.client.post(
            url, {"criteria_scores": {}}, content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
