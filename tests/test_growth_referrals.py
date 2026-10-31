"""
Tests for Stage 8.0.0 Growth Architecture:
- 1-click teacher group invites (/api/v1/groups/join/<token>/)
- Viral referral engine (/api/v1/referrals/my-code/ and apply/)
- Bonus quota attribution (+1 test, +1 essay)
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import ReferralHistory
from apps.accounts.services.referral import apply_referral_reward
from apps.courses.models import StudentGroup
from apps.courses.group_service import join_group_by_token
from apps.subscriptions.services.quota import QuotaService

User = get_user_model()


@pytest.mark.django_db
class TestGroupInviteByToken:
    def setup_method(self):
        self.client = APIClient()
        self.teacher = User.objects.create_user(
            email="teacher_growth@example.com",
            password="StrongPassword123!",
            first_name="Anvar",
            last_name="Ustoz",
            role=User.Role.TEACHER,
        )
        self.student = User.objects.create_user(
            email="student_growth@example.com",
            password="StrongPassword123!",
            first_name="Jasur",
            last_name="Talaba",
            role=User.Role.STUDENT,
        )
        self.group = StudentGroup.objects.create(
            teacher=self.teacher,
            name="11-A Ona Tili va Adabiyot",
            subject="uzbek",
            description="Milliy sertifikatga tayyorgarlik sinfi",
        )

    def test_group_has_invite_token_generated(self):
        assert self.group.invite_token is not None
        assert len(self.group.invite_token) > 10

    def test_get_group_preview_public(self):
        url = f"/api/v1/groups/join/{self.group.invite_token}/"
        resp = self.client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == self.group.id
        assert data["name"] == "11-A Ona Tili va Adabiyot"
        assert "Anvar Ustoz" in data["teacher_name"]
        assert data["student_count"] == 0
        assert data["is_member"] is False

    def test_join_group_unauthenticated_fails(self):
        url = f"/api/v1/groups/join/{self.group.invite_token}/"
        resp = self.client.post(url)
        assert resp.status_code == 401
        assert resp.json()["status"] == "UNAUTHORIZED"

    def test_join_group_authenticated_success_and_pro_activation(self):
        self.client.force_authenticate(user=self.student)
        url = f"/api/v1/groups/join/{self.group.invite_token}/"
        resp = self.client.post(url)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"
        assert data["group_id"] == self.group.id

        # Verify membership
        assert self.group.students.filter(id=self.student.id).exists()

        # Re-joining returns ALREADY_MEMBER
        resp2 = self.client.post(url)
        assert resp2.status_code == 200
        assert resp2.json()["status"] == "ALREADY_MEMBER"

    def test_join_group_via_invite_code_parity(self):
        # Also works when passing invite_code e.g. GR-XXX
        self.client.force_authenticate(user=self.student)
        url = f"/api/v1/groups/join/{self.group.invite_code}/"
        resp = self.client.get(url)
        assert resp.status_code == 200
        assert resp.json()["id"] == self.group.id


@pytest.mark.django_db
class TestReferralSystem:
    def setup_method(self):
        self.client = APIClient()
        self.referrer = User.objects.create_user(
            email="referrer@example.com",
            password="StrongPassword123!",
            first_name="Komiljon",
            last_name="Roziyev",
            role=User.Role.STUDENT,
        )
        self.referee = User.objects.create_user(
            email="referee@example.com",
            password="StrongPassword123!",
            first_name="Sardor",
            last_name="Do'st",
            role=User.Role.STUDENT,
        )

    def test_user_has_referral_code(self):
        assert self.referrer.referral_code is not None
        assert self.referrer.referral_code.startswith("ref_")

    def test_get_my_referral_code_endpoint(self):
        self.client.force_authenticate(user=self.referrer)
        resp = self.client.get("/api/v1/referrals/my-code/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["referral_code"] == self.referrer.referral_code
        assert f"/r/{self.referrer.referral_code}" in data["referral_link"]
        assert f"ref_{self.referrer.referral_code}" in data["telegram_bot_link"] or self.referrer.referral_code in data["telegram_bot_link"]
        assert data["total_invited"] == 0

    def test_apply_referral_awards_bonus_to_both(self):
        initial_referrer_tests = self.referrer.bonus_tests
        initial_referee_tests = self.referee.bonus_tests

        self.client.force_authenticate(user=self.referee)
        resp = self.client.post("/api/v1/referrals/apply/", {"code": self.referrer.referral_code})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "SUCCESS"

        self.referrer.refresh_from_db()
        self.referee.refresh_from_db()

        assert self.referrer.bonus_tests == initial_referrer_tests + 1
        assert self.referrer.bonus_essays >= 1
        assert self.referee.bonus_tests == initial_referee_tests + 1
        assert self.referee.bonus_essays >= 1

        # Check ReferralHistory record
        history = ReferralHistory.objects.filter(referrer=self.referrer, referred_user=self.referee).first()
        assert history is not None
        assert history.reward_given is True

        # Second apply attempt should fail
        resp2 = self.client.post("/api/v1/referrals/apply/", {"code": self.referrer.referral_code})
        assert resp2.status_code == 400

    def test_quota_service_factors_bonus_tests_and_essays(self):
        self.referee.bonus_tests = 2
        self.referee.bonus_essays = 3
        self.referee.save()

        allowed_test, _, details_test = QuotaService.check_test_quota(self.referee)
        assert allowed_test is True
        assert details_test["limit"] == QuotaService.FREE_TEST_LIMIT + 2

        allowed_essay, _, details_essay = QuotaService.check_essay_quota(self.referee)
        assert allowed_essay is True
        assert details_essay["limit"] == QuotaService.FREE_ESSAY_LIMIT + 3
