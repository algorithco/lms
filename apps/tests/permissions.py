"""
Tests permissions — test-taking specific access control.

Separate from accounts/permissions.py to follow SRP.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.accounts.access import is_platform_admin


class IsAttemptOwner(BasePermission):
    """
    Ruxsat: Faqat attempt egasi (student) kirishi mumkin.

    Attempt endpointlari uchun: save-answer, submit, get-status.
    O'qituvchilar o'z kurslaridagi attemptlarni ko'ra oladi.
    """

    # Explicit message: the DRF default ("You do not have permission to
    # perform this action.") hides which rule was applied.
    message = "Only the owner of this attempt may do that."

    def has_permission(self, request, view) -> bool:
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj) -> bool:
        if is_platform_admin(request.user):
            return True
        # Student — faqat o'z attemptini ko'radi/tahrirlaydi
        if request.user.role == "student":
            return obj.student == request.user

        # Teacher — o'z kurslaridagi attemptlarni ko'radi
        if request.user.role == "teacher":
            return obj.test.course.teacher == request.user

        return False


class IsTestOwnerOrStudent(BasePermission):
    """
    Ruxsat:
        - Testni o'qituvchisi (owner) — to'liq kiradi.
        - O'quvchilar — faqat faol testni ko'ra oladi.
        - Admin — to'liq kiradi.
    """

    message = "Test access required."

    def has_permission(self, request, view) -> bool:
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj) -> bool:
        # Safe methods — authenticated har kim
        if request.method in SAFE_METHODS:
            if is_platform_admin(request.user):
                return True
            # Student — faqat active testlarni ko'radi
            if request.user.role == "student":
                return obj.is_active
            # Teacher/Admin — hammani ko'radi
            return request.user.role == "teacher"

        # Write methods — faqat owner teacher yoki admin
        return (
            obj.course.teacher == request.user
            or is_platform_admin(request.user)
        )


class CanStartAttempt(BasePermission):
    """
    Ruxsat: Faqat o'quvchilar testni boshlashi mumkin.
    """

    message = "Only students may start a test."

    def has_permission(self, request, view) -> bool:
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "student"
        )
