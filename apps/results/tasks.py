"""
Results Celery tasks — certificate generation and result processing.

Lifecycle:
    1. generate_certificate_task(result_id) — PDF sertifikat yaratish
    2. These are called from notifications.tasks.process_test_result_task

Architecture:
    - Single Responsibility: only generates PDF, does NOT send notifications.
    - Uses @shared_task for loose coupling (no hard dependency on celery app).
    - Retry policy: max 3 retries, 30s delay between retries.
    - Every task logs its progress for debugging.
"""

from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="results.generate_certificate",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def generate_certificate_task(
    self: Any,
    result_id: int,
) -> dict[str, Any]:
    """
    PDF sertifikat generatsiya qilish (mustaqil Celery task).

    Agar Certificate allaqachon mavjud va generated bo'lsa, qayta yaratmaydi.

    Args:
        result_id: Result model ID.

    Returns:
        {
            "status": "completed" | "error",
            "certificate_number": str | None,
            "file_size": int | None,
        }
    """
    from apps.results.models import Certificate, Result

    try:
        result = Result.objects.select_related(
            "student",
            "test",
            "course",
        ).get(id=result_id)

        logger.info(
            "Generating certificate: result_id=%d, student=%s, passed=%s",
            result_id,
            result.student.email,
            result.is_passed,
        )

        if not result.is_passed:
            logger.info("Student did not pass — no certificate generated.")
            return {
                "status": "skipped",
                "reason": "not_passed",
                "certificate_number": None,
            }

        from apps.certificates.services.generation import generate_certificate as _gen

        cert, generated = _gen(result)

        file_size = cert.file.size if cert.file else 0
        logger.info(
            "Certificate generated: %s, file=%s, size=%d bytes",
            cert.certificate_number,
            cert.file.name,
            file_size,
        )

        return {
            "status": "completed" if generated else "already_exists",
            "certificate_number": cert.certificate_number,
            "file_size": file_size,
        }

    except Result.DoesNotExist:
        logger.error("Result not found: id=%d", result_id)
        return {
            "status": "error",
            "message": "Result not found",
            "certificate_number": None,
        }

    except Exception as exc:
        logger.exception(
            "Certificate generation failed: result_id=%d",
            result_id,
        )
        from apps.certificates.services.generation import mark_failed as _mark_failed

        _mark_failed(result_id)

        raise self.retry(exc=exc)
