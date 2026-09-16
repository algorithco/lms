"""DRF permissions for the React API (mirrors apps/panel/decorators.py)."""
from rest_framework.permissions import BasePermission

from apps.accounts.access import is_platform_admin
from apps.panel.decorators import is_panel_admin


class IsPanelAdmin(BasePermission):
    """Same rule as @admin_required (apps/panel/decorators.py)."""

    message = "Admin access required."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and is_panel_admin(request.user)
        )


class IsTeacherOrAdmin(BasePermission):
    """Teachers and platform admins (same rule as CSV/group views)."""

    message = "Teacher access required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                getattr(user, "role", None) == "teacher"
                or is_platform_admin(user)
            )
        )


def _can_create_essay_topic(user) -> bool:
    """Phase 4: admin controls essay topic creation (Grande design)."""
    if is_platform_admin(user):
        return True
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and getattr(user, "can_create_essay_topic", False)
    )


class IsPanelAdminOrEssayCreator(BasePermission):
    """Allow platform admin OR teacher with can_create_essay_topic flag."""

    message = "Admin access required."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if _can_create_essay_topic(user):
            return True
        # Fallback to IsPanelAdmin check (covers superuser edge)
        return bool(
            user
            and user.is_authenticated
            and is_panel_admin(user)
        )
