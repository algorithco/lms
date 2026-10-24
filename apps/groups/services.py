"""
Teacher CRM & Group Services (Module 3 & Module 4).
Handles tuition calculation, debt tracking, 1-click debtor notifications,
and interactive attendance sessions.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any
from django.utils import timezone
from django.db import transaction

from apps.accounts.models import User, ParentStudentRelation
from apps.courses.models import StudentGroup, GroupEnrollment
from apps.attendance.models import AttendanceSession, AttendanceRecord

logger = logging.getLogger(__name__)


def send_telegram_safe(chat_id: int | str, text: str, reply_markup=None) -> bool:
    """Safely deliver a Telegram message without crashing if delivery fails."""
    if not chat_id:
        return False
    try:
        from apps.notifications.services.telegram_service import TelegramService

        TelegramService.send_message(chat_id=int(chat_id), text=text)
        return True
    except Exception as exc:
        logger.warning("Telegram notification to %s failed: %s", chat_id, exc)
        return False


def get_teacher_groups(teacher: User) -> list[StudentGroup]:
    """Return all active groups belonging to teacher (or all if admin)."""
    if (
        getattr(teacher, "is_superuser", False)
        or getattr(teacher, "role", "") == "admin"
    ):
        return list(StudentGroup.objects.all().order_by("name"))
    return list(StudentGroup.objects.filter(teacher=teacher).order_by("name"))


def sync_group_roster(group: StudentGroup) -> None:
    """Ensure every student in group.students has a GroupEnrollment."""
    existing_ids = set(group.group_enrollments.values_list("student_id", flat=True))
    all_students = group.students.all()
    today = timezone.localdate()

    for st in all_students:
        if st.id not in existing_ids:
            parent_rel = ParentStudentRelation.objects.filter(
                student=st, is_verified=True
            ).first()
            p_phone = parent_rel.parent_phone if parent_rel else ""
            p_tg = (
                str(parent_rel.parent_telegram_id)
                if parent_rel and parent_rel.parent_telegram_id
                else ""
            )

            GroupEnrollment.objects.create(
                group=group,
                student=st,
                monthly_fee=Decimal(str(group.monthly_fee or 400000)),
                billing_cycle_day=10,
                last_payment_date=today,
                next_payment_due=today + timezone.timedelta(days=30),
                payment_status=GroupEnrollment.PaymentStatus.PAID,
                parent_phone=p_phone,
                parent_telegram_id=p_tg,
            )


def get_group_finance_summary(group: StudentGroup) -> dict[str, Any]:
    """Calculate collected tuition, pending debt, and debtors list for a group."""
    sync_group_roster(group)
    enrollments = group.group_enrollments.select_related(
        "student", "student__profile"
    ).filter(is_active=True)
    today = timezone.localdate()

    for e in enrollments:
        e.update_status(today)

    total_students = enrollments.count()
    paid_enrollments = [
        e for e in enrollments if e.payment_status == GroupEnrollment.PaymentStatus.PAID
    ]
    debtor_enrollments = [
        e for e in enrollments if e.payment_status != GroupEnrollment.PaymentStatus.PAID
    ]

    collected_amount = sum(float(e.monthly_fee) for e in paid_enrollments)
    pending_amount = sum(float(e.monthly_fee) for e in debtor_enrollments)

    debtors_data = []
    for e in debtor_enrollments:
        debtors_data.append(
            {
                "enrollment_id": e.id,
                "student_id": e.student.id,
                "student_name": e.student.get_full_name() or e.student.email,
                "fee": float(e.monthly_fee),
                "next_due": e.next_payment_due.strftime("%d.%m.%Y")
                if e.next_payment_due
                else "Muddatsiz",
                "status": "Muddati o'tgan"
                if e.payment_status == GroupEnrollment.PaymentStatus.OVERDUE
                else "To'lov yaqin",
                "parent_telegram_id": e.parent_telegram_id,
            }
        )

    return {
        "group_id": group.id,
        "group_name": group.name,
        "total_students": total_students,
        "paid_count": len(paid_enrollments),
        "debtor_count": len(debtor_enrollments),
        "collected_amount": collected_amount,
        "pending_amount": pending_amount,
        "debtors": debtors_data,
    }


def record_tuition_payment(
    enrollment: GroupEnrollment, amount: float | Decimal
) -> GroupEnrollment:
    """Extend enrollment payment due date by 30 days and mark as PAID."""
    enrollment.record_payment(amount=amount)
    return enrollment


def send_debtor_payment_reminders(
    teacher: User, group_id: int | None = None
) -> dict[str, Any]:
    """
    Send polite Telegram payment reminders to all debtor students and their parents.
    """
    groups = (
        StudentGroup.objects.filter(id=group_id, teacher=teacher)
        if group_id
        else StudentGroup.objects.filter(teacher=teacher)
    )

    sent_count = 0
    parent_sent_count = 0

    for g in groups:
        sync_group_roster(g)
        debtors = g.group_enrollments.filter(
            is_active=True,
            payment_status__in=[
                GroupEnrollment.PaymentStatus.OVERDUE,
                GroupEnrollment.PaymentStatus.DUE_SOON,
                GroupEnrollment.PaymentStatus.GRACE_PERIOD,
            ],
        ).select_related("student")

        for e in debtors:
            st = e.student
            fee_str = f"{float(e.monthly_fee):,.0f} so'm".replace(",", " ")
            due_str = (
                e.next_payment_due.strftime("%d.%m.%Y")
                if e.next_payment_due
                else "belgilangan muddat"
            )

            # 1. Student reminder (if telegram_chat_id exists)
            st_chat = getattr(st, "telegram_chat_id", None)
            if st_chat:
                student_msg = (
                    f"🔔 <b>Oylik to'lov eslatmasi</b>\n\n"
                    f"Hurmatli <b>{st.get_full_name()}</b>!\n"
                    f"Sizning <b>{g.name}</b> kursi uchun oylik to'lov sanangiz: <b>{due_str}</b>.\n"
                    f"To'lov summasi: <b>{fee_str}</b>.\n\n"
                    f"Darslar uzluksiz davom etishi uchun to'lov chekini ushbu botga rasm holida yuboring. Rahmat!"
                )
                if send_telegram_safe(st_chat, student_msg):
                    sent_count += 1

            # 2. Parent reminder (if parent_telegram_id exists)
            p_tg = e.parent_telegram_id
            if p_tg and p_tg.isdigit():
                parent_msg = (
                    f"👨‍👩‍👦 <b>Hurmatli ota-ona!</b>\n\n"
                    f"Farzandingiz <b>{st.get_full_name()}</b> ning <b>{g.name}</b> kursi uchun oylik to'lov muddati: <b>{due_str}</b>.\n"
                    f"Oylik to'lov summasi: <b>{fee_str}</b>.\n\n"
                    f"To'lov amalga oshirilgach, chekni ushbu botga yuborishingiz mumkin. E'tiboringiz uchun tashakkur!"
                )
                if send_telegram_safe(int(p_tg), parent_msg):
                    parent_sent_count += 1

    return {
        "success": True,
        "students_notified": sent_count,
        "parents_notified": parent_sent_count,
        "total_notified": sent_count + parent_sent_count,
    }


def save_interactive_attendance(
    group: StudentGroup,
    teacher: User,
    statuses: dict[int, str],
    lesson_date=None,
) -> tuple[AttendanceSession, dict[str, int]]:
    """
    Save interactive attendance roster.
    statuses: {student_id: 'present' | 'absent'}
    """
    today = lesson_date or timezone.localdate()

    with transaction.atomic():
        session, _ = AttendanceSession.objects.get_or_create(
            group=group,
            lesson_date=today,
            defaults={
                "teacher": teacher,
                "status": AttendanceSession.Status.FINALIZED,
                "created_by": teacher,
                "finalized_by": teacher,
                "finalized_at": timezone.now(),
            },
        )
        if session.status != AttendanceSession.Status.FINALIZED:
            session.status = AttendanceSession.Status.FINALIZED
            session.finalized_at = timezone.now()
            session.finalized_by = teacher
            session.save(update_fields=["status", "finalized_at", "finalized_by"])

        present_cnt = 0
        absent_cnt = 0

        for st_id, st_status in statuses.items():
            status_val = (
                AttendanceRecord.Status.PRESENT
                if st_status == "present"
                else AttendanceRecord.Status.ABSENT
            )
            AttendanceRecord.objects.update_or_create(
                session=session,
                student_id=st_id,
                defaults={"status": status_val},
            )
            if status_val == AttendanceRecord.Status.PRESENT:
                present_cnt += 1
            else:
                absent_cnt += 1
                # Alert parent if parent_telegram_id exists
                enrollment = GroupEnrollment.objects.filter(
                    group=group, student_id=st_id
                ).first()
                if (
                    enrollment
                    and enrollment.parent_telegram_id
                    and enrollment.parent_telegram_id.isdigit()
                ):
                    student = User.objects.filter(id=st_id).first()
                    st_name = student.get_full_name() if student else "Farzandingiz"
                    alert_text = (
                        f"⚠️ <b>Davomat xabarnomasi</b>\n\n"
                        f"Hurmatli ota-ona! Farzandingiz <b>{st_name}</b> bugun ({today.strftime('%d.%m.%Y')}) "
                        f"<b>{group.name}</b> darsiga qatnashmadi."
                    )
                    send_telegram_safe(int(enrollment.parent_telegram_id), alert_text)

    return session, {
        "present": present_cnt,
        "absent": absent_cnt,
        "total": present_cnt + absent_cnt,
    }
