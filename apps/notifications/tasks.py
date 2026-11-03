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
    retry_backoff=True,  # 30s → 60s → 120s … (exponential + jitter)
    retry_backoff_max=300,
    retry_jitter=True,
    time_limit=300,  # PDF gen + Telegram + email can exceed the 120s global
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
            "student",
            "test",
            "course",
            "attempt",
        ).get(id=result_id)

        logger.info(
            "Processing result: id=%d, student=%s, passed=%s",
            result_id,
            result.student.email,
            result.is_passed,
        )

        certificate_generated = False

        # -- Step 1: Certificate generatsiya (o'tgan bo'lsa) ----------------
        if result.is_passed:
            certificate_generated = _generate_certificate(result)

        # -- Step 2: Telegram xabar yuborish --------------------------------
        _send_telegram_result(result, certificate_generated)

        # -- Step 3: Email xabar yuborish ------------------------------------
        _send_email_result(result)

        # -- Step 4: Ota-onaga tezkor xabar yuborish -------------------------
        try:
            from apps.notifications.tasks_parent import send_parent_test_alert_task

            send_parent_test_alert_task.delay(result_id)
        except Exception:
            logger.exception("Parent alert dispatch error for result_id=%s", result_id)

        # -- Step 5: Guruhga avtomatik natija va PDF vedomost yuborish ------
        try:
            _send_group_result_and_vedomost(result)
        except Exception:
            logger.exception("Group result broadcasting error for result_id=%s", result_id)

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
            "student",
            "test",
            "course",
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
            "student",
            "test",
            "course",
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
    Certificate yaratish + PDF generatsiya (thin wrapper over canonical service).

    1. Certificate model yaratish (agar mavjud bo'lmasa).
    2. PDF generatsiya qilish (ReportLab).
    3. PDF faylni Certificate.file ga saqlash.
    4. Status ni GENERATED ga o'zgartirish.

    Returns:
        True agar muvaffaqiyatli yaratilgan bo'lsa.
    """
    from apps.certificates.services.generation import generate_certificate as _gen

    try:
        _gen(result)
        return True
    except Exception:
        from apps.results.models import Certificate

        try:
            cert = Certificate.objects.get(result=result)
            cert.status = Certificate.Status.FAILED
            cert.save(update_fields=["status"])
        except Certificate.DoesNotExist:
            pass
        logger.exception(
            "PDF generation failed for cert result=%s", getattr(result, "id", "?")
        )
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


def _send_group_result_and_vedomost(result: Any) -> None:
    """
    O'quvchi test topshirganda uning guruhi Telegram guruh chatiga
    avtomatik xabarnoma va rasmiy PDF vedomostni yuborish.
    """
    import os
    from apps.notifications.services.telegram_service import TelegramService
    from apps.results.pdf_generator import generate_student_vedomost_pdf

    test = result.test
    student = result.student

    # Find group with telegram_chat_id
    group = getattr(test, "assigned_group", None)
    if not group or not group.telegram_chat_id:
        group = student.student_groups.filter(telegram_chat_id__isnull=False).first()

    if not group or not group.telegram_chat_id:
        logger.info("No group with telegram_chat_id found for result=%s student=%s", result.id, student.email)
        return

    # Generate PDF vedomost
    pdf_path = None
    try:
        if result.attempt_id:
            pdf_path = generate_student_vedomost_pdf(result.attempt_id)
    except Exception:
        logger.exception("Failed to generate student vedomost PDF for result=%s", result.id)

    student_name = student.get_full_name() or student.username
    status_emoji = "✅" if result.is_passed else "⚠️"
    status_str = "O'TDI" if result.is_passed else "O'TMADI"

    grade_str = getattr(result, "bmb_grade", "") or getattr(result, "rasch_grade", "") or ""
    attempt = getattr(result, "attempt", None)
    extras = []
    if grade_str:
        extras.append(f"Daraja: {grade_str}")
    if attempt and attempt.band_score:
        extras.append(f"IELTS Band: {attempt.band_score}")
    if attempt and attempt.cefr_level:
        extras.append(f"CEFR: {attempt.cefr_level}")

    extra_info = f"\n🏆 <b>Ko'rsatkich:</b> {' | '.join(extras)}" if extras else ""

    caption = (
        f"📊 <b>YANGI IMTIHON NATIJASI</b>\n\n"
        f"👤 <b>O'quvchi:</b> {student_name}\n"
        f"🏛 <b>Guruh:</b> {group.name}\n"
        f"📝 <b>Imtihon:</b> {test.title}\n"
        f"🎯 <b>Ball:</b> {result.score:g} / {result.max_score:g} ({result.percentage:.1f}%){extra_info}\n"
        f"{status_emoji} <b>Holat:</b> {status_str}\n\n"
        f"<i>Ilova: Rasmiy imtihon vedomosti (PDF)</i>"
    )

    try:
        if pdf_path and os.path.exists(pdf_path):
            TelegramService._send_document(
                chat_id=group.telegram_chat_id,
                file_path=pdf_path,
                caption=caption,
                recipient=student,
                parse_mode="HTML",
            )
        else:
            TelegramService.send_message(
                chat_id=group.telegram_chat_id,
                text=caption,
                parse_mode="HTML",
            )
        logger.info("Sent result & vedomost to group %s (chat_id=%s)", group.name, group.telegram_chat_id)
    except Exception as exc:
        logger.exception("Failed to send telegram message/vedomost to group %s: %s", group.name, exc)


# Import parent notification tasks so Celery discovers them
from apps.notifications import tasks_parent  # noqa: F401


# ---------------------------------------------------------------------------
# Feedback: admin alert and reply delivery (Celery, never inside the request)
# ---------------------------------------------------------------------------


def _html(value: object) -> str:
    from django.utils.html import escape

    return escape(str(value or ""))


@shared_task(
    bind=True,
    name="notifications.notify_admin_new_feedback",
    max_retries=3,
    default_retry_delay=30,
    retry_backoff=True,
    time_limit=60,
)
def notify_admin_new_feedback(self: Any, feedback_id: int) -> dict[str, Any]:
    """Telegram alert for a new feedback. User text is HTML-escaped; no phone/e-mail."""
    from django.conf import settings

    from apps.notifications.models import UserFeedback
    from apps.notifications.services.telegram_service import TelegramService

    fb = UserFeedback.objects.filter(pk=feedback_id).first()
    admin_id = getattr(settings, "ADMIN_TELEGRAM_ID", None)
    if fb is None or not admin_id:
        return {"status": "skipped"}
    urgent = fb.category == UserFeedback.Category.BUG or fb.rating <= 2
    ctx = fb.context or {}
    text = (
        f"{'🚨' if urgent else '📬'} <b>Yangi fikr #{fb.pk}</b>\n"
        f"🏷 {_html(dict(UserFeedback.Category.choices).get(fb.category, fb.category))}"
        f" · {'⭐' * fb.rating} ({fb.rating}/5)\n"
        f"👤 {_html(fb.short_name or 'Mehmon')} [{_html(ctx.get('role', ''))}/{_html(ctx.get('plan', ''))}]\n"
        f"📍 {_html(ctx.get('path', '-'))}\n\n"
        f"<i>{_html(fb.message[:700])}</i>"
    )
    buttons = []
    if fb.consent_public:
        buttons = [[
            {"text": "✅ Saytda chiqarish", "callback_data": f"publish_feedback_{fb.pk}"},
            {"text": "❌ Rad etish", "callback_data": f"reject_feedback_{fb.pk}"},
        ]]
    try:
        TelegramService.send_message_with_keyboard(
            chat_id=int(admin_id), text=text, buttons=buttons or None, parse_mode="HTML"
        )
    except Exception as exc:
        logger.warning("Feedback #%s admin alert failed: %s", feedback_id, exc)
        raise self.retry(exc=exc)
    return {"status": "sent", "urgent": urgent}


@shared_task(
    bind=True,
    name="notifications.send_feedback_reply",
    max_retries=3,
    default_retry_delay=30,
    retry_backoff=True,
    time_limit=60,
)
def send_feedback_reply(self: Any, feedback_id: int) -> dict[str, Any]:
    """Deliver the admin's reply to the author in the bot, if the account is linked."""
    from apps.notifications.models import UserFeedback
    from apps.notifications.services.telegram_service import TelegramService

    fb = UserFeedback.objects.select_related("user").filter(pk=feedback_id).first()
    chat_id = getattr(getattr(fb, "user", None), "telegram_chat_id", None) if fb else None
    if fb is None or not chat_id or not fb.admin_reply:
        return {"status": "skipped"}
    text = (
        f"💬 <b>Fikringizga javob</b>\n\n"
        f"<i>{_html(fb.message[:300])}</i>\n\n"
        f"{_html(fb.admin_reply)}"
    )
    try:
        TelegramService.send_message(chat_id=int(chat_id), text=text, parse_mode="HTML", recipient=fb.user)
    except Exception as exc:
        logger.warning("Feedback #%s reply delivery failed: %s", feedback_id, exc)
        raise self.retry(exc=exc)
    return {"status": "sent"}
