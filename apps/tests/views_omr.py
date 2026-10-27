"""
OMR Answer Sheet Scanner Views (apps/tests/views_omr.py).

POST /api/v1/tests/scan-omr/
Receives photo of paper answer sheet, runs vision grading, returns instant score.
"""

from __future__ import annotations

import logging
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .omr_service import grade_omr_sheet

logger = logging.getLogger(__name__)


class ScanOMRView(APIView):
    """
    POST /api/v1/tests/scan-omr/
    Accepts multipart/form-data:
      - `image`: file (required)
      - `test_id`: int (optional)
      - `mock_code`: str (optional, e.g. MOCK-101)
    """

    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request: Request) -> Response:
        """Return active tests available for OMR answer sheet grading."""
        from apps.tests.models import Test

        tests = Test.objects.filter(is_active=True).order_by("-id")
        data = [
            {
                "id": t.id,
                "title": t.title,
                "mock_code": t.mock_code or "",
                "access_code": t.access_code,
                "exam_type": t.exam_type,
                "subject": getattr(t, "subject", "uzbek"),
                "total_questions": t.questions.count(),
                "time_limit_minutes": t.time_limit_minutes,
            }
            for t in tests
        ]
        return Response(
            {"ok": True, "count": len(data), "tests": data}, status=status.HTTP_200_OK
        )

    def post(self, request: Request) -> Response:
        image_file = request.FILES.get("image")
        if not image_file:
            return Response(
                {
                    "ok": False,
                    "error": "Titul varaqa rasmi yuklanmadi (image maydoni talab qilinadi).",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        test_id_raw = request.data.get("test_id")
        test_id = (
            int(test_id_raw) if test_id_raw and str(test_id_raw).isdigit() else None
        )
        mock_code = str(request.data.get("mock_code") or "").strip() or None

        user = request.user if request.user and request.user.is_authenticated else None

        try:
            result = grade_omr_sheet(
                image_file=image_file,
                test_id=test_id,
                mock_code=mock_code,
                user=user,
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            logger.exception("OMR scan error: %s", e)
            return Response(
                {
                    "ok": False,
                    "error": f"Titul varaqani tahlil qilishda xatolik: {str(e)}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
