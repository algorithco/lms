"""Essay studio extras for the web app.

- POST /api/v1/essays/ocr/            handwritten pages → text for the student to check (no grading, no quota)
- POST /api/v1/essays/image-submit/   checked OCR text → graded as an IMAGE essay
- POST /api/v1/essays/custom/         own topic (Ona tili only) → graded as a TEXT essay

Quota and grading go through the same system as every other channel:
``enforce_essay_quota`` reserves the allowance, ``start_grading`` queues the AI
job, and the reservation is committed only when the job was accepted (released
otherwise). OCR itself is free, exactly as in the Telegram bot. Essays without a
topic are graded on the Ona tili 12-criteria scale, so own-topic essays are
offered for Ona tili only, and an English photo essay must name an English topic.
"""

from __future__ import annotations

import logging

from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.essays.models import EssaySubmission, EssayTopic
from apps.payments.entitlements import QuotaDenied, commit_usage, enforce_essay_quota, release_usage
from apps.payments.models import SubscriptionUsage

logger = logging.getLogger(__name__)

MIN_WORDS_NO_TOPIC = 50
MAX_TITLE = 200


class OcrThrottle(UserRateThrottle):
    scope = "essay-ocr"


class EssaySubmitThrottle(UserRateThrottle):
    scope = "essay-submit"


def _quota_denied(exc: QuotaDenied) -> Response:
    return Response(
        {
            "detail": "LIMIT_EXCEEDED",
            "error": exc.message,
            "message": exc.message,
            "code": exc.code,
            "upgrade_url": "/pricing",
            "retry_after": exc.retry_after_seconds,
            "remaining": exc.remaining,
        },
        status=status.HTTP_403_FORBIDDEN,
    )


def submit_new_essay(user, text: str, *, kind: str, topic: EssayTopic | None = None, custom_title: str = "") -> Response:
    """Validate, reserve the allowance, create the submission and queue grading."""
    from apps.essays.pre_validation import PreValidationError, pre_validate_essay
    from apps.essays.services import WordCounter, start_grading
    from apps.essays.views import MAX_ESSAY_LENGTH

    text = (text or "").strip()
    if not text:
        return Response({"error": "empty", "code": "empty"}, status=status.HTTP_400_BAD_REQUEST)
    if len(text) > MAX_ESSAY_LENGTH:
        return Response({"error": "too_long", "code": "too_long", "max": MAX_ESSAY_LENGTH}, status=status.HTTP_400_BAD_REQUEST)

    words = WordCounter.count(text)
    min_words = topic.word_limit_min if topic else MIN_WORDS_NO_TOPIC
    if words < min_words:
        return Response({"error": "too_short", "code": "too_short", "min": min_words, "words": words}, status=status.HTTP_400_BAD_REQUEST)
    try:
        pre_validate_essay(text, topic_title=topic.title if topic else custom_title, min_words=min(60, min_words))
    except PreValidationError as exc:
        return Response({"error": str(exc), "code": "invalid"}, status=status.HTTP_400_BAD_REQUEST)

    duplicate = (
        EssaySubmission.objects.filter(
            student=user,
            topic=topic,
            essay_text=text,
            status__in=(EssaySubmission.Status.PENDING, EssaySubmission.Status.GRADED),
        )
        .order_by("-id")
        .first()
    )
    if duplicate:
        return Response({"status": "duplicate", "submission_id": duplicate.id}, status=status.HTTP_200_OK)

    with transaction.atomic():
        submission = EssaySubmission.objects.create(
            student=user,
            topic=topic,
            custom_title=custom_title[:MAX_TITLE],
            essay_text=text,
            word_count=words,
            status=EssaySubmission.Status.DRAFT,
            source=EssaySubmission.Source.WEB,
        )
        try:
            reservation = enforce_essay_quota(user, kind, idempotency_key=f"essay:{submission.pk}", source="web")
        except QuotaDenied as exc:
            transaction.set_rollback(True)  # nothing was graded: keep no trace of the attempt
            return _quota_denied(exc)

    dispatch = start_grading(submission, fail_status=EssaySubmission.Status.ERROR)
    if not dispatch.get("success"):
        release_usage(reservation)
        return Response(
            {"status": "error", "error": dispatch.get("error") or "grading_not_started", "submission_id": submission.id},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    commit_usage(reservation)
    return Response({"status": "processing", "submission_id": submission.id}, status=status.HTTP_202_ACCEPTED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([OcrThrottle])
def essay_ocr_view(request: Request) -> Response:
    """Pages (multipart field ``pages``, in order) → recognised text. Never charges, never grades."""
    from apps.essays.ocr import OCRFailed, OCRUnavailable, OCRValidationError, extract_text

    files = request.FILES.getlist("pages")
    if not files:
        return Response({"error": "no_pages", "code": "no_pages"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = extract_text([f.read() for f in files])
    except OCRValidationError as exc:
        return Response({"error": str(exc), "code": "invalid_image"}, status=status.HTTP_400_BAD_REQUEST)
    except OCRUnavailable:
        return Response({"error": "ocr_unavailable", "code": "ocr_unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except OCRFailed as exc:
        return Response({"error": str(exc), "code": "ocr_failed"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    except Exception:
        logger.exception("Unexpected OCR failure for user=%s", request.user.pk)
        return Response({"error": "ocr_failed", "code": "ocr_failed"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
    return Response({"text": result.text, "incomplete": bool(result.is_probably_incomplete), "warnings": list(result.warnings)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([EssaySubmitThrottle])
def essay_image_submit_view(request: Request) -> Response:
    """{text, topic_id?} — the student-checked OCR text, graded as an image essay."""
    topic = None
    topic_id = request.data.get("topic_id")
    if topic_id not in (None, "", 0, "0"):
        topic = EssayTopic.objects.filter(pk=topic_id, is_active=True).first()
        if topic is None:
            return Response({"error": "topic_not_found", "code": "topic_not_found"}, status=status.HTTP_404_NOT_FOUND)
        if (topic.password or "").strip():
            return Response({"error": "topic_locked", "code": "topic_locked"}, status=status.HTTP_403_FORBIDDEN)
    elif str(request.data.get("subject") or "uzbek") == "english":
        # A topic-less essay is graded on the Ona tili scale; English needs its topic.
        return Response({"error": "topic_required", "code": "topic_required"}, status=status.HTTP_400_BAD_REQUEST)
    return submit_new_essay(
        request.user,
        str(request.data.get("text") or ""),
        kind=SubscriptionUsage.Kind.IMAGE_ESSAY,
        topic=topic,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([EssaySubmitThrottle])
def essay_custom_view(request: Request) -> Response:
    """{title, text} — an Ona tili essay on the student's own topic, graded on the 12 criteria."""
    title = " ".join(str(request.data.get("title") or "").split())
    if len(title) < 3:
        return Response({"error": "title_required", "code": "title_required"}, status=status.HTTP_400_BAD_REQUEST)
    return submit_new_essay(
        request.user,
        str(request.data.get("text") or ""),
        kind=SubscriptionUsage.Kind.TEXT_ESSAY,
        custom_title=title,
    )
