"""
Celery tasks — asinxron vazifalar.

Lifecycle:
    1. process_test_result_task — test yakunlangandan keyin PDF + Telegram
    2. generate_certificate_task — faqat PDF generatsiya
    3. send_telegram_result_task — faqat Telegram xabar yuborish

Har bir taskda xatolik yuz bersa, task retry qiladi (max 3 marta).
Task bajarilishi NotificationLog da qayd etiladi.
"""
from __future__ import annotations

import logging
from typing import Any

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Main orchestrator task
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="notifications.process_test_result",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    retry_backoff=True,      # 30s → 60s → 120s … (exponential + jitter)
    retry_backoff_max=300,
    retry_jitter=True,
    time_limit=300,          # PDF gen + Telegram + email can exceed the 120s global
    soft_time_limit=240,
)
def process_test_result_task(
    self: Any,
    result_id: int,
) -> dict[str, Any]:
    """
    Test natijasini qayta ishlash — PDF + Telegram.

    Bu task SubmitAttemptService dan keyin async ravishda chaqiriladi.
    Ketma-ketlik:
        1. Agar o'tgan bo'lsa → Certificate yaratish + PDF generatsiya
        2. Telegram xabar yuborish (natija)
        3. Agar sertifikat bo'lsa → Telegram ga PDF yuborish

    Args:
        result_id: Result model ID.

    Returns:
        {"status": "completed", "certificate_generated": bool, ...}
    """
    try:
        from apps.results.models import Certificate, Result

        result = Result.objects.select_related(
            "student", "test", "course", "attempt",
        ).get(id=result_id)

        logger.info(
            "Processing result: id=%d, student=%s, passed=%s",
            result_id, result.student.email, result.is_passed,
        )

        certificate_generated = False

        # -- Step 1: Certificate generatsiya (o'tgan bo'lsa) ----------------
        if result.is_passed:
            certificate_generated = _generate_certificate(result)

        # -- Step 2: Telegram xabar yuborish --------------------------------
        _send_telegram_result(result, certificate_generated)

        # -- Step 3: Email xabar yuborish ------------------------------------
        _send_email_result(result)

        return {
            "status": "completed",
            "result_id": result_id,
            "certificate_generated": certificate_generated,
        }

    except Result.DoesNotExist as exc:
        logger.warning("Result not visible yet: id=%d; retrying", result_id)
        raise self.retry(exc=exc)

    except Exception as exc:
        logger.exception("Task failed: result_id=%d", result_id)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# 2. Certificate generation task
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="notifications.generate_certificate",
    max_retries=3,
    default_retry_delay=30,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    time_limit=300,
    soft_time_limit=240,
)
def generate_certificate_task(
    self: Any,
    result_id: int,
) -> dict[str, Any]:
    """
    PDF sertifikat generatsiya qilish (mustaqil task).

    Agar Certificate allaqachon mavjud bo'lsa, qayta yaratmaydi.
    """
    try:
        from apps.results.models import Result
        result = Result.objects.select_related(
            "student", "test", "course",
        ).get(id=result_id)

        success = _generate_certificate(result)
        return {"status": "completed", "success": success}

    except Exception as exc:
        logger.exception("Certificate generation failed: result_id=%d", result_id)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# 3. Telegram notification task
# ---------------------------------------------------------------------------

@shared_task(
    bind=True,
    name="notifications.send_telegram_result",
    max_retries=3,
    default_retry_delay=30,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    time_limit=120,
    soft_time_limit=90,
)
def send_telegram_result_task(
    self: Any,
    result_id: int,
) -> dict[str, Any]:
    """
    Telegram xabar yuborish (mustaqil task).
    """
    try:
        from apps.results.models import Result
        result = Result.objects.select_related(
            "student", "test", "course",
        ).get(id=result_id)

        _send_telegram_result(result, certificate_sent=False)
        return {"status": "completed"}

    except Exception as exc:
        logger.exception("Telegram send failed: result_id=%d", result_id)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _generate_certificate(result: Any) -> bool:
    """
    Certificate yaratish + PDF generatsiya.

    1. Certificate model yaratish (agar mavjud bo'lmasa).
    2. PDF generatsiya qilish (ReportLab).
    3. PDF faylni Certificate.file ga saqlash.
    4. Status ni GENERATED ga o'zgartirish.

    Returns:
        True agar muvaffaqiyatli yaratilgan bo'lsa.
    """
    from apps.results.models import Certificate
    from apps.results.services.pdf_service import generate_certificate_pdf

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
        logger.info("Certificate already generated: %s", cert.certificate_number)
        return True

    # Verify URL
    base_url = getattr(settings, "SITE_URL", "http://localhost:8000")
    verify_url = f"{base_url}/api/certificates/verify/{cert.certificate_number}/"

    try:
        # PDF generatsiya
        pdf_bytes = generate_certificate_pdf(
            certificate_number=cert.certificate_number,
            student_full_name=result.student.get_full_name(),
            course_title=result.course.title,
            test_title=result.test.title,
            percentage=float(result.percentage),
            issued_at=cert.issued_at,
            verify_url=verify_url,
        )

        # PDF ni faylga saqlash
        from django.core.files.base import ContentFile

        filename = f"{cert.certificate_number}.pdf"
        cert.file.save(filename, ContentFile(pdf_bytes), save=False)
        cert.status = Certificate.Status.GENERATED
        cert.save(update_fields=["file", "status"])
        from apps.certificates.services.anti_fraud import generate_and_store_checksum
        generate_and_store_checksum(cert)

        logger.info(
            "Certificate generated: %s, file=%s",
            cert.certificate_number, cert.file.name,
        )
        return True

    except Exception:
        cert.status = Certificate.Status.FAILED
        cert.save(update_fields=["status"])
        logger.exception("PDF generation failed for cert: %s", cert.certificate_number)
        return False


def _send_telegram_result(
    result: Any,
    certificate_sent: bool = False,
) -> None:
    """
    Telegram orqali test natijasini yuborish.

    Agar foydalanuvchining telegram_chat_id bo'lsa, xabar yuboriladi.
    Bo'lmasa, faqat log yoziladi.
    """
    from apps.notifications.services.telegram_service import TelegramService

    student = result.student

    # Telegram chat ID mavjudmi?
    if not student.telegram_chat_id or not student.telegram_identity_verified_at:
        logger.info(
            "Student has no telegram_chat_id: %s — skipping notification",
            student.email,
        )
        return

    # Natija xabarini yuborish
    TelegramService.send_test_result(
        chat_id=student.telegram_chat_id,
        student_name=student.get_full_name(),
        test_title=result.test.title,
        percentage=float(result.percentage),
        is_passed=result.is_passed,
        score=str(result.score),
        max_score=str(result.max_score),
        recipient=student,
        attempt=result.attempt,
    )

    # Agar sertifikat yaratilgan bo'lsa, PDF ni ham yuborish
    if certificate_sent and result.is_passed:
        try:
            from apps.results.models import Certificate
            cert = Certificate.objects.get(result=result)
            if cert.file:
                TelegramService.send_certificate(
                    chat_id=student.telegram_chat_id,
                    student_name=student.get_full_name(),
                    certificate_number=cert.certificate_number,
                    course_title=result.course.title,
                    pdf_file_path=cert.file.path if cert.file else None,
                    recipient=student,
                    certificate=cert,
                )
        except Certificate.DoesNotExist:
            logger.warning("Certificate not found for result: %d", result.id)


def _send_email_result(result: Any) -> None:
    """
    Email orqali test natijasini yuborish.
    """
    from apps.notifications.services.email_service import EmailService

    student = result.student

    try:
        EmailService.send_test_result(
            to_email=student.email,
            student_name=student.get_full_name(),
            test_title=result.test.title,
            percentage=float(result.percentage),
            is_passed=result.is_passed,
            score=str(result.score),
            max_score=str(result.max_score),
            recipient=student,
            attempt=result.attempt,
        )
    except Exception as e:
        logger.error("Email send failed for result %d: %s", result.id, e)
