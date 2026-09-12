"""Regression coverage for Critical/High authorization findings."""
from __future__ import annotations

import json
import io
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import ParentStudentLink
from apps.accounts.services.telegram_link import confirm_link_challenge, link_challenge_status
from apps.courses.models import Category, Course
from apps.essays.models import EssaySubmission, EssayTopic
from apps.essays.services import TeacherReviewService, can_review_submission
from apps.notifications.bot.handlers import _get_or_create_user
from apps.payments.access import can_manage_payments
from apps.results.access import result_queryset_for_user
from apps.results.models import Result
from apps.tests.models import Test, TestAttempt

User = get_user_model()


class PublicRegistrationSecurityTests(TestCase):
    def test_public_api_cannot_assign_teacher_or_admin_role(self):
        for requested_role in ("teacher", "admin"):
            response = self.client.post(
                "/api/auth/register/",
                {
                    "email": f"{requested_role}@example.com",
                    "password": "StrongPass123!",
                    "password_confirm": "StrongPass123!",
                    "first_name": "Public",
                    "last_name": "User",
                    "role": requested_role,
                },
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
            self.assertFalse(
                User.objects.filter(email=f"{requested_role}@example.com").exists()
            )

    def test_public_registration_creates_student(self):
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "student-only@example.com",
                "password": "StrongPass123!",
                "password_confirm": "StrongPass123!",
                "first_name": "Public",
                "last_name": "Student",
                "role": "student",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            User.objects.get(email="student-only@example.com").role,
            User.Role.STUDENT,
        )

    @patch("apps.notifications.services.email_service.EmailService.send_welcome")
    def test_public_web_registration_ignores_teacher_role(self, send_welcome):
        response = self.client.post("/register/", {
            "email": "web-student@example.com",
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "first_name": "Web",
            "last_name": "Student",
            "role": "teacher",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            User.objects.get(email="web-student@example.com").role,
            User.Role.STUDENT,
        )

    def test_teacher_promotion_is_admin_only(self):
        student = User.objects.create_user(email="promote@example.com", password="pass")
        teacher = User.objects.create_user(
            email="ordinary-teacher@example.com", password="pass", role=User.Role.TEACHER,
        )
        admin = User.objects.create_user(
            email="platform-admin@example.com", password="pass", role=User.Role.ADMIN,
        )
        self.client.force_login(teacher)
        self.client.post(f"/manage-teachers/{student.pk}/promote/")
        student.refresh_from_db()
        self.assertEqual(student.role, User.Role.STUDENT)
        self.client.force_login(admin)
        self.client.post(f"/manage-teachers/{student.pk}/promote/")
        student.refresh_from_db()
        self.assertEqual(student.role, User.Role.TEACHER)


class TelegramIdentitySecurityTests(TestCase):
    @patch("apps.telegram_app.views.TelegramMiniAppService.validate_init_data")
    def test_non_numeric_signed_identity_is_rejected_without_credentials(self, validate):
        validate.return_value = {"id": "12345", "username": "anything"}
        response = self.client.post(
            "/tma/api/auth/", {"init_data": "signed"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("tokens", response.json())

    @patch("apps.telegram_app.views.TelegramMiniAppService.validate_init_data")
    def test_recycled_username_never_authenticates_existing_account(self, validate):
        victim = User.objects.create_user(
            email="tg_recycled@telegram.tma",
            password=None,
            telegram_chat_id=2222,
        )
        validate.return_value = {
            "id": 3333,
            "username": "recycled",
            "first_name": "New",
            "last_name": "Owner",
        }

        response = self.client.post(
            "/tma/api/auth/",
            {"init_data": "signed"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()["user"]["id"], victim.id)
        self.assertEqual(User.objects.get(pk=victim.pk).telegram_chat_id, 2222)
        self.assertEqual(
            User.objects.get(pk=response.json()["user"]["id"]).telegram_chat_id,
            3333,
        )

    def test_bot_lookup_uses_numeric_id_even_when_username_matches(self):
        victim = User.objects.create_user(
            email="tg_recycled@telegram.tma",
            password=None,
            telegram_chat_id=4444,
        )
        update = SimpleNamespace(
            effective_user=SimpleNamespace(
                id=5555,
                username="recycled",
                first_name="Other",
                last_name="Person",
            )
        )
        resolved = _get_or_create_user(update)
        self.assertNotEqual(resolved.id, victim.id)
        self.assertEqual(resolved.telegram_chat_id, 5555)

    @patch("apps.telegram_app.views.TelegramMiniAppService.validate_init_data")
    def test_inactive_telegram_user_receives_no_credentials(self, validate):
        user = User.objects.create_user(
            email="disabled@example.com",
            password=None,
            telegram_chat_id=6000,
            telegram_identity_verified_at=timezone.now(),
            is_active=False,
        )
        validate.return_value = {"id": 6000, "first_name": "Disabled"}
        response = self.client.post(
            "/tma/api/auth/",
            {"init_data": "signed"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("tokens", response.json())
        self.assertEqual(User.objects.filter(pk=user.pk).count(), 1)

    def test_raw_chat_id_linking_is_rejected(self):
        user = User.objects.create_user(
            email="web@example.com",
            password="StrongPass123!",
        )
        client = APIClient()
        client.force_authenticate(user)
        response = client.post(
            "/api/auth/telegram/connect/",
            {"chat_id": 987654321},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        user.refresh_from_db()
        self.assertIsNone(user.telegram_chat_id)

    def test_inactive_jwt_cannot_use_tma_or_push_adapters(self):
        inactive = User.objects.create_user(
            email="inactive-adapter@example.com", password="pass", is_active=False,
        )
        token = str(RefreshToken.for_user(inactive).access_token)
        headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
        self.assertEqual(self.client.get("/tma/api/profile/", **headers).status_code, 401)
        self.assertEqual(
            self.client.post(
                "/api/notifications/push/subscribe/",
                data="{}", content_type="application/json", **headers,
            ).status_code,
            401,
        )

    @patch("apps.telegram_app.views.TelegramMiniAppService.validate_init_data")
    def test_legacy_numeric_link_requires_reconciliation(self, validate):
        legacy = User.objects.create_user(
            email="legacy@example.com", password=None, telegram_chat_id=7000,
        )
        validate.return_value = {"id": 7000, "username": "legacy"}
        response = self.client.post(
            "/tma/api/auth/", {"init_data": "signed"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertNotIn("tokens", response.json())
        legacy.refresh_from_db()
        self.assertIsNone(legacy.telegram_identity_verified_at)

    def test_link_requires_signed_bot_confirmation_and_cannot_be_replayed(self):
        user = User.objects.create_user(email="link@example.com", password="StrongPass123!")
        client = APIClient()
        client.force_authenticate(user)
        response = client.post("/api/auth/telegram/connect/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        token = response.data["token"]
        self.assertEqual(link_challenge_status(user, token), "pending")
        user.refresh_from_db()
        self.assertIsNone(user.telegram_chat_id)
        self.assertEqual(confirm_link_challenge(token, 7100), "confirmed")
        self.assertEqual(confirm_link_challenge(token, 7100), "invalid")
        user.refresh_from_db()
        self.assertEqual(user.telegram_chat_id, 7100)
        self.assertIsNotNone(user.telegram_identity_verified_at)
        self.assertEqual(link_challenge_status(user, token), "confirmed")

    def test_link_rejects_numeric_id_owned_by_another_account(self):
        user = User.objects.create_user(email="link2@example.com", password="pass")
        owner = User.objects.create_user(
            email="owner2@example.com", password=None,
            telegram_chat_id=7200, telegram_identity_verified_at=timezone.now(),
        )
        client = APIClient()
        client.force_authenticate(user)
        token = client.post("/api/auth/telegram/connect/", {}, format="json").data["token"]
        self.assertEqual(confirm_link_challenge(token, 7200), "conflict")
        user.refresh_from_db()
        owner.refresh_from_db()
        self.assertIsNone(user.telegram_chat_id)
        self.assertEqual(owner.telegram_chat_id, 7200)

    def test_legacy_reconciliation_requires_matching_id_and_evidence(self):
        user = User.objects.create_user(
            email="reconcile@example.com", password=None, telegram_chat_id=7300,
        )
        with self.assertRaises(CommandError):
            call_command("reconcile_telegram_identity", user_id=user.pk, telegram_id=7301, evidence="ticket-1")
        user.refresh_from_db()
        self.assertIsNone(user.telegram_identity_verified_at)
        with self.assertRaises(CommandError):
            call_command("reconcile_telegram_identity", user_id=user.pk, telegram_id=7300)
        call_command(
            "reconcile_telegram_identity", user_id=user.pk,
            telegram_id=7300, evidence="ticket-1", stdout=io.StringIO(),
        )
        user.refresh_from_db()
        self.assertIsNotNone(user.telegram_identity_verified_at)


class TelegramWebhookSecurityTests(TestCase):
    @override_settings(TELEGRAM_WEBHOOK_MODE=True, TELEGRAM_WEBHOOK_SECRET="")
    def test_deployment_check_rejects_missing_secret_in_webhook_mode(self):
        from django.core.checks import run_checks
        errors = run_checks(include_deployment_checks=True)
        self.assertIn("notifications.E001", [error.id for error in errors])

    @override_settings(TELEGRAM_WEBHOOK_SECRET="", TELEGRAM_BOT_TOKEN="token")
    @patch("apps.notifications.views._get_bot_app")
    def test_missing_secret_fails_closed_before_bot_initialization(self, get_app):
        response = self.client.post(
            "/api/notifications/telegram/webhook/",
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)
        get_app.assert_not_called()

    @override_settings(TELEGRAM_WEBHOOK_SECRET="expected", TELEGRAM_BOT_TOKEN="token")
    @patch("apps.notifications.views._get_bot_app")
    def test_invalid_secret_is_rejected_before_bot_initialization(self, get_app):
        response = self.client.post(
            "/api/notifications/telegram/webhook/",
            data="{}",
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="wrong",
        )
        self.assertEqual(response.status_code, 401)
        get_app.assert_not_called()

    @override_settings(TELEGRAM_WEBHOOK_SECRET="expected", TELEGRAM_BOT_TOKEN="token")
    @patch("telegram.Update.de_json", return_value=object())
    @patch("apps.notifications.views._get_bot_app")
    def test_valid_secret_processes_update(self, get_app, de_json):
        app = SimpleNamespace(bot=object(), process_update=AsyncMock())
        get_app.return_value = app
        response = self.client.post(
            "/api/notifications/telegram/webhook/",
            data=json.dumps({"update_id": 1}),
            content_type="application/json",
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="expected",
        )
        self.assertEqual(response.status_code, 200)
        de_json.assert_called_once()
        app.process_update.assert_awaited_once()


class AuthorizationMatrixSecurityTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="owner@example.com", password="x", role=User.Role.TEACHER,
        )
        self.other_teacher = User.objects.create_user(
            email="other@example.com", password="x", role=User.Role.TEACHER,
        )
        self.student = User.objects.create_user(
            email="student@example.com", password="x", role=User.Role.STUDENT,
        )
        self.parent = User.objects.create_user(
            email="parent@example.com", password="x", role=User.Role.PARENT,
        )
        self.admin = User.objects.create_user(
            email="admin@example.com", password="x", role=User.Role.ADMIN,
        )
        category = Category.objects.create(name="Security")
        self.course = Course.objects.create(
            teacher=self.teacher,
            category=category,
            title="Authorized course",
            description="",
        )
        self.test = Test.objects.create(
            course=self.course,
            title="Authorization test",
            time_limit_minutes=10,
            pass_percentage=60,
        )
        attempt = TestAttempt.objects.create(
            test=self.test,
            student=self.student,
            status=TestAttempt.Status.COMPLETED,
        )
        self.result = Result.objects.create(
            attempt=attempt,
            student=self.student,
            test=self.test,
            course=self.course,
            total_questions=0,
            correct_answers=0,
            wrong_answers=0,
            score=Decimal("0"),
            max_score=Decimal("0"),
            percentage=Decimal("0"),
            is_passed=False,
            time_taken_seconds=0,
        )

    def test_parent_sees_only_approved_linked_student_results(self):
        self.assertFalse(result_queryset_for_user(self.parent).exists())
        link = ParentStudentLink.objects.create(
            parent=self.parent,
            student=self.student,
            is_approved=False,
        )
        self.assertFalse(result_queryset_for_user(self.parent).exists())
        link.is_approved = True
        link.save(update_fields=["is_approved"])
        self.assertEqual(
            list(result_queryset_for_user(self.parent)),
            [self.result],
        )

    def test_unrelated_teacher_cannot_see_result(self):
        self.assertFalse(
            result_queryset_for_user(self.other_teacher)
            .filter(pk=self.result.pk)
            .exists()
        )

    def test_ordinary_teacher_cannot_manage_payments(self):
        self.assertFalse(can_manage_payments(self.teacher))
        self.teacher.is_staff = True
        self.teacher.save(update_fields=["is_staff"])
        self.assertFalse(can_manage_payments(self.teacher))
        self.assertTrue(can_manage_payments(self.admin))
        from django.contrib.admin.sites import AdminSite
        from apps.payments.admin import PaymentRequestAdmin
        from apps.payments.models import PaymentRequest
        from django.test import RequestFactory
        request = RequestFactory().get("/admin/payments/paymentrequest/")
        request.user = self.teacher
        admin = PaymentRequestAdmin(PaymentRequest, AdminSite())
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request))
        self.assertFalse(admin.has_delete_permission(request))
        from django.contrib.auth.models import Permission
        permission = Permission.objects.get(
            codename="change_paymentrequest", content_type__app_label="payments",
        )
        self.teacher.user_permissions.add(permission)
        self.assertTrue(can_manage_payments(User.objects.get(pk=self.teacher.pk)))

    def test_unrelated_teacher_and_unlinked_parent_cannot_open_result_endpoints(self):
        for user in (self.other_teacher, self.parent):
            self.client.force_login(user)
            api = self.client.get(f"/api/results/{self.result.pk}/detail/")
            self.assertIn(api.status_code, (403, 404))
            page = self.client.get(f"/results/{self.result.pk}/")
            self.assertIn(page.status_code, (403, 404))
            self.client.logout()

    def test_teacher_cannot_review_unrelated_essay_via_web(self):
        topic = EssayTopic.objects.create(
            title="Teacher owned", description="", created_by=self.teacher,
        )
        submission = EssaySubmission.objects.create(
            student=self.student, topic=topic, essay_text="Text",
            status=EssaySubmission.Status.PENDING_TEACHER,
            assigned_reviewer=self.teacher,
        )
        self.client.force_login(self.other_teacher)
        response = self.client.post(
            f"/essays/teacher/{submission.pk}/submit-review/",
            {f"score_{i}": "1" for i in range(1, 13)},
        )
        self.assertIn(response.status_code, (403, 404))
        submission.refresh_from_db()
        self.assertEqual(submission.status, EssaySubmission.Status.PENDING_TEACHER)

    def test_unrelated_teacher_cannot_review_essay_at_service_layer(self):
        topic = EssayTopic.objects.create(
            title="Owned topic",
            description="",
            created_by=self.teacher,
        )
        submission = EssaySubmission.objects.create(
            student=self.student,
            topic=topic,
            essay_text="Text",
            status=EssaySubmission.Status.PENDING_TEACHER,
            assigned_reviewer=self.teacher,
        )
        self.assertFalse(can_review_submission(self.other_teacher, submission))
        with self.assertRaises(PermissionDenied):
            TeacherReviewService.submit_review(
                submission,
                self.other_teacher,
                {criterion_id: 1 for criterion_id in range(1, 13)},
            )
