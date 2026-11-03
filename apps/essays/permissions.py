"""
Essays permissions — access control and quota enforcement for essays.
"""

from __future__ import annotations

from typing import Any
from rest_framework.permissions import BasePermission
from apps.accounts.access import is_platform_admin


def check_user_limits(user: Any) -> bool:
    """Check if user has unlimited/available limits for essay submission."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if (
        getattr(user, "is_superuser", False)
        or getattr(user, "role", "") in ("admin", "center_admin")
    ):
        return True  # Adminlarga hamma narsa cheksiz va bepul
    from apps.subscriptions.services.quota import QuotaService

    tier = QuotaService.get_user_tier(user)
    return tier in ("pro", "premium")


def has_active_subscription(user: Any) -> bool:
    """Check if user has an active subscription."""
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if (
        getattr(user, "is_superuser", False)
        or getattr(user, "role", "") in ("admin", "center_admin")
    ):
        return True  # Adminlarga hamma narsa cheksiz va bepul
    from apps.payments.models import UserSubscription

    sub = UserSubscription.objects.filter(
        user=user, status=UserSubscription.Status.ACTIVE
    ).first()
    return bool(sub and sub.is_active)


class CanSubmitEssay(BasePermission):
    """
    Permission to submit an essay.
    Administrators and staff have unlimited access.
    """

    message = "Esse yuborish uchun ruxsat yoki kvota yetarli emas."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if (
            getattr(user, "is_superuser", False)
            or getattr(user, "role", "") in ("admin", "center_admin")
            or is_platform_admin(user)
        ):
            return True
        from apps.subscriptions.services.quota import QuotaService

        allowed, _, _ = QuotaService.check_essay_quota(user)
        return allowed


class IsEssayOwnerOrStaff(BasePermission):
    """
    Permission to view or edit essay submission.
    """

    message = "Ushbu inshoga faqat egasi yoki ustoz/admin kirishi mumkin."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if (
            getattr(user, "is_superuser", False)
            or getattr(user, "role", "") in ("admin", "center_admin")
            or is_platform_admin(user)
        ):
            return True
        return getattr(obj, "student_id", None) == user.id or getattr(obj, "student", None) == user
