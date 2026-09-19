"""
Essays Celery tasks.

auto_submit_expired_essays — muddati o'tgan draft esselarni avtomatik baholash.

Scheduled via Celery Beat: every 2 minutes.
"""
from __future__ import annotations

import logging

from celery import shared_task
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

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

    Correct architecture (see human task Phase 2):
      A. Short txn: fetch + verify gradeable, snapshot essay_text/topic.
      B. NO txn: call external LLM (bounded timeout, model fallback).
      C. Short txn: persist result or error.

    Never holds a row lock while calling the LLM.
    """
    from django.db import transaction

    from apps.essays.models import EssaySubmission
    from apps.essays.services import (
        _GRADEABLE_STATUSES,
        apply_ai_result,
        grade_essay,
        notify_student_essay_graded,
    )

    # --- Phase A: short claim txn ---------------------------------------
    essay_text: str | None = None
    topic_title = ""
    topic_none = False
    try:
        with transaction.atomic():
            submission = (
                EssaySubmission.objects.select_for_update()
                .select_related("topic")
                .filter(pk=submission_id)
                .first()
            )
            if submission is None:
                return {"status": "missing", "submission_id": submission_id}

            if submission.status not in _GRADEABLE_STATUSES:
                return {"status": "not_gradeable", "current": submission.status}

            essay_text = (submission.essay_text or "").strip()
            topic_none = submission.topic is None
            topic_title = submission.topic.title if submission.topic else ""
            # Empty/under-min are inline fallbacks — persist inside this short
            # txn (no LLM needed) and return; no second txn required.
            if not essay_text:
                from apps.essays.services import _send_to_teacher
                # _send_to_teacher does its own save; we are still inside the
                # outer atomic — run it after committing this claim txn.
                pass
            elif not topic_none:
                from apps.essays.services import WordCounter
                min_words = submission.topic.word_limit_min
                if WordCounter.count(essay_text) < min_words:
                    pass
    except Exception as exc:
        # Claim txn failed (DB contention); let Celery retry.
        if self.request.retries >= self.max_retries:
            _mark_grading_failed(submission_id, exc)
        logger.warning(
            "Essay grade task claim failed: submission=%d, error=%s",
            submission_id, exc,
        )
        raise self.retry(exc=exc)

    # Resolve inline empty/under-min without LLM (reuse claim data).
    # We do this outside the claim txn to keep it short; re-lock briefly.
    if essay_text is not None and not essay_text:
        try:
            with transaction.atomic():
                locked = (
                    EssaySubmission.objects.select_for_update()
                    .filter(pk=submission_id)
                    .first()
                )
                if locked and locked.status in _GRADEABLE_STATUSES and not (locked.essay_text or "").strip():
                    from apps.essays.services import _send_to_teacher as _s2t
                    result = _s2t(locked, "empty")
                    return {"status": "ok", "result": result}
                return {"status": "not_gradeable"}
        except Exception as exc:
            if self.request.retries >= self.max_retries:
                _mark_grading_failed(submission_id, exc)
            raise self.retry(exc=exc)

    if not topic_none and essay_text:
        from apps.essays.services import WordCounter
        try:
            with transaction.atomic():
                locked = (
                    EssaySubmission.objects.select_for_update()
                    .select_related("topic")
                    .filter(pk=submission_id)
                    .first()
                )
                if locked and locked.status in _GRADEABLE_STATUSES and locked.topic is not None:
                    if WordCounter.count((locked.essay_text or "").strip()) < locked.topic.word_limit_min:
                        from apps.essays.services import _send_to_teacher as _s2t2
                        result2 = _s2t2(locked, f"under_min ({WordCounter.count((locked.essay_text or '').strip())} < {locked.topic.word_limit_min})")
                        return {"status": "ok", "result": result2}
        except Exception as exc:
            if self.request.retries >= self.max_retries:
                _mark_grading_failed(submission_id, exc)
            raise self.retry(exc=exc)

    # --- Phase B: LLM outside any txn (topic None path may still LLM) -----
    if topic_none:
        # submit-new form (no topic): legacy behavior grades any non-empty
        # text without the min-word / PENDING_TEACHER contract.
        try:
            result_llm = grade_essay(essay_text or "", topic_title="")
        except (ValueError, ImportError, ImproperlyConfigured) as exc:
            # Handle ImproperlyConfigured as well (not an ImportError).
            from django.core.exceptions import ImproperlyConfigured as _IC
            if isinstance(exc, _IC):
                pass  # falls through to same handling
            try:
                with transaction.atomic():
                    sub2 = (
                        EssaySubmission.objects.select_for_update()
                        .filter(pk=submission_id)
                        .first()
                    )
                    if sub2 is not None and sub2.status in _GRADEABLE_STATUSES:
                        sub2.status = EssaySubmission.Status.ERROR
                        sub2.error_message = str(exc)
                        sub2.save(update_fields=["status", "error_message", "updated_at"])
                logger.error(
                    "Grade task failed: submission=%d, error=%s", submission_id, exc,
                )
                return {"status": "error", "error": str(exc)}
            except Exception as e2:
                if self.request.retries >= self.max_retries:
                    _mark_grading_failed(submission_id, e2)
                raise self.retry(exc=e2)
        except Exception as exc:
            # Transient / unexpected — let Celery retry.
            if self.request.retries >= self.max_retries:
                _mark_grading_failed(submission_id, exc)
            logger.warning(
                "Essay grade task attempt %d failed: submission=%d, error=%s",
                self.request.retries + 1, submission_id, exc,
            )
            raise self.retry(exc=exc)
        # LLM succeeded for topic-less — persist in short txn C.
        try:
            with transaction.atomic():
                sub3 = (
                    EssaySubmission.objects.select_for_update()
                    .filter(pk=submission_id)
                    .first()
                )
                if sub3 is None or sub3.status not in _GRADEABLE_STATUSES:
                    return {"status": "not_gradeable", "current": getattr(sub3, "status", None)}
                apply_ai_result(sub3, result_llm)
                notify_student_essay_graded(sub3)
                return {"status": "graded", "total_score": str(sub3.total_score)}
        except Exception as exc:
            if self.request.retries >= self.max_retries:
                _mark_grading_failed(submission_id, exc)
            raise self.retry(exc=exc)

    # Normal topic-based path: LLM outside txn.
    try:
        result_llm2 = grade_essay(essay_text or "", topic_title=topic_title)
    except (ValueError, ImportError, ImproperlyConfigured) as ie:
        from django.core.exceptions import ImproperlyConfigured as _IC2
        if isinstance(ie, _IC2):
            # Config errors are fatal — do not Celery-retry; record fail_status.
            try:
                with transaction.atomic():
                    subf = (
                        EssaySubmission.objects.select_for_update()
                        .filter(pk=submission_id)
                        .first()
                    )
                    if subf is not None and subf.status in _GRADEABLE_STATUSES:
                        subf.status = fail_status
                        subf.auto_submitted = True
                        from django.utils import timezone as _tz
                        subf.submitted_at = _tz.now()
                        subf.error_message = str(ie)
                        subf.save(update_fields=["status", "auto_submitted", "submitted_at", "error_message", "updated_at"])
                return {"status": "error", "error": str(ie)}
            except Exception as e2:
                if self.request.retries >= self.max_retries:
                    _mark_grading_failed(submission_id, e2)
                raise self.retry(exc=e2)
        # Regular ValueError → same handling (fail_status) without retry.
        try:
            with transaction.atomic():
                subf2 = (
                    EssaySubmission.objects.select_for_update()
                    .filter(pk=submission_id)
                    .first()
                )
                if subf2 is not None and subf2.status in _GRADEABLE_STATUSES:
                    subf2.status = fail_status
                    subf2.auto_submitted = True
                    from django.utils import timezone as _tz2
                    subf2.submitted_at = _tz2.now()
                    subf2.error_message = str(ie)
                    subf2.save(update_fields=["status", "auto_submitted", "submitted_at", "error_message", "updated_at"])
            return {"status": "error", "error": str(ie)}
        except Exception as e2:
            if self.request.retries >= self.max_retries:
                _mark_grading_failed(submission_id, e2)
            raise self.retry(exc=e2)
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            _mark_grading_failed(submission_id, exc)
        logger.warning(
            "Essay grade task attempt %d failed: submission=%d, error=%s",
            self.request.retries + 1, submission_id, exc,
        )
        raise self.retry(exc=exc)

    # --- Phase C: persist success in short txn --------------------------
    try:
        with transaction.atomic():
            subc = (
                EssaySubmission.objects.select_for_update()
                .filter(pk=submission_id)
                .first()
            )
            if subc is None or subc.status not in _GRADEABLE_STATUSES:
                return {"status": "not_gradeable", "current": getattr(subc, "status", None)}
            apply_ai_result(subc, result_llm2)
            subc.auto_submitted = True
            from django.utils import timezone as _tz3
            subc.submitted_at = _tz3.now()
            subc.save(update_fields=["auto_submitted", "submitted_at", "updated_at"])
            # Re-check graded state after apply.
            if subc.status == EssaySubmission.Status.GRADED:
                notify_student_essay_graded(subc)
            return {"status": "ok", "result": {"success": True}}
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            _mark_grading_failed(submission_id, exc)
        logger.warning(
            "Essay grade persist failed: submission=%d, error=%s",
            submission_id, exc,
        )
        raise self.retry(exc=exc)


@shared_task(
    name="essays.reap_stale_pending",
    acks_late=True,
    bind=True,
    max_retries=0,
    time_limit=60,
    soft_time_limit=45,
)
def reap_stale_pending_essays(self) -> dict:
    """
    Stale PENDING reaper — recovers essays orphaned when a daemon thread
    or worker disappeared (restart, OOM, 502). Queued every 60s via beat.

    Uses existing updated_at; no new timestamp. Threshold 10 minutes
    (max legitimate grading << 10m under the bounded 180s LLM budget).
    Bounded batch (20) + conditional requeue (atomic claim) + .delay().
    Idempotent: repeated sweeps requeue at most once per stale row.
    """
    from datetime import timedelta

    from django.db import transaction
    from django.utils import timezone

    from apps.essays.models import EssaySubmission
    from apps.essays.services import expire_overdue_pending_grading

    # The normal stale requeue path updates ``updated_at`` for deduplication;
    # it must not be allowed to renew the absolute pending deadline forever.
    timeout_seconds = max(
        1, int(getattr(settings, "ESSAY_GRADING_PENDING_TIMEOUT_SECONDS", 720))
    )
    deadline = timezone.now() - timedelta(seconds=timeout_seconds)
    overdue = list(
        EssaySubmission.objects.filter(
            status=EssaySubmission.Status.PENDING,
            grading_started_at__isnull=False,
            grading_started_at__lte=deadline,
        ).values_list("id", flat=True)[:20]
    )
    expired = 0
    for sid in overdue:
        pending = EssaySubmission.objects.filter(pk=sid).first()
        if pending is not None and expire_overdue_pending_grading(pending):
            expired += 1

    threshold = timezone.now() - timedelta(minutes=10)
    batch = list(
        EssaySubmission.objects.filter(
            status=EssaySubmission.Status.PENDING,
            updated_at__lte=threshold,
        ).exclude(pk__in=overdue).values_list("id", flat=True)[:20]
    )
    requeued = 0
    for sid in batch:
        try:
            with transaction.atomic():
                claimed = (
                    EssaySubmission.objects.select_for_update()
                    .filter(pk=sid, status=EssaySubmission.Status.PENDING, updated_at__lte=threshold)
                    .first()
                )
                if claimed is None:
                    continue
                # Touch updated_at so the next sweep won't pick it again until
                # another stale window passes; also acts as dedup window.
                claimed.save(update_fields=["updated_at"])
            # Enqueue outside the txn so worker sees committed row.
            from apps.essays.tasks import grade_submission_task
            try:
                grade_submission_task.delay(sid, fail_status=EssaySubmission.Status.ERROR)
                requeued += 1
            except Exception as exc:
                # Broker down — leave PENDING; next sweep will retry. Do not
                # fail the row here; thread fallback is not appropriate inside beat.
                logger.warning("Stale reaper enqueue failed: id=%s %s", sid, exc)
        except Exception:
            logger.exception("Stale reaper failed for %s", sid)
    if requeued:
        logger.info("Reaped %d stale PENDING essays", requeued)
    return {"requeued": requeued, "expired": expired, "scanned": len(batch)}


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
    from django.utils import timezone

    from apps.essays.models import EssaySubmission
    from apps.essays.services import auto_submit_essay

    expired_submissions = list(
        EssaySubmission.objects.filter(
            status=EssaySubmission.Status.DRAFT,
            password_verified_at__isnull=False,
            auto_submitted=False,
            essay_text__gt="",
        ).select_related("topic")[:50]
    )

    count = 0
    fallback_count = 0
    error_count = 0
    enqueued = 0

    for submission in expired_submissions:
        if not submission.is_expired:
            continue

        try:
            # Claim: set processing marker inside a short txn, then enqueue
            # grading outside the txn. Beat must never run LLM inline.
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
                    continue
                locked.auto_submitted = True
                locked.status = EssaySubmission.Status.PENDING
                locked.grading_started_at = timezone.now()
                locked.save(update_fields=[
                    "auto_submitted", "status", "grading_started_at", "updated_at",
                ])
            # Enqueue grading outside txn.
            from apps.essays.tasks import grade_submission_task
            try:
                grade_submission_task.delay(submission.pk)
                enqueued += 1
                count += 1
            except Exception as exc:
                # Broker down — rollback marker so next beat can retry.
                with transaction.atomic():
                    fb = (
                        EssaySubmission.objects.select_for_update()
                        .filter(pk=submission.pk)
                        .first()
                    )
                    if fb is not None and fb.status == EssaySubmission.Status.PENDING:
                        fb.status = EssaySubmission.Status.DRAFT
                        fb.auto_submitted = False
                        fb.grading_started_at = None
                        fb.save(update_fields=[
                            "status", "auto_submitted", "grading_started_at", "updated_at",
                        ])
                logger.warning("Auto-submit enqueue failed: id=%d %s", submission.pk, exc)

        except Exception as e:
            error_count += 1
            logger.error(
                "Auto-submit task failed: submission=%d, error=%s",
                submission.id, str(e), exc_info=True,
            )

    if count > 0 or enqueued > 0:
        logger.info(
            "Auto-submit task: %d enqueued, %d fallback, %d errors",
            enqueued, fallback_count, error_count,
        )

    return {
        "status": "completed",
        "submitted": enqueued,
        "fallback": fallback_count,
        "errors": error_count,
    }
