import pytest
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.accounts.serializers import UserProfileSerializer
from apps.notifications.models import TelegramAuthToken
from apps.notifications.bot.handlers import _authenticate_or_provision_tg_user
from apps.payments.models import SubscriptionPlan, UserSubscription
from apps.billing.tasks import check_and_notify_expiring_subscriptions

User = get_user_model()


@pytest.mark.django_db
def test_1click_telegram_sso_user_provisioning():
    token = "test_sso_token_123"
    auth_token = TelegramAuthToken.objects.create(token=token)

    tg_data = {
        "id": 9988776655,
        "first_name": "Alisher",
        "last_name": "Navoiy",
        "username": "alisher_n",
    }

    user, is_new = _authenticate_or_provision_tg_user(token, tg_data)
    assert is_new is True
    assert user is not None
    assert user.email == "tg_9988776655@grandec.uz"
    assert user.first_name == "Alisher"
    assert user.last_name == "Navoiy"
    assert user.telegram_chat_id == 9988776655
    assert user.is_active is True

    auth_token.refresh_from_db()
    assert auth_token.is_verified is True
    assert auth_token.phone_verified is True
    assert auth_token.user == user
    assert auth_token.telegram_chat_id == 9988776655


@pytest.mark.django_db
def test_user_profile_serializer_expiry_fields():
    user = User.objects.create_user(
        email="student_expiry@grandec.uz",
        password="ValidPassword123!",
        first_name="Test",
        last_name="Student",
        role=User.Role.STUDENT,
        telegram_chat_id=12345678,
    )

    plan, _ = SubscriptionPlan.objects.get_or_create(
        plan_type=SubscriptionPlan.PlanType.PRO,
        defaults={"name": "Pro Plan", "description": "Pro plan"},
    )

    now = timezone.now()
    # Subscription expiring in 3 days
    expires_at = now + timedelta(days=3)
    UserSubscription.objects.create(
        user=user,
        plan=plan,
        status=UserSubscription.Status.ACTIVE,
        started_at=now - timedelta(days=27),
        expires_at=expires_at,
    )

    serializer = UserProfileSerializer(user)
    data = serializer.data

    assert data["subscription_expires_at"] == expires_at.isoformat()
    assert data["days_until_expiration"] == 3
    assert data["is_expiring_soon"] is True

    # Platform Admin immunity
    admin = User.objects.create_superuser(
        email="admin_expiry@grandec.uz",
        password="ValidPassword123!",
        first_name="Admin",
        last_name="Super",
    )
    admin_serializer = UserProfileSerializer(admin)
    admin_data = admin_serializer.data

    assert admin_data["subscription_expires_at"] is None
    assert admin_data["days_until_expiration"] is None
    assert admin_data["is_expiring_soon"] is False


@pytest.mark.django_db
def test_check_and_notify_expiring_subscriptions_task():
    res = check_and_notify_expiring_subscriptions()
    assert res["status"] == "ok"
    assert "notified" in res
