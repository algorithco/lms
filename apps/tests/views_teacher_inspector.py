"""
Teacher Mistake Inspector & Test Analytics Views (8.1.0-BOSQICH).

Provides:
1. GET /api/v1/teacher/tests/<test_id>/analytics/
   - Question-level failure percentages, total attempts, Rasch weights, and top 5 hardest questions.
2. GET /api/v1/teacher/attempts/<attempt_id>/details/
   - Deep inspection of a student's attempt:
     - Question text, choices with student's selection vs correct answer.
     - Question type, point weight, official explanation, and AI reasoning.
     - Permissions: User must be teacher/admin/staff or test/group owner.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.access import is_platform_admin
from apps.tests.models import Choice, Question, StudentAnswer, Test, TestAttempt

logger = logging.getLogger(__name__)


def _can_inspect_test_or_attempt(user: Any, test: Test, attempt: TestAttempt | None = None) -> bool:
    """Validate that the requesting user has permission to inspect test analytics or attempt details."""
    if not user or not user.is_authenticated:
        return False

    # Platform Admins, Superusers, and Staff have global root inspection rights
    if is_platform_admin(user) or user.is_staff or user.is_superuser or getattr(user, "role", "") in ("admin", "center_admin"):
        return True

    # Teachers can inspect tests they authored or tests linked to their courses/groups
    if getattr(user, "role", "") == "teacher":
        if test.course and test.course.teacher_id == user.id:
            return True
        # If the test belongs to a group taught by this teacher
        if hasattr(user, "teacher_groups") and user.teacher_groups.filter(id=getattr(test, "group_id", None)).exists():
            return True
        # If the teacher authored the test or is an instructor
        return True

    # Student viewing their own attempt
    if attempt and attempt.student_id == user.id:
        return True

    return False


class TeacherTestAnalyticsView(APIView):
    """
    GET /api/v1/teacher/tests/<test_id>/analytics/
    GET /api/tests/<test_id>/analytics/

    Returns question-level failure percentages, attempt counts, and the top 5 hardest questions.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="O'qituvchi: Test bo'yicha savollar tahlili va eng qiyin savollar",
        description="Har bir savol bo'yicha xato foizlari va eng ko'p o'quvchilar adashgan top 5 savol.",
        tags=["Teacher Analytics"],
    )
    def get(self, request: Request, test_id: int, *args: Any, **kwargs: Any) -> Response:
        try:
            test = Test.objects.prefetch_related("questions", "questions__choices").get(id=test_id)
        except Test.DoesNotExist:
            return Response({"error": "Test topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        if not _can_inspect_test_or_attempt(request.user, test):
            return Response(
                {"error": "Ushbu test tahlilini ko'rish uchun ruxsatingiz yo'q."},
                status=status.HTTP_403_FORBIDDEN,
            )

        questions = test.questions.all().order_by("position")
        total_questions = questions.count()

        # Attempts on this test
        attempts = TestAttempt.objects.filter(
            test=test,
            status__in=[TestAttempt.Status.COMPLETED, TestAttempt.Status.TIMEOUT],
        )
        total_attempts = attempts.count()

        question_stats = []
        for idx, q in enumerate(questions, start=1):
            q_num = q.position or idx
            tot = q.total_attempts
            cor = q.correct_attempts
            fail_count = max(0, tot - cor)
            accuracy_pct = round((cor / tot) * 100.0, 1) if tot > 0 else 100.0
            failure_pct = round(100.0 - accuracy_pct, 1)

            question_stats.append({
                "question_id": q.id,
                "question_number": q_num,
                "text": q.text[:120] + ("..." if len(q.text) > 120 else ""),
                "question_type": q.question_type,
                "points": q.points,
                "rasch_weight": round(q.current_rasch_weight, 1),
                "total_attempts": tot,
                "correct_attempts": cor,
                "failure_count": fail_count,
                "accuracy_percentage": accuracy_pct,
                "failure_percentage": failure_pct,
            })

        # Top 5 hardest questions (highest failure percentage, with at least 1 attempt if available)
        attempted_qs = [q for q in question_stats if q["total_attempts"] > 0]
        if attempted_qs:
            top_hardest = sorted(attempted_qs, key=lambda x: (x["failure_percentage"], x["rasch_weight"]), reverse=True)[:5]
        else:
            top_hardest = sorted(question_stats, key=lambda x: x["rasch_weight"], reverse=True)[:5]

        return Response(
            {
                "test_id": test.id,
                "test_title": test.title,
                "mock_code": test.mock_code or "",
                "subject": test.subject,
                "total_questions": total_questions,
                "total_attempts": total_attempts,
                "questions": question_stats,
                "top_5_hardest": top_hardest,
            },
            status=status.HTTP_200_OK,
        )


class TeacherAttemptDetailsView(APIView):
    """
    GET /api/v1/teacher/attempts/<attempt_id>/details/
    GET /api/tests/attempts/<attempt_id>/details/

    Provides full question-by-question mistake inspection for an attempt:
    - Which choice was chosen by the student vs correct choice
    - Explanation and AI reasoning
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="O'qituvchi: O'quvchi urinishi va xatolari tahlili",
        description="Talabaning har bir savolga bergan javoblari, xatolari va tushuntirishlari.",
        tags=["Teacher Analytics"],
    )
    def get(self, request: Request, attempt_id: int, *args: Any, **kwargs: Any) -> Response:
        try:
            attempt = (
                TestAttempt.objects.select_related("test", "student")
                .prefetch_related(
                    "answers",
                    "answers__question",
                    "answers__question__choices",
                    "answers__selected_choices",
                )
                .get(id=attempt_id)
            )
        except TestAttempt.DoesNotExist:
            return Response({"error": "Test urinishi topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        test = attempt.test
        if not _can_inspect_test_or_attempt(request.user, test, attempt):
            return Response(
                {"error": "Ushbu o'quvchi xatoliklarini ko'rish uchun ruxsatingiz yo'q."},
                status=status.HTTP_403_FORBIDDEN,
            )

        student = attempt.student
        student_name = student.get_full_name() or student.username
        total_questions = test.questions.count()

        # Map student answers by question_id
        answers_by_qid = {ans.question_id: ans for ans in attempt.answers.all()}

        # Fetch questions in order
        all_questions = test.questions.all().prefetch_related("choices").order_by("position")

        questions_detail = []
        correct_count = 0
        mistake_count = 0
        unanswered_count = 0

        for idx, q in enumerate(all_questions, start=1):
            q_num = q.position or idx
            ans = answers_by_qid.get(q.id)

            selected_choice_ids = set()
            student_text = ""
            is_correct = False
            answered = False

            if ans:
                answered = True
                selected_choice_ids = {c.id for c in ans.selected_choices.all()}
                student_text = ans.text_answer or ans.written_text or ""
                is_correct = bool(ans.is_correct)
                if is_correct:
                    correct_count += 1
                else:
                    mistake_count += 1
            else:
                unanswered_count += 1

            # Build choices list
            choices_data = []
            for c in q.choices.all().order_by("position", "id"):
                choices_data.append({
                    "id": c.id,
                    "text": c.text,
                    "is_correct": c.is_correct,
                    "is_selected": c.id in selected_choice_ids,
                })

            ai_feedback = ans.ai_feedback if ans else {}

            questions_detail.append({
                "question_id": q.id,
                "question_number": q_num,
                "question_text": q.text,
                "passage": q.passage or (q.reading_passage.content if q.reading_passage else ""),
                "question_type": q.question_type,
                "points": q.points,
                "rasch_weight": round(q.current_rasch_weight, 1),
                "explanation": q.explanation or "",
                "answered": answered,
                "is_correct": is_correct,
                "student_text_answer": student_text,
                "correct_text": q.correct_text or "",
                "choices": choices_data,
                "ai_feedback": ai_feedback,
            })

        # Calculate time spent formatted
        time_spent_secs = 0
        if attempt.completed_at and attempt.started_at:
            time_spent_secs = max(0, int((attempt.completed_at - attempt.started_at).total_seconds()))
        mins = time_spent_secs // 60
        secs = time_spent_secs % 60
        time_formatted = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

        return Response(
            {
                "attempt_id": attempt.id,
                "test_id": test.id,
                "test_title": test.title,
                "mock_code": test.mock_code or "",
                "student": {
                    "id": student.id,
                    "full_name": student_name,
                    "username": student.username,
                    "email": student.email,
                },
                "status": attempt.status,
                "raw_score": attempt.raw_score,
                "total_questions": total_questions,
                "percentage": float(attempt.percentage),
                "rasch_score": float(attempt.rasch_score),
                "rasch_grade": attempt.rasch_grade or "-",
                "correct_count": correct_count,
                "mistake_count": mistake_count,
                "unanswered_count": unanswered_count,
                "time_spent_formatted": time_formatted,
                "started_at": attempt.started_at.strftime("%d.%m.%Y %H:%M") if attempt.started_at else "-",
                "completed_at": attempt.completed_at.strftime("%d.%m.%Y %H:%M") if attempt.completed_at else "-",
                "questions": questions_detail,
            },
            status=status.HTTP_200_OK,
        )
