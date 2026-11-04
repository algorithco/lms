"""The session bridge must report the same tier as /me.

A SPA restored from the Django session cookie (Telegram / Google login) used
the session payload as the user, which had no plan, so the sidebar said FREE
next to an active PRO subscription.
"""

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.payments.models import SubscriptionPlan, UserSubscription

User = get_user_model()


def _status(client):
    return client.get(reverse("accounts:session_status")).json()


@pytest.mark.django_db
def test_session_status_reports_active_pro_plan(client):
    user = User.objects.create_user(email="pro-session@example.test", password="x-test-pass-1", role="student")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        plan_type="pro", defaults={"name": "Pro", "price_monthly": 15000}
    )
    UserSubscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": UserSubscription.Status.ACTIVE,
            "expires_at": timezone.now() + timedelta(days=29),
        },
    )
    client.force_login(user)
    body = _status(client)
    assert body["authenticated"] is True
    assert body["user"]["plan"] == "PRO"
    me = client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {body['tokens']['access']}").json()
    assert me["plan"] == body["user"]["plan"]


@pytest.mark.django_db
def test_session_status_free_and_anonymous(client):
    assert _status(client) == {"authenticated": False, "user": None, "tokens": None}
    user = User.objects.create_user(email="free-session@example.test", password="x-test-pass-1", role="student")
    client.force_login(user)
    assert _status(client)["user"]["plan"] == "FREE"
