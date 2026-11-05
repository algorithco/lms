"""
API views for Teacher AI Document-to-Test Converter.
"""

from __future__ import annotations

import logging
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.ai_health import AIUnavailable, record_ai_failure, record_ai_success
from apps.payments.ai_quota import consume_feature_cap, refund_feature_cap
from apps.tests.ai_converter import ConverterError, convert_document_to_test_data, save_converted_test

logger = logging.getLogger(__name__)


def _is_teacher_or_admin(user) -> bool:
    """Tekshiruv: faqat o'qituvchi va administratorlar test yarata oladi."""
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    role = getattr(user, "role", "")
    return role in ("teacher", "admin", "center_admin")


class AiConvertDocumentView(APIView):
    """
    POST /api/v1/tests/ai-convert-document/
    POST /api/tests/ai-convert-document/

    Ustoz yuklagan qog'oz fotosurati yoki test PDF faylini tahlil qilib,
    interaktiv savollar to'plamiga aylantirib qaytaradi.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ai-tools"
    MAX_UPLOAD_BYTES = 15 * 1024 * 1024

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
        if upload_file.size > self.MAX_UPLOAD_BYTES:
            return Response(
                {"error": "Fayl juda katta (15 MB gacha).", "code": "file_too_large"},
                status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            )
        ctype = str(getattr(upload_file, "content_type", "") or "").lower()
        if not (ctype == "application/pdf" or ctype.startswith("image/")):
            return Response(
                {"error": "Faqat PDF yoki rasm yuklang.", "code": "bad_file_type"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        allowed, limit = consume_feature_cap(request.user, "converter")
        if not allowed:
            return Response(
                {"error": "Bugungi konvertatsiya limiti tugadi.", "code": "daily_limit", "limit": limit},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        subject = request.data.get("subject", "uzbek")
        file_bytes = upload_file.read()
        content_type = (
            getattr(upload_file, "content_type", "") or "application/octet-stream"
        )
        filename = getattr(upload_file, "name", "test_doc")

        try:
            parsed_data = convert_document_to_test_data(
                file_bytes=file_bytes,
                filename=filename,
                content_type=content_type,
                subject=subject,
            )
            record_ai_success("converter")
            return Response(
                {"success": True, "data": parsed_data}, status=status.HTTP_200_OK
            )
        except ConverterError:
            # Nothing readable: no template questions are made up.
            refund_feature_cap(request.user, "converter")
            record_ai_failure("converter", "nothing recognised")
            return Response(
                {"error": ConverterError.user_message, "code": "nothing_recognised"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except AIUnavailable as exc:
            refund_feature_cap(request.user, "converter")
            record_ai_failure("converter", exc)
            return Response(
                {"error": AIUnavailable.user_message, "code": "not_converted"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            refund_feature_cap(request.user, "converter")
            logger.exception("AI convert failed: %s", e)
            return Response(
                {"error": "Faylni konvertatsiya qilishda xatolik yuz berdi.", "code": "not_converted"},
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
