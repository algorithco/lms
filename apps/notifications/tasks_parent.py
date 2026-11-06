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



        total_questions = (
            getattr(result, "total_questions", 0)
            or getattr(result.test, "question_count", 0)
            or 30
        )
        correct_answers = getattr(result, "correct_answers", 0)
        if not correct_answers and pct > 0:
            correct_answers = int(round(total_questions * (pct / 100.0)))

        student_name = student.get_full_name() or student.email

        # Fan va emoji
        subject_key = getattr(result.test, "subject", "") or getattr(result.course, "subject", "") or "uzbek"
        SUBJECT_MAP = {
            "uzbek": ("🇺🇿", "Ona tili va Adabiyot"),
            "english": ("🇬🇧", "Ingliz tili (CEFR & IELTS)"),
            "biology": ("🧬", "Biologiya (Milliy sertifikat)"),
            "chemistry": ("🧪", "Kimyo (Milliy sertifikat)"),
            "law": ("⚖️", "Huquqshunoslik (Yurisprudensiya)"),
        }
        subject_icon, subject_name = SUBJECT_MAP.get(subject_key, ("📚", "Umumiy Fan"))

        # Streak info
        from apps.accounts.gamification import get_user_streak_info
        streak_data = get_user_streak_info(student)
        streak_days = streak_data.get("streak_days", 1)

        # Zaif mavzu (xato savollar mavzusi)
        weak_topics = "Barcha savollar to'g'ri ishlangan!"
        if getattr(result, "attempt", None):
            wrong_answers = (
                result.attempt.answers.filter(is_correct=False)
                .select_related("question")[:3]
            )
            topics = []
            for wa in wrong_answers:
                q = wa.question
                topic = (
                    getattr(q, "topic", "")
                    or (q.section.name if getattr(q, "section", None) else "")
                    or (q.text[:40] if getattr(q, "text", None) else "")
                )
                if topic and topic not in topics:
                    topics.append(topic)
            if topics:
                weak_topics = ", ".join(topics)
            elif wrong_answers.exists():
                weak_topics = "Asosiy tushunchalar va qonuniyatlarni takrorlash"

        # Guruhdagi o'rni
        group_rank = "Faol ishtirokchi"
        group = student.student_groups.first()
        if group:
            from apps.results.models import Result as RModel
            group_students = group.students.all()
            better_count = RModel.objects.filter(
                student__in=group_students,
                percentage__gt=result.percentage,
                calculated_at__gte=timezone.now() - timedelta(days=30),
            ).values("student").distinct().count()
            group_rank = f"{better_count + 1}-o'rin"

        message = (
            f"📚 <b>Farzandingiz yangi test topshirdi!</b>\n"
            f"👤 <b>O'quvchi:</b> {student_name}\n"
            f"{subject_icon} <b>Fan:</b> {subject_name}\n"
            f"📊 <b>Natija:</b> {result.score} ball ({pct:.1f}%) — BMB darajasi: <b>{bmb_grade}</b>\n"
            f"🔥 <b>Streak:</b> {streak_days} kunlik uzluksiz o'qish\n"
            f"⚠️ <b>Tavsiya (zaif mavzu):</b> {weak_topics}\n"
            f"🏆 <b>Guruhdagi o'rni:</b> {group_rank}\n\n"
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


@shared_task(
    bind=True,
    name="notifications.send_monday_branch_digest",
    max_retries=2,
    default_retry_delay=60,
)
def send_monday_branch_digest_task(self: Any) -> dict[str, Any]:
    """
    Har dushanba soat 08:30 da Filial rahbarining Telegramiga filiali bo'yicha qisqa vedomost jo'natish.
    '📊 {branch_name} haftalik tahlili: Faol o'quvchilar: {active_count}, Xavf ostidagilar: {risk_count}. Eng yaxshi natija ko'rsatgan ustoz: {top_teacher}.'
    """
    try:
        from apps.organizations.models import CenterBranch
        from apps.accounts.models import User
        from apps.tests.models import TestAttempt
        from apps.notifications.services.telegram_service import TelegramService
        from django.db.models import Q, Count
        from django.utils import timezone

        now = timezone.now()
        three_days_ago = now - timedelta(days=3)
        five_days_ago = now - timedelta(days=5)

        branches = CenterBranch.objects.filter(is_active=True).select_related("director")
        dispatched = 0

        for branch in branches:
            director = branch.director
            if not director:
                continue

            director_chat_id = getattr(director, "telegram_chat_id", None)
            if not director_chat_id:
                continue

            students = User.objects.filter(
                Q(branch=branch) | Q(student_groups__branch=branch),
                role=User.Role.STUDENT,
                is_active=True,
            ).distinct()

            total_count = students.count()
            if total_count == 0:
                continue

            active_students = TestAttempt.objects.filter(
                student__in=students,
                started_at__gte=three_days_ago,
            ).values("student").distinct().count()

            recently_active_5d = TestAttempt.objects.filter(
                student__in=students,
                started_at__gte=five_days_ago,
            ).values_list("student_id", flat=True).distinct()
            risk_count = students.exclude(id__in=recently_active_5d).count()

            top_teacher_name = "Ustozlar faol"
            top_group = (
                branch.groups.annotate(attempts_count=Count("assigned_tests__attempts"))
                .order_by("-attempts_count")
                .select_related("teacher")
                .first()
            )
            if top_group and top_group.teacher:
                top_teacher_name = top_group.teacher.get_full_name() or top_group.teacher.email

            digest_msg = (
                f"📊 <b>{branch.name} haftalik tahlili:</b>\n\n"
                f"👥 <b>Jami o'quvchilar:</b> {total_count} nafar\n"
                f"🟢 <b>Faol o'quvchilar:</b> {active_students} nafar\n"
                f"🔴 <b>Xavf ostidagilar:</b> {risk_count} nafar\n"
                f"⭐ <b>Eng yaxshi natija ko'rsatgan ustoz:</b> {top_teacher_name}\n\n"
                f"<i>GRAND EDUCATION Kursxona Boshqaruvi</i>"
            )

            try:
                TelegramService.send_message(
                    chat_id=director_chat_id,
                    text=digest_msg,
                    recipient=director,
                    parse_mode="HTML",
                )
                dispatched += 1
            except Exception as e:
                logger.warning("Could not dispatch Monday digest to director %s: %s", director.id, e)

        return {"status": "completed", "dispatched": dispatched}

    except Exception as exc:
        logger.exception("Failed sending Monday branch digest")
        raise self.retry(exc=exc)
