"""
Essays Celery tasks.

auto_submit_expired_essays — muddati o'tgan draft esselarni avtomatik baholash.

Scheduled via Celery Beat: every 2 minutes.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def _mark_grading_failed(submission_id: int, error: Exception) -> None:
    """Mark a submission ERROR after all retries are exhausted.

    Guarantees a submission is never left stuck in PENDING when the LLM
    call crashes with an unexpected (non-ValueError) exception.
    """
    from django.db import transaction

    from apps.essays.models import EssaySubmission
    from apps.essays.services import _GRADEABLE_STATUSES

    try:
        with transaction.atomic():
            sub = (
                EssaySubmission.objects.select_for_update()
                .filter(pk=submission_id)
                .first()
            )
            if sub is not None and sub.status in _GRADEABLE_STATUSES:
                sub.status = EssaySubmission.Status.ERROR
                sub.error_message = f"AI baholashda tizim xatoligi: {error}"
                sub.save(update_fields=["status", "error_message", "updated_at"])
    except Exception:
        logger.exception("Failed to mark essay %d as error", submission_id)


@shared_task(
    name="essays.grade_submission",
    acks_late=True,
    bind=True,
    max_retries=2,
    retry_backoff=True,        # exponential backoff: ~2s, ~4s, ...
    retry_backoff_max=120,
    retry_jitter=True,
    # Override the global 120/90s limits — an LLM call with max_tokens=4096
    # legitimately takes longer than 90 seconds.
    time_limit=240,
    soft_time_limit=200,
)
def grade_submission_task(self, submission_id: int, fail_status: str = "pending_teacher") -> dict:
    """
    AI baholashni Celery worker'da bajarish (web thread'ni bloklamaslik).

    Web sahifadagi submit/vaqt-tugash yo'llari faqat ``.delay()`` qiladi;
    sekin LLM chaqiruvi (30–90s) shu task ichida ishlaydi. Row-lock bilan
    ikki marta baholanishning oldini oladi.

    Retry contract:
        - ValueError/ImportError from grade_essay (parse/validation/rate
          errors) → handled inline: manual submit → ERROR, timeout →
          PENDING_TEACHER fallback. No retry (the teacher fallback exists).
        - Any OTHER exception (network crash, timeout, DB error) → retried
          with exponential backoff; after max_retries the submission is
          marked ERROR so it is never stuck in PENDING.

    Args:
        submission_id: EssaySubmission pk.
        fail_status: AI xatoligidagi status ("pending_teacher" yoki "error").

    Returns:
        {"status": ...} dict.
    """
    from django.db import transaction

    from apps.essays.models import EssaySubmission
    from apps.essays.services import (
        _GRADEABLE_STATUSES,
        apply_ai_result,
        auto_submit_essay,
        grade_essay,
        notify_student_essay_graded,
    )

    try:
        with transaction.atomic():
            submission = (
                EssaySubmission.objects.select_for_update()
                .filter(pk=submission_id)
                .first()
            )
            if submission is None:
                return {"status": "missing", "submission_id": submission_id}

            if submission.status not in _GRADEABLE_STATUSES:
                # A concurrent submit/grade already finished it — nothing to do.
                return {"status": "not_gradeable", "current": submission.status}

            # submit-new form (no topic): legacy behavior grades any non-empty
            # text without the min-word / PENDING_TEACHER contract.
            if submission.topic is None:
                try:
                    result = grade_essay(submission.essay_text, topic_title="")
                except (ValueError, ImportError) as exc:
                    submission.status = EssaySubmission.Status.ERROR
                    submission.error_message = str(exc)
                    submission.save(update_fields=["status", "error_message", "updated_at"])
                    logger.error(
                        "Grade task failed: submission=%d, error=%s", submission_id, exc,
                    )
                    return {"status": "error", "error": str(exc)}
                apply_ai_result(submission, result)
                # Background notification — Telegram API hech qachon task'ni
                # buzmasligi kerak (notify funksiyasi o'zi try/except qiladi).
                notify_student_essay_graded(submission)
                return {"status": "graded", "total_score": str(submission.total_score)}

            result = auto_submit_essay(submission, fail_status=fail_status)
            if result.get("success") and submission.status == EssaySubmission.Status.GRADED:
                notify_student_essay_graded(submission)
            return {"status": "ok", "result": result}
    except Exception as exc:
        # Mark ERROR only when no retries remain, otherwise the retry can
        # still grade a PENDING submission.
        if self.request.retries >= self.max_retries:
            _mark_grading_failed(submission_id, exc)
        logger.warning(
            "Essay grade task attempt %d failed: submission=%d, error=%s",
            self.request.retries + 1, submission_id, exc,
        )
        raise self.retry(exc=exc)


@shared_task(
    name="essays.auto_submit_expired",
    acks_late=True,
    bind=True,
    max_retries=2,
    # A sweep over many essays may grade several LLM calls — give it room.
    time_limit=300,
    soft_time_limit=240,
)
def auto_submit_expired_essays(self) -> dict:
    """
    Muddati o'tgan, hali yuborilmagan draft esse larni avtomatik baholash.

    Brauzer yopilgan yoki autosave ishlamagan holatlarda ishlaydi.
    Har 2 daiqada Celery Beat orqali chaqiriladi.
    """
    from django.db import transaction

    from apps.essays.models import EssaySubmission
    from apps.essays.services import auto_submit_essay

    expired_submissions = EssaySubmission.objects.filter(
        status=EssaySubmission.Status.DRAFT,
        password_verified_at__isnull=False,
        auto_submitted=False,
        essay_text__gt="",
    ).select_related("topic")

    count = 0
    fallback_count = 0
    error_count = 0

    for submission in expired_submissions:
        if not submission.is_expired:
            continue

        try:
            # Lock the row for the duration of the grading so two Celery
            # workers (or a worker + an in-flight browser submit) can never
            # grade the same DRAFT submission twice.
            with transaction.atomic():
                locked = (
                    EssaySubmission.objects.select_for_update()
                    .filter(pk=submission.pk)
                    .first()
                )
                if locked is None:
                    continue
                if (
                    locked.status != EssaySubmission.Status.DRAFT
                    or locked.auto_submitted
                ):
                    # Already graded/submitted by a concurrent request
                    continue

                result = auto_submit_essay(locked)
                count += 1

                if result["fallback"]:
                    fallback_count += 1
                elif not result["success"]:
                    error_count += 1

        except Exception as e:
            error_count += 1
            logger.error(
                "Auto-submit task failed: submission=%d, error=%s",
                submission.id, str(e), exc_info=True,
            )

    if count > 0:
        logger.info(
            "Auto-submit task: %d submitted, %d fallback, %d errors",
            count, fallback_count, error_count,
        )

    return {
        "status": "completed",
        "submitted": count,
        "fallback": fallback_count,
        "errors": error_count,
    }
