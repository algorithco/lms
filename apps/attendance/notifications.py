"""Attendance, observation and group-summary notification routing.

Two destinations, two different privacy classes:

* **Private parent chat** — a named child's attendance detail goes only to an
  *approved* ``ParentStudentLink`` whose parent has a verified Telegram link.
  Never to a group.
* **Approved group destination** — aggregate, non-identifying summaries only
  ("9-A: 12 dan 9 nafari qatnashdi"). A named absconder is never published.

Delivery is idempotent: each message carries a deterministic
``NotificationLog.dedup_key`` (UNIQUE where non-empty), so a replayed Telegram
webhook or a retried Celery task cannot send a duplicate to a parent or a group.

Everything is driven by the canonical sender
:class:`apps.notifications.services.telegram_service.TelegramService`, so every
attempt lands in the existing ``NotificationLog`` audit trail.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.accounts.models import ParentStudentLink
from apps.notifications.services.telegram_service import TelegramService

from .models import (
    AttendanceRecord,
    AttendanceSession,
    ClassroomObservation,
    GroupNotificationDestination,
    NotificationPreference,
)

logger = logging.getLogger(__name__)

#: Notification categories a group destination can subscribe to.
CATEGORY_ATTENDANCE_SUMMARY = "attendance_summary"
CATEGORY_ATTENDANCE_ALWAYS = "attendance_session_finalized"

STATUS_LABELS_UZ = {
    AttendanceRecord.Status.PRESENT: "Keldi",
    AttendanceRecord.Status.LATE: "Kechikdi",
    AttendanceRecord.Status.ABSENT: "Kelmadi",
    AttendanceRecord.Status.EXCUSED: "Sababli",
}


# ---------------------------------------------------------------------------
# Delivery primitive with idempotency
# ---------------------------------------------------------------------------


def _deliver(
    *,
    chat_id: int,
    text: str,
    dedup_key: str,
    notification_type: str,
    recipient=None,
    title: str = "",
) -> dict:
    """Send one Telegram message at most once for a given ``dedup_key``.

    Returns ``{"success": bool, "duplicate": bool, "error": str|None}``.
    """
    from apps.notifications.models import NotificationLog

    if not dedup_key:
        raise ValueError("A dedup_key is required for attendance notifications.")

    # Reserve the key first: a concurrent duplicate loses the unique race and
    # bails out instead of sending a second message.
    try:
        with transaction.atomic():
            NotificationLog.objects.create(
                recipient=recipient,
                channel=NotificationLog.Channel.TELEGRAM,
                notification_type=notification_type,
                title=title,
                message=text,
                status=NotificationLog.Status.PENDING,
                dedup_key=dedup_key,
            )
    except IntegrityError:
        # Only a *replayed* key may be treated as a duplicate. Any other
        # integrity failure (e.g. a missing required attribute) must surface:
        # swallowing it would silently drop the message while reporting success.
        if not NotificationLog.objects.filter(dedup_key=dedup_key).exists():
            logger.exception(
                "Notification reservation failed for an unexpected reason "
                "(dedup_key=%s)",
                dedup_key,
            )
            raise
        logger.info("Duplicate notification suppressed (dedup_key=%s)", dedup_key)
        return {"success": True, "duplicate": True, "error": None}

    if not getattr(settings, "TELEGRAM_BOT_TOKEN", ""):
        logger.warning(
            "TELEGRAM_BOT_TOKEN not configured; notification %s not delivered",
            dedup_key,
        )
        NotificationLog.objects.filter(dedup_key=dedup_key).update(
            status=NotificationLog.Status.FAILED,
            error_message="TELEGRAM_BOT_TOKEN sozlanmagan.",
        )
        return {"success": False, "duplicate": False, "error": "bot token missing"}

    result = TelegramService._send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        notification_type=notification_type,
        recipient=recipient,
        title=title,
    )
    return {
        "success": bool(result.get("success")),
        "duplicate": False,
        "error": result.get("error"),
    }


# ---------------------------------------------------------------------------
# Parent notifications
# ---------------------------------------------------------------------------


def _parents_for(student):
    """Approved, Telegram-linked parents of *student*.

    An unapproved ``ParentStudentLink`` discloses nothing — not even the fact
    that a link was requested.
    """
    links = ParentStudentLink.objects.filter(
        student=student, is_approved=True
    ).select_related("parent")
    parents = []
    for link in links:
        parent = link.parent
        if not getattr(parent, "is_active", False):
            continue
        if not getattr(parent, "telegram_chat_id", None):
            continue
        if not getattr(parent, "telegram_identity_verified_at", None):
            # An unverified numeric link must never receive child data.
            continue
        parents.append(parent)
    return parents


def _preference_allows(user, attribute: str) -> bool:
    try:
        preference = NotificationPreference.for_user(user)
    except ValueError:
        return False
    if not preference.telegram_enabled:
        return False
    return bool(getattr(preference, attribute, True))


def notify_parents_of_record(
    record: AttendanceRecord,
    *,
    is_correction: bool = False,
) -> dict:
    """Send one private message per approved parent for a marked record."""
    student = record.student
    session = record.session
    status_label = STATUS_LABELS_UZ.get(record.status, record.get_status_display())

    lines = [
        "🏫 *Grandec xabarnomasi*",
        "",
        f"Farzandingizning *{session.group.name}* guruhidagi "
        f"{session.lesson_date.strftime('%d.%m.%Y')} dars davomati:",
        "",
        f"Holat: *{status_label}*",
    ]
    if record.status == AttendanceRecord.Status.LATE and record.late_minutes:
        lines.append(f"Kechikish: {record.late_minutes} daqiqa")
    if record.note:
        lines.append(f"Izoh: {record.note}")
    if is_correction:
        lines.append("")
        lines.append("_Bu avvalgi yozuv tuzatilgandan keyingi holat._")
    lines.append("")
    lines.append("Batafsil ma'lumotni Grandec orqali ko'rishishingiz mumkin.")
    text = "\n".join(lines)

    sent = 0
    duplicates = 0
    failed = 0
    for parent in _parents_for(student):
        if not _preference_allows(parent, "attendance_alerts"):
            continue
        key = f"attendance:{record.pk}:{parent.pk}:{'correction' if is_correction else 'initial'}"
        outcome = _deliver(
            chat_id=parent.telegram_chat_id,
            text=text,
            dedup_key=key,
            notification_type="attendance",
            recipient=parent,
            title=f"Davomat: {student.get_full_name()}",
        )
        if outcome.get("duplicate"):
            duplicates += 1
        elif outcome.get("success"):
            sent += 1
        else:
            failed += 1

    return {
        "sent": sent,
        "duplicates": duplicates,
        "failed": failed,
        "student_id": student.pk,
        "record_id": record.pk,
    }


def notify_parents_of_session(session: AttendanceSession, *, only=None) -> dict:
    """Notify every approved parent about their child's record in *session*.

    Intended to run from ``transaction.on_commit()`` after finalization so a
    rollback never sends a message about a state that did not persist.
    """
    records = session.records.select_related("student", "session", "session__group")
    if only:
        records = records.filter(pk__in=list(only))
    totals = {"sent": 0, "duplicates": 0, "failed": 0, "records": 0}
    for record in records:
        result = notify_parents_of_record(record)
        totals["sent"] += result["sent"]
        totals["duplicates"] += result["duplicates"]
        totals["failed"] += result["failed"]
        totals["records"] += 1
    return totals


def notify_parents_of_observation(observation: ClassroomObservation) -> dict:
    """Send a *confirmed* neutral observation to the student's parents.

    Refuses unless the recording teacher confirmed it, and refuses again here
    so an unconfirmed observation can never leak through a retry.
    """
    if not observation.is_confirmed:
        raise ValueError("Tasdiqlanmagan kuzatuvni yuborib bo'lmaydi.")

    lines = [
        "🏫 *Grandec xabarnomasi*",
        "",
        f"Farzandingiz bo'yicha o'qituvchi kuzatuvi:",
        "",
        f"Holat: *{observation.get_observation_type_display()}*",
        observation.neutral_description,
        "",
        "Batafsil ma'lumotni Grandec orqali ko'rishishingiz mumkin.",
    ]
    text = "\n".join(lines)

    sent = 0
    duplicates = 0
    failed = 0
    for parent in _parents_for(observation.student):
        if not _preference_allows(parent, "observation_alerts"):
            continue
        key = f"observation:{observation.pk}:{parent.pk}"
        outcome = _deliver(
            chat_id=parent.telegram_chat_id,
            text=text,
            dedup_key=key,
            notification_type="observation",
            recipient=parent,
            title="Kuzatuv xabari",
        )
        if outcome.get("duplicate"):
            duplicates += 1
        elif outcome.get("success"):
            sent += 1
        else:
            failed += 1

    mark_sent = sent > 0 or duplicates > 0
    if mark_sent:
        from .services import mark_observation_sent

        mark_observation_sent(observation)
    return {"sent": sent, "duplicates": duplicates, "failed": failed}


# ---------------------------------------------------------------------------
# Group (aggregate-only) notifications
# ---------------------------------------------------------------------------


def group_summary_text(session: AttendanceSession) -> str:
    """Aggregate attendance line — deliberately free of any student name."""
    from .services import summary

    data = summary(session)
    return (
        f"📊 *{session.group.name} guruhi davomati*\n\n"
        f"Sana: {session.lesson_date.strftime('%d.%m.%Y')}\n"
        f"{data['roster_size']} o'quvchidan "
        f"{data['attended']} nafari qatnashdi, "
        f"{data['late']} nafari kechikdi, "
        f"{data['absent']} nafari kelmadi."
    )


def destinations_for(group, category: str):
    """Approved destinations for *group* (plus global rows) that accept *category*.

    Approval is re-checked here rather than trusted from the caller: a chat id
    a teacher typed is never a delivery target until an admin approved it.
    """
    candidates = GroupNotificationDestination.objects.filter(
        is_enabled=True,
        is_approved=True,
    ).filter(Q(group=group) | Q(group__isnull=True))
    return [destination for destination in candidates if destination.accepts(category)]


def send_group_attendance_summary(
    session: AttendanceSession, *, category: str = CATEGORY_ATTENDANCE_SUMMARY
) -> dict:
    """Publish the aggregate summary to approved group/parent destinations.

    Only :data:`CATEGORY_ATTENDANCE_SUMMARY` text (no names) is ever sent here.
    """
    text = group_summary_text(session)
    sent = 0
    duplicates = 0
    failed = 0
    for destination in destinations_for(session.group, category):
        key = f"group-attendance:{session.pk}:{destination.chat_id}"
        outcome = _deliver(
            chat_id=destination.chat_id,
            text=text,
            dedup_key=key,
            notification_type="attendance_summary",
            # A group chat has no single recipient; attribute the audit row to
            # the responsible human (the approver, else the group's teacher).
            recipient=destination.approved_by or session.group.teacher,
            title=f"Davomat: {session.group.name}",
        )
        if outcome.get("duplicate"):
            duplicates += 1
        elif outcome.get("success"):
            sent += 1
        else:
            failed += 1
    return {"sent": sent, "duplicates": duplicates, "failed": failed}


# ---------------------------------------------------------------------------
# Teacher notifications
# ---------------------------------------------------------------------------


def notify_teacher(
    *,
    teacher,
    text: str,
    dedup_key: str,
    title: str = "",
    notification_type: str = "general",
) -> dict:
    """Targeted teacher notice. Deduplicated so batches never spam."""
    if teacher is None or not getattr(teacher, "telegram_chat_id", None):
        return {"success": False, "duplicate": False, "error": "teacher not linked"}
    if not getattr(teacher, "telegram_identity_verified_at", None):
        return {"success": False, "duplicate": False, "error": "teacher unverified"}
    return _deliver(
        chat_id=teacher.telegram_chat_id,
        text=text,
        dedup_key=dedup_key,
        notification_type=notification_type,
        recipient=teacher,
        title=title,
    )


def notify_teachers_of_submission(submission) -> dict:
    """Tell the owning teacher(s) that a group-assigned essay was submitted.

    Only teachers who actually own a group the submission is associated with
    are notified — never every teacher, and never for private essays.
    """
    assignment = getattr(submission, "assignment", None)
    if assignment is None:
        return {"sent": 0, "duplicates": 0, "failed": 0, "skipped": True}

    teacher = assignment.group.teacher
    if teacher is None:
        return {"sent": 0, "duplicates": 0, "failed": 0, "skipped": True}
    if not _preference_allows(teacher, "teacher_new_essay"):
        return {"sent": 0, "duplicates": 0, "failed": 0, "skipped": True}

    student_name = submission.student.get_full_name() or submission.student.email
    topic_title = assignment.topic.title if assignment.topic_id else "Esse"
    text = (
        "📝 *Yangi esse topshirildi*\n\n"
        f"👤 O'quvchi: *{student_name}*\n"
        f"📚 Mavzu: *{topic_title}*\n"
        f"🏫 Guruh: *{assignment.group.name}*"
    )
    outcome = notify_teacher(
        teacher=teacher,
        text=text,
        dedup_key=f"essay-submitted:{submission.pk}:{teacher.pk}",
        title=f"Yangi esse: {student_name}",
        notification_type="essay_graded",
    )
    return {
        "sent": 1 if outcome.get("success") and not outcome.get("duplicate") else 0,
        "duplicates": 1 if outcome.get("duplicate") else 0,
        "failed": 0 if outcome.get("success") else 1,
        "skipped": False,
    }


def notify_student_essay_graded(submission) -> dict:
    """Notify the student (and their parents) that grading finished.

    Reuses the existing essay notification contract and adds the parent copy.
    """
    student = submission.student
    score = (
        submission.final_score
        if submission.final_score is not None
        else submission.total_score
    )
    max_score = submission.max_score
    text = (
        "📝 *Esse baholandi*\n\n"
        f"📚 Mavzu: *{submission.topic.title if submission.topic_id else 'Umumiy esse'}*\n"
        f"📊 Ball: *{score}/{max_score}*"
    )

    results = {"sent": 0, "duplicates": 0, "failed": 0}
    if getattr(student, "telegram_chat_id", None) and getattr(
        student,
        "telegram_identity_verified_at",
        None,
    ):
        outcome = _deliver(
            chat_id=student.telegram_chat_id,
            text=text,
            dedup_key=f"essay-graded-student:{submission.pk}",
            notification_type="essay_graded",
            recipient=student,
            title="Esse baholandi",
        )
        results["sent"] += (
            1 if outcome.get("success") and not outcome.get("duplicate") else 0
        )
        results["duplicates"] += 1 if outcome.get("duplicate") else 0

    for parent in _parents_for(student):
        if not _preference_allows(parent, "essay_graded_alerts"):
            continue
        parent_text = (
            "🏫 *Grandec xabarnomasi*\n\n"
            f"Farzandingizning essesi baholandi.\n\n"
            f"📚 Mavzu: *{submission.topic.title if submission.topic_id else 'Umumiy esse'}*\n"
            f"📊 Ball: *{score}/{max_score}*"
        )
        outcome = _deliver(
            chat_id=parent.telegram_chat_id,
            text=parent_text,
            dedup_key=f"essay-graded-parent:{submission.pk}:{parent.pk}",
            notification_type="essay_graded",
            recipient=parent,
            title="Esse baholandi",
        )
        results["sent"] += (
            1 if outcome.get("success") and not outcome.get("duplicate") else 0
        )
        results["duplicates"] += 1 if outcome.get("duplicate") else 0
    return results
