"""
API views for Teacher AI Document-to-Test Converter.
"""

from __future__ import annotations

import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.tests.ai_converter import convert_document_to_test_data, save_converted_test

logger = logging.getLogger(__name__)


def _is_teacher_or_admin(user) -> bool:
    """Tekshiruv: faqat ustoz yoki adminlar test yarata oladi."""
    return (
        user.is_authenticated
        and (getattr(user, "role", None) in ("teacher", "admin") or user.is_staff)
    )


class AiConvertDocumentView(APIView):
    """
    POST /api/v1/tests/ai-convert-document/
    POST /api/tests/ai-convert-document/

    Ustoz yuklagan qog'oz fotosurati yoki test PDF faylini tahlil qilib,
    interaktiv savollar to'plamiga aylantirib qaytaradi.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        if not _is_teacher_or_admin(request.user):
            return Response(
                {"error": "Faqat o'qituvchi va administratorlar test yarata oladi."},
                status=status.HTTP_403_FORBIDDEN,
            )

        upload_file = request.FILES.get("file")
        if not upload_file:
            return Response(
                {"error": "Iltimos, test rasmi yoki PDF faylni yuklang."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        subject = request.data.get("subject", "uzbek")
        file_bytes = upload_file.read()
        content_type = getattr(upload_file, "content_type", "") or "application/octet-stream"
        filename = getattr(upload_file, "name", "test_doc")

        try:
            parsed_data = convert_document_to_test_data(
                file_bytes=file_bytes,
                filename=filename,
                content_type=content_type,
                subject=subject,
            )
            return Response({"success": True, "data": parsed_data}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("AI convert failed: %s", e)
            return Response(
                {"error": f"Faylni konvertatsiya qilishda xatolik yuz berdi: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AiSaveConvertedTestView(APIView):
    """
    POST /api/v1/tests/ai-save-converted/
    POST /api/tests/ai-save-converted/

    Ustoz tomonidan ko'rib chiqilgan va tahrirlangan savollarni bazaga
    rasmiy Test va #MOCK-... kodi sifatida saqlaydi.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        if not _is_teacher_or_admin(request.user):
            return Response(
                {"error": "Faqat o'qituvchi va administratorlar test saqlay oladi."},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            result = save_converted_test(request.user, request.data)
            return Response(result, status=status.HTTP_201_CREATED)
        except ValueError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception("Save converted test failed: %s", e)
            return Response(
                {"error": f"Testni saqlashda xatolik yuz berdi: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
