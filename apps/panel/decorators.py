"""Access control for the in-app admin panel.

A user is an administrator for the panel when they are authenticated AND
active AND (they are a Django superuser OR their platform role is 'admin').
Plain ``is_staff`` alone grants nothing here — it only gates Django /admin/.
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from apps.accounts.access import is_platform_admin


def is_panel_admin(user) -> bool:
    return is_platform_admin(user)


def is_essay_topic_creator(user) -> bool:
    """Phase 4: allow platform admin OR user.can_create_essay_topic."""
    if is_platform_admin(user):
        return True
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and getattr(user, "can_create_essay_topic", False)
    )


def essay_topic_required(view_func):
    """Decorator: require login + (platform-admin OR can_create_essay_topic), else 403."""

    @wraps(view_func)
    @login_required
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not is_essay_topic_creator(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped


def admin_required(view_func):
    """Decorator: require login + platform-admin, else raise 403."""

    @wraps(view_func)
    @login_required
    def _wrapped(request: HttpRequest, *args, **kwargs):
        if not is_panel_admin(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped


class AdminRequiredMixin:
    """Mixin for class-based views: login + platform-admin."""

    def dispatch(self, request, *args, **kwargs):
        if not is_panel_admin(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
