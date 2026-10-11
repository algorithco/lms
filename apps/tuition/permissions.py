"""Object-level permissions for course tuition.

The rule this module exists to enforce: **being a teacher is not a financial
privilege, and being a relative is not an identity.** A teacher can take
attendance for a group without ever seeing who owes money; a parent sees only
invoices of children whose link an administrator has approved.
"""
from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.db.models import Q

from apps.accounts.access import has_platform_permission, is_platform_admin

MANAGE_PERMISSION = "tuition.change_courseinvoice"
VIEW_PERMISSION = "tuition.view_courseinvoice"


def can_manage_tuition(user) -> bool:
    """Record/verify payments, edit policies and agreements, adjust invoices."""
    return has_platform_permission(user, MANAGE_PERMISSION)


def can_view_tuition(user) -> bool:
    """Read financial reports (e.g. the weekly payment block) for a scope."""
    return has_platform_permission(user, VIEW_PERMISSION)


def assert_can_manage_tuition(user) -> None:
    if not can_manage_tuition(user):
        raise PermissionDenied("To'lov ma'lumotlarini boshqarish huquqi yo'q.")


def can_view_invoice(user, invoice) -> bool:
    """A student's own invoice, an approved parent's child invoice, or an admin."""
    if user is None or not getattr(user, "is_authenticated", False) or invoice is None:
        return False
    if is_platform_admin(user) or can_view_tuition(user):
        return True
    if invoice.student_id == getattr(user, "pk", None):
        return True
    from apps.accounts.models import ParentStudentLink

    return ParentStudentLink.objects.filter(
        parent=user, student_id=invoice.student_id, is_approved=True,
    ).exists()


def visible_invoices(user):
    """Every invoice *user* is allowed to read, and nothing else."""
    from .models import CourseInvoice

    if user is None or not getattr(user, "is_authenticated", False):
        return CourseInvoice.objects.none()
    if is_platform_admin(user) or can_view_tuition(user):
        return CourseInvoice.objects.all()
    from apps.accounts.models import ParentStudentLink

    child_ids = list(
        ParentStudentLink.objects.filter(parent=user, is_approved=True)
        .values_list("student_id", flat=True)
    )
    return CourseInvoice.objects.filter(
        Q(student_id=user.pk) | Q(student_id__in=child_ids),
    )


def can_view_student_tuition(user, student) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if is_platform_admin(user) or can_view_tuition(user):
        return True
    if getattr(user, "pk", None) == getattr(student, "pk", None):
        return True
    from apps.accounts.models import ParentStudentLink

    return ParentStudentLink.objects.filter(
        parent=user, student=student, is_approved=True,
    ).exists()
