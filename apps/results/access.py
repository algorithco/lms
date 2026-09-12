"""Single source of truth for result and certificate access."""
from __future__ import annotations

from django.db.models import QuerySet

from apps.accounts.access import is_platform_admin

from .models import Result


def result_queryset_for_user(user) -> QuerySet:
    queryset = Result.objects.all()
    if not user or not user.is_authenticated or not user.is_active:
        return queryset.none()
    if is_platform_admin(user):
        return queryset
    if getattr(user, "role", None) == "student":
        return queryset.filter(student=user)
    if getattr(user, "role", None) == "teacher":
        return queryset.filter(course__teacher=user)
    if getattr(user, "role", None) == "parent":
        return queryset.filter(
            student__parent_links__parent=user,
            student__parent_links__is_approved=True,
        ).distinct()
    return queryset.none()


def can_access_certificate(user, certificate) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if is_platform_admin(user):
        return True
    if getattr(user, "role", None) == "student":
        return certificate.student_id == user.id
    if getattr(user, "role", None) == "teacher":
        return certificate.course.teacher_id == user.id
    if getattr(user, "role", None) == "parent":
        return certificate.student.parent_links.filter(
            parent=user,
            is_approved=True,
        ).exists()
    return False
