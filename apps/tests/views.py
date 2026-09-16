"""
Tests views — test-taking endpoints.

OPTIMIZATIONS (Phase 7):
    1. Proper logging for all error paths.
    2. Edge case handling: stale attempt detection, timeout on view access.
    3. Better error responses with structured messages.

Endpoints:
    POST /api/tests/{id}/start/                  — Testni boshlash
    GET  /api/tests/attempts/{id}/               — Attempt status + timer
    POST /api/tests/attempts/{id}/save-answer/   — Javob auto-save
    POST /api/tests/attempts/{id}/submit/        — Testni yakunlash
    GET  /api/tests/                             — Testlar ro'yxati
"""
from typing import Any

import logging

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStudent
from apps.accounts.access import is_platform_admin

from .models import Test, TestAttempt
from .permissions import CanStartAttempt, IsAttemptOwner
from .serializers import (
    AttemptCreateSerializer,
    AttemptDetailSerializer,
    AttemptSerializer,
    SaveAnswerSerializer,
    TestDetailSerializer,
    TestListSerializer,
)
from .services import SaveAnswerService, StartAttemptService, SubmitAttemptService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test List (Student: only active tests, Teacher/Admin: all)
# ---------------------------------------------------------------------------
@extend_schema_view(
    list=extend_schema(
        summary="Testlar ro'yxati",
        description=(
            "Barcha testlarni olish.\n\n"
            "- **Student**: faqat active testlar\n"
            "- **Teacher**: o'zi yaratgan testlar\n"
            "- **Admin**: barcha testlar"
        ),
        tags=["Tests"],
    ),
)
class TestListView(generics.ListAPIView):
    """GET /api/tests/ — Testlar ro'yxati."""

    serializer_class = TestListSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        from django.db.models import Count
        user = self.request.user
        qs = Test.objects.select_related("course").annotate(
            total_questions=Count("questions"),
        )

        if is_platform_admin(user):
            return qs
        if user.role == "student":
            return qs.filter(is_active=True)
        elif user.role == "teacher":
            return qs.filter(course__teacher=user)
        return qs.none()


# ---------------------------------------------------------------------------
# Test Detail (with questions)
# ---------------------------------------------------------------------------
@extend_schema_view(
    retrieve=extend_schema(
        summary="Test tafsilotlari",
        description="Test ID bo'yicha to'liq ma'lumot olish — savollar va variantlar bilan.",
        tags=["Tests"],
    ),
)
class TestDetailView(generics.RetrieveAPIView):
    """GET /api/tests/{id}/ — Test tafsilotlari."""

    serializer_class = TestDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if is_platform_admin(user):
            return Test.objects.all()
        if user.role == "student":
            return Test.objects.filter(is_active=True)
        if user.role == "teacher":
            return Test.objects.filter(course__teacher=user)
        return Test.objects.none()


# ---------------------------------------------------------------------------
# Start Attempt
# ---------------------------------------------------------------------------
class StartAttemptView(APIView):
    """
    POST /api/tests/{id}/start/

    Testni boshlash — yangi TestAttempt yaratish.
    Faqat o'quvchilar. Max attempts chegarasi nazorat qilinadi.
    """

    permission_classes = [IsAuthenticated, IsStudent]

    @extend_schema(
        summary="Testni boshlash",
        description=(
            "Yangi test attempt yaratish.\n\n"
            "**Business rules:**\n"
            "- Faqat o'quvchilar test topshira oladi\n"
            "- Aktiv attempt bo'lmasligi kerak\n"
            "- Max attempts chegarasini bosmaslik kerak\n"
            "- Vaqt chegarasi: `time_limit_minutes` daqiqa"
        ),
        request=None,
        responses={
            201: AttemptSerializer,
            400: {"description": "Business rule xatoligi"},
        },
        tags=["Tests"],
    )
    def post(self, request: Request, test_id: int, *args: Any, **kwargs: Any) -> Response:
        """Yangi attempt yaratish."""
        try:
            attempt = StartAttemptService.execute(
                test_id=test_id,
                student=request.user,
            )
        except ValueError as e:
            logger.warning(
                "Start attempt failed: test=%d, user=%d, error=%s",
                test_id, request.user.id, str(e),
            )
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AttemptSerializer(attempt)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Attempt Status (with timer)
# ---------------------------------------------------------------------------
@extend_schema_view(
    retrieve=extend_schema(
        summary="Attempt holati",
        description=(
            "Aktiv attempt holatini olish — timer, javoblar, savollar.\n\n"
            "Student faqat o'z attemptini ko'radi.\n"
            "Vaqt tugagan bo'lsa, avtomatik timeout qilinadi."
        ),
        responses={200: AttemptDetailSerializer},
        tags=["Tests"],
    ),
)
class AttemptDetailView(generics.RetrieveAPIView):
    """GET /api/tests/attempts/{id}/ — Attempt status + timer."""

    serializer_class = AttemptDetailSerializer
    permission_classes = [IsAuthenticated, IsAttemptOwner]

    def get_queryset(self):
        return TestAttempt.objects.select_related(
            "test", "student",
        ).prefetch_related(
            "answers", "answers__selected_choices",
        )

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Attempt holatini olish + timeout tekshirish."""
        instance = self.get_object()

        if instance.status == TestAttempt.Status.IN_PROGRESS:
            if instance.is_time_expired:
                from .services import SubmitAttemptService
                SubmitAttemptService._timeout_attempt(instance)
                instance.refresh_from_db()
                logger.info("Auto-timeout on attempt view: id=%d", instance.id)

        serializer = self.get_serializer(instance)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Save Answer (Auto-save)
# ---------------------------------------------------------------------------
class SaveAnswerView(APIView):
    """
    POST /api/tests/attempts/{id}/save-answer/

    Javobni avtomatik saqlash — har bir javob yozilganda.
    Frontend har bir javob o'zgarishida shu endpointni chaqiradi.
    """

    permission_classes = [IsAuthenticated, IsAttemptOwner]

    @extend_schema(
        summary="Javobni avtomatik saqlash",
        description=(
            "Single yoki multiple choice javobni saqlash.\n\n"
            "- Har bir javob o'zgarishida frontend chaqiradi\n"
            "- Eski javob bo'lsa, yangilanadi (upsert)\n"
            "- Vaqt tugagan bo'lsa, avtomatik timeout"
        ),
        request=SaveAnswerSerializer,
        responses={
            200: {
                "description": "Javob saqlandi",
                "examples": [{
                    "message": "Javob saqlandi.",
                    "question_id": 15,
                    "saved_choices": [23],
                    "remaining_seconds": 1750,
                }],
            },
            400: {"description": "Validation xatoligi"},
        },
        tags=["Tests"],
    )
    def post(self, request: Request, attempt_id: int, *args: Any, **kwargs: Any) -> Response:
        """Javobni saqlash."""
        serializer = SaveAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            answer = SaveAnswerService.execute(
                attempt_id=attempt_id,
                question_id=serializer.validated_data["question_id"],
                choice_ids=serializer.validated_data["choice_ids"],
                text_answer=serializer.validated_data.get("text_answer", ""),
                student=request.user,
            )
        except ValueError as e:
            logger.warning(
                "Save answer failed: attempt=%d, user=%d, error=%s",
                attempt_id, request.user.id, str(e),
            )
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Javob saqlandi.",
                "question_id": answer.question_id,
                "saved_choices": list(
                    answer.selected_choices.values_list("id", flat=True)
                ),
                "remaining_seconds": answer.attempt.remaining_seconds,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Submit Attempt (Finish)
# ---------------------------------------------------------------------------
class SubmitAttemptView(APIView):
    """
    POST /api/tests/attempts/{id}/submit/

    Testni yakunlash — barcha javoblarni tekshirish, ball hisoblash,
    Result yaratish, PDF sertifikat va Telegram xabar async yuborish.
    """

    permission_classes = [IsAuthenticated, IsAttemptOwner]

    @extend_schema(
        summary="Testni yakunlash",
        description=(
            "Testni yakunlash va natijani hisoblash.\n\n"
            "**Steps:**\n"
            "1. Barcha javoblar grading qilinadi\n"
            "2. Ball hisoblanadi (single/multiple choice)\n"
            "3. Result modeliga saqlanadi\n"
            "4. Agar o'tgan bo'lsa → PDF sertifikat generatsiya\n"
            "5. Telegram xabar yuboriladi (async Celery task)"
        ),
        request=None,
        responses={
            200: {
                "description": "Test yakunlandi",
                "examples": [{
                    "message": "Test muvaffaqiyatli yakunlandi!",
                    "result": {
                        "attempt_id": 1,
                        "total_questions": 10,
                        "correct_answers": 8,
                        "wrong_answers": 2,
                        "unanswered": 0,
                        "score": "8.00",
                        "max_score": "10.00",
                        "percentage": "80.00",
                        "is_passed": True,
                        "time_taken_seconds": 1200,
                    },
                }],
            },
            400: {"description": "Business rule xatoligi"},
        },
        tags=["Tests"],
    )
    def post(self, request: Request, attempt_id: int, *args: Any, **kwargs: Any) -> Response:
        """Testni yakunlash."""
        try:
            result = SubmitAttemptService.execute(
                attempt_id=attempt_id,
                student=request.user,
            )
        except ValueError as e:
            logger.warning(
                "Submit failed: attempt=%d, user=%d, error=%s",
                attempt_id, request.user.id, str(e),
            )
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Test muvaffaqiyatli yakunlandi!",
                "result": {
                    "attempt_id": result.attempt_id,
                    "total_questions": result.total_questions,
                    "correct_answers": result.correct_answers,
                    "wrong_answers": result.wrong_answers,
                    "unanswered": result.unanswered,
                    "score": str(result.score),
                    "max_score": str(result.max_score),
                    "percentage": str(result.percentage),
                    "is_passed": result.is_passed,
                    "time_taken_seconds": result.time_taken_seconds,
                },
            },
            status=status.HTTP_200_OK,
        )
