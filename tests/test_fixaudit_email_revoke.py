"""Tests for frontend/fixaudit fixes: email lower unique + refresh revoke on deactivate."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from rest_framework import status

from tests.conftest import LMSBaseTestCase

User = get_user_model()


class EmailLowerUniqueTests(LMSBaseTestCase):
    """1) DB case-insensitive uniqueness."""

    def test_register_case_insensitive_duplicate_rejected(self):
        resp = self.client.post(
            "/api/auth/register/",
            {
                "email": "Case@Test.com",
                "password": "securepass123",
                "password_confirm": "securepass123",
                "first_name": "Case",
                "last_name": "One",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        # same email different case must be 400
        resp2 = self.client.post(
            "/api/auth/register/",
            {
                "email": "case@test.com",
                "password": "securepass123",
                "password_confirm": "securepass123",
                "first_name": "Case",
                "last_name": "Two",
            },
            format="json",
        )
        self.assertEqual(resp2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", resp2.data)

    def test_db_constraint_blocks_case_insensitive_duplicate(self):
        User.objects.create_user(email="dup@example.com", password="testpass123", first_name="A", last_name="B")
        with self.assertRaises(IntegrityError):
            # bypass serializer — direct ORM should hit DB constraint Lower(email)
            User.objects.create_user(email="DUP@example.com", password="testpass123", first_name="C", last_name="D")

    def test_manager_normalizes_to_lower(self):
        u = User.objects.create_user(email="MiXeD@Example.COM", password="testpass123", first_name="X", last_name="Y")
        self.assertEqual(u.email, "mixed@example.com")
        u2 = User.objects.get(id=u.id)
        self.assertEqual(u2.email, "mixed@example.com")

    def test_model_save_normalizes(self):
        u = User(email="SAVE@Example.COM", first_name="S", last_name="T", role="student")
        u.set_password("testpass123")
        u.save()
        self.assertEqual(u.email, "save@example.com")

    def test_constraint_exists(self):
        names = {c.name for c in User._meta.constraints}
        self.assertIn("uniq_user_email_lower", names)


class TokenRevokeOnDeactivateTests(LMSBaseTestCase):
    """2) Revoke refresh when user is deactivated."""

    def test_refresh_blocked_after_deactivation_via_panel(self):
        # student gets tokens
        tokens = self.get_jwt_tokens(email="student@test.com", password="testpass123")
        self.assertIn("refresh", tokens)
        self.assertIn("access", tokens)
        # admin deactivates student via panel block
        admin_client = self.get_authenticated_client(email="admin@test.com")
        resp = admin_client.post(f"/api/v1/panel/users/{self.student.id}/block/", format="json")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
        # refresh must fail 401
        resp2 = self.client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(resp2.status_code, status.HTTP_401_UNAUTHORIZED)
        # access must also fail 401
        from rest_framework.test import APIClient

        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        resp3 = c.get("/api/auth/me/")
        self.assertEqual(resp3.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_blacklist_created_on_deactivate(self):
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

        self.get_jwt_tokens(email="student@test.com", password="testpass123")
        # OutstandingToken must exist after login
        self.assertTrue(OutstandingToken.objects.filter(user=self.student).exists())
        admin_client = self.get_authenticated_client(email="admin@test.com")
        admin_client.post(f"/api/v1/panel/users/{self.student.id}/block/", format="json")
        # after deactivation, tokens must be blacklisted
        outstanding = OutstandingToken.objects.filter(user=self.student)
        self.assertTrue(outstanding.exists())
        for tok in outstanding:
            self.assertTrue(BlacklistedToken.objects.filter(token=tok).exists())

    def test_reactivation_allows_new_login_but_old_refresh_still_blocked(self):
        tokens_old = self.get_jwt_tokens(email="student@test.com", password="testpass123")
        admin_client = self.get_authenticated_client(email="admin@test.com")
        admin_client.post(f"/api/v1/panel/users/{self.student.id}/block/", format="json")
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
        # reactivate
        admin_client.post(f"/api/v1/panel/users/{self.student.id}/block/", format="json")
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)
        # old refresh still blocked
        resp = self.client.post("/api/auth/token/refresh/", {"refresh": tokens_old["refresh"]}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        # new login works
        tokens_new = self.get_jwt_tokens(email="student@test.com", password="testpass123")
        self.assertIn("access", tokens_new)
        from rest_framework.test import APIClient

        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens_new['access']}")
        resp2 = c.get("/api/auth/me/")
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)

    def test_inactive_cannot_refresh_even_without_panel_blacklist(self):
        # Direct deactivation without panel (simulates admin console or signal)
        tokens = self.get_jwt_tokens(email="student@test.com", password="testpass123")
        self.student.is_active = False
        self.student.save(update_fields=["is_active"])
        resp = self.client.post("/api/auth/token/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
