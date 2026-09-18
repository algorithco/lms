"""Regression coverage for product-facing authentication and permissions."""
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path
import re
import os
import subprocess
import sys
from types import SimpleNamespace
from urllib.parse import urlsplit
from unittest.mock import AsyncMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.core.files.storage import storages
from django.test import TestCase, override_settings
from django.test import Client, SimpleTestCase
from django.urls import reverse
from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator

from apps.accounts.access import is_platform_admin
from apps.accounts.models import Profile
from apps.accounts.services.telegram_identity import (
    TelegramAuthAmbiguous,
    TelegramAuthConflict,
    TelegramIdentityUnverified,
    find_users_by_phone,
    normalize_phone,
    resolve_bot_auth_user,
)
from apps.courses.models import Course, StudentGroup
from apps.tests.models import Test as LmsTest
from apps.core.translations import TRANSLATIONS, get_user_language, t
from apps.notifications.models import PushSubscription, TelegramAuthToken
from apps.notifications.bot.handlers import _handle_auth_token, start_handler
from rest_framework_simplejwt.tokens import RefreshToken
import json
import urllib.parse
from io import BytesIO
from apps.accounts.google_auth import _verified_claims


User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    SITE_URL="https://lms.example.test",
)
class PasswordResetFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="reset@example.test", password="OldStrongPass123!",
        )

    def _request_link(self):
        response = self.client.post(
            reverse("accounts:password_reset_request"), {"email": self.user.email},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        return next(
            line.strip() for line in body.splitlines()
            if "/password-reset/confirm/" in line
        )

    @staticmethod
    def _split_link(link):
        parts = urlsplit(link).path.rstrip("/").split("/")
        return parts[-2], parts[-1]

    def test_unknown_email_has_same_response_and_no_mail(self):
        response = self.client.post(
            reverse("accounts:password_reset_request"), {"email": "missing@example.test"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(mail.outbox, [])

    def test_token_changes_password_and_cannot_be_reused(self):
        link = self._request_link()
        uid, token = self._split_link(link)
        url = reverse("accounts:password_reset_confirm_api")
        weak = self.client.post(
            url, {"uid": uid, "token": token, "new_password1": "123", "new_password2": "123"},
            content_type="application/json",
        )
        self.assertEqual(weak.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldStrongPass123!"))
        success = self.client.post(
            url, {
                "uid": uid, "token": token,
                "new_password1": "NewStrongPass123!",
                "new_password2": "NewStrongPass123!",
            },
            content_type="application/json",
        )
        self.assertEqual(success.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewStrongPass123!"))
        self.assertFalse(self.user.check_password("OldStrongPass123!"))
        reused = self.client.post(
            url, {
                "uid": uid, "token": token,
                "new_password1": "AnotherStrong123!",
                "new_password2": "AnotherStrong123!",
            },
            content_type="application/json",
        )
        self.assertEqual(reused.status_code, 400)

    def test_token_expires_after_one_hour(self):
        link = self._request_link()
        uid, token = self._split_link(link)
        future = datetime.now() + timedelta(hours=1, seconds=2)
        with patch.object(default_token_generator, "_now", return_value=future):
            response = self.client.post(
                reverse("accounts:password_reset_confirm_api"),
                {
                    "uid": uid, "token": token,
                    "new_password1": "NewStrongPass123!",
                    "new_password2": "NewStrongPass123!",
                },
                content_type="application/json",
            )
        self.assertEqual(response.status_code, 400)

    def test_rate_limit_keeps_generic_response(self):
        for _ in range(4):
            response = self.client.post(
                reverse("accounts:password_reset_request"), {"email": self.user.email},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 3)

    @override_settings(DEBUG=False, SITE_URL="https://lms.example.test")
    def test_production_link_uses_trusted_https_origin(self):
        link = self._request_link()
        self.assertTrue(link.startswith("https://lms.example.test/password-reset/confirm/"))

    def test_email_localized_in_all_three_languages(self):
        for lang in ("uz", "ru", "en"):
            cache.clear()
            mail.outbox.clear()
            session = self.client.session
            session["language"] = lang
            session.save()
            self._request_link()
            self.assertIn(t("reset_email_subject", lang), mail.outbox[0].subject)
            self.assertIn(t("reset_email_body", lang), mail.outbox[0].body)
            self.assertIn(
                t("reset_email_action", lang),
                unescape(mail.outbox[0].alternatives[0].content),
            )


class PlatformAdminPolicyTests(TestCase):
    def test_staff_flag_alone_does_not_grant_platform_admin(self):
        staff = User.objects.create_user(
            email="staff-only@example.test", password="pass", role="teacher", is_staff=True,
        )
        self.assertFalse(is_platform_admin(staff))
        self.client.force_login(staff)
        self.assertEqual(self.client.get("/api/v1/panel/users/").status_code, 403)
        # ...but staff still counts as teacher for the school API.
        self.assertEqual(self.client.get("/api/v1/school/teacher/").status_code, 200)

    def test_role_admin_and_superuser_reach_panel(self):
        role_admin = User.objects.create_user(
            email="role-admin@example.test", password="pass", role="admin",
        )
        superuser = User.objects.create_superuser(
            email="superuser@example.test", password="pass", role="student",
        )
        for user in (role_admin, superuser):
            self.client.force_login(user)
            self.assertEqual(self.client.get("/api/v1/panel/users/").status_code, 200)

    def test_inactive_admin_denied(self):
        user = User.objects.create_user(
            email="inactive-admin@example.test", password="pass", role="admin",
            is_active=False,
        )
        self.assertFalse(is_platform_admin(user))

    def test_superuser_with_student_role_sees_unpublished_tests(self):
        teacher = User.objects.create_user(email="test-owner@example.test", password="pass", role="teacher")
        course = Course.objects.create(teacher=teacher, title="Private course", description="Course")
        test = LmsTest.objects.create(course=course, title="Private assessment", is_active=False)
        superuser = User.objects.create_superuser(
            email="student-superuser@example.test", password="pass", role="student",
        )
        self.client.force_login(superuser)
        titles = [t["title"] for t in self.client.get("/api/tests/").json()["results"]]
        self.assertIn(test.title, titles)
        self.assertEqual(self.client.get(f"/api/tests/{test.pk}/").status_code, 200)

    def test_admin_can_manage_other_teachers_group_without_opening_teacher_access(self):
        teacher = User.objects.create_user(email="group-owner@example.test", password="pass", role="teacher")
        other_teacher = User.objects.create_user(email="other-teacher@example.test", password="pass", role="teacher")
        admin = User.objects.create_user(email="groups-admin@example.test", password="pass", role="admin")
        group = StudentGroup.objects.create(teacher=teacher, name="9-A")
        self.client.force_login(other_teacher)
        self.assertEqual(self.client.get(f"/api/v1/school/groups/{group.pk}/").status_code, 404)
        self.client.force_login(admin)
        names = [g["name"] for g in self.client.get("/api/v1/school/groups/").json()]
        self.assertIn("9-A", names)
        self.assertEqual(self.client.get(f"/api/v1/school/groups/{group.pk}/").status_code, 200)


class LanguagePersistenceTests(TestCase):
    def test_default_language_is_uzbek(self):
        user = User.objects.create_user(
            email="default-lang@example.test", password="pass",
        )
        self.assertEqual(user.language, "uz")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("accounts:profile")).json()["language"], "uz")

    def test_language_survives_pages_and_logout(self):
        User.objects.create_user(
            email="language@example.test", password="StrongPass123!", role="student",
        )
        response = self.client.get(
            reverse("web:set-language", args=["ru"]), HTTP_REFERER="/login/",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/login/")
        self.assertEqual(response.cookies["language"].value, "ru")

    def test_account_preference_served_via_profile(self):
        user = User.objects.create_user(
            email="english@example.test", password="pass", language="en",
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("accounts:profile")).json()["language"], "en")

    def test_profile_language_update_and_validation(self):
        user = User.objects.create_user(
            email="switcher@example.test", password="pass", language="uz",
        )
        self.client.force_login(user)
        response = self.client.patch(
            reverse("accounts:profile"), {"language": "ru"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["language"], "ru")
        user.refresh_from_db()
        self.assertEqual(user.language, "ru")
        bad = self.client.patch(
            reverse("accounts:profile"), {"language": "de"},
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, 400)

    def test_language_switch_rejects_external_redirect(self):
        response = self.client.get(
            reverse("web:set-language", args=["en"]),
            HTTP_REFERER="https://evil.example/phish",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_all_literal_template_translation_keys_exist(self):
        keys = set()
        for path in Path("templates").rglob("*.html"):
            keys.update(re.findall(r'{%\s*t\s+"([^"]+)"', path.read_text(encoding="utf-8")))
        for lang, entries in TRANSLATIONS.items():
            self.assertFalse(keys - entries.keys(), f"missing {lang}: {keys - entries.keys()}")


class PushCsrfTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="push@example.test", password="pass",
        )
        self.body = json.dumps({
            "endpoint": "https://push.example.test/subscription",
            "p256dh": "public-key", "auth": "auth-key",
        })

    def test_session_write_requires_csrf_but_valid_csrf_succeeds(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        url = reverse("notifications:push-subscribe")
        self.assertEqual(
            client.post(url, self.body, content_type="application/json").status_code,
            403,
        )
        self.assertFalse(PushSubscription.objects.exists())
        client.get(reverse("notifications:push-vapid-key"))
        response = client.post(
            url, self.body, content_type="application/json",
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PushSubscription.objects.count(), 1)

    def test_jwt_write_does_not_need_browser_csrf(self):
        client = Client(enforce_csrf_checks=True)
        token = str(RefreshToken.for_user(self.user).access_token)
        response = client.post(
            reverse("notifications:push-subscribe"), self.body,
            content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(response.status_code, 200)


class ProductionStorageTests(TestCase):
    def test_static_storage_uses_manifest_backend(self):
        from config.settings.base import STORAGES as configured_storages
        self.assertEqual(
            configured_storages["staticfiles"]["BACKEND"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )


class DashboardEmptyStateTests(TestCase):
    def test_teacher_with_no_results_gets_empty_overview(self):
        teacher = User.objects.create_user(email="empty-teacher@example.test", password="pass", role="teacher")
        self.client.force_login(teacher)
        response = self.client.get("/api/v1/school/teacher/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["recent_results"], [])
        self.assertEqual(response.json()["groups"], [])


class TelegramLoginReplayTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="telegram-replay@example.test", password="pass", role="student",
        )

    def test_pending_token_is_not_deleted_before_advertised_expiry(self):
        token = TelegramAuthToken.objects.create(token="pending-six-minutes")
        TelegramAuthToken.objects.filter(pk=token.pk).update(
            created_at=timezone.now() - timedelta(minutes=6),
        )

        response = self.client.post(reverse("notifications:tg-auth-start"))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(TelegramAuthToken.objects.filter(pk=token.pk).exists())

    def _verified_token(self, code="123456"):
        response = self.client.post(reverse("notifications:tg-auth-start"))
        self.assertEqual(response.status_code, 200)
        token = response.json()["token"]
        TelegramAuthToken.objects.filter(token=token).update(
            is_verified=True, user=self.user, short_code=code,
        )
        return token

    def test_token_is_bound_to_starting_session_post_only_and_single_use(self):
        token = self._verified_token()
        status_url = reverse("notifications:tg-auth-status", args=[token])
        login_url = reverse("notifications:tg-auth-login", args=[token])
        self.assertEqual(self.client.get(status_url).json()["login_url"], login_url)
        self.assertEqual(self.client.get(login_url).status_code, 405)
        other_browser = Client()
        self.assertEqual(other_browser.get(status_url).status_code, 404)
        self.assertEqual(other_browser.post(login_url).status_code, 404)
        self.assertFalse("_auth_user_id" in other_browser.session)
        self.assertEqual(self.client.post(login_url).status_code, 200)
        self.assertIsNotNone(TelegramAuthToken.objects.get(token=token).consumed_at)
        self.assertEqual(self.client.post(login_url).status_code, 404)
        self.assertEqual(other_browser.post(login_url).status_code, 404)


    def test_token_login_returns_jwt_pair_for_spa(self):
        token = self._verified_token()
        login_url = reverse("notifications:tg-auth-login", args=[token])
        response = self.client.post(login_url)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertIn("access", body["tokens"])
        self.assertIn("refresh", body["tokens"])
        self.assertEqual(body["user"]["email"], self.user.email)
        self.assertIn("role", body["user"])

    def test_short_code_cannot_be_replayed_or_used_for_ambiguous_account(self):
        token = self._verified_token()
        url = reverse("notifications:tg-auth-code-login")
        body = json.dumps({"code": "123456"})
        second = Client()
        code_response = second.post(url, body, content_type="application/json")
        self.assertEqual(code_response.status_code, 200)
        code_body = code_response.json()
        self.assertIn("access", code_body["tokens"])
        self.assertIn("refresh", code_body["tokens"])
        self.assertEqual(code_body["user"]["email"], self.user.email)
        self.assertEqual(self.client.post(url, body, content_type="application/json").status_code, 404)
        self.assertIsNotNone(TelegramAuthToken.objects.get(token=token).consumed_at)
        other = User.objects.create_user(email="telegram-other@example.test", password="pass")
        TelegramAuthToken.objects.create(token="duplicate-a", user=self.user, is_verified=True, short_code="777777")
        TelegramAuthToken.objects.create(token="duplicate-b", user=other, is_verified=True, short_code="777777")
        self.assertEqual(Client().post(url, json.dumps({"code": "777777"}), content_type="application/json").status_code, 404)


class TelegramBotLoginUXTests(TestCase):
    def test_website_deep_link_reaches_bot_and_completes_status(self):
        user = User.objects.create_user(
            email="deep-link@example.test",
            password=None,
            first_name="Deep",
            last_name="Link",
            telegram_chat_id=99887767,
            telegram_identity_verified_at=timezone.now(),
        )
        start = self.client.post(reverse("notifications:tg-auth-start"))
        self.assertEqual(start.status_code, 200)
        body = start.json()
        payload = urllib.parse.parse_qs(urlsplit(body["deep_link"]).query)["start"][0]
        self.assertEqual(payload, f"auth_{body['token']}")

        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(
            effective_user=SimpleNamespace(
                id=user.telegram_chat_id,
                first_name=user.first_name,
                last_name=user.last_name,
            ),
            message=message,
        )
        context = SimpleNamespace(args=[payload], user_data={})
        async_to_sync(start_handler)(update, context)

        auth_token = TelegramAuthToken.objects.get(token=body["token"])
        self.assertTrue(auth_token.is_verified)
        status_url = reverse("notifications:tg-auth-status", args=[body["token"]])
        status = self.client.get(status_url)
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["status"], "verified")

    def test_plain_start_shows_normal_instructions(self):
        user = User.objects.create_user(
            email="plain-start@example.test",
            password=None,
            first_name="Plain",
            telegram_chat_id=99887768,
            telegram_identity_verified_at=timezone.now(),
        )
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(
            effective_user=SimpleNamespace(
                id=user.telegram_chat_id,
                first_name=user.first_name,
                last_name="",
            ),
            message=message,
        )
        context = SimpleNamespace(args=[], user_data={})

        async_to_sync(start_handler)(update, context)

        reply = message.reply_text.await_args.args[0]
        self.assertIn("Ona Tili & Adabiyot", reply)
        self.assertNotIn("Noto'g'ri yoki eskirgan token", reply)

    def test_already_linked_account_does_not_require_phone_share(self):
        user = User.objects.create_user(
            email="linked-bot@example.test",
            password=None,
            first_name="Linked",
            last_name="User",
            telegram_chat_id=99887766,
            telegram_identity_verified_at=timezone.now(),
        )
        token = TelegramAuthToken.objects.create(token="linked-bot-token")
        message = SimpleNamespace(reply_text=AsyncMock())
        update = SimpleNamespace(
            effective_user=SimpleNamespace(
                id=99887766,
                first_name="Linked",
                last_name="User",
            ),
            message=message,
        )
        context = SimpleNamespace(user_data={})

        async_to_sync(_handle_auth_token)(update, context, f"auth_{token.token}")

        token.refresh_from_db()
        self.assertTrue(token.is_verified)
        self.assertEqual(token.user_id, user.pk)
        self.assertFalse(token.phone_verified)
        self.assertEqual(token.phone_number, "")
        reply = message.reply_text.await_args.args[0]
        self.assertIn("Telegram hisobingiz tasdiqlandi", reply)
        self.assertNotIn("Telefonni yuborish", reply)


class TelegramPhoneMatchingTests(TestCase):
    """Website users must match their existing account by verified phone."""

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            email="phone-match@example.test", password="pass", role="student",
        )
        Profile.objects.filter(user=self.user).update(phone="+998 90 123-45-67")

    def _set_user_fields(self, user, **fields):
        # Queryset update (NOT user.save()): the post_save profile signal
        # would otherwise persist a stale in-memory profile over our edit.
        User.objects.filter(pk=user.pk).update(**fields)
        user.refresh_from_db()

    def test_normalize_phone(self):
        self.assertEqual(normalize_phone("+998 90 123-45-67"), "998901234567")
        self.assertEqual(normalize_phone("998901234567"), "998901234567")
        self.assertEqual(normalize_phone("short"), "")
        self.assertEqual(normalize_phone(""), "")

    def test_find_users_by_phone_matches_format_variants(self):
        found = find_users_by_phone("+998901234567")
        self.assertEqual([u.pk for u in found], [self.user.pk])

    def test_resolve_by_phone_links_identity(self):
        user, how = resolve_bot_auth_user(777000111, "+998901234567")
        self.assertEqual(user.pk, self.user.pk)
        self.assertEqual(how, "phone")
        self.user.refresh_from_db()
        self.assertEqual(self.user.telegram_chat_id, 777000111)
        self.assertIsNotNone(self.user.telegram_identity_verified_at)

    def test_resolve_by_telegram_link_wins(self):
        from django.utils import timezone
        self._set_user_fields(
            self.user, telegram_chat_id=777000111,
            telegram_identity_verified_at=timezone.now(),
        )
        user, how = resolve_bot_auth_user(777000111, "+998901234567")
        self.assertEqual(user.pk, self.user.pk)
        self.assertEqual(how, "tg")

    def test_resolve_conflict_when_phone_and_telegram_differ(self):
        other = User.objects.create_user(email="phone-other@example.test", password="pass")
        from django.utils import timezone
        self._set_user_fields(
            other, telegram_chat_id=777000222,
            telegram_identity_verified_at=timezone.now(),
        )
        with self.assertRaises(TelegramAuthConflict):
            resolve_bot_auth_user(777000222, "+998901234567")

    def test_resolve_ambiguous_when_phone_shared(self):
        other = User.objects.create_user(email="phone-dup@example.test", password="pass")
        Profile.objects.filter(user=other).update(phone="998901234567")
        with self.assertRaises(TelegramAuthAmbiguous):
            resolve_bot_auth_user(777000333, "+998901234567")

    def test_resolve_none_for_unknown_number(self):
        user, how = resolve_bot_auth_user(777000444, "+998907654321")
        self.assertIsNone(user)
        self.assertEqual(how, "none")

    def test_resolve_rejects_inactive_account(self):
        self._set_user_fields(self.user, is_active=False)
        with self.assertRaises(ValueError):
            resolve_bot_auth_user(777000555, "+998901234567")

    def test_resolve_rejects_unverified_legacy_link(self):
        self._set_user_fields(
            self.user, telegram_chat_id=777000666,
            telegram_identity_verified_at=None,
        )
        with self.assertRaises(TelegramIdentityUnverified):
            resolve_bot_auth_user(777000666, "+998901234567")

    def test_code_login_returns_phone_matched_existing_user(self):
        """End-to-end: verified token for the phone-matched user logs THEM in."""
        from django.utils import timezone
        self._set_user_fields(
            self.user, telegram_chat_id=555000111,
            telegram_identity_verified_at=timezone.now(),
        )
        token = TelegramAuthToken.objects.create(
            token="phone-login-token",
            user=self.user,
            is_verified=True,
            phone_number="+998901234567",
            phone_verified=True,
            short_code="654321",
        )
        url = reverse("notifications:tg-auth-code-login")
        body = json.dumps({"code": "654321"})
        response = Client().post(url, body, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["email"], "phone-match@example.test")
        self.assertIn("access", response.json()["tokens"])
        token.refresh_from_db()
        self.assertIsNotNone(token.consumed_at)


class GoogleOAuthLinkingTests(TestCase):
    class TokenResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"id_token":"signed-token"}'

    def setUp(self):
        self.existing = User.objects.create_user(
            email="existing-google@example.test", password="StrongPass123!",
        )

    @override_settings(GOOGLE_CLIENT_ID="client-id", GOOGLE_CLIENT_SECRET="client-secret", GOOGLE_REDIRECT_URI="https://lms.example.test/api/auth/google/callback/")
    def test_google_oauth_routes_are_wired(self):
        # The server-rendered login/test-list pages are retired (SPA owns them);
        # OAuth start/callback endpoints themselves stay covered below.
        start = self.client.get(reverse("accounts:google_auth_start"))
        self.assertEqual(start.status_code, 302)

    def _callback(self, claims, *, authenticated=False):
        if authenticated:
            self.client.force_login(self.existing)
        start = self.client.get(reverse("accounts:google_auth_start"))
        self.assertEqual(start.status_code, 302)
        state = urllib.parse.parse_qs(urllib.parse.urlsplit(start.url).query)["state"][0]
        nonce = self.client.session["google_oauth_nonce"]
        claims = dict(claims, nonce=nonce)
        with patch("urllib.request.urlopen", return_value=self.TokenResponse()), patch(
            "google.oauth2.id_token.verify_oauth2_token", return_value=claims,
        ) as verify:
            response = self.client.get(reverse("accounts:google_auth_callback"), {
                "code": "authorization-code", "state": state,
            })
        self.assertEqual(verify.call_args.args[2], "client-id")
        return response

    @override_settings(GOOGLE_CLIENT_ID="client-id", GOOGLE_CLIENT_SECRET="client-secret", GOOGLE_REDIRECT_URI="https://lms.example.test/api/auth/google/callback/")
    def test_existing_email_is_not_silently_linked(self):
        response = self._callback({
            "sub": "google-123", "email": self.existing.email, "email_verified": True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.url).path, reverse("web:login"))
        self.existing.refresh_from_db()
        self.assertIsNone(self.existing.google_id)
        self.assertNotIn("_auth_user_id", self.client.session)

    @override_settings(GOOGLE_CLIENT_ID="client-id", GOOGLE_CLIENT_SECRET="client-secret", GOOGLE_REDIRECT_URI="https://lms.example.test/api/auth/google/callback/")
    def test_authenticated_owner_can_link_then_login_by_google_subject(self):
        self._callback({
            "sub": "google-123", "email": self.existing.email, "email_verified": True,
        }, authenticated=True)
        self.existing.refresh_from_db()
        self.assertEqual(self.existing.google_id, "google-123")
        self.client.logout()
        response = self._callback({
            "sub": "google-123", "email": "new-address@example.test", "email_verified": True,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.url).path, reverse("web:dashboard"))
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.existing.pk)

    @override_settings(GOOGLE_CLIENT_ID="client-id", GOOGLE_CLIENT_SECRET="client-secret", GOOGLE_REDIRECT_URI="https://lms.example.test/api/auth/google/callback/")
    def test_unverified_email_and_nonce_mismatch_rejected(self):
        response = self._callback({
            "sub": "google-123", "email": self.existing.email, "email_verified": False,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlsplit(response.url).path, reverse("web:login"))
        self.assertIsNone(self.existing.google_id)
        with patch("google.oauth2.id_token.verify_oauth2_token", return_value={
            "sub": "google-123", "email": self.existing.email,
            "email_verified": True, "nonce": "wrong",
        }):
            self.assertIsNone(_verified_claims("signed-token", "client-id", "expected"))


class WebSocketOriginTests(SimpleTestCase):
    @override_settings(ALLOWED_HOSTS=["testserver", "localhost"])
    def test_untrusted_origin_is_rejected_before_consumer(self):
        from config.asgi import application

        async def connect_from(origin):
            communicator = WebsocketCommunicator(
                application, "/ws/arena/", headers=[(b"origin", origin)],
            )
            connected, _ = await communicator.connect()
            if connected:
                await communicator.disconnect()
            return connected

        self.assertFalse(async_to_sync(connect_from)(b"https://evil.example"))


class TunneledDevelopmentSettingsTests(SimpleTestCase):
    def test_public_tunnel_requires_explicit_https_origins_and_restricts_cors(self):
        env = os.environ.copy()
        env.update({
            "DEV_PUBLIC_TUNNEL": "true",
            "DEV_EXTERNAL_HOSTS": "lms-tunnel.example.test",
            "DEV_CSRF_TRUSTED_ORIGINS": "https://lms-tunnel.example.test",
        })
        completed = subprocess.run(
            [sys.executable, "-c", "from config.settings.development import ALLOWED_HOSTS, CORS_ALLOW_ALL_ORIGINS, CORS_ALLOWED_ORIGINS, SESSION_COOKIE_SECURE; assert '*' not in ALLOWED_HOSTS; assert CORS_ALLOW_ALL_ORIGINS is False; assert CORS_ALLOWED_ORIGINS == ['https://lms-tunnel.example.test']; assert SESSION_COOKIE_SECURE is True"],
            env=env, capture_output=True, text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

        env["DEV_CSRF_TRUSTED_ORIGINS"] = "http://lms-tunnel.example.test"
        invalid = subprocess.run(
            [sys.executable, "-c", "import config.settings.development"],
            env=env, capture_output=True, text=True,
        )
        self.assertNotEqual(invalid.returncode, 0)


class RegisterCsrfTests(TestCase):
    """POST /api/auth/register/ is JWT-only: a stale Django session must
    never trigger 403 CSRF Failed (Ro'yxatdan o'tish regression)."""

    def _payload(self, email):
        return {
            "email": email,
            "password": "StrongPass123!",
            "password_confirm": "StrongPass123!",
            "first_name": "Brand",
            "last_name": "New",
        }

    def test_register_with_active_session_and_csrf_checks_returns_201(self):
        holder = User.objects.create_user(
            email="holder@example.test", password="OldStrongPass123!",
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(holder)
        response = client.post(
            reverse("accounts:register"), self._payload("new-one@example.test"),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("tokens", response.json())

    def test_anonymous_register_with_csrf_checks_returns_201(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(
            reverse("accounts:register"), self._payload("new-two@example.test"),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
