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
            past_avg = sum(float(r.percentage) for r in past_results) / past_results.count()
            if pct >= past_avg:
                dynamics = "📈 Ijobiy (O'sish kuzatilmoqda)"
            else:
                dynamics = "⚠️ Ko'proq takrorlash kerak"
        else:
            dynamics = "📊 Birinchi haftalik natija"

        total_questions = getattr(result, "total_questions", 0) or getattr(result.test, "question_count", 0) or 30
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
                logger.warning("Failed to send parent alert to %s: %s", rel.parent_telegram_id, exc)

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
                    lesson__date__gte=seven_days_ago.date(),
                )
                total_lessons = attendances.count()
                attended_lessons = attendances.filter(is_present=True).count()
                att_pct = f"{int((attended_lessons / total_lessons) * 100)}%" if total_lessons > 0 else "100%"
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
                logger.warning("Failed sending weekly digest to %s: %s", rel.parent_telegram_id, e)

        return {"status": "completed", "dispatched": dispatched}

    except Exception as exc:
        logger.exception("Failed running weekly digest task")
        raise self.retry(exc=exc)
