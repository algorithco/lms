"""Access control for the in-app admin panel.

A user is an administrator for the panel when they are authenticated AND
(they are Django staff OR their platform role is 'admin').
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.accounts.access import is_platform_admin


def is_panel_admin(user) -> bool:
    return is_platform_admin(user)


def admin_required(view_func):
    """Decorator: require login + staff/admin role, else raise 403."""

    @wraps(view_func)
    @login_required
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not is_panel_admin(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped


class AdminRequiredMixin:
    """Mixin for class-based views: login + staff/admin role."""

    def dispatch(self, request, *args, **kwargs):
        if not is_panel_admin(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
