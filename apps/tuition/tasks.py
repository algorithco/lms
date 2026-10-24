"""Celery tasks for course tuition.

All three are idempotent, which is what lets beat restart, an operator re-run a
missed month, and a reminder ladder retry a failed Telegram send without
double-billing anyone or sending a duplicate notice.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from celery import shared_task
from django.utils.dateparse import parse_date

from . import notifications, services

logger = logging.getLogger(__name__)


def _parse(value: str | None) -> date | None:
    if not value:
        return None
    parsed = parse_date(value)
    if parsed is None:
        raise ValueError("Sana formati noto'g'ri (YYYY-MM-DD kerak).")
    return parsed


@shared_task(
    bind=True,
    name="tuition.generate_monthly_invoices",
    max_retries=3,
    default_retry_delay=300,
    retry_backoff=True,
    retry_backoff_max=3600,
    retry_jitter=True,
    acks_late=True,
    time_limit=600,
    soft_time_limit=540,
)
def generate_monthly_invoices(
    self: Any, period_start: str | None = None, dry_run: bool = False
) -> dict[str, Any]:
    """Generate the month's invoices (idempotent per student/period/scope)."""
    try:
        reference = _parse(period_start) or services.today()
        result = services.generate_period_invoices(
            reference,
            dry_run=dry_run,
            reason="Oylik avtomatik hisoblash",
        )
        logger.info("Tuition invoicing: %s", result)
        return {"status": "completed", **result}
    except Exception as exc:
        logger.exception("Tuition invoice generation failed")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="tuition.mark_overdue_invoices",
    max_retries=3,
    default_retry_delay=300,
    retry_backoff=True,
    time_limit=300,
    soft_time_limit=240,
)
def mark_overdue_invoices(self: Any, as_of: str | None = None) -> dict[str, Any]:
    """Flag invoices past due (+grace). Never affects enrollment."""
    try:
        return {
            "status": "completed",
            **services.mark_overdue_invoices(as_of=_parse(as_of) or services.today()),
        }
    except Exception as exc:
        logger.exception("Overdue marking failed")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="tuition.send_payment_reminders",
    max_retries=3,
    default_retry_delay=600,
    retry_backoff=True,
    time_limit=600,
    soft_time_limit=540,
)
def send_payment_reminders(self: Any, as_of: str | None = None) -> dict[str, Any]:
    """Run the reminder ladder. Quiet hours and preferences are respected inside."""
    try:
        return {
            "status": "completed",
            **notifications.send_due_reminders(as_of=_parse(as_of) or services.today()),
        }
    except Exception as exc:
        logger.exception("Tuition reminder run failed")
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    name="tuition.check_group_tuition_due_dates_task",
    max_retries=3,
    default_retry_delay=300,
)
def check_group_tuition_due_dates_task(self: Any) -> dict[str, Any]:
    """
    Har kuni ertalab soat 10:00 da o'quvchilar va ota-onalarga to'lov muddatlarini eslatish (3-Modul).
    """
    from django.utils import timezone
    from apps.courses.models import GroupEnrollment
    from apps.accounts.models import ParentStudentRelation
    from apps.webapi.views_crm import send_telegram_message_safe

    today = timezone.localdate()
    enrollments = GroupEnrollment.objects.select_related("group", "student").filter(
        is_active=True
    )

    sent_students = 0
    sent_parents = 0

    for e in enrollments:
        e.update_status(today)

        if not e.next_payment_due:
            continue

        days_diff = (e.next_payment_due - today).days
        st = e.student
        group = e.group
        fee_str = f"{float(e.monthly_fee):,.0f} so'm".replace(",", " ")
        due_str = e.next_payment_due.strftime("%d.%m.%Y")

        student_msg = ""
        parent_msg = ""

        # 1. Muddatga 2 kun qolganda
        if days_diff == 2:
            student_msg = (
                f"🔔 <b>Hurmatli {st.first_name}!</b>\n\n"
                f"<b>{group.name}</b> kursi uchun oylik to'lov sanasiga <b>2 kun</b> qoldi ({due_str}).\n"
                f"Oylik to'lov summasi: <b>{fee_str}</b>.\n\n"
                f"Darslar to'xtab qolmasligi uchun to'lov qilib chekni botga yuborishingiz mumkin."
            )
            parent_msg = (
                f"👨‍👩‍👧‍👦 <b>Hurmatli ota-ona! (Grand Education)</b>\n\n"
                f"Farzandingiz <b>{st.get_full_name()}</b> ning <b>{group.name}</b> kursi uchun to'lov muddatiga 2 kun qoldi ({due_str}).\n"
                f"Oylik to'lov: <b>{fee_str}</b>."
            )
        # 2. To'lov kunida
        elif days_diff == 0:
            student_msg = (
                f"⚠️ <b>Hurmatli {st.first_name}!</b>\n\n"
                f"Bugun <b>{group.name}</b> kursi uchun to'lovning oxirgi kuni!\n"
                f"Oylik to'lov summasi: <b>{fee_str}</b>.\n\n"
                f"Kurs to'xtab qolmasligi uchun to'lov qilib, chekni ushbu botga yuboring."
            )
            parent_msg = (
                f"⚠️ <b>Hurmatli ota-ona!</b>\n\n"
                f"Bugun farzandingiz <b>{st.get_full_name()}</b> ning <b>{group.name}</b> kursi uchun to'lov sanasi ({due_str}).\n"
                f"Iltimos, to'lovni amalga oshirib chekni yuboring."
            )
        # 3. Muddat o'tganda (har 3 kunda bir yoki birinchi kun)
        elif days_diff < 0 and abs(days_diff) in (1, 3, 7, 14):
            student_msg = (
                f"🔴 <b>Hurmatli {st.first_name}!</b>\n\n"
                f"<b>{group.name}</b> kursi uchun to'lov muddati <b>{abs(days_diff)} kun oldin o'tgan</b> ({due_str}).\n"
                f"Qarzdorlik summasi: <b>{fee_str}</b>.\n\n"
                f"Iltimos, to'lovni zudlik bilan amalga oshiring va chekni yuboring."
            )
            parent_msg = (
                f"🔴 <b>Hurmatli ota-ona!</b>\n\n"
                f"Farzandingiz <b>{st.get_full_name()}</b> ning <b>{group.name}</b> kursi uchun to'lov muddati o'tgan ({due_str}).\n"
                f"Qarzdorlik: <b>{fee_str}</b>. Iltimos, kursdan chetlatilmaslik uchun to'lovni amalga oshiring."
            )

        # Xabarlarni jo'natish
        if student_msg and st.telegram_chat_id:
            if send_telegram_message_safe(st.telegram_chat_id, student_msg):
                sent_students += 1

        if parent_msg:
            parent_chat_id = None
            if e.parent_telegram_id and e.parent_telegram_id.isdigit():
                parent_chat_id = int(e.parent_telegram_id)
            else:
                rel = ParentStudentRelation.objects.filter(
                    student=st, is_verified=True
                ).first()
                if rel and rel.parent_telegram_id:
                    parent_chat_id = rel.parent_telegram_id
            if parent_chat_id:
                if send_telegram_message_safe(parent_chat_id, parent_msg):
                    sent_parents += 1

    return {
        "status": "success",
        "sent_students": sent_students,
        "sent_parents": sent_parents,
    }
