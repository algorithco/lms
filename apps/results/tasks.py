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
            "student", "test", "course",
        ).get(id=result_id)

        logger.info(
            "Generating certificate: result_id=%d, student=%s, passed=%s",
            result_id, result.student.email, result.is_passed,
        )

        if not result.is_passed:
            logger.info("Student did not pass — no certificate generated.")
            return {
                "status": "skipped",
                "reason": "not_passed",
                "certificate_number": None,
            }

        # Certificate allaqachon mavjudmi?
        cert, created = Certificate.objects.get_or_create(
            result=result,
            defaults={
                "student": result.student,
                "test": result.test,
                "course": result.course,
            },
        )

        if cert.status == Certificate.Status.GENERATED and cert.file:
            logger.info(
                "Certificate already generated: %s",
                cert.certificate_number,
            )
            return {
                "status": "already_exists",
                "certificate_number": cert.certificate_number,
                "file_size": cert.file.size if cert.file else None,
            }

        # Verify URL generatsiya
        base_url = getattr(settings, "SITE_URL", "http://localhost:8000")
        verify_url = f"{base_url}/certificates/verify/{cert.certificate_number}/"

        # PDF generatsiya qilish
        from apps.results.services.pdf_service import generate_certificate_pdf

        pdf_bytes = generate_certificate_pdf(
            certificate_number=cert.certificate_number,
            student_full_name=result.student.get_full_name(),
            course_title=result.course.title,
            test_title=result.test.title,
            percentage=float(result.percentage),
            issued_at=cert.issued_at,
            verify_url=verify_url,
        )

        # PDF faylni modelga saqlash
        from django.core.files.base import ContentFile

        filename = f"{cert.certificate_number}.pdf"
        cert.file.save(filename, ContentFile(pdf_bytes), save=False)
        cert.status = Certificate.Status.GENERATED
        cert.save(update_fields=["file", "status"])
        from apps.certificates.services.anti_fraud import generate_and_store_checksum
        generate_and_store_checksum(cert)

        file_size = cert.file.size if cert.file else 0
        logger.info(
            "Certificate generated: %s, file=%s, size=%d bytes",
            cert.certificate_number, cert.file.name, file_size,
        )

        return {
            "status": "completed",
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
            "Certificate generation failed: result_id=%d", result_id,
        )
        # Mark certificate as failed if it exists
        try:
            cert = Certificate.objects.get(result_id=result_id)
            cert.status = Certificate.Status.FAILED
            cert.save(update_fields=["status"])
        except Certificate.DoesNotExist:
            pass

        raise self.retry(exc=exc)
