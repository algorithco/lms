"""
Billing & Limits Service.
Enforces quota, subscription, and limit rules.
Guarantees unlimited access for platform administrators (superusers, staff, admin role).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)


def is_admin_user(user: Any) -> bool:
    """Check if user has full administrative immunity."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
        or getattr(user, "role", "") in ("admin", "center_admin")
    )


def check_user_limits(user: Any) -> bool:
    """
    Check if user is within allowed limits for test/essay/AI access.
    Admins (superuser, staff, role='admin') are NEVER limited.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if is_admin_user(user):
        return True  # Adminlarga hamma narsa cheksiz va bepul

    from apps.subscriptions.services.quota import QuotaService

    tier = QuotaService.get_user_tier(user)
    return tier in ("pro", "premium")


def has_active_subscription(user: Any) -> bool:
    """
    Check if user has an active paid or granted subscription.
    Admins (superuser, staff, role='admin') always have active unlimited subscription.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if is_admin_user(user):
        return True  # Adminlarga hamma narsa cheksiz va bepul

    from apps.payments.models import UserSubscription

    sub = UserSubscription.objects.filter(
        user=user, status=UserSubscription.Status.ACTIVE
    ).first()
    return bool(sub and sub.is_active)


def can_take_test(user: Any, test_id: int | None = None) -> Tuple[bool, str, Dict[str, Any]]:
    """Check if user can start a test."""
    if is_admin_user(user):
        return True, "", {"tier": "admin", "allowed": True, "remaining": 999999, "limit": None}

    from apps.subscriptions.services.quota import QuotaService

    return QuotaService.check_test_quota(user, test_id=test_id)


def can_submit_essay(user: Any) -> Tuple[bool, str, Dict[str, Any]]:
    """Check if user can submit an essay."""
    if is_admin_user(user):
        return True, "", {"tier": "admin", "allowed": True, "remaining": 999999, "limit": None}

    from apps.subscriptions.services.quota import QuotaService

    return QuotaService.check_essay_quota(user)
