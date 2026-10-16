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


def _own_attempt_or_404(request: Request, attempt_id: int):
    """Owner-student attempt or None (→ 404, hides existence from others).

    Teachers may READ own-course attempts (IsAttemptOwner on safe views) but
    only the taking student may mutate/submit through these endpoints.
    """
    try:
        return TestAttempt.objects.get(id=attempt_id, student=request.user)
    except TestAttempt.DoesNotExist:
        return None


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
            "section_progress", "section_progress__section",
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
        elif instance.status == TestAttempt.Status.PENDING_GRADING:
            # Yozma baho fonda tugagan bo'lsa — o'qishda yakunlash
            # (idempotent; hali tayyor emas bo'lsa ValueError yutiladi).
            from .services import SubmitAttemptService
            try:
                SubmitAttemptService.finalize_pending_grading(
                    attempt_id=instance.id, student=request.user,
                )
                instance.refresh_from_db()
                logger.info("Auto-finalized on attempt view: id=%d", instance.id)
            except ValueError:
                pass

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
        """Javobni saqlash (barcha savol turlari; kalitlar hech qachon qaytmaydi)."""
        if _own_attempt_or_404(request, attempt_id) is None:
            return Response(
                {"error": "Attempt topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = SaveAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            answer = SaveAnswerService.execute(
                attempt_id=attempt_id,
                question_id=serializer.validated_data["question_id"],
                choice_ids=serializer.validated_data.get("choice_ids") or [],
                text_answer=serializer.validated_data.get("text_answer", ""),
                gap_answers=serializer.validated_data.get("gap_answers") or {},
                matching=serializer.validated_data.get("matching") or {},
                written_text=serializer.validated_data.get("written_text"),
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
                "saved_gap_positions": sorted(
                    answer.gap_responses.values_list("blank_position", flat=True)
                ),
                "saved_matching_count": answer.matching_responses.count(),
                "written_word_count": answer.written_word_count,
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
        if _own_attempt_or_404(request, attempt_id) is None:
            return Response(
                {"error": "Attempt topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )
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
                    "grading_status": result.grading_status,
                    "certificate_status": result.certificate_status,
                    "objective_score": str(result.objective_score),
                    "writing_score": str(result.writing_score),
                    "pending_written_count": result.pending_written_count,
                },
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Finalize Attempt (PENDING_GRADING → COMPLETED once writing is graded)
# ---------------------------------------------------------------------------
class FinalizeAttemptView(APIView):
    """
    POST /api/tests/attempts/{id}/finalize/

    Yozma baho tayyor bo'lgach kutilayotgan attemptni yakunlash.
    Idempotent: tayyor bo'lmasa 202 + pending qaytaradi.
    """

    permission_classes = [IsAuthenticated, IsAttemptOwner]

    @extend_schema(
        summary="Kutilayotgan natijani yakunlash",
        description=(
            "PENDING_GRADING holatdagi attemptni yakunlash.\n\n"
            "- Yozma ish baholangan bo'lsa → COMPLETED + yangilangan Result\n"
            "- Hali tayyor emas bo'lsa → 202 + pending holat\n"
            "- Boshqa holatlar → 400 (noto'g'ri o'tish)"
        ),
        request=None,
        responses={200: {"description": "Yakunlandi"}, 202: {"description": "Hali kutilmoqda"}},
        tags=["Tests"],
    )
    def post(self, request: Request, attempt_id: int, *args: Any, **kwargs: Any) -> Response:
        """Kutilayotgan baholashni yakunlash."""
        if _own_attempt_or_404(request, attempt_id) is None:
            return Response(
                {"error": "Attempt topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            result = SubmitAttemptService.finalize_pending_grading(
                attempt_id=attempt_id,
                student=request.user,
            )
        except ValueError as e:
            message = str(e)
            if "kutilmoqda" in message:
                return Response(
                    {"status": "pending", "detail": message},
                    status=status.HTTP_202_ACCEPTED,
                )
            logger.warning(
                "Finalize failed: attempt=%d, user=%d, error=%s",
                attempt_id, request.user.id, message,
            )
            return Response(
                {"error": message},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "message": "Natija yakunlandi!",
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
                    "grading_status": result.grading_status,
                    "certificate_status": result.certificate_status,
                    "objective_score": str(result.objective_score),
                    "writing_score": str(result.writing_score),
                    "pending_written_count": result.pending_written_count,
                },
            },
            status=status.HTTP_200_OK,
        )


# ===========================================================================
# 24/7 AI Tutor & Mistake Diagnostics Views
# ===========================================================================

class ResultDiagnosticsView(APIView):
    """
    POST /api/tests/results/<int:result_id>/diagnostics/
    GET  /api/tests/results/<int:result_id>/diagnostics/

    Test natijasi bo'yicha zaif mavzular tahlili va shaxsiy tavsiyalar.
    """
    permission_classes = [IsAuthenticated]

    def get_or_post(self, request: Request, result_id: int) -> Response:
        from apps.results.models import Result
        from apps.tests.ai_tutor import get_result_diagnostics

        result = Result.objects.filter(id=result_id).first()
        if not result:
            return Response({"error": "Natija topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        if not (
            result.student_id == request.user.id
            or is_platform_admin(request.user)
            or (getattr(request.user, "role", None) == "teacher" and result.course.teacher_id == request.user.id)
        ):
            return Response({"error": "Ruxsat etilmagan."}, status=status.HTTP_403_FORBIDDEN)

        data = get_result_diagnostics(result_id)
        return Response(data, status=status.HTTP_200_OK)

    def get(self, request: Request, result_id: int) -> Response:
        return self.get_or_post(request, result_id)

    def post(self, request: Request, result_id: int) -> Response:
        return self.get_or_post(request, result_id)


class QuestionExplainMistakeView(APIView):
    """
    POST /api/tests/questions/<int:question_id>/explain-mistake/

    Xato ishlangan savol uchun interaktiv 24/7 repetitor tushuntirishi.
    Body: {"selected_choice_id": 12, "attempt_id": 34}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, question_id: int) -> Response:
        from apps.tests.ai_tutor import explain_question_mistake

        selected_choice_id = request.data.get("selected_choice_id")
        attempt_id = request.data.get("attempt_id")

        if selected_choice_id is not None:
            try:
                selected_choice_id = int(selected_choice_id)
            except (ValueError, TypeError):
                selected_choice_id = None

        if attempt_id is not None:
            try:
                attempt_id = int(attempt_id)
            except (ValueError, TypeError):
                attempt_id = None

        data = explain_question_mistake(
            question_id=question_id,
            selected_choice_id=selected_choice_id,
            attempt_id=attempt_id,
        )
        return Response(data, status=status.HTTP_200_OK)


# ===========================================================================
# Fast Key-Based Mock Test Views
# ===========================================================================

class QuickMockCreateView(APIView):
    """
    POST /api/tests/mock/create/

    Ustoz uchun bir qatorli kalitlar bilan tezkor Mock sessiya yaratish.
    Body:
    {
        "keys": "1a2b3c4d...40b",
        "title": "Milliy Sertifikat Mock #1",
        "time_limit_minutes": 120,
        "custom_code": "#MOCK-401"
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        user = request.user
        role = getattr(user, "role", None)
        if not (role in ("teacher", "admin") or is_platform_admin(user)):
            return Response(
                {"error": "Faqat o'qituvchilar va administratorlar mock sessiya yarata oladi."},
                status=status.HTTP_403_FORBIDDEN,
            )

        keys_str = request.data.get("keys", "")
        title = request.data.get("title", "")
        time_limit = request.data.get("time_limit_minutes", 120)
        custom_code = request.data.get("custom_code")

        try:
            time_limit = int(time_limit)
        except (ValueError, TypeError):
            time_limit = 120

        from apps.tests.mock_service import create_quick_mock

        try:
            res = create_quick_mock(
                teacher=user,
                key_string=keys_str,
                title=title,
                time_limit_minutes=time_limit,
                custom_code=custom_code,
            )
            return Response(res, status=status.HTTP_201_CREATED)
        except ValueError as err:
            return Response({"error": str(err)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as exc:
            logger.exception("Quick mock creation failed: %s", exc)
            return Response(
                {"error": "Mock test yaratishda xatolik yuz berdi."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class QuickMockJoinView(APIView):
    """
    POST /api/tests/mock/join/

    O'quvchi #MOCK-XXX kodi orqali testga ulanadi va testni boshlaydi.
    Body: {"code": "#MOCK-401", "auto_start": true}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        code = request.data.get("code", "")
        auto_start = bool(request.data.get("auto_start", True))

        if not code or not code.strip():
            return Response({"error": "Mock kodi kiritilmadi."}, status=status.HTTP_400_BAD_REQUEST)

        from apps.tests.mock_service import find_mock_by_code
        test = find_mock_by_code(code.strip())
        if not test:
            return Response(
                {"error": f"'{code}' kodi bo'yicha faol Mock test topilmadi. Kodni tekshirib qayta kiriting."},
                status=status.HTTP_404_NOT_FOUND,
            )

        attempt_id = None
        if auto_start:
            # Mavjud active attempt bormi?
            active = test.attempts.filter(student=request.user, status="in_progress").first()
            if active:
                attempt_id = active.id
            else:
                try:
                    attempt = StartAttemptService.execute(test_id=test.id, student=request.user)
                    attempt_id = attempt.id
                except ValueError as err:
                    # e.g. already reached max attempts
                    active = test.attempts.filter(student=request.user).order_by("-started_at").first()
                    if active:
                        attempt_id = active.id
                    else:
                        return Response({"error": str(err)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "test_id": test.id,
            "title": test.title,
            "mock_code": test.mock_code,
            "total_questions": test.total_questions,
            "time_limit_minutes": test.time_limit_minutes,
            "attempt_id": attempt_id,
        }, status=status.HTTP_200_OK)


class MockLeaderboardView(APIView):
    """
    GET /api/tests/mock/<int:test_id>/leaderboard/

    Mock test bo'yicha guruh reytingi va BMB darajalari taqsimoti.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, test_id: int) -> Response:
        from apps.tests.mock_service import get_mock_leaderboard
        data = get_mock_leaderboard(test_id)
        return Response(data, status=status.HTTP_200_OK)

