"""Weekly report rendering, recipient resolution and idempotent delivery.

Split from ``services.py`` on purpose: aggregation answers *what happened*, this
module answers *who may see it and how it is sent*. Every delivery goes through
one row of :class:`~apps.weekly_reports.models.WeeklyReportDelivery` whose
``dedup_key`` is UNIQUE, so a retried Celery task, a replayed scheduler tick or
a double-clicked admin button can never send the same Monday report twice.

Financial figures are attached at *render* time, per recipient, because a
teacher may legitimately receive the academic report while having no permission
to see tuition at all.
"""

from __future__ import annotations

import logging
from datetime import datetime

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.access import is_platform_admin

from .models import (
    WeeklyGroupReport,
    WeeklyReportDelivery,
    WeeklyReportSettings,
    WeeklyStudentReport,
)

logger = logging.getLogger(__name__)

PREFERENCE_TEACHER_WEEKLY = "teacher_weekly_report"
PREFERENCE_PARENT_WEEKLY = "parent_weekly_report"
PREFERENCE_TUITION = "tuition_reminders"


# ---------------------------------------------------------------------------
# Preference handling
# ---------------------------------------------------------------------------


def preference_allows(user, field: str) -> bool:
    """Whether *user* has left the relevant switch on (default: yes).

    ``getattr`` with a default is deliberate: a preference row may predate the
    field, and an absent row must mean "opted in", not "silently dropped".
    """
    if user is None:
        return False
    preference = getattr(user, "notification_preference", None)
    if preference is None:
        from apps.attendance.models import NotificationPreference

        preference = NotificationPreference.objects.filter(user=user).first()
    if preference is None:
        return True
    if not getattr(preference, "telegram_enabled", True):
        return False
    return bool(getattr(preference, field, True))


# ---------------------------------------------------------------------------
# Recipients
# ---------------------------------------------------------------------------


def recipients_for_group(group) -> list:
    """Teacher of the group plus explicitly subscribed administrators.

    A group's teacher always receives their own group. Administrators are only
    included when an operator added them to the settings' recipient list —
    mailing every report to every administrator is how a real alert gets
    ignored.
    """
    recipients = []
    if group.teacher_id:
        teacher = group.teacher
        if getattr(teacher, "is_active", False):
            recipients.append(teacher)
    try:
        config = WeeklyReportSettings.load()
        subscribed = list(config.admin_recipients.filter(is_active=True))
    except Exception:  # pragma: no cover - settings table not ready
        subscribed = []
    for admin in subscribed:
        if admin.pk not in {user.pk for user in recipients} and is_platform_admin(
            admin
        ):
            recipients.append(admin)
    return recipients


def recipients_for_student(student):
    """Verified, approved parents of *student* — never anyone else."""
    from apps.accounts.models import ParentStudentLink

    links = ParentStudentLink.objects.filter(
        student=student, is_approved=True
    ).select_related("parent")
    out = []
    for link in links:
        parent = link.parent
        if parent and parent.is_active and getattr(parent, "telegram_chat_id", None):
            out.append(parent)
    return out


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _line(label: str, value, suffix: str = "") -> str:
    if value is None:
        return f"{label}: —"
    return f"{label}: *{value}*{suffix}"


def group_report_text(
    report: WeeklyGroupReport, *, include_finance: bool = False
) -> str:
    """The private teacher message. Counts are always real data."""
    summary = report.summary or {}
    attendance = summary.get("attendance", {})
    essays = summary.get("essays", {})
    tests = summary.get("tests", {})
    parts = [
        "📊 *GRANDEC — HAFTALIK HISOBOT*",
        f"Guruh: *{summary.get('group_name', report.group.name)}*",
        f"Davr: {report.period_label or ''}",
        "",
        f"👥 O'quvchilar: *{attendance.get('active_students', 0)}*",
        f"🗓 Yakunlangan darslar: *{attendance.get('finalized_lessons', 0)}*",
        _line(
            "✅ Davomat",
            attendance.get("attendance_percentage"),
            "%" if attendance.get("attendance_percentage") is not None else "",
        ),
        f"   Keldi *{attendance.get('present', 0)}* · "
        f"Kechikdi *{attendance.get('late', 0)}* · "
        f"Sababli *{attendance.get('excused_absences', 0)}* · "
        f"Sababsiz *{attendance.get('unexcused_absences', 0)}*",
    ]
    if attendance.get("unfinished_lessons"):
        parts.append(
            f"   ⚠️ Yakunlanmagan davomat: *{attendance['unfinished_lessons']}* "
            "(kelmaganlik deb hisoblanmaydi)"
        )
    parts += [
        "",
        f"📝 Esse topshirildi: *{essays.get('submitted_students', 0)}*"
        f"/*{attendance.get('active_students', 0)}*",
        _line("   O'rtacha AI ball", essays.get("average_raw_score")),
        _line("   AI baholash kutilmoqda", essays.get("pending_ai")),
        _line("   Topshirilmagan", essays.get("missing_submissions")),
        "",
        f"🧪 Testlar: *{tests.get('completed_attempts', 0)}* yakunlangan",
        _line(
            "   O'rtacha mashq natijasi",
            tests.get("average_practice_percentage"),
            "%" if tests.get("average_practice_percentage") is not None else "",
        ),
    ]
    if tests.get("needs_support_count"):
        parts.append(f"   🆘 Qo'shimcha mashq kerak: *{tests['needs_support_count']}*")

    if include_finance and summary.get("finance"):
        finance = summary["finance"]
        parts += ["", "💳 Kurs to'lovlari:"]
        if finance.get("policy_configured"):
            parts += [
                f"   To'langan: *{finance.get('paid_count', 0)}*",
                f"   Qisman to'langan: *{finance.get('partial_count', 0)}*",
                f"   Muddati o'tgan: *{finance.get('overdue_count', 0)}*",
                f"   Hisoblangan: *{finance.get('billed_uzs', 0)}* so'm",
                f"   Tasdiqlangan: *{finance.get('confirmed_paid_uzs', 0)}* so'm",
                f"   Qoldiq: *{finance.get('outstanding_uzs', 0)}* so'm",
            ]
        else:
            parts.append("   Kurs to'lovi siyosati sozlanmagan")
    parts += [
        "",
        "_Bu hisobot faqat sizga yuboriladi._",
    ]
    return "\n".join(parts)


def student_report_text(
    report: WeeklyStudentReport, *, include_finance: bool = False
) -> str:
    """The private parent message — only this child's permitted figures."""
    summary = report.summary or {}
    attendance = summary.get("attendance", {})
    essays = summary.get("essays", {})
    tests = summary.get("tests", {})
    parts = [
        "📊 *GRANDEC — HAFTALIK HISOBOT*",
        f"O'quvchi: *{summary.get('student_name', '')}*",
        f"Davr: {report.period_label or ''}",
        "",
        f"✅ Davomat: *{attendance.get('attendance_percentage', '—')}*%",
        f"   Keldi *{attendance.get('present', 0)}* · "
        f"Kechikdi *{attendance.get('late', 0)}* · "
        f"Sababli *{attendance.get('excused_absences', 0)}* · "
        f"Sababsiz *{attendance.get('unexcused_absences', 0)}*",
        "",
        f"📝 Baholangan esse: *{essays.get('graded', 0)}*",
        _line("🧪 Testlar", tests.get("completed_attempts", 0)),
        _line(
            "   O'rtacha mashq natijasi",
            tests.get("average_practice_percentage"),
            "%" if tests.get("average_practice_percentage") is not None else "",
        ),
    ]
    if include_finance and summary.get("finance"):
        finance = summary["finance"]
        parts += [
            "",
            f"💳 Kurs to'lovi holati: *{finance.get('status_label', '—')}*",
            _line("   Qoldiq", finance.get("outstanding_uzs")),
        ]
    parts.append("")
    parts.append("_Batafsil ma'lumotni Grandec orqali ko'rishingiz mumkin._")
    return "\n".join(parts)


def report_buttons(
    report: WeeklyGroupReport, *, include_finance: bool = False
) -> list[list[dict]]:
    """Inline keyboard. Finance button only for authorized recipients."""
    rid = report.pk
    rows = [
        [
            {"text": "📋 Davomat tafsilotlari", "callback_data": f"wr_att_{rid}"},
            {"text": "📝 Esse natijalari", "callback_data": f"wr_ess_{rid}"},
        ],
        [
            {"text": "🧪 Test natijalari", "callback_data": f"wr_tst_{rid}"},
            {"text": "📄 To'liq hisobot", "callback_data": f"wr_full_{rid}"},
        ],
    ]
    if include_finance:
        rows.append(
            [
                {"text": "💳 Kurs to'lovlari", "callback_data": f"wr_fin_{rid}"},
            ]
        )
    return rows


def visible_summary(report: WeeklyGroupReport, user) -> dict:
    """The persisted summary with finance stripped unless *user* may see it."""
    from .permissions import can_view_group_finance

    summary = dict(report.summary or {})
    if not can_view_group_finance(user):
        summary.pop("finance", None)
        summary["finance_visible"] = False
    else:
        summary["finance_visible"] = True
    # Group snapshot ids are internal routing metadata, not a student roster API.
    summary.pop("student_ids", None)
    return summary


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


def _default_transport(
    chat_id: int, text: str, buttons, recipient, title: str = ""
) -> dict:
    """Send through the one canonical Telegram sender (it logs every attempt)."""
    from apps.notifications.services.telegram_service import TelegramService

    return TelegramService.send_message_with_keyboard(
        chat_id=chat_id,
        text=text,
        buttons=buttons,
        notification_type="general",
        recipient=recipient,
        title=title or "Haftalik hisobot",
    )


def _deliver(
    *,
    report,
    recipient,
    text: str,
    buttons,
    channel: str,
    dedup_key: str,
    transport=None,
    title: str = "",
) -> WeeklyReportDelivery:
    """Create-or-reuse one delivery row, then attempt to send it."""
    with transaction.atomic():
        delivery, created = (
            WeeklyReportDelivery.objects.select_for_update().get_or_create(
                dedup_key=dedup_key,
                defaults={
                    "report": report if isinstance(report, WeeklyGroupReport) else None,
                    "student_report": report
                    if isinstance(report, WeeklyStudentReport)
                    else None,
                    "recipient": recipient,
                    "channel": channel,
                },
            )
        )
        #: Whether this call reached the transport. A caller must never report a
        #: re-seen SENT row as a fresh send.
        delivery.attempted = False
        if not created and delivery.status == WeeklyReportDelivery.Status.SENT:
            # A successful reservation must never be sent a second time.
            return delivery
        if not created and delivery.status == WeeklyReportDelivery.Status.PENDING:
            # A worker may have died after reserving the row. Reclaim only a
            # stale reservation, and atomically advance its lease so competing
            # workers cannot also decide that it is stale.
            claim_time = timezone.now()
            stale_before = claim_time - timezone.timedelta(minutes=10)
            reclaimed = (
                WeeklyReportDelivery.objects.filter(
                    pk=delivery.pk,
                    status=WeeklyReportDelivery.Status.PENDING,
                )
                .filter(
                    Q(last_attempt_at__lt=stale_before)
                    | Q(last_attempt_at__isnull=True, created_at__lt=stale_before)
                )
                .update(last_attempt_at=claim_time)
            )
            if not reclaimed:
                return delivery

        config = WeeklyReportSettings.load()
        if delivery.retry_count >= int(config.max_delivery_attempts):
            delivery.status = WeeklyReportDelivery.Status.FAILED
            delivery.last_error = "Maksimal urinishlar soniga yetdi."
            delivery.save(update_fields=["status", "last_error"])
            return delivery

        delivery.retry_count += 1
        delivery.last_attempt_at = timezone.now()
        delivery.status = WeeklyReportDelivery.Status.PENDING
        delivery.last_error = ""
        delivery.save(
            update_fields=[
                "retry_count",
                "last_attempt_at",
                "status",
                "last_error",
            ]
        )

    if channel == WeeklyReportDelivery.Channel.DASHBOARD:
        # The dashboard copy always succeeds: it is the fallback that makes a
        # Telegram outage a delivery problem rather than a reporting gap.
        delivery.mark_sent()
        delivery.attempted = True
        return delivery

    chat_id = getattr(recipient, "telegram_chat_id", None)
    if not chat_id:
        # Deferred, not dropped: the report stays readable in the dashboard and
        # this row is retried once the teacher links Telegram.
        delivery.status = WeeklyReportDelivery.Status.DEFERRED
        delivery.last_error = "Telegram hisob ulanmagan."
        delivery.save(update_fields=["status", "last_error"])
        return delivery

    delivery.attempted = True
    send = transport or _default_transport
    try:
        # One calling convention for every transport (injected or real):
        # (chat_id, text, buttons, recipient, title) -> {success, message_id, error}.
        result = send(chat_id, text, buttons, recipient, title)
    except Exception as exc:  # transport must never break the batch
        logger.exception("Weekly report delivery failed for %s", recipient.pk)
        delivery.status = WeeklyReportDelivery.Status.FAILED
        delivery.last_error = str(exc)[:2000]
        delivery.save(update_fields=["status", "last_error"])
        return delivery

    if result and result.get("success"):
        delivery.mark_sent(result.get("message_id") or "")
    else:
        delivery.status = WeeklyReportDelivery.Status.FAILED
        delivery.last_error = str((result or {}).get("error") or "Noma'lum xatolik")[
            :2000
        ]
        delivery.save(update_fields=["status", "last_error"])
    return delivery


def group_dedup_key(report: WeeklyGroupReport, recipient, channel: str) -> str:
    return f"weekly-group:{report.pk}:{report.version}:{recipient.pk}:{channel}"


def student_dedup_key(report: WeeklyStudentReport, recipient, channel: str) -> str:
    return f"weekly-student:{report.pk}:{report.version}:{recipient.pk}:{channel}"


def deliver_group_report(
    report: WeeklyGroupReport,
    recipient,
    *,
    transport=None,
    include_finance: bool | None = None,
) -> WeeklyReportDelivery:
    """Deliver one group report to one recipient (dedup-keyed, retry-safe)."""
    from .permissions import can_view_group_finance

    if include_finance is None:
        include_finance = can_view_group_finance(recipient)
    text = group_report_text(report, include_finance=include_finance)
    return _deliver(
        report=report,
        recipient=recipient,
        text=text,
        buttons=report_buttons(report, include_finance=include_finance),
        channel=WeeklyReportDelivery.Channel.TELEGRAM,
        dedup_key=group_dedup_key(
            report, recipient, WeeklyReportDelivery.Channel.TELEGRAM
        ),
        transport=transport,
        title=f"Haftalik hisobot — {report.group.name}",
    )


def deliver_student_report(
    report: WeeklyStudentReport, recipient, *, transport=None
) -> WeeklyReportDelivery:
    text = student_report_text(report)
    return _deliver(
        report=report,
        recipient=recipient,
        text=text,
        buttons=None,
        channel=WeeklyReportDelivery.Channel.TELEGRAM,
        dedup_key=student_dedup_key(
            report,
            recipient,
            WeeklyReportDelivery.Channel.TELEGRAM,
        ),
        transport=transport,
        title="Haftalik hisobot",
    )


def send_reports(
    period_start: datetime,
    period_end: datetime,
    *,
    transport=None,
    now: datetime | None = None,
) -> dict:
    """Send every current report for the period, honouring preferences.

    Returns a small audit dict; a delivery that already succeeded for the same
    version is reported as ``skipped`` rather than sent again.
    """
    from . import services

    services.ensure_complete(period_end, now=now)
    sent = failed = skipped = deferred = duplicates = 0

    reports = WeeklyGroupReport.objects.filter(
        period_start=period_start,
        is_current=True,
    ).select_related("group", "group__teacher")
    for report in reports:
        for recipient in recipients_for_group(report.group):
            if not preference_allows(recipient, PREFERENCE_TEACHER_WEEKLY):
                skipped += 1
                continue
            delivery = deliver_group_report(report, recipient, transport=transport)
            status = delivery.status
            attempted = bool(getattr(delivery, "attempted", False))
            sent += attempted and status == WeeklyReportDelivery.Status.SENT
            failed += attempted and status == WeeklyReportDelivery.Status.FAILED
            deferred += status == WeeklyReportDelivery.Status.DEFERRED
            duplicates += (
                not attempted and status != WeeklyReportDelivery.Status.DEFERRED
            )
            if attempted and status == WeeklyReportDelivery.Status.SENT:
                _mark_report_status(report)

    student_reports = WeeklyStudentReport.objects.filter(
        period_start=period_start,
        is_current=True,
    ).select_related("student")
    for student_report in student_reports:
        for parent in recipients_for_student(student_report.student):
            if not preference_allows(parent, PREFERENCE_PARENT_WEEKLY):
                skipped += 1
                continue
            delivery = deliver_student_report(
                student_report,
                parent,
                transport=transport,
            )
            status = delivery.status
            attempted = bool(getattr(delivery, "attempted", False))
            sent += attempted and status == WeeklyReportDelivery.Status.SENT
            failed += attempted and status == WeeklyReportDelivery.Status.FAILED
            deferred += status == WeeklyReportDelivery.Status.DEFERRED
            duplicates += (
                not attempted and status != WeeklyReportDelivery.Status.DEFERRED
            )

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "sent": sent,
        "failed": failed,
        "skipped": skipped,
        "deferred": deferred,
        "duplicates": duplicates,
    }


def _mark_report_status(report: WeeklyGroupReport) -> None:
    if report.status != "sent":
        WeeklyGroupReport.objects.filter(pk=report.pk).update(status="sent")


def retry_failed_deliveries(*, limit: int = 100, transport=None) -> dict:
    """Retry failed/deferred Telegram deliveries (missed-job recovery)."""
    config = WeeklyReportSettings.load()
    if not config.retry_failed_deliveries:
        return {"retried": 0, "sent": 0, "failed": 0, "disabled": True}

    pending = list(
        WeeklyReportDelivery.objects.filter(
            channel=WeeklyReportDelivery.Channel.TELEGRAM,
            status__in=(
                WeeklyReportDelivery.Status.FAILED,
                WeeklyReportDelivery.Status.DEFERRED,
            ),
            retry_count__lt=int(config.max_delivery_attempts),
        ).select_related("report", "student_report", "recipient")[:limit]
    )
    sent = failed = duplicates = 0
    for delivery in pending:
        target = delivery.target
        if target is None:
            continue
        if isinstance(target, WeeklyGroupReport):
            text = group_report_text(
                target,
                include_finance=_may_see_finance(delivery.recipient),
            )
            buttons = report_buttons(
                target,
                include_finance=_may_see_finance(delivery.recipient),
            )
        else:
            text = student_report_text(target)
            buttons = None
        refreshed = _deliver(
            report=target,
            recipient=delivery.recipient,
            text=text,
            buttons=buttons,
            channel=delivery.channel,
            dedup_key=delivery.dedup_key,
            transport=transport,
        )
        attempted = bool(getattr(refreshed, "attempted", False))
        sent += attempted and refreshed.status == WeeklyReportDelivery.Status.SENT
        failed += attempted and refreshed.status == WeeklyReportDelivery.Status.FAILED
        duplicates += not attempted
    return {
        "retried": len(pending),
        "sent": sent,
        "failed": failed,
        "duplicates": duplicates,
    }


def _may_see_finance(user) -> bool:
    from .permissions import can_view_group_finance

    return can_view_group_finance(user)
