"""
Accounts permissions — role-based access control.

Custom DRF permissions following the Single Responsibility Principle.
Each permission class handles one specific authorization rule.
"""
from rest_framework.permissions import BasePermission, SAFE_METHODS

from apps.accounts.access import is_platform_admin


class IsTeacher(BasePermission):
    """
    Ruxsat: Faqat o'qituvchi yoki admin foydalanuvchilar.

    Qo'llaniladi:
        - Kurs yaratish
        - Test tuzish
        - Savollar qo'shish
    """

    def has_permission(self, request, view) -> bool:
        return (
            request.user
            and request.user.is_authenticated
            and (request.user.role == "teacher" or is_platform_admin(request.user))
        )


class IsStudent(BasePermission):
    """
    Ruxsat: Faqat o'quvchi foydalanuvchilar.

    Qo'llaniladi:
        - Test topshirish
        - Natijalarni ko'rish
    """

    def has_permission(self, request, view) -> bool:
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "student"
        )


class IsStudentOrReadOnly(BasePermission):
    """
    Ruxsat: O'quvchilar to'liq kiradi, boshqalar faqat o'qiydi.

    Qo'llaniladi:
        - Test attempt endpoints
        - Student answer endpoints
    """

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "student"
        )


class IsOwnerOrReadOnly(BasePermission):
    """
    Ruxsat: Faqat o'z obyektini tahrirlash mumkin.

    Object-level permission — `has_object_permission` tekshiradi
    obyekt egasi foydalanuvchining o'zi ekanligini.

    Qo'llaniladi:
        - Profilni ko'rish/tahrirlash
        - O'z natijalarini ko'rish
    """

    def has_permission(self, request, view) -> bool:
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj) -> bool:
        """
        Obyekt egasini aniqlash.

        Supports:
            - User object (obj.pk == user.pk)
            - Objects with `user` field (obj.user == request.user)
            - Objects with `student` field (obj.student == request.user)
            - Objects with `owner` field (obj.owner == request.user)
        """
        # SAFE_METHODS — har kim o'qishi mumkin (masalan, profilni ko'rish)
        if request.method in SAFE_METHODS:
            return True

        # User obyekti — to'g'ridan-to'g'ri tekshirish
        if hasattr(obj, "pk") and obj.pk == request.user.pk:
            return True

        # Obyekt user field'iga ega
        if hasattr(obj, "user") and obj.user == request.user:
            return True

        # Obyekt student field'iga ega
        if hasattr(obj, "student") and obj.student == request.user:
            return True

        # Obyekt owner field'iga ega
        if hasattr(obj, "owner") and obj.owner == request.user:
            return True

        return False


class IsAdminOrReadOnly(BasePermission):
    """
    Ruxsat: Admin to'liq kiradi, boshqalar faqat o'qiydi.

    Qo'llaniladi:
        - Category CRUD
        - Platform sozlamalari
    """

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return request.user and request.user.is_authenticated
        return (
            request.user
            and request.user.is_authenticated
            and is_platform_admin(request.user)
        )
