"""Canonical attendance, observation and reporting services.

Every entry point — the React teacher panel, the Telegram bot and the JSON API —
resolves data through this module. Handlers must never re-implement roster,
marking, aggregation or authorization logic.

Guarantees
----------
* **Ownership.** ``teacher_groups(user)`` is the single scoping rule: a platform
  admin sees all groups, a teacher sees only the groups they own.
* **Idempotency.** A session may carry an ``idempotency_key``; replaying a bot
  callback returns the existing session instead of creating a second register.
  Records are unique per ``(session, student)`` so repeated markings update
  rather than duplicate.
* **No silent absences.** Finalizing refuses while any student is unmarked
  unless the caller explicitly passes ``mark_unmarked_as_absent=True``.
* **Corrections are audited.** Every status change appends an
  :class:`AttendanceAuditLog` row with the actor and the old/new value.
* **Aggregation, not loops.** Reports use ``values().annotate()`` so a group of
  any size costs a bounded number of queries.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.access import is_platform_admin
from apps.courses.models import StudentGroup

from .models import (
    AttendanceAuditLog,
    AttendanceRecord,
    AttendanceSession,
    ClassroomObservation,
)

logger = logging.getLogger(__name__)

#: Statuses that count as "the student was physically in the lesson".
ATTENDED_STATUSES = (
    AttendanceRecord.Status.PRESENT,
    AttendanceRecord.Status.LATE,
)

#: Statuses treated as an absence for the unexcused-absence metric.
UNEXCUSED_STATUSES = (AttendanceRecord.Status.ABSENT,)


class AttendanceError(ValidationError):
    """A domain-level validation failure with a user-facing Uzbek message."""


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


def teacher_groups(user):
    """Groups *user* may manage. Admins see everything, teachers their own."""
    if user is None or not getattr(user, "is_authenticated", False):
        return StudentGroup.objects.none()
    if is_platform_admin(user):
        return StudentGroup.objects.all()
    return StudentGroup.objects.filter(teacher=user)


def can_manage_group(user, group) -> bool:
    if group is None:
        return False
    return teacher_groups(user).filter(pk=group.pk).exists()


def assert_can_manage_group(user, group) -> None:
    if not can_manage_group(user, group):
        raise PermissionDenied("Bu guruh sizga tegishli emas.")


def get_session_for_user(user, session_id: int) -> AttendanceSession:
    session = (
        AttendanceSession.objects.select_related("group", "teacher")
        .filter(pk=session_id)
        .first()
    )
    if session is None:
        raise AttendanceSession.DoesNotExist("Davomat darsi topilmadi.")
    assert_can_manage_group(user, session.group)
    return session


def session_for_student(user, session_id: int) -> AttendanceSession:
    """A student may only read a session they have a record in."""
    session = (
        AttendanceSession.objects.select_related("group")
        .filter(pk=session_id, records__student=user)
        .distinct()
        .first()
    )
    if session is None:
        raise AttendanceSession.DoesNotExist("Davomat darsi topilmadi.")
    return session


def _assert_group_member(group, student) -> None:
    if not group.students.filter(pk=student.pk).exists():
        raise AttendanceError("O'quvchi bu guruhga a'zo emas.")


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


def create_session(
    *,
    group: StudentGroup,
    teacher,
    lesson_date: date | None = None,
    start_time=None,
    end_time=None,
    title: str = "",
    actor=None,
    idempotency_key: str | None = None,
) -> tuple[AttendanceSession, bool]:
    """Create — or resolve — the register for one group/date/period.

    Returns ``(session, created)``. Passing an ``idempotency_key`` makes this
    safe to call from a Telegram callback path that may be delivered twice.
    """
    assert_can_manage_group(teacher if teacher is not None else actor, group)
    lesson_date = lesson_date or timezone.localdate()
    actor = actor or teacher

    if idempotency_key:
        existing = (
            AttendanceSession.objects.filter(
                idempotency_key=idempotency_key,
            )
            .select_related("group")
            .first()
        )
        if existing is not None:
            if existing.group_id != group.pk:
                raise AttendanceError("Idempotentlik kaliti boshqa guruhga tegishli.")
            return existing, False

    try:
        with transaction.atomic():
            session, created = AttendanceSession.objects.get_or_create(
                group=group,
                lesson_date=lesson_date,
                start_time=start_time,
                defaults={
                    "teacher": teacher or actor,
                    "end_time": end_time,
                    "title": title,
                    "created_by": actor,
                    "idempotency_key": idempotency_key or None,
                },
            )
            if created:
                # Seed the register with the current roster as UNMARKED by not
                # creating rows at all: an absent-by-default register would let
                # a forgotten session look like a full absence.
                logger.info(
                    "Attendance session %s created for group %s on %s",
                    session.pk,
                    group.pk,
                    lesson_date,
                )
    except IntegrityError:
        # Lost the unique-slot race (or the idempotency-key race): resolve the
        # row a concurrent caller created.
        session = AttendanceSession.objects.filter(
            group=group,
            lesson_date=lesson_date,
            start_time=start_time,
        ).first()
        if session is None and idempotency_key:
            session = AttendanceSession.objects.filter(
                idempotency_key=idempotency_key,
            ).first()
        if session is None:
            raise
        return session, False

    if created and idempotency_key and not session.idempotency_key:
        AttendanceSession.objects.filter(pk=session.pk).update(
            idempotency_key=idempotency_key,
        )
        session.idempotency_key = idempotency_key
    return session, created


def today_session(group: StudentGroup, *, teacher=None) -> AttendanceSession | None:
    """The most recent unfinalized register for *group* today, if any."""
    return (
        AttendanceSession.objects.filter(
            group=group,
            lesson_date=timezone.localdate(),
        )
        .exclude(status=AttendanceSession.Status.CANCELLED)
        .order_by("-start_time", "-id")
        .first()
    )


def roster(session: AttendanceSession) -> list[dict]:
    """Current roster with each student's record (``status`` is None if unmarked)."""
    students = session.group.students.filter(is_active=True).order_by(
        "first_name", "last_name"
    )
    records = {record.student_id: record for record in session.records.all()}
    rows = []
    for student in students:
        record = records.get(student.pk)
        rows.append(
            {
                "student_id": student.pk,
                "name": student.get_full_name() or student.email,
                "record_id": record.pk if record else None,
                "status": record.status if record else None,
                "status_label": record.get_status_display()
                if record
                else "Belgilanmagan",
                "late_minutes": record.late_minutes if record else 0,
                "note": record.note if record else "",
                "marked": record is not None,
            }
        )
    return rows


def summary(session: AttendanceSession) -> dict:
    """Counts for one session, including the still-unmarked students."""
    counts = {
        status: total
        for status, total in session.records.values_list("status").annotate(
            total=Count("id")
        )
    }
    roster_size = session.group.students.filter(is_active=True).count()
    marked = sum(counts.values())
    return {
        "session_id": session.pk,
        "group_id": session.group_id,
        "group_name": session.group.name,
        "lesson_date": session.lesson_date.isoformat(),
        "time_label": session.local_time_label(),
        "status": session.status,
        "status_label": session.get_status_display(),
        "roster_size": roster_size,
        "marked": marked,
        "unmarked": max(0, roster_size - marked),
        "present": counts.get(AttendanceRecord.Status.PRESENT, 0),
        "late": counts.get(AttendanceRecord.Status.LATE, 0),
        "absent": counts.get(AttendanceRecord.Status.ABSENT, 0),
        "excused": counts.get(AttendanceRecord.Status.EXCUSED, 0),
        "attended": (
            counts.get(AttendanceRecord.Status.PRESENT, 0)
            + counts.get(AttendanceRecord.Status.LATE, 0)
        ),
    }


# ---------------------------------------------------------------------------
# Marking
# ---------------------------------------------------------------------------


def mark(
    session: AttendanceSession,
    student,
    status: str,
    *,
    late_minutes: int = 0,
    note: str = "",
    actor=None,
    reason: str = "",
) -> AttendanceRecord:
    """Create or correct one student's status, writing an audit row.

    Correcting an existing record is allowed (a teacher fixing a mistake is
    normal) and is recorded rather than rejected.
    """
    if status not in dict(AttendanceRecord.Status.choices):
        raise AttendanceError(f"Noma'lum davomat holati: {status}")
    if session.status == AttendanceSession.Status.CANCELLED:
        raise AttendanceError("Bekor qilingan davomat darsini o'zgartirib bo'lmaydi.")
    _assert_group_member(session.group, student)

    if status == AttendanceRecord.Status.LATE:
        late_minutes = max(0, int(late_minutes or 0))
    else:
        late_minutes = 0

    with transaction.atomic():
        record, created = AttendanceRecord.objects.select_for_update().get_or_create(
            session=session,
            student=student,
            defaults={
                "status": status,
                "late_minutes": late_minutes,
                "note": note[:200],
                "marked_by": actor,
                "marked_at": timezone.now(),
            },
        )
        if not created:
            old_status = record.status
            old_minutes = record.late_minutes
            record.status = status
            record.late_minutes = late_minutes
            record.note = note[:200]
            record.marked_by = actor
            record.marked_at = timezone.now()
            record.save(
                update_fields=[
                    "status",
                    "late_minutes",
                    "note",
                    "marked_by",
                    "marked_at",
                    "updated_at",
                ]
            )
            if old_status != status:
                AttendanceAuditLog.objects.create(
                    session=session,
                    record=record,
                    student=student,
                    actor=actor,
                    field="status",
                    old_value=old_status,
                    new_value=status,
                    reason=reason[:200],
                )
            elif old_minutes != late_minutes:
                AttendanceAuditLog.objects.create(
                    session=session,
                    record=record,
                    student=student,
                    actor=actor,
                    field="late_minutes",
                    old_value=str(old_minutes),
                    new_value=str(late_minutes),
                    reason=reason[:200],
                )
        else:
            AttendanceAuditLog.objects.create(
                session=session,
                record=record,
                student=student,
                actor=actor,
                field="status",
                old_value="",
                new_value=status,
                reason=reason[:200],
            )
    return record


def mark_many(
    session: AttendanceSession, marks: list[dict], *, actor=None, reason: str = ""
) -> int:
    """Apply a batch of ``{"student_id": int, "status": str, ...}`` markings."""
    students = {
        student.pk: student
        for student in session.group.students.filter(
            pk__in=[m.get("student_id") for m in marks if m.get("student_id")],
        )
    }
    applied = 0
    for entry in marks:
        student = students.get(entry.get("student_id"))
        if student is None:
            continue
        mark(
            session,
            student,
            entry.get("status"),
            late_minutes=entry.get("late_minutes", 0),
            note=entry.get("note", ""),
            actor=actor,
            reason=reason,
        )
        applied += 1
    return applied


def mark_all_present(session: AttendanceSession, *, actor=None) -> int:
    """Convenience: mark every currently-unmarked student PRESENT.

    Only used behind an explicit teacher action — the register never assumes
    presence on its own.
    """
    roster_students = session.group.students.filter(is_active=True)
    marked_ids = set(session.records.values_list("student_id", flat=True))
    unmarked = [s for s in roster_students if s.pk not in marked_ids]
    for student in unmarked:
        mark(
            session,
            student,
            AttendanceRecord.Status.PRESENT,
            actor=actor,
            reason="Hammasi keldi",
        )
    return len(unmarked)


def finalize(
    session: AttendanceSession,
    *,
    actor=None,
    mark_unmarked_as_absent: bool = False,
    reason: str = "",
) -> dict:
    """Finalize a register transactionally.

    Refuses while students are unmarked unless the caller explicitly confirms
    ``mark_unmarked_as_absent=True`` — an unfinished register must never be
    silently treated as a full absence.
    """
    with transaction.atomic():
        locked = AttendanceSession.objects.select_for_update().get(pk=session.pk)
        rows = roster(locked)
        unmarked_ids = [row["student_id"] for row in rows if not row["marked"]]

        if unmarked_ids and not mark_unmarked_as_absent:
            return {
                "ok": False,
                "reason": "unmarked_students",
                "unmarked": [
                    {"student_id": row["student_id"], "name": row["name"]}
                    for row in rows
                    if not row["marked"]
                ],
                "session_id": locked.pk,
            }

        if unmarked_ids and mark_unmarked_as_absent and actor is not None:
            pending = {
                student.pk: student
                for student in locked.group.students.filter(pk__in=unmarked_ids)
            }
            for student_id in unmarked_ids:
                student = pending.get(student_id)
                if student is None:
                    continue
                mark(
                    locked,
                    student,
                    AttendanceRecord.Status.ABSENT,
                    actor=actor,
                    reason=reason or "Davomat yakunlashda belgilanmagan",
                )

        locked.status = AttendanceSession.Status.FINALIZED
        locked.finalized_at = timezone.now()
        locked.finalized_by = actor
        locked.save(
            update_fields=["status", "finalized_at", "finalized_by", "updated_at"]
        )

    result = summary(locked)
    result["ok"] = True
    return result


# ---------------------------------------------------------------------------
# Reports (aggregated, no per-student queries)
# ---------------------------------------------------------------------------


def _default_period(start=None, end=None) -> tuple[date, date]:
    today = timezone.localdate()
    if start is None and end is None:
        return today - timedelta(days=29), today
    return start or today - timedelta(days=29), end or today


def finalize_and_notify(
    session: AttendanceSession,
    *,
    actor=None,
    mark_unmarked_as_absent: bool = False,
    reason: str = "",
    notify_parents: bool = True,
    notify_group: bool = True,
) -> dict:
    """Canonical finalize entry point for every channel (API, bot, admin).

    Notifications are scheduled with ``transaction.on_commit()`` so a message is
    only ever sent for a registration state that actually persisted, and each
    message carries a deterministic dedup key so a retry cannot duplicate it.
    """
    result = finalize(
        session,
        actor=actor,
        mark_unmarked_as_absent=mark_unmarked_as_absent,
        reason=reason,
    )
    if not result.get("ok"):
        return result

    from django.db import transaction as _tx

    from . import notifications as _notifications

    session.refresh_from_db()
    record_ids = list(session.records.values_list("pk", flat=True))

    def _dispatch():
        if notify_parents:
            try:
                _notifications.notify_parents_of_session(session, only=record_ids)
            except Exception:  # pragma: no cover - delivery must not break finalize
                logger.exception(
                    "Parent attendance notification failed for %s", session.pk
                )
        if notify_group:
            try:
                _notifications.send_group_attendance_summary(session)
            except Exception:  # pragma: no cover
                logger.exception("Group attendance summary failed for %s", session.pk)

    _tx.on_commit(_dispatch)
    return result


def group_attendance_report(
    group: StudentGroup, *, start: date | None = None, end: date | None = None
) -> dict:
    """Attendance statistics for one group over a date range.

    Only FINALIZED sessions feed the percentage: an unfinished register is
    reported separately as ``pending_sessions`` and never counted as absence.
    Excused absences are reported separately and are excluded from the
    "unexcused" figure.
    """
    start, end = _default_period(start, end)
    sessions = AttendanceSession.objects.filter(
        group=group,
        lesson_date__gte=start,
        lesson_date__lte=end,
    )
    finalized = sessions.filter(status=AttendanceSession.Status.FINALIZED)

    agg = finalized.aggregate(
        total=Count("id", distinct=True),
    )
    counts = dict(
        AttendanceRecord.objects.filter(session__in=finalized)
        .values_list("status")
        .annotate(total=Count("id"))
    )
    present = counts.get(AttendanceRecord.Status.PRESENT, 0)
    late = counts.get(AttendanceRecord.Status.LATE, 0)
    absent = counts.get(AttendanceRecord.Status.ABSENT, 0)
    excused = counts.get(AttendanceRecord.Status.EXCUSED, 0)
    marked_total = present + late + absent + excused
    attended = present + late

    return {
        "group_id": group.pk,
        "group_name": group.name,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "roster_size": group.students.filter(is_active=True).count(),
        "sessions_total": sessions.count(),
        "finalized_sessions": agg["total"] or 0,
        "pending_sessions": sessions.exclude(
            status=AttendanceSession.Status.FINALIZED,
        ).count(),
        "present": present,
        "late": late,
        "absent": absent,
        "excused": excused,
        "unexcused_absent": absent,
        "attended": attended,
        "marked_records": marked_total,
        "attendance_percentage": (
            round(attended / marked_total * 100, 1) if marked_total else None
        ),
        "late_arrivals": late,
    }


def group_daily_breakdown(
    group: StudentGroup, *, start: date | None = None, end: date | None = None
) -> list[dict]:
    """Per-day attendance rows for one group (aggregated in the database)."""
    start, end = _default_period(start, end)
    rows = (
        AttendanceRecord.objects.filter(
            session__group=group,
            session__status=AttendanceSession.Status.FINALIZED,
            session__lesson_date__gte=start,
            session__lesson_date__lte=end,
        )
        .values("session__lesson_date")
        .annotate(
            present=Count("id", filter=Q(status=AttendanceRecord.Status.PRESENT)),
            late=Count("id", filter=Q(status=AttendanceRecord.Status.LATE)),
            absent=Count("id", filter=Q(status=AttendanceRecord.Status.ABSENT)),
            excused=Count("id", filter=Q(status=AttendanceRecord.Status.EXCUSED)),
        )
        .order_by("session__lesson_date")
    )
    out = []
    for row in rows:
        marked = row["present"] + row["late"] + row["absent"] + row["excused"]
        attended = row["present"] + row["late"]
        out.append(
            {
                "date": row["session__lesson_date"].isoformat(),
                "present": row["present"],
                "late": row["late"],
                "absent": row["absent"],
                "excused": row["excused"],
                "attendance_percentage": (
                    round(attended / marked * 100, 1) if marked else None
                ),
            }
        )
    return out


def student_attendance_report(
    student,
    *,
    start: date | None = None,
    end: date | None = None,
    group: StudentGroup | None = None,
) -> dict:
    """One student's attendance history (their own view, a parent's, or a teacher's)."""
    start, end = _default_period(start, end)
    qs = AttendanceRecord.objects.filter(
        student=student,
        session__lesson_date__gte=start,
        session__lesson_date__lte=end,
    )
    if group is not None:
        qs = qs.filter(session__group=group)

    counts = dict(qs.values_list("status").annotate(total=Count("id")))
    present = counts.get(AttendanceRecord.Status.PRESENT, 0)
    late = counts.get(AttendanceRecord.Status.LATE, 0)
    absent = counts.get(AttendanceRecord.Status.ABSENT, 0)
    excused = counts.get(AttendanceRecord.Status.EXCUSED, 0)
    marked_total = present + late + absent + excused
    attended = present + late

    recent = qs.select_related("session", "session__group").order_by(
        "-session__lesson_date", "-session__start_time"
    )[:20]
    return {
        "student_id": student.pk,
        "name": student.get_full_name() or student.email,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "present": present,
        "late": late,
        "absent": absent,
        "excused": excused,
        "unexcused_absent": absent,
        "attended": attended,
        "marked_records": marked_total,
        "attendance_percentage": (
            round(attended / marked_total * 100, 1) if marked_total else None
        ),
        "recent": [
            {
                "date": record.session.lesson_date.isoformat(),
                "time": record.session.local_time_label(),
                "group": record.session.group.name,
                "status": record.status,
                "status_label": record.get_status_display(),
                "late_minutes": record.late_minutes,
                "note": record.note,
            }
            for record in recent
        ],
    }


def teacher_attendance_overview(user) -> dict:
    """All manageable groups with their current-period attendance summary."""
    groups = list(teacher_groups(user).order_by("name"))
    rows = []
    for group in groups:
        report = group_attendance_report(group)
        rows.append(
            {
                "group_id": group.pk,
                "group_name": group.name,
                "roster_size": report["roster_size"],
                "finalized_sessions": report["finalized_sessions"],
                "pending_sessions": report["pending_sessions"],
                "attendance_percentage": report["attendance_percentage"],
                "absent": report["absent"],
                "late": report["late"],
                "excused": report["excused"],
            }
        )
    return {
        "groups": rows,
        "start": _default_period()[0].isoformat(),
        "end": _default_period()[1].isoformat(),
    }


# ---------------------------------------------------------------------------
# Classroom observations
# ---------------------------------------------------------------------------

OBSERVATION_CATEGORY = "student_observation"


def create_observation(
    *,
    student,
    teacher,
    observation_type: str,
    neutral_description: str,
    session: AttendanceSession | None = None,
) -> ClassroomObservation:
    """Record a neutral observation. Nothing is sent until it is confirmed."""
    if observation_type not in dict(ClassroomObservation.ObservationType.choices):
        raise AttendanceError(f"Noma'lum kuzatuv turi: {observation_type}")
    text = (neutral_description or "").strip()
    if len(text) < 5:
        raise AttendanceError("Kuzatuv izohi juda qisqa.")
    if session is not None:
        assert_can_manage_group(teacher, session.group)
        _assert_group_member(session.group, student)
    else:
        # Without a session, the teacher must still share a group with the
        # student — otherwise any teacher could annotate any student.
        if not teacher_groups(teacher).filter(students=student).exists():
            raise PermissionDenied("Bu o'quvchi sizning guruhingizda emas.")

    return ClassroomObservation.objects.create(
        student=student,
        teacher=teacher,
        session=session,
        observation_type=observation_type,
        neutral_description=text,
        notification_status=ClassroomObservation.NotificationStatus.NOT_SENT,
    )


def update_observation(
    observation: ClassroomObservation,
    *,
    actor,
    neutral_description: str,
    observation_type: str | None = None,
) -> ClassroomObservation:
    """Correct a mistaken observation. Only the recording teacher (or an admin)."""
    if observation.teacher_id != getattr(actor, "pk", None) and not is_platform_admin(
        actor
    ):
        raise PermissionDenied("Faqat yozgan o'qituvchi tuzatishi mumkin.")
    if observation.notification_status == ClassroomObservation.NotificationStatus.SENT:
        raise AttendanceError("Yuborilgan kuzatuvni o'zgartirib bo'lmaydi.")
    text = (neutral_description or "").strip()
    if len(text) < 5:
        raise AttendanceError("Kuzatuv izohi juda qisqa.")
    observation.neutral_description = text
    if observation_type is not None:
        if observation_type not in dict(ClassroomObservation.ObservationType.choices):
            raise AttendanceError(f"Noma'lum kuzatuv turi: {observation_type}")
        observation.observation_type = observation_type
    observation.save(
        update_fields=[
            "neutral_description",
            "observation_type",
            "updated_at",
        ]
    )
    return observation


def confirm_observation(
    observation: ClassroomObservation, *, actor, send: bool = True, reason: str = ""
) -> ClassroomObservation:
    """Teacher confirmation. Only here may an observation reach a parent."""
    if observation.teacher_id != getattr(actor, "pk", None) and not is_platform_admin(
        actor
    ):
        raise PermissionDenied("Faqat yozgan o'qituvchi tasdiqlashi mumkin.")
    observation.confirmed_by = actor
    observation.confirmed_at = timezone.now()
    observation.notification_status = (
        ClassroomObservation.NotificationStatus.PENDING_CONFIRMATION
        if send
        else ClassroomObservation.NotificationStatus.SKIPPED
    )
    observation.save(
        update_fields=[
            "confirmed_by",
            "confirmed_at",
            "notification_status",
            "updated_at",
        ]
    )
    return observation


def mark_observation_sent(observation: ClassroomObservation) -> None:
    observation.notification_status = ClassroomObservation.NotificationStatus.SENT
    observation.sent_at = timezone.now()
    observation.save(update_fields=["notification_status", "sent_at", "updated_at"])
