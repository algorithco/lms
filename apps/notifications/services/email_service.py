"""
Email Service — HTML email notifications.

Sends emails via Django's email backend (SMTP).
Logs every email to NotificationLog for audit trail.

Email types:
    1. Test result — score, percentage, pass/fail status.
    2. Essay graded — AI/teacher grading result.
    3. Certificate — certificate number + download link.
    4. Welcome — on registration.
"""
from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


class EmailService:
    """
    Email xizmati — HTML xabarlar yuborish.

    Barcha xabarlar NotificationLog modelida qayd etiladi.
    """

    DEFAULT_FROM = getattr(settings, "DEFAULT_FROM_EMAIL", "Ona Tili & Adabiyot <noreply@lms-platform.uz>")

    @classmethod
    def _get_from(cls) -> str:
        return cls.DEFAULT_FROM

    # -------------------------------------------------------------------
    # Public methods
    # -------------------------------------------------------------------

    @classmethod
    def send_test_result(
        cls,
        to_email: str,
        student_name: str,
        test_title: str,
        percentage: float,
        is_passed: bool,
        score: str,
        max_score: str,
        recipient: Any = None,
        attempt: Any = None,
    ) -> dict[str, Any]:
        """Test natijasi haqida HTML email yuborish."""
        lang = cls._recipient_language(recipient)
        status_text = "O'tdi ✅" if is_passed else "O'tmadi ❌"
        greeting = "Tabriklaymiz" if is_passed else "Afsuski"

        context = {
            "student_name": student_name,
            "test_title": test_title,
            "percentage": percentage,
            "is_passed": is_passed,
            "status_text": status_text,
            "score": score,
            "max_score": max_score,
            "greeting": greeting,
            "lang": lang,
            "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
        }

        html_content = render_to_string("emails/test_result.html", context)
        text_content = (
            f"{greeting}, {student_name}!\n\n"
            f"Test: {test_title}\n"
            f"Ball: {score}/{max_score}\n"
            f"Foiz: {percentage:.1f}%\n"
            f"Status: {status_text}\n\n"
            f"Batafsil: {context['site_url']}/results/"
        )

        return cls._send_email(
            to_email=to_email,
            subject=f"Test natijasi: {test_title} — {status_text}",
            text_content=text_content,
            html_content=html_content,
            notification_type="test_result",
            recipient=recipient,
            attempt=attempt,
        )

    @classmethod
    def send_essay_graded(
        cls,
        to_email: str,
        student_name: str,
        topic_title: str,
        total_score: float,
        max_score: int,
        converted_score: int | None,
        summary: str,
        recipient: Any = None,
        submission: Any = None,
    ) -> dict[str, Any]:
        """Esse baholanganini bildiruvchi HTML email."""
        lang = cls._recipient_language(recipient)
        context = {
            "student_name": student_name,
            "topic_title": topic_title,
            "total_score": total_score,
            "max_score": max_score,
            "converted_score": converted_score,
            "summary": summary,
            "lang": lang,
            "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
        }

        html_content = render_to_string("emails/essay_graded.html", context)
        text_content = (
            f"Esse baholandi!\n\n"
            f"Mavzu: {topic_title}\n"
            f"Ball: {total_score}/{max_score}\n"
        )
        if converted_score:
            text_content += f"Umumiy: {converted_score}/75\n"
        if summary:
            text_content += f"\nXulosa: {summary}\n"

        return cls._send_email(
            to_email=to_email,
            subject=f"Esse baholandi: {topic_title}",
            text_content=text_content,
            html_content=html_content,
            notification_type="essay_graded",
            recipient=recipient,
        )

    @classmethod
    def send_welcome(
        cls,
        to_email: str,
        student_name: str,
        recipient: Any = None,
    ) -> dict[str, Any]:
        """Ro'yxatdan o'tgan foydalanuvchiga xush kelibsiz emaili."""
        context = {
            "student_name": student_name,
            "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
        }

        html_content = render_to_string("emails/welcome.html", context)
        text_content = (
            f"Xush kelibsiz, {student_name}!\n\n"
            f"Ona Tili & Adabiyot platformasiga ro'yxatdan o'tdingiz.\n"
            f"Bilimingizni sinashni boshlang!\n\n"
            f"{context['site_url']}/dashboard/"
        )

        return cls._send_email(
            to_email=to_email,
            subject="Ona Tili & Adabiyot platformasiga xush kelibsiz!",
            text_content=text_content,
            html_content=html_content,
            notification_type="welcome",
            recipient=recipient,
        )

    @classmethod
    def send_certificate(
        cls,
        to_email: str,
        student_name: str,
        certificate_number: str,
        course_title: str,
        recipient: Any = None,
        certificate: Any = None,
    ) -> dict[str, Any]:
        """Sertifikat tayyorligini bildiruvchi email."""
        context = {
            "student_name": student_name,
            "certificate_number": certificate_number,
            "course_title": course_title,
            "site_url": getattr(settings, "SITE_URL", "http://localhost:8000"),
        }

        html_content = render_to_string("emails/certificate.html", context)
        text_content = (
            f"Tabriklaymiz, {student_name}!\n\n"
            f"Sertifikatingiz tayyor!\n"
            f"Sertifikat raqami: {certificate_number}\n"
            f"Kurs: {course_title}\n\n"
            f"Yuklab olish: {context['site_url']}/certificates/"
        )

        return cls._send_email(
            to_email=to_email,
            subject=f"Sertifikat tayyor: {certificate_number}",
            text_content=text_content,
            html_content=html_content,
            notification_type="certificate",
            recipient=recipient,
            certificate=certificate,
        )

    # -------------------------------------------------------------------
    # Internal
    # -------------------------------------------------------------------

    @classmethod
    def _recipient_language(cls, recipient: Any) -> str:
        """Best-effort language code for the recipient (default: uz)."""
        try:
            lang = getattr(recipient, "language", "")
            return lang if lang in {"uz", "ru", "en"} else "uz"
        except Exception:
            return "uz"

    @classmethod
    def _send_email(
        cls,
        to_email: str,
        subject: str,
        text_content: str,
        html_content: str,
        notification_type: str = "general",
        recipient: Any = None,
        attempt: Any = None,
        certificate: Any = None,
    ) -> dict[str, Any]:
        """Email yuborish + NotificationLog ga yozish."""
        from apps.notifications.models import NotificationLog

        log_entry = NotificationLog.objects.create(
            recipient=recipient,
            channel=NotificationLog.Channel.EMAIL,
            notification_type=notification_type,
            title=subject,
            message=text_content[:1000],
            status=NotificationLog.Status.PENDING,
            related_test_attempt=attempt,
            related_certificate=certificate,
        )

        try:
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=cls._get_from(),
                to=[to_email],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send(fail_silently=False)

            log_entry.status = NotificationLog.Status.SENT
            log_entry.sent_at = timezone.now()
            log_entry.save(update_fields=["status", "sent_at"])

            logger.info("Email sent: to=%s, subject=%s", to_email, subject)
            return {"success": True, "error": None}

        except Exception as e:
            log_entry.status = NotificationLog.Status.FAILED
            log_entry.error_message = str(e)
            log_entry.save(update_fields=["status", "error_message"])

            logger.error("Email send failed: to=%s, error=%s", to_email, e)
            return {"success": False, "error": str(e)}
