"""
Web API views for Parent Monitoring & Smart Alerts.
"""
import random
import re
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import ParentStudentRelation


def _clean_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 9:
        digits = "998" + digits
    if not digits.startswith("+") and digits:
        digits = "+" + digits
    return digits


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def parent_relations_view(request):
    """
    GET: O'quvchining barcha ota-ona ulanishlarini olish.
    POST: Yangi ota-ona telefon raqamini kiritish va tasdiqlash kodini generatsiya qilish.
    """
    user = request.user

    if request.method == "GET":
        relations = ParentStudentRelation.objects.filter(student=user).order_by("-created_at")
        data = [
            {
                "id": r.id,
                "parent_phone": r.parent_phone,
                "parent_telegram_id": r.parent_telegram_id,
                "is_verified": r.is_verified,
                "verification_code": r.verification_code,
                "weekly_report_enabled": r.weekly_report_enabled,
                "instant_alerts_enabled": r.instant_alerts_enabled,
                "created_at": r.created_at,
            }
            for r in relations
        ]
        return Response({"relations": data})

    if request.method == "POST":
        raw_phone = request.data.get("parent_phone", "")
        phone = _clean_phone(raw_phone)
        if len(phone) < 9:
            return Response(
                {"error": "Telefon raqami noto'g'ri kiritildi. Masalan: +998901234567"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Generate 6-digit verification code
        code = f"{random.randint(100000, 999999)}"

        relation, created = ParentStudentRelation.objects.get_or_create(
            student=user,
            parent_phone=phone,
            defaults={
                "verification_code": code,
                "weekly_report_enabled": True,
                "instant_alerts_enabled": True,
            },
        )
        if not created and not relation.is_verified:
            relation.verification_code = code
            relation.save(update_fields=["verification_code"])

        return Response(
            {
                "id": relation.id,
                "parent_phone": relation.parent_phone,
                "is_verified": relation.is_verified,
                "verification_code": relation.verification_code,
                "weekly_report_enabled": relation.weekly_report_enabled,
                "instant_alerts_enabled": relation.instant_alerts_enabled,
                "message": (
                    f"Raqam muvaffaqiyatli saqlandi. Ota-onangiz botda ushbu kodni kiritsa "
                    f"yoki botga o'z raqamini yuborsa, tizim avtomatik bog'lanadi."
                ),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def parent_relation_detail_view(request, pk):
    """
    PATCH: Sozlamalarni yangilash (haftalik hisobot yoki tezkor xabarnomalar).
    DELETE: Ota-ona aloqasini o'chirish.
    """
    relation = get_object_or_404(ParentStudentRelation, id=pk, student=request.user)

    if request.method == "DELETE":
        relation.delete()
        return Response({"deleted": True})

    if request.method == "PATCH":
        if "weekly_report_enabled" in request.data:
            val = request.data["weekly_report_enabled"]
            if isinstance(val, str):
                relation.weekly_report_enabled = val.lower() in ("true", "1")
            else:
                relation.weekly_report_enabled = bool(val)
        if "instant_alerts_enabled" in request.data:
            val = request.data["instant_alerts_enabled"]
            if isinstance(val, str):
                relation.instant_alerts_enabled = val.lower() in ("true", "1")
            else:
                relation.instant_alerts_enabled = bool(val)
        relation.save(update_fields=["weekly_report_enabled", "instant_alerts_enabled", "updated_at"])

        return Response(
            {
                "id": relation.id,
                "weekly_report_enabled": relation.weekly_report_enabled,
                "instant_alerts_enabled": relation.instant_alerts_enabled,
            }
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def parent_verify_code_view(request):
    """
    O'quvchi yoki ota-ona tomonidan 6 xonali tasdiqlash kodini kiritish.
    """
    code = str(request.data.get("verification_code", "")).strip()
    if not code:
        return Response({"error": "Tasdiqlash kodi kiritilmadi."}, status=status.HTTP_400_BAD_REQUEST)

    relation = ParentStudentRelation.objects.filter(verification_code=code).first()
    if not relation:
        return Response({"error": "Noto'g'ri yoki eskirgan tasdiqlash kodi."}, status=status.HTTP_404_NOT_FOUND)

    relation.is_verified = True
    relation.save(update_fields=["is_verified", "updated_at"])

    return Response({
        "success": True,
        "message": f"Ota-ona ({relation.parent_phone}) va o'quvchi ({relation.student.get_full_name()}) muvaffaqiyatli bog'landi!",
        "relation_id": relation.id,
    })
