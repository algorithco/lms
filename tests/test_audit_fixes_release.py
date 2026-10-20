"""
Tests for AUDIT_AND_SOLUTIONS_REPORT fixes:
1. Channels JWT authentication middleware & WebSocket connection.
2. DRF JWT Essay improve and request-review endpoints.
3. Multi-tenant course boundary in school import_test_view.
4. Nginx /admin/ gate hardening on grandec.uz.
5. SPA redirect loop prevention and template-missing auth views.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from apps.arena.consumers import QuizArenaConsumer
from apps.arena.middleware import JwtAuthMiddleware
from apps.core.spa import serve_spa_shell
from apps.courses.models import Course
from apps.essays.models import EssaySubmission, EssayTopic
from apps.tests.models import Test as QuizTest, TestAttempt

User = get_user_model()


class AuditChannelsJwtTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="ws-student@example.com",
            password="testpass123",
            first_name="WS",
            last_name="Student",
        )
        self.token = str(AccessToken.for_user(self.user))

    def test_jwt_middleware_query_string(self):
        async def scenario():
            async def dummy_app(scope, receive, send):
                return scope.get("user")

            app = JwtAuthMiddleware(dummy_app)
            scope = {
                "type": "websocket",
                "query_string": f"token={self.token}".encode("utf-8"),
                "headers": [],
            }
            resolved_user = await app(scope, None, None)
            self.assertEqual(resolved_user, self.user)

        async_to_sync(scenario)()

    def test_jwt_middleware_header(self):
        async def scenario():
            async def dummy_app(scope, receive, send):
                return scope.get("user")

            app = JwtAuthMiddleware(dummy_app)
            scope = {
                "type": "websocket",
                "query_string": b"",
                "headers": [
                    (b"authorization", f"Bearer {self.token}".encode("utf-8")),
                ],
            }
            resolved_user = await app(scope, None, None)
            self.assertEqual(resolved_user, self.user)

        async_to_sync(scenario)()

    def test_jwt_middleware_invalid_token(self):
        async def scenario():
            async def dummy_app(scope, receive, send):
                return scope.get("user")

            app = JwtAuthMiddleware(dummy_app)
            scope = {
                "type": "websocket",
                "query_string": b"token=invalid_jwt_token",
                "headers": [],
            }
            resolved_user = await app(scope, None, None)
            self.assertFalse(resolved_user.is_authenticated)

        async_to_sync(scenario)()

    def test_consumer_connects_with_jwt_query_string(self):
        async def scenario():
            # Wrap QuizArenaConsumer in JwtAuthMiddleware
            app = JwtAuthMiddleware(QuizArenaConsumer.as_asgi())
            comm = WebsocketCommunicator(app, f"/ws/arena/?token={self.token}")
            connected, _ = await comm.connect()
            self.assertTrue(connected)
            event = await comm.receive_json_from()
            self.assertEqual(event.get("type"), "connected")
            self.assertEqual(event.get("user_id"), self.user.id)
            await comm.disconnect()

        async_to_sync(scenario)()

    def test_arena_api_with_jwt_bearer(self):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.token}")
        res = client.get("/arena/api/stats/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("stats", res.json())


class AuditEssaysJwtTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="student-essay@example.com",
            password="testpass123",
            first_name="Student",
            last_name="One",
        )
        self.other_student = User.objects.create_user(
            email="student-other@example.com",
            password="testpass123",
        )
        self.topic = EssayTopic.objects.create(
            title="AI Future",
            description="Discuss AI future.",
            word_limit_min=50,
            word_limit_max=500,
        )
        self.submission = EssaySubmission.objects.create(
            student=self.student,
            topic=self.topic,
            essay_text="This is an essay written about artificial intelligence in modern education.",
            word_count=10,
            status=EssaySubmission.Status.GRADED,
            total_score=20,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.student)

    @patch("apps.essays.services.generate_improved_essay")
    def test_drf_essay_improve_endpoint(self, mock_generate):
        mock_generate.return_value = (
            "Improved essay version with richer vocabulary and grammar."
        )
        res = self.client.post(f"/api/v1/essays/{self.submission.id}/improve/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("ok"))
        self.assertIn("Improved essay", data.get("content", ""))

    def test_drf_essay_improve_permission_denied_for_other(self):
        self.client.force_authenticate(user=self.other_student)
        res = self.client.post(f"/api/v1/essays/{self.submission.id}/improve/")
        self.assertEqual(res.status_code, 404)

    def test_drf_essay_request_review_endpoint(self):
        res = self.client.post(
            f"/api/v1/essays/{self.submission.id}/request-review/",
            {"reason": "Please double check paragraph 2."},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get("ok"))
        self.submission.refresh_from_db()
        self.assertTrue(self.submission.teacher_review_requested)
        self.assertEqual(self.submission.status, EssaySubmission.Status.PENDING_TEACHER)

    def test_legacy_essay_request_review_returns_json_without_template(self):
        # Even on the legacy view, missing review_request_partial.html shouldn't 500
        self.client.force_login(self.student)
        res = self.client.post(
            f"/essays/{self.submission.id}/request-review/",
            {"reason": "Legacy form submit"},
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("ok", res.json())


class AuditSchoolSecurityTests(TestCase):
    def setUp(self):
        self.teacher1 = User.objects.create_user(
            email="teacher1@example.com",
            password="pass",
            role=User.Role.TEACHER,
            can_create_test=True,
        )
        self.teacher2 = User.objects.create_user(
            email="teacher2@example.com",
            password="pass",
            role=User.Role.TEACHER,
            can_create_test=True,
        )
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="pass",
            role=User.Role.ADMIN,
        )
        self.course1 = Course.objects.create(
            title="Teacher 1 Course",
            teacher=self.teacher1,
        )
        self.course2 = Course.objects.create(
            title="Teacher 2 Course",
            teacher=self.teacher2,
        )
        self.client = APIClient()

    def test_teacher_only_sees_own_courses_in_import_test(self):
        self.client.force_authenticate(user=self.teacher1)
        res = self.client.get("/api/v1/school/import-test/")
        self.assertEqual(res.status_code, 200)
        course_ids = [c["id"] for c in res.json()["courses"]]
        self.assertIn(self.course1.id, course_ids)
        self.assertNotIn(self.course2.id, course_ids)

    def test_admin_sees_all_courses_in_import_test(self):
        self.client.force_authenticate(user=self.admin)
        res = self.client.get("/api/v1/school/import-test/")
        self.assertEqual(res.status_code, 200)
        course_ids = [c["id"] for c in res.json()["courses"]]
        self.assertIn(self.course1.id, course_ids)
        self.assertIn(self.course2.id, course_ids)


class AuditNginxHardeningTests(TestCase):
    def test_admin_blocked_on_grandec_uz(self):
        conf_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "deploy",
            "nginx",
            "nginx-ssl.conf",
        )
        with open(conf_path, encoding="utf-8") as f:
            content = f.read()

        # Check grandec.uz SSL block has location /admin/ returning 404
        grandec_block = None
        for block in content.split("server {"):
            if "server_name grandec.uz" in block and "listen 443" in block:
                grandec_block = block
                break

        self.assertIsNotNone(grandec_block)
        self.assertIn("location /admin/ {", grandec_block)
        self.assertIn("return 404;", grandec_block)
        self.assertNotIn(
            "proxy_pass", grandec_block.split("location /admin/ {")[1].split("}")[0]
        )


class AuditSpaAndAuthViewsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @override_settings(DEBUG=True)
    @patch("pathlib.Path.read_text", side_effect=OSError("not found"))
    def test_spa_redirect_loop_prevention_in_debug(self, mock_read):
        request = self.factory.get("/")
        # Path / with fallback / should NOT redirect to / (which would loop)
        res = serve_spa_shell(request, fallback="/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Frontend Unbaked", res.content.decode("utf-8"))

    @override_settings(DEBUG=False)
    @patch("pathlib.Path.read_text", side_effect=OSError("not found"))
    def test_spa_redirect_loop_prevention_in_prod(self, mock_read):
        request = self.factory.get("/")
        res = serve_spa_shell(request, fallback="/")
        self.assertEqual(res.status_code, 503)

    def test_register_and_password_reset_views_no_missing_template(self):
        client = APIClient()
        # GET /register/
        res = client.get("/register/")
        self.assertIn(res.status_code, (200, 302))

        # POST /register/ with bad data
        res_post = client.post(
            "/register/", {"email": "bad"}, HTTP_ACCEPT="application/json"
        )
        self.assertEqual(res_post.status_code, 400)

        # GET /password-reset/
        res_reset = client.get("/password-reset/")
        self.assertIn(res_reset.status_code, (200, 302))

        # GET /password-reset/done/
        res_done = client.get("/password-reset/done/")
        self.assertIn(res_done.status_code, (200, 302))


class AuditModelCollectionTests(TestCase):
    def test_models_have_test_disabled_for_pytest(self):
        self.assertFalse(getattr(QuizTest, "__test__", True))
        self.assertFalse(getattr(TestAttempt, "__test__", True))
