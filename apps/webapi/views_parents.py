"""
Web API views for Parent Monitoring & Smart Alerts.
"""

from __future__ import annotations

import random
import re
from typing import Any

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import ParentStudentRelation
from apps.accounts.services.parent_link import get_parent_deep_link


def _clean_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 9:
        digits = "998" + digits
    if not digits.startswith("+") and digits:
        digits = "+" + digits
    return digits


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def parent_relations_view(request: Any) -> Response:
    """
    GET: O'quvchining barcha ota-ona ulanishlarini va Telegram deep-linkini olish.
    POST: Yangi ota-ona telefon raqamini kiritish va tasdiqlash kodini generatsiya qilish.
    """
    user = request.user

    if request.method == "GET":
        relations = ParentStudentRelation.objects.filter(student=user).order_by("-created_at")
        deep_link = get_parent_deep_link(user.id)
        data = [
            {
                "id": r.id,
                "parent_name": r.parent_name,
                "parent_phone": r.parent_phone,
                "parent_telegram_id": r.parent_telegram_id,
                "is_verified": r.is_verified,
                "notifications_enabled": r.notifications_enabled,
                "verification_code": r.verification_code,
                "weekly_report_enabled": r.weekly_report_enabled,
                "instant_alerts_enabled": r.instant_alerts_enabled,
                "created_at": r.created_at,
            }
            for r in relations
        ]
        return Response(
            {
                "relations": data,
                "deep_link": deep_link,
                "student_id": user.id,
                "has_connected_parent": any(r.is_verified and r.parent_telegram_id for r in relations),
            }
        )

    if request.method == "POST":
        raw_phone = request.data.get("parent_phone", "")
        parent_name = str(request.data.get("parent_name", "")).strip()
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
                "parent_name": parent_name,
                "verification_code": code,
                "notifications_enabled": True,
                "weekly_report_enabled": True,
                "instant_alerts_enabled": True,
            },
        )
        if not created and not relation.is_verified:
            relation.verification_code = code
            if parent_name:
                relation.parent_name = parent_name
            relation.save(update_fields=["verification_code", "parent_name"])

        return Response(
            {
                "id": relation.id,
                "parent_name": relation.parent_name,
                "parent_phone": relation.parent_phone,
                "is_verified": relation.is_verified,
                "notifications_enabled": relation.notifications_enabled,
                "verification_code": relation.verification_code,
                "weekly_report_enabled": relation.weekly_report_enabled,
                "instant_alerts_enabled": relation.instant_alerts_enabled,
                "deep_link": get_parent_deep_link(user.id),
                "message": (
                    "Raqam muvaffaqiyatli saqlandi. Ota-onangiz botda ushbu kodni kiritsa "
                    "yoki maxsus havolani ochsa, tizim avtomatik bog'lanadi."
                ),
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def parent_relation_detail_view(request: Any, pk: int) -> Response:
    """
    PATCH: Sozlamalarni yangilash (xabarnomalar, haftalik hisobot yoki ism).
    DELETE: Ota-ona aloqasini o'chirish.
    """
    relation = get_object_or_404(ParentStudentRelation, id=pk, student=request.user)

    if request.method == "DELETE":
        relation.delete()
        return Response({"deleted": True})

    if request.method == "PATCH":
        update_fields = ["updated_at"]

        if "parent_name" in request.data:
            relation.parent_name = str(request.data["parent_name"]).strip()
            update_fields.append("parent_name")

        if "notifications_enabled" in request.data:
            val = request.data["notifications_enabled"]
            relation.notifications_enabled = val.lower() in ("true", "1") if isinstance(val, str) else bool(val)
            update_fields.append("notifications_enabled")

        if "weekly_report_enabled" in request.data:
            val = request.data["weekly_report_enabled"]
            relation.weekly_report_enabled = val.lower() in ("true", "1") if isinstance(val, str) else bool(val)
            update_fields.append("weekly_report_enabled")

        if "instant_alerts_enabled" in request.data:
            val = request.data["instant_alerts_enabled"]
            relation.instant_alerts_enabled = val.lower() in ("true", "1") if isinstance(val, str) else bool(val)
            update_fields.append("instant_alerts_enabled")

        relation.save(update_fields=update_fields)

        return Response(
            {
                "id": relation.id,
                "parent_name": relation.parent_name,
                "notifications_enabled": relation.notifications_enabled,
                "weekly_report_enabled": relation.weekly_report_enabled,
                "instant_alerts_enabled": relation.instant_alerts_enabled,
            }
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def parent_verify_code_view(request: Any) -> Response:
    """
    O'quvchi yoki ota-ona tomonidan 6 xonali tasdiqlash kodini kiritish.
    """
    code = str(request.data.get("verification_code", "")).strip()
    if not code:
        return Response(
            {"error": "Tasdiqlash kodi kiritilmadi."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    relation = ParentStudentRelation.objects.filter(verification_code=code).first()
    if not relation:
        return Response(
            {"error": "Noto'g'ri yoki eskirgan tasdiqlash kodi."},
            status=status.HTTP_404_NOT_FOUND,
        )

    relation.is_verified = True
    relation.notifications_enabled = True
    relation.save(update_fields=["is_verified", "notifications_enabled", "updated_at"])

    return Response(
        {
            "success": True,
            "message": f"Ota-ona ({relation.parent_phone}) va o'quvchi ({relation.student.get_full_name()}) muvaffaqiyatli bog'landi!",
            "relation_id": relation.id,
        }
    )
