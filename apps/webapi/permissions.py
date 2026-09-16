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
