"""Essays teacher-review JSON API — queue, detail and submit.
Mirrors apps/essays/views.py teacher_*_view queries (same authorization).
"""
from __future__ import annotations

import logging

from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.access import is_platform_admin
from apps.essays.models import EssayCriterionScore, EssaySubmission
from apps.essays.services import TeacherReviewService, WordCounter, can_review_submission

logger = logging.getLogger(__name__)


def _require_teacher(user) -> None:
    """Same rule as apps/essays/views.py teacher_required."""
    if not (user.is_authenticated and user.is_active and (
        getattr(user, "role", None) == "teacher" or is_platform_admin(user)
    )):
        raise PermissionDenied("Faqat o'qituvchi va adminlar uchun.")


def _pending_for(user):
    base = EssaySubmission.objects.filter(
        status=EssaySubmission.Status.PENDING_TEACHER,
    ).select_related("student", "topic", "assigned_reviewer")
    if not is_platform_admin(user):
        base = base.filter(
            Q(assigned_reviewer=user)
            | Q(assigned_reviewer__isnull=True, student__student_groups__teacher=user)
        ).distinct()
    return base


def _submission_card(s: EssaySubmission) -> dict:
    student = s.student
    return {
        "id": s.id,
        "student": student.get_full_name() or student.email,
        "student_email": student.email,
        "topic": s.topic.title if s.topic else None,
        "topic_id": s.topic_id,
        "total_score": float(s.total_score),
        "max_score": s.max_score,
        "word_count": s.word_count,
        "status": s.status,
        "teacher_review_requested": s.teacher_review_requested,
        "teacher_review_reason": s.teacher_review_reason,
        "submitted_at": s.submitted_at.isoformat() if getattr(s, "submitted_at", None) else None,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def teacher_queue_view(request):
    _require_teacher(request.user)
    base = _pending_for(request.user)
    student_requested = base.filter(teacher_review_requested=True).order_by(
        "-teacher_review_requested_at"
    )
    pending = base.filter(teacher_review_requested=False).order_by("-submitted_at")
    reviewed = (
        request.user.essay_reviews.select_related(
            "submission", "submission__student", "submission__topic"
        ).order_by("-reviewed_at")[:20]
    )
    return Response({
        "student_requested": [
            _submission_card(s)
            for s in student_requested.select_related("student", "topic")
        ],
        "pending": [_submission_card(s) for s in pending],
        "reviewed": [{
            "submission_id": r.submission_id,
            "student": r.submission.student.get_full_name() or r.submission.student.email,
            "topic": r.submission.topic.title if r.submission.topic else None,
            "final_score": float(r.final_score),
            "reviewed_at": r.reviewed_at.isoformat(),
        } for r in reviewed],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def teacher_submission_view(request, submission_id: int):
    _require_teacher(request.user)
    submission = get_object_or_404(
        EssaySubmission.objects.select_related(
            "student", "topic", "assigned_reviewer",
        ),
        id=submission_id,
    )
    if not can_review_submission(request.user, submission):
        raise PermissionDenied("Bu esseni tekshirishga ruxsatingiz yo'q.")
    ai_criteria = list(submission.criteria.all().order_by("criterion_id"))
    existing_review = getattr(submission, "teacher_review", None)
    return Response({
        "submission": {
            **_submission_card(submission),
            "essay_text": submission.essay_text,
            "summary": submission.summary,
        },
        "ai_criteria": [{
            "criterion_id": c.criterion_id,
            "name": c.name,
            "score": float(c.score),
            "reason": c.reason,
        } for c in ai_criteria],
        "criterion_names": EssayCriterionScore.CRITERION_NAMES,
        "existing_review": (
            {
                "criteria_scores": existing_review.criteria_scores,
                "final_score": float(existing_review.final_score),
                "teacher_comments": existing_review.teacher_comments,
                "reviewed_at": existing_review.reviewed_at.isoformat(),
            } if existing_review else None
        ),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def teacher_submit_review_view(request, submission_id: int):
    _require_teacher(request.user)
    submission = get_object_or_404(EssaySubmission, id=submission_id)
    if not can_review_submission(request.user, submission):
        raise PermissionDenied("Bu esseni tekshirishga ruxsatingiz yo'q.")

    raw_scores = request.data.get("criteria_scores", {})
    if not isinstance(raw_scores, dict):
        return Response(
            {"detail": "criteria_scores must be an object {criterion_id: score}."},
            status=400,
        )
    criteria_scores: dict[int, float] = {}
    allowed_scores = {0.0, 0.5, 1.0, 1.5, 2.0}
    import math as _math
    for cid in range(1, 13):
        raw = raw_scores.get(cid, raw_scores.get(str(cid), None))
        if raw is None:
            return Response({"detail": f"Mezon #{cid}: ball kiritilmadi."}, status=400)
        if isinstance(raw, bool):
            return Response({"detail": f"Mezon #{cid}: ball noto'g'ri."}, status=400)
        try:
            val = float(str(raw).strip() if isinstance(raw, str) else raw)
        except (ValueError, TypeError):
            return Response({"detail": f"Mezon #{cid}: ball noto'g'ri format '{raw}'."}, status=400)
        if not _math.isfinite(val) or val not in allowed_scores:
            return Response({"detail": f"Mezon #{cid}: ball {raw} yaroqsiz. Ruxsat: {sorted(allowed_scores)}"}, status=400)
        criteria_scores[cid] = val

    try:
        review = TeacherReviewService.submit_review(
            submission=submission,
            teacher=request.user,
            criteria_scores=criteria_scores,
            teacher_comments=str(request.data.get("teacher_comments", "")),
        )
    except PermissionDenied as e:
        return Response({"detail": str(e)}, status=403)
    except ValueError as e:
        return Response({"detail": str(e)}, status=400)

    return Response({
        "ok": True,
        "final_score": float(review.final_score),
        "reviewed_at": review.reviewed_at.isoformat(),
    })


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def teacher_edit_submission_view(request, submission_id: int):
    """Platform-admin-only: edit a student's whole essay text.

    Recomputes word_count. Scores are left untouched on purpose — submit a
    review afterwards if the new text needs re-grading.
    """
    if not is_platform_admin(request.user):
        raise PermissionDenied("Faqat platforma adminlari uchun.")
    submission = get_object_or_404(EssaySubmission, id=submission_id)
    essay_text = request.data.get("essay_text", None)
    if not isinstance(essay_text, str) or not essay_text.strip():
        return Response({"detail": "essay_text must be a non-empty string."}, status=400)
    from apps.essays.views import MAX_ESSAY_LENGTH as _MAXLEN2
    if len(essay_text) > _MAXLEN2:
        return Response({"detail": f"esse juda uzun ({len(essay_text)}). Maksimal {_MAXLEN2}."}, status=400)
    submission.essay_text = essay_text
    submission.word_count = WordCounter.count(essay_text)
    submission.save(update_fields=["essay_text", "word_count", "updated_at"])
    return Response({
        **_submission_card(submission),
        "essay_text": submission.essay_text,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def student_improve_view(request, submission_id: int):
    """AI yaxshilangan esse versiyasini qaytarish (yoki yaratish)."""
    submission = get_object_or_404(
        EssaySubmission.objects.select_related("student", "topic"),
        id=submission_id,
        student=request.user,
    )
    if submission.status not in (
        EssaySubmission.Status.GRADED,
        EssaySubmission.Status.AI_EVALUATED,
        EssaySubmission.Status.TEACHER_REVIEWED,
    ):
        return Response(
            {"ok": False, "error": "Esse hali baholanmagan — yaxshilash mumkin emas."},
            status=400,
        )

    from apps.essays.services import generate_improved_essay

    try:
        content = generate_improved_essay(submission)
    except ImproperlyConfigured as e:
        return Response({"ok": False, "error": str(e)}, status=503)
    except ValueError as e:
        return Response({"ok": False, "error": str(e)}, status=502)
    except Exception:
        logger.exception("Unexpected improve error: submission=%s", submission_id)
        return Response(
            {"ok": False, "error": "Kutilmagan xatolik. Qayta urinib ko'ring."},
            status=500,
        )

    return Response({
        "ok": True,
        "improved": bool(getattr(submission, "_improved_fresh", False)),
        "content": content,
        "word_count": WordCounter.count(content),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def student_request_review_view(request, submission_id: int):
    """Ustoz tekshiruvini so'rash."""
    submission = get_object_or_404(
        EssaySubmission,
        id=submission_id,
        student=request.user,
    )
    reason = str(request.data.get("reason", "") if hasattr(request, "data") else "").strip()
    try:
        TeacherReviewService.request_teacher_review(
            submission, request.user, reason,
        )
    except ValueError as e:
        return Response({"ok": False, "error": str(e)}, status=400)

    submission.refresh_from_db()
    logger.info(
        "Teacher review requested: submission=%d, reason=%s",
        submission.id,
        submission.teacher_review_reason[:100] if submission.teacher_review_reason else "",
    )
    return Response({
        "ok": True,
        "submission_id": submission.id,
        "status": submission.status,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ielts_grade_view(request):
    """POST /api/v1/essays/ielts/grade/
    Payload: {
      "essay_text": "...",
      "topic_id": optional int,
      "topic_title": optional str,
      "task_type": "ielts_task1" | "ielts_task2"
    }
    Evaluates English Writing via the 4 official IELTS criteria (Band 1.0–9.0) and persists an EssaySubmission.
    """
    from django.utils import timezone
    from apps.essays.models import EssayTopic
    from apps.essays.services import apply_ai_result, grade_ielts_essay

    data = request.data or {}
    essay_text = str(data.get("essay_text") or "").strip()
    if not essay_text:
        return Response({"error": "Please enter your essay text."}, status=400)

    topic_id = data.get("topic_id")
    topic = EssayTopic.objects.filter(id=topic_id).first() if topic_id else None
    task_type = str(data.get("task_type") or (topic.rubric_type if topic else "ielts_task2")).strip().lower()
    if task_type not in ("ielts_task1", "ielts_task2"):
        task_type = "ielts_task2"

    min_words = topic.word_limit_min if topic else (150 if task_type == "ielts_task1" else 250)
    topic_title = str(data.get("topic_title") or (topic.title if topic else "IELTS Writing Task")).strip()

    submission = EssaySubmission.objects.create(
        student=request.user,
        topic=topic,
        essay_text=essay_text,
        word_count=WordCounter.count(essay_text),
        max_score=9,
        status=EssaySubmission.Status.PENDING,
        password_verified_at=timezone.now(),
        submitted_at=timezone.now(),
        grading_started_at=timezone.now(),
        source=EssaySubmission.Source.WEB,
    )

    result = grade_ielts_essay(
        essay_text=essay_text,
        topic_title=topic_title,
        task_type=task_type,
        min_words=min_words,
    )
    apply_ai_result(submission, result)
    submission.refresh_from_db()

    return Response({
        "ok": True,
        "submission_id": submission.id,
        "overall_band": result["overall_band"],
        "cefr_level": result["cefr_level"],
        "word_count": result["word_count"],
        "min_words": result["min_words"],
        "criteria": result["criteria"],
        "summary": result["summary"],
        "strengths": result["strengths"],
        "weaknesses": result["weaknesses"],
        "teacher_recommendation": result["teacher_recommendation"],
        "improved_text": result["improved_text"],
    })


