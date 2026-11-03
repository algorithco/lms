"""A FREE student can never obtain a paid tier by themselves.

Covered paths: receipt upload (old instant 24h trial), AI receipt check,
group join, tournament prize, XP/streak, OMR, stale Profile.plan / old
receipts, expired-but-"active" rows. Allowed grants are audited and need the
right actor; limits shown and enforced come from one rule.
"""

import io
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.gamification import record_user_activity
from apps.accounts.models import Profile
from apps.courses.group_service import join_group_by_invite_code, join_group_by_token
from apps.courses.models import Course, StudentGroup
from apps.payments.ai_quota import get_user_plan_tier
from apps.payments.entitlements import get_remaining_limits
from apps.payments.models import (
    EntitlementAuditLog,
    PaymentReceipt,
    SubscriptionPlan,
    UserSubscription,
)
from apps.payments.subscriptions import (
    SubscriptionGrantDenied,
    expire_overdue_subscriptions,
    grant_subscription,
)
from apps.subscriptions.services.quota import QuotaService
from apps.tests.models import Test, TestAttempt

User = get_user_model()


@pytest.fixture
def pro_plan(db):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        plan_type=SubscriptionPlan.PlanType.PRO,
        defaults={"name": "Pro", "price_monthly": Decimal("15000"), "test_limit": 30},
    )
    return plan


@pytest.fixture
def student(db):
    user = User.objects.create_user(email="leak_student@example.test", password="x-Pass-123!", role="student")
    Profile.objects.get_or_create(user=user)
    return user


@pytest.fixture
def admin(db):
    return User.objects.create_superuser(email="leak_admin@example.test", password="x-Pass-123!")


@pytest.fixture
def teacher(db):
    return User.objects.create_user(email="leak_teacher@example.test", password="x-Pass-123!", role="teacher")


def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def image_upload(seed: int):
    buf = io.BytesIO()
    img = Image.new("RGB", (400, 600), color="white")
    for i in range(seed + 1):
        img.paste((20 * i % 255, 40, 200), (10 + 30 * i, 10, 30 + 30 * i, 590))
    img.save(buf, "JPEG")
    return SimpleUploadedFile(f"receipt{seed}.jpg", buf.getvalue(), content_type="image/jpeg")


def assert_free(user):
    user.refresh_from_db()
    assert not UserSubscription.objects.filter(user=user, status=UserSubscription.Status.ACTIVE).exists()
    assert get_user_plan_tier(user) == "free"
    assert User.objects.get(pk=user.pk).has_pro_access is False
    assert api(user).get("/api/auth/me/").json().get("plan") in ("FREE", None)


# -- self-service paths -------------------------------------------------------


@pytest.mark.django_db
def test_receipt_upload_grants_nothing_even_repeated(student, pro_plan):
    for seed in range(3):
        res = api(student).post(
            "/api/v1/payments/receipts/", {"plan": "pro", "receipt_image": image_upload(seed)}, format="multipart"
        )
        assert res.status_code == 201, res.content
        assert res.json()["trial_granted"] is False
    assert PaymentReceipt.objects.filter(user=student, status=PaymentReceipt.Status.PENDING).count() == 3
    assert_free(student)


@pytest.mark.django_db
def test_ai_accepted_receipt_only_queues_for_admin(student, pro_plan):
    from apps.subscriptions.services.receipt_verifier import ReceiptVerifier

    scan = {
        "is_valid": True,
        "amount": 15000.0,
        "transaction_id": "TX-LEAK-1",
        "payment_system": "click",
        "date": timezone.now().strftime("%Y-%m-%d %H:%M"),
    }
    with patch("apps.subscriptions.services.receipt_verifier.scan_receipt_vision", return_value=scan), patch(
        "apps.subscriptions.services.receipt_verifier.is_receipt_date_recent", return_value=True
    ), patch("apps.payments.services.notify_admin_new_receipt"):
        result = ReceiptVerifier.verify_receipt(student, image_upload(7).read(), plan_type="pro")
    assert result["success"] is True and result["pending_admin"] is True
    assert PaymentReceipt.objects.filter(user=student, status=PaymentReceipt.Status.PENDING).exists()
    assert_free(student)


@pytest.mark.django_db
def test_group_join_grants_nothing(student, teacher, pro_plan):
    Course.objects.create(teacher=teacher, title="C", slug="leak-c")
    group = StudentGroup.objects.create(teacher=teacher, name="G")
    join_group_by_invite_code(student, group.invite_code)
    join_group_by_invite_code(student, group.invite_code)
    join_group_by_token(student, group.invite_code)
    assert group.students.filter(pk=student.pk).exists()
    assert_free(student)


@pytest.mark.django_db
def test_xp_streak_and_omr_grant_nothing(student, pro_plan):
    for _ in range(50):
        record_user_activity(student, xp_amount=30, activity_type="omr_scan")
    test = Test.objects.create(title="T", course=Course.objects.create(
        teacher=User.objects.create_user(email="t2@example.test", password="x-Pass-123!", role="teacher"),
        title="C2", slug="leak-c2"), is_active=True, max_attempts=0)
    api(student).post("/api/v1/tests/scan-omr/confirm/", {"test_id": test.id, "answers": {}}, format="json")
    assert_free(student)


@pytest.mark.django_db
def test_stale_profile_plan_and_old_receipt_do_not_grant(student, pro_plan):
    student.profile.plan = "pro"
    student.profile.save(update_fields=["plan"])
    PaymentReceipt.objects.create(
        user=student, plan="pro", amount=Decimal("15000"), receipt_image=image_upload(9),
        image_hash="old-approved", status=PaymentReceipt.Status.APPROVED,
    )
    assert get_user_plan_tier(student) == "free"
    assert User.objects.get(pk=student.pk).has_pro_access is False
    assert api(student).get("/api/auth/me/").json()["plan"] == "FREE"


@pytest.mark.django_db
def test_expired_row_still_marked_active_is_not_pro(student, admin, pro_plan):
    sub = grant_subscription(student, pro_plan, kind="admin", actor=admin, days=1, reason="test")
    UserSubscription.objects.filter(pk=sub.pk).update(expires_at=timezone.now() - timedelta(minutes=1))
    assert get_user_plan_tier(student) == "free"
    body = api(User.objects.get(pk=student.pk)).get("/api/v1/billing/my/").json()["subscription"]
    assert body["status"] == "active" and body["is_active"] is False
    assert expire_overdue_subscriptions() == 1
    assert EntitlementAuditLog.objects.filter(
        student=student, action=EntitlementAuditLog.Action.EXPIRE_SUBSCRIPTION
    ).exists()


# -- the gate -----------------------------------------------------------------


@pytest.mark.django_db
def test_grant_requires_allowed_kind_actor_and_reason(student, teacher, admin, pro_plan):
    with pytest.raises(TypeError):
        grant_subscription(student, pro_plan, actor=admin, reason="x")  # kind is mandatory
    for kwargs in (
        {"kind": "reward", "actor": admin, "reason": "x"},
        {"kind": "admin", "actor": None, "reason": "x"},
        {"kind": "admin", "actor": student, "reason": "x"},
        {"kind": "admin", "actor": admin, "reason": ""},
        {"kind": "approved_payment", "actor": admin, "reason": "x"},  # no payment reference
        {"kind": "provider_payment", "actor": None, "reason": "x"},
        {"kind": "teacher_quota", "actor": student, "reason": "x"},
    ):
        with pytest.raises(SubscriptionGrantDenied):
            grant_subscription(student, pro_plan, **kwargs)
    assert_free(student)

    grant_subscription(student, pro_plan, kind="admin", actor=admin, days=30, reason="support ticket #1")
    log = EntitlementAuditLog.objects.filter(student=student).latest("created_at")
    assert log.actor == admin
    assert log.details["kind"] == "admin" and log.details["reason"] == "support ticket #1"
    assert get_user_plan_tier(student) == "pro"


@pytest.mark.django_db
def test_admin_approved_receipt_grants_with_audit(student, admin, pro_plan):
    from apps.payments.services import approve_payment_receipt

    receipt = PaymentReceipt.objects.create(
        user=student, plan="pro", amount=Decimal("15000"), receipt_image=image_upload(11), image_hash="ok-1",
    )
    approve_payment_receipt(receipt, admin_user=admin)
    assert get_user_plan_tier(student) == "pro"
    log = EntitlementAuditLog.objects.filter(student=student).latest("created_at")
    assert log.details["kind"] == "approved_payment" and log.actor == admin


# -- one limit rule -------------------------------------------------------------


@pytest.mark.django_db
def test_displayed_and_enforced_test_limits_match(student, admin, pro_plan):
    course = Course.objects.create(teacher=admin, title="C3", slug="leak-c3")
    test = Test.objects.create(title="T3", course=course, is_active=True, max_attempts=0)

    remaining = get_remaining_limits(student)["test"]
    allowed, _msg, details = QuotaService.check_test_quota(student, test_id=test.id)
    assert allowed and details["limit"] == remaining["limit"] and details["used"] == remaining["used"] == 0

    TestAttempt.objects.create(test=test, student=student, status=TestAttempt.Status.COMPLETED)
    remaining = get_remaining_limits(student)["test"]
    allowed, _msg, details = QuotaService.check_test_quota(student, test_id=test.id)
    assert remaining["used"] == details["used"] == 1
    assert allowed is (remaining["remaining"] > 0)


@pytest.mark.django_db
def test_tournament_win_and_referrals_grant_nothing(student, teacher, pro_plan):
    from apps.accounts.services.referral import apply_referral_reward
    from apps.arena.models import Tournament, TournamentParticipant
    from apps.arena.services_tournament import finalize_tournament_awards

    for code in ("premium", "starter"):
        SubscriptionPlan.objects.get_or_create(plan_type=code, defaults={"name": code, "price_monthly": 1})
    course = Course.objects.create(teacher=teacher, title="TC", slug="leak-tc")
    test = Test.objects.create(title="TT", course=course, is_active=True)
    tournament = Tournament.objects.create(
        title="Leak cup", scheduled_at=timezone.now(), duration_minutes=10, test=test,
        status=Tournament.Status.LIVE,
    )
    TournamentParticipant.objects.create(
        tournament=tournament, user=student, score=100, rank=1, is_finished=True, time_taken_seconds=5,
    )
    result = finalize_tournament_awards(tournament.id)
    assert result["awarded"][0]["prize_plan"] == "premium"  # listed for the admin, not granted
    assert_free(student)

    # Referrals: only extra free tests/essays, never a paid tier — even many of them.
    student.referral_code = student.referral_code or "LEAKREF1"
    student.save(update_fields=["referral_code"])
    for i in range(5):
        newcomer = User.objects.create_user(email=f"ref{i}@example.test", password="x-Pass-123!", role="student")
        apply_referral_reward(newcomer, student.referral_code)
    assert_free(student)
