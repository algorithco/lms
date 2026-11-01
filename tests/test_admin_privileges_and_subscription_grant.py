"""
Tests for Admin Unlimited Privileges and Subscription Grant System.
Phase 9.4.0 Directive QA Gate.
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.billing.services import (
    check_user_limits,
    has_active_subscription,
    can_take_test,
    can_submit_essay,
)
from apps.payments.models import SubscriptionPlan, UserSubscription
from apps.payments.ai_quota import check_and_consume_ai_quota, get_user_ai_quota
from apps.payments.entitlements import enforce_essay_quota, enforce_test_quota
from apps.subscriptions.services.quota import QuotaService

User = get_user_model()


@pytest.fixture
def plans(db):
    pro_plan, _ = SubscriptionPlan.objects.get_or_create(
        plan_type=SubscriptionPlan.PlanType.PRO,
        defaults={
            "name": "PRO",
            "price_monthly": 49000,
            "duration_days": 30,
            "is_active": True,
            "is_public": True,
        },
    )
    prem_plan, _ = SubscriptionPlan.objects.get_or_create(
        plan_type=SubscriptionPlan.PlanType.PREMIUM,
        defaults={
            "name": "PREMIUM",
            "price_monthly": 60000,
            "duration_days": 30,
            "is_active": True,
            "is_public": True,
        },
    )
    return pro_plan, prem_plan


@pytest.fixture
def admin_user(db):
    user = User.objects.create_superuser(
        email="superadmin@grandec.uz",
        password="AdminPassword123!",
        role="admin",
    )
    return user


@pytest.fixture
def teacher_user(db):
    user = User.objects.create_user(
        email="teacher1@grandec.uz",
        password="TeacherPassword123!",
        role="teacher",
        first_name="Ustoz",
        last_name="Test",
    )
    return user


@pytest.fixture
def student_user(db):
    user = User.objects.create_user(
        email="student1@grandec.uz",
        password="StudentPassword123!",
        role="student",
        first_name="Talaba",
        last_name="Sinov",
    )
    return user


@pytest.mark.django_db
def test_admin_unlimited_privileges(admin_user):
    """Test that platform admin has 100% unlimited access across all checks."""
    assert check_user_limits(admin_user) is True
    assert has_active_subscription(admin_user) is True

    # Test checking
    can_test, msg, details = can_take_test(admin_user)
    assert can_test is True
    assert details.get("allowed") is True

    # Essay checking
    can_essay, msg, details = can_submit_essay(admin_user)
    assert can_essay is True
    assert details.get("allowed") is True

    # QuotaService checks
    ok, _, q_det = QuotaService.check_test_quota(admin_user)
    assert ok is True
    assert q_det.get("allowed") is True

    ok, _, q_det = QuotaService.check_essay_quota(admin_user)
    assert ok is True
    assert q_det.get("allowed") is True

    ok, _, q_det = QuotaService.check_arena_quota(admin_user)
    assert ok is True

    # AI Quota check
    ai_allowed, ai_err = check_and_consume_ai_quota(admin_user)
    assert ai_allowed is True
    assert ai_err == ""

    # Enforce essay & test quota
    res_essay = enforce_essay_quota(admin_user, "text_essay")
    assert res_essay.ok is True

    res_test = enforce_test_quota(admin_user)
    assert res_test.ok is True


@pytest.mark.django_db
def test_admin_grant_pro_subscription_to_student(admin_user, student_user, plans):
    """Test that admin can grant PRO subscription to a student via API."""
    client = APIClient()
    client.force_authenticate(user=admin_user)

    url = f"/api/v1/panel/users/{student_user.id}/grant-subscription/"
    payload = {
        "plan_type": "pro",
        "days": 30,
        "reason": "Test admin grant",
    }
    response = client.post(url, payload, format="json")
    assert response.status_code == 200, response.data
    assert response.data["status"] == "success"
    assert response.data["plan_type"] == "pro"
    assert response.data["days"] == 30

    student_user.refresh_from_db()
    assert student_user.has_pro_access is True

    sub = UserSubscription.objects.filter(user=student_user, status=UserSubscription.Status.ACTIVE).first()
    assert sub is not None
    assert sub.plan.plan_type == "pro"
    assert sub.is_active is True
    assert sub.expires_at > timezone.now()


@pytest.mark.django_db
def test_admin_grant_premium_subscription_to_teacher(admin_user, teacher_user, plans):
    """Test that admin can grant PREMIUM 365-day subscription to a teacher."""
    client = APIClient()
    client.force_authenticate(user=admin_user)

    url = f"/api/v1/panel/users/{teacher_user.id}/grant-subscription/"
    payload = {
        "plan_type": "premium",
        "days": 365,
        "reason": "1-year sponsor",
    }
    response = client.post(url, payload, format="json")
    assert response.status_code == 200, response.data
    assert response.data["status"] == "success"
    assert response.data["plan_type"] == "premium"
    assert response.data["days"] == 365

    sub = UserSubscription.objects.filter(user=teacher_user, status=UserSubscription.Status.ACTIVE).first()
    assert sub is not None
    assert sub.plan.plan_type == "premium"


@pytest.mark.django_db
def test_non_admin_cannot_grant_subscription(student_user, teacher_user):
    """Test that regular student/teacher cannot call admin grant-subscription endpoint."""
    client = APIClient()
    client.force_authenticate(user=student_user)

    url = f"/api/v1/panel/users/{teacher_user.id}/grant-subscription/"
    response = client.post(url, {"plan_type": "pro", "days": 30}, format="json")
    assert response.status_code == 403
