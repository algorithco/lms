"""
TMA Test-taking API endpoints.

Endpoints:
    POST /api/telegram/tests/{id}/start/   — Start test attempt
    GET  /api/telegram/tests/{id}/question/ — Get current question
    POST /api/telegram/tests/{id}/answer/   — Submit answer for current question
    GET  /api/telegram/attempts/{id}/result/ — Get attempt result
"""
from __future__ import annotations

import logging
import json
import random
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

logger = logging.getLogger(__name__)


def _jwt_auth(request):
    """Authenticate with SimpleJWT's standard active-user checks."""
    try:
        from rest_framework_simplejwt.authentication import JWTAuthentication
        authenticated = JWTAuthentication().authenticate(request)
        return authenticated[0] if authenticated else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Start Test
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def tma_test_start_view(request, test_id: int) -> JsonResponse:
    """
    POST /api/telegram/tests/{id}/start/

    Start a new test attempt.

    Returns: {attempt_id, questions: [...], time_limit_minutes, started_at}
    """
    user = _jwt_auth(request)
    if not user:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    from apps.tests.models import Test, TestAttempt, Question, Choice

    try:
        test = Test.objects.get(id=test_id, is_active=True)
    except Test.DoesNotExist:
        return JsonResponse({"error": "Test topilmadi"}, status=404)

    # Check for existing active attempt
    existing = TestAttempt.objects.filter(
        test=test, student=user, status=TestAttempt.Status.IN_PROGRESS,
    ).first()

    if existing:
        # Resume existing attempt
        attempt = existing
    else:
        # Create new attempt
        from apps.tests.services import StartAttemptService
        try:
            attempt = StartAttemptService.execute(test_id=test_id, student=user)
        except ValueError as e:
            return JsonResponse({"error": str(e)}, status=400)

    # Get questions
    questions = list(
        test.questions.prefetch_related("choices").order_by("position")
    )

    if test.shuffle_questions:
        random.shuffle(questions)

    # Build question data (without correct answers)
    questions_data = []
    for q in questions:
        choices = list(q.choices.all())
        if test.shuffle_choices:
            random.shuffle(choices)

        # Get previously selected answers
        selected_ids = set()
        saved_text = ""
        try:
            from apps.tests.models import StudentAnswer
            sa = StudentAnswer.objects.filter(
                attempt=attempt, question=q,
            ).first()
            if sa:
                selected_ids = set(sa.selected_choices.values_list("id", flat=True))
                saved_text = sa.text_answer
        except Exception:
            pass

        questions_data.append({
            "id": q.id,
            "text": q.text,
            "question_type": q.question_type,
            "points": q.points,
            "position": q.position,
            "choices": [
                {"id": c.id, "text": c.text}
                for c in choices
            ],
            "selected_choice_ids": list(selected_ids),
            "text_answer": saved_text,
        })

    return JsonResponse({
        "attempt_id": attempt.id,
        "test_title": test.title,
        "test_description": test.description,
        "time_limit_minutes": test.time_limit_minutes,
        "total_questions": len(questions_data),
        "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
        "remaining_seconds": attempt.remaining_seconds,
        "questions": questions_data,
    })


# ---------------------------------------------------------------------------
# Submit Answer (single question)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def tma_test_answer_view(request, test_id: int) -> JsonResponse:
    """
    POST /api/telegram/tests/{id}/answer/

    Submit answer for a single question.

    Request body: {attempt_id, question_id, choice_ids: [int]}
    """
    user = _jwt_auth(request)
    if not user:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    from apps.tests.models import TestAttempt
    from apps.tests.services import SaveAnswerService

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    attempt_id = data.get("attempt_id")
    question_id = data.get("question_id")
    choice_ids = data.get("choice_ids", [])

    if not attempt_id or not question_id:
        return JsonResponse({"error": "attempt_id va question_id kerak"}, status=400)

    try:
        attempt = TestAttempt.objects.get(
            id=attempt_id,
            student=user,
            test_id=test_id,
        )
        SaveAnswerService.execute(
            attempt_id=attempt.id,
            question_id=int(question_id),
            choice_ids=choice_ids if isinstance(choice_ids, list) else [],
            text_answer=str(data.get("text_answer", "")),
            student=user,
            allow_clear=True,
        )
    except TestAttempt.DoesNotExist:
        return JsonResponse({"error": "Attempt topilmadi"}, status=404)
    except (TypeError, ValueError) as exc:
        is_timeout = "Vaqt tugadi" in str(exc)
        return JsonResponse(
            {"error": str(exc), "time_expired": is_timeout},
            status=408 if is_timeout else 400,
        )

    return JsonResponse({"success": True, "saved": True})


# ---------------------------------------------------------------------------
# Submit Test (finish)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def tma_test_submit_view(request, test_id: int) -> JsonResponse:
    """
    POST /api/telegram/tests/{id}/submit/

    Submit all answers and finish the test.

    Request body: {attempt_id, answers: {question_id: [choice_id, ...]}}
    """
    user = _jwt_auth(request)
    if not user:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    from apps.results.models import Result
    from apps.tests.models import TestAttempt
    from apps.tests.services import SaveAnswerService, SubmitAttemptService

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    attempt_id = data.get("attempt_id")
    answers = data.get("answers", {})

    if not attempt_id:
        return JsonResponse({"error": "attempt_id kerak"}, status=400)
    if not isinstance(answers, dict):
        return JsonResponse({"error": "answers obyekt bo'lishi kerak"}, status=400)

    try:
        with transaction.atomic():
            attempt = TestAttempt.objects.select_for_update().get(
                id=attempt_id, student=user, test_id=test_id,
            )
            if attempt.status != TestAttempt.Status.IN_PROGRESS:
                raise ValueError("Attempt allaqachon yakunlangan")

            for q_id_str, c_ids in answers.items():
                q_id = int(q_id_str)
                if isinstance(c_ids, dict):
                    choice_ids = c_ids.get("choice_ids", [])
                    text_answer = str(c_ids.get("text_answer", ""))
                else:
                    choice_ids = c_ids
                    text_answer = ""
                if not isinstance(choice_ids, list):
                    raise ValueError("choice_ids ro'yxat bo'lishi kerak")
                SaveAnswerService.execute(
                    attempt_id=attempt.id,
                    question_id=q_id,
                    choice_ids=choice_ids,
                    text_answer=text_answer,
                    student=user,
                    allow_clear=True,
                )

            outcome = SubmitAttemptService.execute(
                attempt_id=attempt.id,
                student=user,
            )
            result = Result.objects.get(attempt_id=outcome.attempt_id)
    except TestAttempt.DoesNotExist:
        return JsonResponse({"error": "Attempt topilmadi"}, status=404)
    except (TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and "Vaqt tugadi" in str(exc):
            # The failed batch has rolled back. Finalize in a fresh transaction
            # so a timeout cannot be rolled back with its response.
            try:
                outcome = SubmitAttemptService.execute(
                    attempt_id=attempt_id, student=user,
                )
                return JsonResponse({
                    "error": "Vaqt tugadi! Test avtomatik yakunlandi.",
                    "time_expired": True,
                    "result_id": Result.objects.get(attempt_id=outcome.attempt_id).id,
                }, status=408)
            except ValueError:
                pass
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception:
        logger.exception("TMA submit failed: attempt=%s", attempt.id)
        return JsonResponse({"error": "Topshirishda ichki xatolik."}, status=500)

    return JsonResponse({
        "success": True,
        "result_id": result.id if result else None,
        "percentage": float(result.percentage) if result else 0,
        "is_passed": result.is_passed if result else False,
        "correct_answers": result.correct_answers if result else 0,
        "total_questions": result.total_questions if result else 0,
        "score": str(result.score) if result else "0",
        "max_score": str(result.max_score) if result else "0",
    })


# ---------------------------------------------------------------------------
# Get Result
# ---------------------------------------------------------------------------

@csrf_exempt
@require_GET
def tma_attempt_result_view(request, attempt_id: int) -> JsonResponse:
    """
    GET /api/telegram/attempts/{id}/result/

    Get detailed result for a completed attempt.
    """
    user = _jwt_auth(request)
    if not user:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    from apps.tests.models import TestAttempt

    try:
        attempt = TestAttempt.objects.get(
            id=attempt_id, student=user,
        )
    except TestAttempt.DoesNotExist:
        return JsonResponse({"error": "Attempt topilmadi"}, status=404)

    result = getattr(attempt, "result", None)
    if not result:
        return JsonResponse({"error": "Natija hali tayyor emas"}, status=404)

    # Get question details
    questions = attempt.test.questions.prefetch_related("choices").order_by("position")
    question_details = []
    for q in questions:
        try:
            from apps.tests.models import StudentAnswer
            sa = StudentAnswer.objects.filter(attempt=attempt, question=q).first()
            selected_ids = set(sa.selected_choices.values_list("id", flat=True)) if sa else set()
            is_correct = sa.is_correct if sa else None
        except Exception:
            selected_ids = set()
            is_correct = None

        choices = []
        for c in q.choices.all():
            choices.append({
                "id": c.id,
                "text": c.text,
                "is_correct": c.is_correct,
            })

        question_details.append({
            "question_text": q.text,
            "question_type": q.question_type,
            "points": q.points,
            "is_correct": is_correct,
            "choices": choices,
            "selected_ids": list(selected_ids),
        })

    return JsonResponse({
        "result_id": result.id,
        "test_title": attempt.test.title,
        "percentage": float(result.percentage),
        "is_passed": result.is_passed,
        "correct_answers": result.correct_answers,
        "total_questions": result.total_questions,
        "score": str(result.score),
        "max_score": str(result.max_score),
        "time_taken_seconds": result.time_taken_seconds,
        "question_details": question_details,
    })
