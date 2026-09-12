"""
Telegram Bot Service — send notifications via Telegram Bot API.

Uses httpx (async HTTP client) for non-blocking requests.
Logs every attempt to NotificationLog for audit trail.

Message types:
    1. Test result notification — score, percentage, pass/fail status.
    2. Certificate notification — certificate number + PDF document.
    3. General notification — arbitrary text message.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class TelegramService:
    """
    Telegram Bot API xizmati.

    Barcha xabarlar NotificationLog modelida qayd etiladi.
    Xatolik bo'lsa ham log yoziladi (audit trail).

    Message types:
        1. Test result notification — score, percentage, pass/fail status.
        2. Certificate notification — certificate number + PDF document.
        3. Essay graded notification — AI/teacher grading result.
        4. General notification — arbitrary text message.
        5. Inline keyboard — interactive buttons.
    """

    API_BASE = "https://api.telegram.org"

    @classmethod
    def _get_bot_token(cls) -> str:
        """Bot token olish."""
        token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise ValueError("TELEGRAM_BOT_TOKEN sozlanmagan.")
        return token

    @classmethod
    def _get_api_url(cls, method: str) -> str:
        """Full API URL generatsiya qilish."""
        return f"{cls.API_BASE}/bot{cls._get_bot_token()}/{method}"

    # -----------------------------------------------------------------------
    # Utility methods
    # -----------------------------------------------------------------------

    @classmethod
    def send_message_with_keyboard(
        cls,
        chat_id: int,
        text: str,
        buttons: list[list[dict]] | None = None,
        parse_mode: str = "Markdown",
        notification_type: str = "general",
        recipient: Any = None,
        title: str = "",
    ) -> dict[str, Any]:
        """
        Inline keyboard bilan xabar yuborish.

        buttons format: [[{"text": "Tugma", "url": "..."}, ...], ...]
        Yoki callback_data: [[{"text": "Tugma", "callback_data": "..."}, ...]]
        """
        from apps.notifications.models import NotificationLog

        log_entry = NotificationLog.objects.create(
            recipient=recipient,
            channel=NotificationLog.Channel.TELEGRAM,
            notification_type=notification_type,
            title=title,
            message=text,
            status=NotificationLog.Status.PENDING,
        )

        try:
            url = cls._get_api_url("sendMessage")
            payload: dict[str, Any] = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            }

            if buttons:
                payload["reply_markup"] = {"inline_keyboard": buttons}

            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, json=payload)
                data = response.json()

            if data.get("ok"):
                message_id = data["result"]["message_id"]
                log_entry.status = NotificationLog.Status.SENT
                log_entry.external_id = str(message_id)
                log_entry.sent_at = timezone.now()
                log_entry.save(update_fields=["status", "external_id", "sent_at"])
                return {"success": True, "message_id": message_id, "error": None}
            else:
                error_msg = data.get("description", "Unknown error")
                log_entry.status = NotificationLog.Status.FAILED
                log_entry.error_message = error_msg
                log_entry.save(update_fields=["status", "error_message"])
                return {"success": False, "message_id": None, "error": error_msg}

        except Exception as e:
            log_entry.status = NotificationLog.Status.FAILED
            log_entry.error_message = str(e)
            log_entry.save(update_fields=["status", "error_message"])
            return {"success": False, "message_id": None, "error": str(e)}

    @classmethod
    def answer_callback_query(
        cls,
        callback_query_id: str,
        text: str = "",
        show_alert: bool = False,
    ) -> dict[str, Any]:
        """Callback query ga javob berish (tugma bosilganda)."""
        try:
            url = cls._get_api_url("answerCallbackQuery")
            payload = {
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": show_alert,
            }
            with httpx.Client(timeout=5.0) as client:
                response = client.post(url, json=payload)
                return response.json()
        except Exception as e:
            logger.error("answerCallbackQuery failed: %s", e)
            return {"ok": False, "error": str(e)}

    # -----------------------------------------------------------------------
    # Public methods
    # -----------------------------------------------------------------------

    @classmethod
    def send_essay_graded_by_teacher(
        cls,
        chat_id: int,
        student_name: str,
        topic_title: str,
        ai_score: str,
        teacher_score: str,
        max_score: str,
        converted_score: int | None,
        recipient: Any = None,
    ) -> dict[str, Any]:
        """
        O'qituvchi baholagan esse natijasi haqida o'quvchiga xabar.

        Args:
            chat_id: Telegram chat ID.
            student_name: O'quvchi ismi.
            topic_title: Esse mavzusi.
            ai_score: AI bergan ball (masalan "18").
            teacher_score: O'qituvchi bergan ball (masalan "20").
            max_score: Maksimal ball (masalan "24").
            converted_score: 75 balllik shkalada (masalan 62).
            recipient: User instance (NotificationLog uchun).
        """
        text = (
            f"📝 *Esse Baholandi!*\n\n"
            f"👤 O'quvchi: *{student_name}*\n"
            f"📚 Mavzu: *{topic_title}*\n\n"
            f"🤖 AI bahosi: *{ai_score}/{max_score}*\n"
            f"👨‍🏫 O'qituvchi bahosi: *{teacher_score}/{max_score}*\n"
        )
        if converted_score is not None:
            text += f"📊 Umumiy: *{converted_score}/75*\n"
        text += (
            f"\n✅ O'qituvchi sizning essingizni ko'rib chiqdi."
            f"\n🔗 Natijani ko'rish: /essays/result/"
        )

        return cls._send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
            notification_type="essay_graded",
            recipient=recipient,
            title=f"Esse baholandi: {topic_title}",
        )

    @classmethod
    def send_essay_review_requested(
        cls,
        chat_id: int,
        teacher_name: str,
        student_name: str,
        topic_title: str,
        reason: str,
        submission_id: int,
        recipient: Any = None,
    ) -> dict[str, Any]:
        """
        O'quvchi ustozdan tekshirish so'raganda o'qituvchiga xabar.

        Args:
            chat_id: Telegram chat ID (o'qituvchining).
            teacher_name: O'qituvchi ismi.
            student_name: O'quvchi ismi.
            topic_title: Esse mavzusi.
            reason: O'quvchi sababi.
            submission_id: Submission ID.
            recipient: User instance.
        """
        text = (
            f"🔔 *Esse Tekshirish So'rovi*\n\n"
            f"👤 *{student_name}* sizning bahosingizga e'tiroz bildirdi.\n"
            f"📚 Mavzu: *{topic_title}*\n"
        )
        if reason:
            text += f"💬 Sabab: _{reason}_\n"
        text += (
            f"\n🔗 Tekshirish: /essays/teacher/{submission_id}/review/"
        )

        return cls._send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
            notification_type="essay_review_request",
            recipient=recipient,
            title=f"Esse tekshirish so'rovi: {student_name}",
        )

    @classmethod
    def send_test_result(
        cls,
        chat_id: int,
        student_name: str,
        test_title: str,
        percentage: float,
        is_passed: bool,
        score: str,
        max_score: str,
        recipient: Any = None,
        attempt: Any = None,
    ) -> dict[str, Any]:
        """
        Test natijasi haqida xabar yuborish.

        Xabar formati:
            Tabriklaymiz, Jasur! 🎉
            Siz "Django Quiz 1" testidan 90% oldingiz. ✅
            Ball: 9/10
            Status: O'tdi ✅

        Args:
            chat_id: Telegram chat ID.
            student_name: O'quvchi ismi.
            test_title: Test nomi.
            percentage: Foiz (0-100).
            is_passed: O'tdimi?
            score: Ball (format: "9.00").
            max_score: Maks ball (format: "10.00").
            recipient: User instance (NotificationLog uchun).
            attempt: TestAttempt instance (NotificationLog uchun).

        Returns:
            {"success": bool, "message_id": int|None, "error": str|None}
        """
        status_emoji = "✅" if is_passed else "❌"
        status_text = "O'tdi" if is_passed else "O'tmadi"
        greeting = "Tabriklaymiz" if is_passed else "Afsuski"

        text = (
            f"🎓 *Ona Tili & Adabiyot*\n\n"
            f"{greeting}, *{student_name}*!\n\n"
            f"📝 Test: *{test_title}*\n"
            f"📊 Ball: *{score}/{max_score}*\n"
            f"📈 Foiz: *{percentage:.1f}%*\n"
            f"📋 Status: {status_text} {status_emoji}\n\n"
        )

        if is_passed:
            text += "🏆 Sertifikatingiz tayyorlanmoqda!"
        else:
            text += "📚 Keyingi safar yaxshiroq tayyorlang!"

        return cls._send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
            notification_type="test_result",
            recipient=recipient,
            attempt=attempt,
            title=f"Test natijasi: {test_title}",
        )

    @classmethod
    def send_certificate(
        cls,
        chat_id: int,
        student_name: str,
        certificate_number: str,
        course_title: str,
        pdf_file_path: str | None = None,
        recipient: Any = None,
        certificate: Any = None,
    ) -> dict[str, Any]:
        """
        Sertifikat haqida xabar + PDF fayl yuborish.

        Agar pdf_file_path bo'lsa, document sifatida yuboriladi.
        Aks holda, faqat matn xabar yuboriladi.

        Args:
            chat_id: Telegram chat ID.
            student_name: O'quvchi ismi.
            certificate_number: Sertifikat raqami.
            course_title: Kurs nomi.
            pdf_file_path: PDF fayl yo'li (None bo'lsa faqat matn).
            recipient: User instance.
            certificate: Certificate instance.

        Returns:
            {"success": bool, "message_id": int|None, "error": str|None}
        """
        text = (
            f"📜 *Sertifikat Tayyor!*\n\n"
            f"Tabriklaymiz, *{student_name}*!\n\n"
            f"📋 Sertifikat raqami: *{certificate_number}*\n"
            f"📚 Kurs: *{course_title}*\n\n"
            f"🔗 Tekshirish: /verify/{certificate_number}/\n\n"
            f"PDF fayl quyida yuborilmoqda..."
        )

        # Matn xabarini yuborish
        result = cls._send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
            notification_type="certificate",
            recipient=recipient,
            certificate=certificate,
            title=f"Sertifikat: {certificate_number}",
        )

        # Agar PDF fayl bo'lsa, document sifatida yuborish
        if pdf_file_path and result.get("success"):
            cls._send_document(
                chat_id=chat_id,
                file_path=pdf_file_path,
                caption=f"Sertifikat: {certificate_number}",
                recipient=recipient,
                certificate=certificate,
            )

        return result

    # -----------------------------------------------------------------------
    # Internal methods
    # -----------------------------------------------------------------------

    @classmethod
    def _send_message(
        cls,
        chat_id: int,
        text: str,
        parse_mode: str = "Markdown",
        notification_type: str = "general",
        recipient: Any = None,
        attempt: Any = None,
        certificate: Any = None,
        title: str = "",
    ) -> dict[str, Any]:
        """
        Telegram API orqali matn xabar yuborish.

        Har bir yuborilgan/yuborilmagan xabar NotificationLog ga yoziladi.
        """
        from apps.notifications.models import NotificationLog

        # NotificationLog yaratish (PENDING)
        log_entry = NotificationLog.objects.create(
            recipient=recipient,
            channel=NotificationLog.Channel.TELEGRAM,
            notification_type=notification_type,
            title=title,
            message=text,
            status=NotificationLog.Status.PENDING,
            related_test_attempt=attempt,
            related_certificate=certificate,
        )

        try:
            url = cls._get_api_url("sendMessage")
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            }

            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, json=payload)
                data = response.json()

            if data.get("ok"):
                message_id = data["result"]["message_id"]
                log_entry.status = NotificationLog.Status.SENT
                log_entry.external_id = str(message_id)
                log_entry.sent_at = timezone.now()
                log_entry.save(update_fields=[
                    "status", "external_id", "sent_at",
                ])

                logger.info(
                    "Telegram message sent: chat_id=%s, message_id=%s",
                    chat_id, message_id,
                )
                return {"success": True, "message_id": message_id, "error": None}
            else:
                error_msg = data.get("description", "Unknown error")
                log_entry.status = NotificationLog.Status.FAILED
                log_entry.error_message = error_msg
                log_entry.save(update_fields=["status", "error_message"])

                logger.error(
                    "Telegram API error: chat_id=%s, error=%s",
                    chat_id, error_msg,
                )
                return {"success": False, "message_id": None, "error": error_msg}

        except Exception as e:
            log_entry.status = NotificationLog.Status.FAILED
            log_entry.error_message = str(e)
            log_entry.save(update_fields=["status", "error_message"])

            logger.exception("Telegram send failed: chat_id=%s", chat_id)
            return {"success": False, "message_id": None, "error": str(e)}

    @classmethod
    def _send_document(
        cls,
        chat_id: int,
        file_path: str,
        caption: str = "",
        recipient: Any = None,
        certificate: Any = None,
    ) -> dict[str, Any]:
        """
        Telegram API orqali fayl (document) yuborish.

        PDF sertifikat faylini yuborish uchun ishlatiladi.
        """
        from apps.notifications.models import NotificationLog

        log_entry = NotificationLog.objects.create(
            recipient=recipient,
            channel=NotificationLog.Channel.TELEGRAM,
            notification_type="certificate",
            title=f"Certificate PDF: {caption}",
            message=f"PDF fayl yuborildi: {file_path}",
            status=NotificationLog.Status.PENDING,
            related_certificate=certificate,
        )

        try:
            url = cls._get_api_url("sendDocument")

            with httpx.Client(timeout=30.0) as client:
                with open(file_path, "rb") as f:
                    files = {"document": (file_path.split("/")[-1], f, "application/pdf")}
                    data = {"chat_id": chat_id, "caption": caption}
                    response = client.post(url, data=data, files=files)
                    result = response.json()

            if result.get("ok"):
                message_id = result["result"]["message_id"]
                log_entry.status = NotificationLog.Status.SENT
                log_entry.external_id = str(message_id)
                log_entry.sent_at = timezone.now()
                log_entry.save(update_fields=[
                    "status", "external_id", "sent_at",
                ])
                return {"success": True, "message_id": message_id, "error": None}
            else:
                error_msg = result.get("description", "Unknown error")
                log_entry.status = NotificationLog.Status.FAILED
                log_entry.error_message = error_msg
                log_entry.save(update_fields=["status", "error_message"])
                return {"success": False, "message_id": None, "error": error_msg}

        except Exception as e:
            log_entry.status = NotificationLog.Status.FAILED
            log_entry.error_message = str(e)
            log_entry.save(update_fields=["status", "error_message"])
            logger.exception("Telegram document send failed: chat_id=%s", chat_id)
            return {"success": False, "message_id": None, "error": str(e)}
