"""
Celery tasks for Parent Monitoring & Smart Alerts.
"""

from __future__ import annotations

import logging
from typing import Any
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


def calculate_bmb_grade(percentage: float) -> str:
    """Calculate National Certificate BMB grade from percentage."""
    if percentage >= 86:
        return "A+ (A'lo)"
    if percentage >= 80:
        return "A (A'lo)"
    if percentage >= 73:
        return "B+ (Yaxshi)"
    if percentage >= 67:
        return "B (Yaxshi)"
    if percentage >= 60:
        return "C+ (Qoniqarli)"
    if percentage >= 53:
        return "C (Qoniqarli)"
    return "Fail (Yetarli emas)"


@shared_task(
    bind=True,
    name="notifications.send_parent_test_alert",
    max_retries=3,
    default_retry_delay=30,
)
def send_parent_test_alert_task(self: Any, result_id: int) -> dict[str, Any]:
    """
    O'quvchi test yoki Mock test topshirganda ota-onasining Telegramiga tezkor xabarnoma jo'natish.
    """
    try:
        from apps.accounts.models import ParentStudentRelation
        from apps.notifications.services.telegram_service import TelegramService
        from apps.results.models import Result

        result = Result.objects.select_related("student", "test").get(id=result_id)
        student = result.student

        relations = ParentStudentRelation.objects.filter(
            student=student,
            is_verified=True,
            instant_alerts_enabled=True,
            parent_telegram_id__isnull=False,
        )
        if not relations.exists():
            return {"status": "no_active_parent_subscribers"}

        pct = float(result.percentage)
        bmb_grade = calculate_bmb_grade(pct)

        # Haftalik dinamika
        one_week_ago = timezone.now() - timedelta(days=7)
        past_results = Result.objects.filter(
            student=student,
            calculated_at__gte=one_week_ago,
        ).exclude(id=result.id)

        if past_results.exists():
            past_avg = (
                sum(float(r.percentage) for r in past_results) / past_results.count()
            )
            if pct >= past_avg:
                dynamics = "📈 Ijobiy (O'sish kuzatilmoqda)"
            else:
                dynamics = "⚠️ Ko'proq takrorlash kerak"
        else:
            dynamics = "📊 Birinchi haftalik natija"

        total_questions = (
            getattr(result, "total_questions", 0)
            or getattr(result.test, "question_count", 0)
            or 30
        )
        correct_answers = getattr(result, "correct_answers", 0)
        if not correct_answers and pct > 0:
            correct_answers = int(round(total_questions * (pct / 100.0)))

        student_name = student.get_full_name() or student.email

        message = (
            f"🔔 <b>Farzandingiz {student_name} yangi test topshirdi!</b>\n\n"
            f"📝 <b>Test:</b> {result.test.title}\n"
            f"📊 <b>Natija:</b> {correct_answers}/{total_questions} ({pct:.1f}%)\n"
            f"🏆 <b>BMB Darajasi:</b> {bmb_grade}\n"
            f"📈 <b>Haftalik dinamika:</b> {dynamics}\n\n"
            f"<i>GRAND EDUCATION — Farzandingiz kelajagi biz bilan ishonchli qo'llarda!</i>"
        )

        sent_count = 0
        for rel in relations:
            try:
                TelegramService.send_message(
                    chat_id=rel.parent_telegram_id,
                    text=message,
                    recipient=student,
                    parse_mode="HTML",
                )
                sent_count += 1
            except Exception as exc:
                logger.warning(
                    "Failed to send parent alert to %s: %s", rel.parent_telegram_id, exc
                )

        return {"status": "sent", "count": sent_count}

    except Exception as exc:
        logger.exception("Error sending parent test alert for result_id=%s", result_id)
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="notifications.send_parent_weekly_digest",
    max_retries=2,
    default_retry_delay=60,
)
def send_parent_weekly_digest_task(self: Any) -> dict[str, Any]:
    """
    Har yakshanba soat 18:00 da ota-onalarga haftalik jamlangan hisobotni yuborish.
    """
    try:
        from apps.accounts.models import ParentStudentRelation
        from apps.notifications.services.telegram_service import TelegramService
        from apps.results.models import Result
        from apps.attendance.models import AttendanceRecord

        now = timezone.now()
        seven_days_ago = now - timedelta(days=7)

        active_relations = ParentStudentRelation.objects.filter(
            is_verified=True,
            weekly_report_enabled=True,
            parent_telegram_id__isnull=False,
        ).select_related("student")

        dispatched = 0
        for rel in active_relations:
            student = rel.student
            student_name = student.get_full_name() or student.email

            # Tests this week
            week_results = Result.objects.filter(
                student=student,
                calculated_at__gte=seven_days_ago,
            )
            tests_count = week_results.count()
            if tests_count > 0:
                avg_pct = sum(float(r.percentage) for r in week_results) / tests_count
                avg_grade = calculate_bmb_grade(avg_pct)
            else:
                avg_pct = 0.0
                avg_grade = "Test ishlanmadi"

            # Attendance this week
            try:
                attendances = AttendanceRecord.objects.filter(
                    student=student,
                    session__lesson_date__gte=seven_days_ago.date(),
                )
                total_lessons = attendances.count()
                attended_lessons = attendances.filter(
                    status__in=["present", "late"]
                ).count()
                att_pct = (
                    f"{int((attended_lessons / total_lessons) * 100)}%"
                    if total_lessons > 0
                    else "100%"
                )
            except Exception:
                att_pct = "100%"

            digest_msg = (
                f"📊 <b>FARZANDINGIZNING HAFTALIK HISOBOTI</b>\n"
                f"👤 <b>O'quvchi:</b> {student_name}\n"
                f"📅 <b>Davr:</b> Oxirgi 7 kun\n\n"
                f"📝 <b>Ishlangan testlar soni:</b> {tests_count} ta\n"
                f"🎯 <b>O'rtacha o'zlashtirish:</b> {avg_pct:.1f}%\n"
                f"🏆 <b>O'rtacha BMB darajasi:</b> {avg_grade}\n"
                f"⏱ <b>Darslarga qatnashish davomati:</b> {att_pct}\n\n"
                f"💡 <b>Tavsiya:</b> Ona tili grammatikasi va Milliy sertifikat qoliplarida muntazam test ishlashni davom ettiring.\n\n"
                f"<i>GRAND EDUCATION Smart Monitoring</i>"
            )

            try:
                TelegramService.send_message(
                    chat_id=rel.parent_telegram_id,
                    text=digest_msg,
                    parse_mode="HTML",
                )
                dispatched += 1
            except Exception as e:
                logger.warning(
                    "Failed sending weekly digest to %s: %s", rel.parent_telegram_id, e
                )

        return {"status": "completed", "dispatched": dispatched}

    except Exception as exc:
        logger.exception("Failed running weekly digest task")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="notifications.send_parent_essay_alert",
    max_retries=3,
    default_retry_delay=30,
)
def send_parent_essay_alert_task(self: Any, submission_id: int) -> dict[str, Any]:
    """
    Esse AI yoki ustoz tomonidan baholanganda ota-onaga tezkor xabar yetkazish.
    """
    try:
        from apps.accounts.models import ParentStudentRelation
        from apps.essays.models import EssaySubmission
        from apps.notifications.services.telegram_service import TelegramService

        sub = EssaySubmission.objects.select_related("student", "topic").get(
            id=submission_id
        )
        student = sub.student
        topic_title = sub.topic.title if sub.topic else "Erkin mavzu"

        relations = ParentStudentRelation.objects.filter(
            student=student,
            is_verified=True,
            instant_alerts_enabled=True,
            parent_telegram_id__isnull=False,
        )
        if not relations.exists():
            return {"status": "no_active_parent_subscribers"}

        student_name = student.get_full_name() or student.email
        total_score = float(sub.total_score or 0)
        summary = sub.summary or "Esse muvaffaqiyatli baholandi."

        msg = (
            f"📝 <b>Farzandingiz {student_name}ning essesi baholandi!</b>\n\n"
            f"📌 <b>Mavzu:</b> {topic_title}\n"
            f"🎯 <b>Ball:</b> {total_score:.1f}/24.0\n"
            f"💡 <b>Xulosa:</b> {summary[:300]}\n\n"
            f"<i>GRAND EDUCATION Smart Monitoring</i>"
        )

        sent_count = 0
        for rel in relations:
            try:
                TelegramService.send_message(
                    chat_id=rel.parent_telegram_id,
                    text=msg,
                    recipient=student,
                    parse_mode="HTML",
                )
                sent_count += 1
            except Exception as exc:
                logger.warning(
                    "Failed to send parent essay alert to %s: %s",
                    rel.parent_telegram_id,
                    exc,
                )

        return {"status": "sent", "count": sent_count}
    except Exception as exc:
        logger.exception(
            "Error in send_parent_essay_alert_task for sub_id=%s", submission_id
        )
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="notifications.send_parent_absence_alert",
    max_retries=3,
    default_retry_delay=30,
)
def send_parent_absence_alert_task(
    self: Any, session_id: int, student_id: int
) -> dict[str, Any]:
    """
    O'quvchi darsga kelmaganda (15 daqiqalik kutish oynasidan so'ng) ota-onasiga Telegram xabar yuborish.
    Agar o'quvchi 15 daqiqa ichida darsga kelib status 'present' yoki 'late' ga o'zgargan bo'lsa,
    xabar bekor qilinadi.
    """
    try:
        from apps.accounts.models import ParentStudentLink, ParentStudentRelation, User
        from apps.attendance.models import AttendanceRecord, AttendanceSession
        from apps.notifications.services.telegram_service import TelegramService

        session = AttendanceSession.objects.select_related("group").get(id=session_id)
        student = User.objects.get(id=student_id)
        student_name = student.get_full_name() or student.email

        rec = AttendanceRecord.objects.filter(
            session_id=session_id, student_id=student_id
        ).first()
        if rec is not None and rec.status != "absent":
            return {"status": "cancelled_student_arrived", "current_status": rec.status}

        chat_ids: list[int] = []
        relations = ParentStudentRelation.objects.filter(
            student=student,
            is_verified=True,
            instant_alerts_enabled=True,
            parent_telegram_id__isnull=False,
        )
        for rel in relations:
            if rel.parent_telegram_id and int(rel.parent_telegram_id) not in chat_ids:
                chat_ids.append(int(rel.parent_telegram_id))

        links = ParentStudentLink.objects.filter(
            student=student,
            is_approved=True,
        ).select_related("parent")
        for link in links:
            parent_tg = getattr(link.parent, "telegram_chat_id", None) or getattr(
                link.parent, "telegram_id", None
            )
            if parent_tg and int(parent_tg) not in chat_ids:
                chat_ids.append(int(parent_tg))

        if not chat_ids:
            return {"status": "no_active_parent_subscribers"}

        date_str = session.lesson_date.strftime("%d.%m.%Y")
        msg = (
            f"⚠️ <b>Hurmatli ota-ona!</b>\n\n"
            f"Farzandingiz <b>{student_name}</b> bugun ({date_str}) "
            f"<b>{session.group.name}</b> darsiga kelmadi.\n\n"
            f"Iltimos, dars qoldirilishi sababidan xabardor bo'ling.\n"
            f"<i>GRAND EDUCATION — Mas'uliyatli ta'lim</i>"
        )

        sent_count = 0
        for chat_id in chat_ids:
            try:
                TelegramService.send_message(
                    chat_id=chat_id,
                    text=msg,
                    recipient=student,
                    parse_mode="HTML",
                )
                sent_count += 1
            except Exception as exc:
                logger.warning(
                    "Failed to send parent absence alert to %s: %s", chat_id, exc
                )

        return {"status": "sent", "count": sent_count}
    except Exception as exc:
        logger.exception("Error in send_parent_absence_alert_task")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="notifications.send_tuition_due_alerts",
    max_retries=2,
    default_retry_delay=60,
)
def send_tuition_due_alerts_task(self: Any) -> dict[str, Any]:
    """
    Kurs to'lovi muddati yaqinlashganda (2 kun oldin va muddat kuni) o'quvchi va ota-onaga eslatma yuborish.
    """
    try:
        from datetime import date
        from apps.accounts.models import ParentStudentRelation
        from apps.notifications.services.telegram_service import TelegramService
        from apps.tuition.models import StudentTuition

        today = date.today()
        two_days_later = today + timedelta(days=2)

        # 2 kun qolgan va to'lov kuni bo'lgan to'lanmagan to'lovlar
        tuitions = StudentTuition.objects.filter(
            status__in=[StudentTuition.Status.PENDING, StudentTuition.Status.OVERDUE],
            due_date__in=[today, two_days_later],
        ).select_related("student", "group")

        sent_count = 0
        for tuit in tuitions:
            student = tuit.student
            student_name = student.get_full_name() or student.email
            group_name = tuit.group.name
            fee_formatted = f"{tuit.monthly_fee:,}".replace(",", " ")
            due_str = tuit.due_date.strftime("%d.%m.%Y")

            is_today = tuit.due_date == today
            timing_text = (
                "BUGUN to'lovning oxirgi kuni!"
                if is_today
                else f"To'lov muddatiga 2 kun qoldi ({due_str})."
            )

            # O'quvchiga Telegram xabar
            student_tg_id = getattr(student, "telegram_chat_id", None) or getattr(
                student, "telegram_id", None
            )
            student_msg = (
                f"💳 <b>Kurs to'lovi eslatmasi!</b>\n\n"
                f"Hurmatli <b>{student_name}</b>, sizning <b>{group_name}</b> guruhi uchun oylik to'lovingiz: <b>{fee_formatted} so'm</b>.\n"
                f"⏰ {timing_text}\n\n"
                f"To'lovni amalga oshirib, ustozingizga ma'lum qilishingizni so'raymiz."
            )
            if student_tg_id:
                try:
                    TelegramService.send_message(
                        chat_id=student_tg_id, text=student_msg, parse_mode="HTML"
                    )
                    sent_count += 1
                except Exception:
                    pass

            # Ota-onaga Telegram xabar
            parent_rels = ParentStudentRelation.objects.filter(
                student=student,
                is_verified=True,
                instant_alerts_enabled=True,
                parent_telegram_id__isnull=False,
            )
            parent_msg = (
                f"💳 <b>Hurmatli ota-ona!</b>\n\n"
                f"Farzandingiz <b>{student_name}</b> ning <b>{group_name}</b> guruhi oylik to'lovi: <b>{fee_formatted} so'm</b>.\n"
                f"⏰ {timing_text}\n\n"
                f"<i>GRAND EDUCATION o'quv markazi</i>"
            )
            for rel in parent_rels:
                try:
                    TelegramService.send_message(
                        chat_id=rel.parent_telegram_id,
                        text=parent_msg,
                        parse_mode="HTML",
                    )
                    sent_count += 1
                except Exception:
                    pass

        return {"status": "sent", "count": sent_count}
    except Exception as exc:
        logger.exception("Error in send_tuition_due_alerts_task")
        raise self.retry(exc=exc)
