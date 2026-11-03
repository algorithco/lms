"""
OMR Answer Sheet Scanner Views (apps/tests/views_omr.py).

GET  /api/v1/tests/scan-omr/          tests that can be checked with a sheet
POST /api/v1/tests/scan-omr/          photo → per-question review (no grading)
POST /api/v1/tests/scan-omr/confirm/  confirmed answers → graded attempt
"""

from __future__ import annotations

import logging

from rest_framework import permissions, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .numbering import number_questions
from .omr_service import OmrError, confirm_sheet, omr_tests_queryset, scan_sheet

logger = logging.getLogger(__name__)


def _error(exc: OmrError) -> Response:
    return Response({"ok": False, "code": exc.code, "error": exc.message}, status=exc.http_status)


def _int_or_none(value) -> int | None:
    return int(value) if value and str(value).isdigit() else None


class ScanOMRView(APIView):
    """
    POST multipart/form-data:
      - `image`: JPG/PNG/WEBP photo (required)
      - `test_id`: int, or `mock_code`: str
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_throttles(self):
        self.throttle_scope = "omr-scan" if self.request.method == "POST" else None
        return super().get_throttles()

    def get(self, request: Request) -> Response:
        tests = omr_tests_queryset().prefetch_related("questions__section").order_by("-id")
        data = []
        for t in tests:
            objective = len(number_questions(t, t.questions.all()))
            if not objective:
                continue
            data.append(
                {
                    "id": t.id,
                    "title": t.title,
                    "mock_code": t.mock_code or "",
                    "access_code": t.access_code,
                    "exam_type": t.exam_type,
                    "subject": getattr(t, "subject", "uzbek"),
                    "total_questions": objective,
                    "time_limit_minutes": t.time_limit_minutes,
                }
            )
        return Response({"ok": True, "count": len(data), "tests": data}, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        image_file = request.FILES.get("image")
        if not image_file:
            return _error(OmrError("image_required", "Javoblar varaqasi rasmini yuklang."))
        try:
            result = scan_sheet(
                image_file=image_file,
                test_id=_int_or_none(request.data.get("test_id")),
                mock_code=str(request.data.get("mock_code") or "").strip() or None,
            )
        except OmrError as exc:
            return _error(exc)
        except Exception:
            logger.exception("OMR scan failed")
            return _error(OmrError("scan_failed", "Varaqni tahlil qilib bo'lmadi. Qayta urinib ko'ring.", 500))
        return Response(result, status=status.HTTP_200_OK)


class ConfirmOMRView(APIView):
    """
    POST JSON: {"test_id": 14, "answers": {"<question_id>": "B", ...}}
    Answers were reviewed by the student; grading uses the online pipeline.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]
    throttle_scope = "omr-confirm"

    def post(self, request: Request) -> Response:
        test_id = _int_or_none(request.data.get("test_id"))
        answers = request.data.get("answers")
        if not test_id or not isinstance(answers, dict):
            return _error(OmrError("bad_request", "test_id va answers maydonlari talab qilinadi."))
        try:
            result = confirm_sheet(test_id=test_id, answers=answers, user=request.user)
        except OmrError as exc:
            return _error(exc)
        except ValueError as exc:
            return _error(OmrError("grading_failed", str(exc)))
        return Response(result, status=status.HTTP_200_OK)
