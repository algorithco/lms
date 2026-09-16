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


def _ignore_missing_dir(path):
    try:
        path.rmdir()
    except OSError:
        pass


class TmaPageTests(TestCase):
    """GET /tma/ (bot web_app button) serves the SPA shell (no redirect loop)."""
    def _write_baked_shell(self):
        from pathlib import Path

        from django.conf import settings

        spa_dir = Path(settings.BASE_DIR) / "spa"
        spa_dir.mkdir(exist_ok=True)
        index = spa_dir / "index.html"
        index.write_text(
            '<div id="root"></div><script src="/assets/app.js"></script>',
            encoding="utf-8",
        )
        # addCleanup runs LIFO: unlink first, then remove the dir we created.
        self.addCleanup(_ignore_missing_dir, spa_dir)
        self.addCleanup(index.unlink, True)

    def test_tma_page_serves_spa_shell(self):
        self._write_baked_shell()
        response = self.client.get(reverse("telegram_app:index"))
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="root"', response.content.decode())
        self.assertIn("/assets/", response.content.decode())

    def test_tma_page_serves_shell_with_query_string(self):
        self._write_baked_shell()
        response = self.client.get(reverse("telegram_app:index") + "?tgWebAppData=abc")
        self.assertEqual(response.status_code, 200)
        self.assertIn('id="root"', response.content.decode())

    def test_tma_page_falls_back_to_spa_route_without_baked_build(self):
        # Dev bind-mount hides /app/spa — old redirect semantics preserved.
        response = self.client.get(reverse("telegram_app:index"))
        if response.status_code == 200:
            self.skipTest("baked SPA shell present in this environment")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/tma")


class LegacyPageShellTests(TestCase):
    """Retired HTML pages (payments/essays/arena) serve the SPA shell.

    Regression for grandec.uz/subscribe/ → Server Error (500): the page
    templates were removed in the SPA cutover, so render() raised
    TemplateDoesNotExist. Page views now answer with spa/index.html
    (prod, baked) or a SPA-route redirect (dev, unbaked) — never 500.
    """

    def setUp(self):
        from apps.arena.models import ArenaRoom
        from apps.payments.models import SubscriptionPlan

        self.student = User.objects.create_user(
            email="shell-student@test.com", password="testpass123", role="student",
        )
        self.teacher = User.objects.create_user(
            email="shell-teacher@test.com", password="testpass123", role="teacher",
        )
        self.topic = EssayTopic.objects.create(
            title="Shell mavzu", description="Tavsif", created_by=self.teacher,
        )
        self.sub = EssaySubmission.objects.create(
            student=self.student,
            topic=self.topic,
            essay_text="Esse matni " * 30,
            status=EssaySubmission.Status.DRAFT,
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Pro", plan_type="pro", description="Pro reja",
            price_monthly=Decimal("49000"), is_active=True,
        )
        self.room = ArenaRoom.objects.create(
            room_code="SHELL01", player1=self.student,
        )
        self.pages = [
            reverse("payments:plans"),
            reverse("payments:subscribe", args=[self.plan.id]),
            reverse("payments:my-subscription"),
            reverse("essays:topics"),
            reverse("essays:password-gate", args=[self.topic.id]),
            reverse("essays:write", args=[self.sub.id]),
            reverse("essays:result", args=[self.sub.id]),
            reverse("essays:submit-new"),
            reverse("arena:lobby"),
            reverse("arena:room", args=[self.room.room_code]),
        ]

    def _write_baked_shell(self):
        from pathlib import Path

        from django.conf import settings

        spa_dir = Path(settings.BASE_DIR) / "spa"
        spa_dir.mkdir(exist_ok=True)
        index = spa_dir / "index.html"
        index.write_text(
            '<div id="root"></div><script src="/assets/app.js"></script>',
            encoding="utf-8",
        )
        self.addCleanup(_ignore_missing_dir, spa_dir)
        self.addCleanup(index.unlink, True)

    def test_pages_serve_shell_when_baked(self):
        self._write_baked_shell()
        self.client.force_login(self.student)
        for url in self.pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertIn('id="root"', response.content.decode())

    def test_pages_never_500_without_baked_build(self):
        self.client.force_login(self.student)
        for url in self.pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(response.status_code, (200, 302))

    def test_bogus_ids_still_404(self):
        self.client.force_login(self.student)
        self.assertEqual(
            self.client.get(
                reverse("payments:subscribe", args=[99999])
            ).status_code, 404,
        )
        self.assertEqual(
            self.client.get(reverse("arena:room", args=["NOPE00"])).status_code, 404,
        )
