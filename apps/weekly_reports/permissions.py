"""Object-level permissions for weekly reports.

Two independent questions, deliberately not merged:

* **Can this user read this group's report?** — the group's own teacher, or a
  platform administrator (whose existing administrative scope already governs
  what they may reach).
* **May this user see the tuition block?** — a separate privilege. A teacher
  gets the academic report by ownership but sees course payments only when an
  administrator has explicitly delegated ``tuition.view_courseinvoice``.

Keeping them apart is what stops "can read the report" from silently becoming
"can read every family's tuition balance".
"""
from __future__ import annotations

from django.core.exceptions import PermissionDenied

from apps.accounts.access import has_platform_permission, is_platform_admin

#: The single permission that unlocks course-tuition figures in a report.
FINANCE_PERMISSION = "tuition.view_courseinvoice"


def can_view_group(user, group) -> bool:
    """True for the group's teacher and for platform administrators."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if is_platform_admin(user):
        return True
    return bool(group is not None and group.teacher_id == getattr(user, "pk", None))


def assert_can_view_group(user, group) -> None:
    if not can_view_group(user, group):
        raise PermissionDenied("Bu guruh hisoboti sizga tegishli emas.")


def can_view_group_finance(user) -> bool:
    """Administrators, or anyone explicitly granted the tuition permission."""
    return has_platform_permission(user, FINANCE_PERMISSION)


def can_view_student_report(user, student) -> bool:
    """The student themselves, a verified parent, their teacher, or an admin."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if is_platform_admin(user):
        return True
    if getattr(user, "pk", None) == getattr(student, "pk", None):
        return True
    from apps.accounts.models import ParentStudentLink

    if ParentStudentLink.objects.filter(
        parent=user, student=student, is_approved=True,
    ).exists():
        return True
    return student.student_groups.filter(teacher=user).exists()
