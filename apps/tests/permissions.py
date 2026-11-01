"""
Tests permissions — test-taking specific access control.

Separate from accounts/permissions.py to follow SRP.
"""

from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.accounts.access import is_platform_admin


class IsAttemptOwner(BasePermission):
    """
    Ruxsat: Faqat attempt egasi yoki vakolatli xodimlar kirishi mumkin.

    Attempt endpointlari uchun: save-answer, submit, get-status.
    O'qituvchilar o'z kurslaridagi attemptlarni ko'ra oladi.
    """

    message = "Only the owner of this attempt may do that."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if is_platform_admin(user) or getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return True
        # Attempt egasi (student, o'qituvchi yoki admin preview)
        if getattr(obj, "student_id", None) == user.id or getattr(obj, "student", None) == user:
            return True

        # Teacher — o'z kurslaridagi attemptlarni ko'radi
        if getattr(user, "role", "") == "teacher":
            test = getattr(obj, "test", None)
            course = getattr(test, "course", None)
            return bool(course and getattr(course, "teacher_id", None) == user.id)

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
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        user = request.user
        # Safe methods — authenticated har kim
        if request.method in SAFE_METHODS:
            if is_platform_admin(user) or getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
                return True
            # Student — faqat active testlarni ko'radi
            if getattr(user, "role", "") == "student":
                return bool(obj.is_active)
            # Teacher/Admin — barchasini ko'radi
            return getattr(user, "role", "") in ["teacher", "admin", "center_admin"]

        # Write methods — faqat owner teacher yoki admin
        course = getattr(obj, "course", None)
        return (
            (course and getattr(course, "teacher", None) == user)
            or getattr(obj, "created_by", None) == user
            or is_platform_admin(user)
            or getattr(user, "is_superuser", False)
            or getattr(user, "is_staff", False)
        )


class CanStartAttempt(BasePermission):
    """
    Ruxsat: O'quvchilar, o'qituvchilar va administratorlar testni boshlashi (yoki preview qilishi) mumkin.
    """

    message = "Ushbu amal uchun tizimga kirish talab etiladi."

    def has_permission(self, request, view) -> bool:
        u = getattr(request, "user", None)
        if not (u and u.is_authenticated):
            return False
        if is_platform_admin(u) or getattr(u, "is_superuser", False) or getattr(u, "is_staff", False):
            return True
        role = getattr(u, "role", "")
        return role in ["student", "teacher", "admin", "center_admin"]
