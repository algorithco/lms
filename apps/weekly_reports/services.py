"""Canonical weekly academic report service.

This module is the single place that answers "what happened in group X during
the completed week?" — the Celery beat job, the Telegram bot and the React
dashboard all call it, so the three can never disagree.

Two rules are load-bearing:

1. **A report is a record, not a view.** Figures are computed once for a closed
   week and persisted on :class:`~apps.weekly_reports.models.WeeklyGroupReport`.
   Correcting attendance or grading afterwards produces an explicit, versioned
   regeneration — the old row stays for audit and an already-sent message can
   still be explained.
2. **Nothing is invented.** Unmarked students are never counted as absent, a
   pending essay is never a zero-scored graded essay, a raw practice percentage
   is never presented as an official Milliy Sertifikat result, and financial
   figures exist only for recipients who are authorized to see them.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.accounts.access import is_platform_admin
from apps.attendance import services as attendance_services
from apps.attendance.models import (
    AttendanceRecord,
    AttendanceSession,
    NotificationPreference,
)
from apps.courses.models import Enrollment, StudentGroup
from apps.essays import group_reports
from apps.essays.models import EssayAssignment, EssaySubmission

from .models import (
    ReportPeriodMixin,
    WeeklyGroupReport,
    WeeklyReportDelivery,
    WeeklyReportSettings,
    WeeklyStudentReport,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "Asia/Tashkent"

#: A student is flagged for attendance follow-up at or above this many
#: unexcused absences in the week...
FOLLOW_UP_ABSENCES = 2
#: ...or below this attendance percentage (only when records exist).
FOLLOW_UP_PERCENTAGE = 80.0
#: A student is flagged for academic support below this average practice score.
SUPPORT_PERCENTAGE = 60.0


# ---------------------------------------------------------------------------
# Period arithmetic
# ---------------------------------------------------------------------------


def reporting_timezone_name() -> str:
    try:
        return WeeklyReportSettings.load().timezone_name or DEFAULT_TIMEZONE
    except Exception:  # pragma: no cover - database unavailable during checks
        return getattr(settings, "WEEKLY_REPORT_TIMEZONE", DEFAULT_TIMEZONE)


def reporting_timezone() -> ZoneInfo:
    name = reporting_timezone_name()
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("Unknown weekly report timezone %r; falling back to UTC", name)
        return ZoneInfo("UTC")


def _local(value: datetime | None = None) -> datetime:
    return (value or timezone.now()).astimezone(reporting_timezone())


def week_bounds(anchor: datetime | None = None) -> tuple[datetime, datetime]:
    """The Monday 00:00 → Sunday 23:59:59.999999 week containing *anchor*.

    Both ends are timezone-aware instants in the configured reporting zone.
    ``period_end`` is *inclusive* (the last microsecond of Sunday) because that
    is what an operator reads in the UI; every query below converts to the
    half-open interval internally.
    """
    local = _local(anchor)
    monday = (local - timedelta(days=local.weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    sunday_end = monday + timedelta(days=7) - timedelta(microseconds=1)
    return monday, sunday_end


def previous_week_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    """The *completed* week before the one containing *now*.

    This is what the scheduled job reports on, which is also why an incomplete
    week can never be sent as a final report.
    """
    return week_bounds(_local(now) - timedelta(days=7))


def period_end_exclusive(period_end: datetime) -> datetime:
    """Convert the stored inclusive Sunday instant into a half-open bound."""
    return period_end + timedelta(microseconds=1)


def period_dates(period_start: datetime, period_end: datetime) -> tuple[date, date]:
    """Local calendar dates for the stored instants (used by date-filtered services)."""
    return (
        _local(period_start).date(),
        _local(period_end).date(),
    )


def period_label(period_start: datetime, period_end: datetime) -> str:
    start, end = period_dates(period_start, period_end)
    return f"{start:%Y-%m-%d} — {end:%Y-%m-%d}"


def is_period_complete(period_end: datetime, *, now: datetime | None = None) -> bool:
    """True once the week has actually finished."""
    return period_end <= (now or timezone.now())


def ensure_complete(period_end: datetime, *, now: datetime | None = None) -> None:
    """Refuse to treat a still-running week as final."""
    if not is_period_complete(period_end, now=now):
        raise ValueError("Tugallanmagan hafta uchun yakuniy hisobot tayyorlanmaydi.")


def next_run_at(now: datetime | None = None) -> datetime:
    """Next scheduled send instant per the configurable settings row."""
    config = WeeklyReportSettings.load()
    tz = reporting_timezone()
    local = _local(now)
    candidate = local.replace(
        hour=int(config.send_hour) % 24,
        minute=int(config.send_minute) % 60,
        second=0,
        microsecond=0,
    )
    candidate += timedelta(
        days=(int(config.send_weekday) - local.weekday()) % 7,
    )
    if candidate <= local:
        candidate += timedelta(days=7)
    return candidate.astimezone(tz)


# ---------------------------------------------------------------------------
# Aggregation: attendance
# ---------------------------------------------------------------------------


def attendance_summary(
    group: StudentGroup, period_start: datetime, period_end: datetime
) -> dict:
    """Attendance block, built from FINALIZED sessions only.

    Delegates the counts to :mod:`apps.attendance.services` so the weekly report
    and the attendance screen can never disagree, then adds the follow-up list —
    computed with one grouped query, not a per-student loop.
    """
    start_date, end_date = period_dates(period_start, period_end)
    report = attendance_services.group_attendance_report(
        group,
        start=start_date,
        end=end_date,
    )
    finalized = AttendanceSession.objects.filter(
        group=group,
        status=AttendanceSession.Status.FINALIZED,
        lesson_date__gte=start_date,
        lesson_date__lte=end_date,
    )
    rows = (
        AttendanceRecord.objects.filter(session__in=finalized)
        .values("student_id")
        .annotate(
            present=Count("id", filter=Q(status=AttendanceRecord.Status.PRESENT)),
            late=Count("id", filter=Q(status=AttendanceRecord.Status.LATE)),
            absent=Count("id", filter=Q(status=AttendanceRecord.Status.ABSENT)),
            excused=Count("id", filter=Q(status=AttendanceRecord.Status.EXCUSED)),
        )
    )
    names = dict(group.students.filter(is_active=True).values_list("pk", "first_name"))
    follow_up = []
    for row in rows:
        marked = row["present"] + row["late"] + row["absent"] + row["excused"]
        if not marked:
            continue
        attended = row["present"] + row["late"]
        percentage = round(attended / marked * 100, 1)
        if row["absent"] >= FOLLOW_UP_ABSENCES or percentage < FOLLOW_UP_PERCENTAGE:
            follow_up.append(
                {
                    "student_id": row["student_id"],
                    "name": names.get(row["student_id"], ""),
                    "unexcused_absences": row["absent"],
                    "excused_absences": row["excused"],
                    "late": row["late"],
                    "attendance_percentage": percentage,
                }
            )
    follow_up.sort(
        key=lambda item: (-item["unexcused_absences"], item["attendance_percentage"])
    )

    return {
        "active_students": report["roster_size"],
        "finalized_lessons": report["finalized_sessions"],
        "unfinished_lessons": report["pending_sessions"],
        "present": report["present"],
        "late": report["late"],
        "excused_absences": report["excused"],
        "unexcused_absences": report["unexcused_absent"],
        "attendance_percentage": report["attendance_percentage"],
        "marked_records": report["marked_records"],
        "students_requiring_follow_up": follow_up,
        "follow_up_count": len(follow_up),
    }


# ---------------------------------------------------------------------------
# Aggregation: essays
# ---------------------------------------------------------------------------


def essays_summary(
    group: StudentGroup, period_start: datetime, period_end: datetime
) -> dict:
    """Essay block.

    Visibility follows the canonical rule in :mod:`apps.essays.group_reports`:
    a submission counts only when it is explicitly attached to an assignment of
    this group, or the student opted the essay into group visibility. Merely
    being a group member is never enough, and a private essay is never counted.
    """
    start_date, end_date = period_dates(period_start, period_end)
    assignments = EssayAssignment.objects.filter(group=group, is_active=True)
    submitted = group_reports._visible_submissions(group).filter(
        Q(submitted_at__date__gte=start_date, submitted_at__date__lte=end_date)
        | Q(
            submitted_at__isnull=True,
            updated_at__date__gte=start_date,
            updated_at__date__lte=end_date,
        )
    )
    stats = submitted.aggregate(
        graded=Count("id", filter=Q(status__in=group_reports.GRADED_STATUSES)),
        pending=Count("id", filter=Q(status__in=group_reports.PENDING_STATUSES)),
        failed=Count("id", filter=Q(status__in=group_reports.FAILED_STATUSES)),
        reviewed=Count(
            "id",
            filter=Q(status=EssaySubmission.Status.TEACHER_REVIEWED),
        ),
        avg_raw=Avg("total_score", filter=Q(status__in=group_reports.GRADED_STATUSES)),
    )
    graded = stats["graded"] or 0

    # Score distribution by percentage of max_score, so essays with different
    # maxima stay comparable. Raw score is never averaged across maxima.
    buckets = {"0-50%": 0, "50-70%": 0, "70-90%": 0, "90-100%": 0}
    for total, maximum in submitted.filter(
        status__in=group_reports.GRADED_STATUSES,
    ).values_list("total_score", "max_score"):
        if not maximum:
            continue
        percentage = float(total or 0) / float(maximum) * 100
        key = (
            "0-50%"
            if percentage < 50
            else "50-70%"
            if percentage < 70
            else "70-90%"
            if percentage < 90
            else "90-100%"
        )
        buckets[key] += 1

    roster = group.students.filter(is_active=True).count()
    assignment_count = assignments.count()
    # A submission is counted once per (assignment, student) pair, so a student
    # who revised and resubmitted is not counted twice toward "submitted".
    submitted_pairs = submitted.values("assignment_id", "student_id").distinct().count()
    expected = roster * assignment_count
    return {
        "assigned_essays": assignment_count,
        "expected_submissions": expected,
        "submitted": submitted.count(),
        "submitted_students": submitted.values("student_id").distinct().count(),
        "counted_pairs": submitted_pairs,
        "missing_submissions": max(0, expected - submitted_pairs),
        "graded": graded,
        "pending_ai": stats["pending"] or 0,
        "teacher_reviewed": stats["reviewed"] or 0,
        "grading_failed": stats["failed"] or 0,
        "average_raw_score": (
            round(float(stats["avg_raw"]), 2) if stats["avg_raw"] is not None else None
        ),
        "max_score": _dominant_max_score(submitted),
        "score_distribution": buckets,
    }


def _dominant_max_score(submitted) -> int | None:
    row = (
        submitted.filter(status__in=group_reports.GRADED_STATUSES)
        .values("max_score")
        .annotate(total=Count("id"))
        .order_by("-total")
        .first()
    )
    return row["max_score"] if row else None


# ---------------------------------------------------------------------------
# Aggregation: tests
# ---------------------------------------------------------------------------


def tests_summary(
    group: StudentGroup, period_start: datetime, period_end: datetime
) -> dict:
    """Test block.

    "Assigned" means a published test on a course that at least one group
    member is enrolled in — the only explicit course↔student relationship the
    platform has. A raw practice percentage is reported as ``practice`` and is
    never labelled an official Milliy Sertifikat score.
    """
    from apps.results.models import Result
    from apps.tests.models import Test, TestAttempt

    students = group.students.filter(is_active=True)
    course_ids = list(
        Enrollment.objects.filter(student__in=students)
        .values_list("course_id", flat=True)
        .distinct()
    )
    assigned_tests = (
        Test.objects.filter(
            is_active=True,
            status=Test.Status.PUBLISHED,
            course_id__in=course_ids,
        ).count()
        if course_ids
        else 0
    )

    attempts = TestAttempt.objects.filter(
        student__in=students,
        started_at__gte=period_start,
        started_at__lt=period_end_exclusive(period_end),
    )
    status_counts = dict(attempts.values_list("status").annotate(total=Count("id")))
    completed = status_counts.get(TestAttempt.Status.COMPLETED, 0)
    incomplete = status_counts.get(TestAttempt.Status.IN_PROGRESS, 0)
    pending_grading = status_counts.get(TestAttempt.Status.PENDING_GRADING, 0)

    results = Result.objects.filter(
        attempt__in=attempts.filter(status=TestAttempt.Status.COMPLETED),
    )
    avg_percentage = results.aggregate(value=Avg("percentage"))["value"]

    per_student = (
        Result.objects.filter(
            attempt__in=attempts.filter(status=TestAttempt.Status.COMPLETED),
        )
        .values("student_id")
        .annotate(practice=Avg("percentage"), taken=Count("id"))
    )
    needs_support = []
    for row in per_student:
        if row["practice"] is None:
            continue
        if float(row["practice"]) < SUPPORT_PERCENTAGE:
            needs_support.append(
                {
                    "student_id": row["student_id"],
                    "practice_percentage": round(float(row["practice"]), 1),
                    "tests_taken": row["taken"],
                }
            )

    return {
        "assigned_tests": assigned_tests,
        "attempts": attempts.count(),
        "completed_attempts": completed,
        "incomplete_attempts": incomplete,
        "pending_grading": pending_grading,
        "cancelled_attempts": status_counts.get(TestAttempt.Status.CANCELLED, 0),
        "timed_out_attempts": status_counts.get(TestAttempt.Status.TIMEOUT, 0),
        # Explicitly a *practice* score — not a Milliy Sertifikat standard score.
        "average_practice_percentage": (
            round(float(avg_percentage), 1) if avg_percentage is not None else None
        ),
        "score_basis": "practice",
        "needs_support": needs_support,
        "needs_support_count": len(needs_support),
    }


# ---------------------------------------------------------------------------
# Aggregation: course payments (authorized recipients only)
# ---------------------------------------------------------------------------


def finance_block(
    group: StudentGroup, period_start: datetime, period_end: datetime
) -> dict | None:
    """Course-tuition block, or ``None`` when the tuition domain is unavailable.

    The figures are always *aggregate*: counts of invoices by status and total
    amounts. No payment proof, banking detail or another group's finances are
    ever included. Rendering decides whether a recipient may see the block.
    """
    try:
        from apps.tuition import services as tuition_services
    except Exception:  # pragma: no cover - tuition app is optional at runtime
        return None
    if not hasattr(tuition_services, "group_finance_summary"):
        return None
    try:
        return tuition_services.group_finance_summary(
            group,
            period_start,
            period_end,
        )
    except Exception:
        logger.exception("Tuition summary failed for group %s", group.pk)
        return None


# ---------------------------------------------------------------------------
# Summary assembly
# ---------------------------------------------------------------------------


def build_group_summary(
    group: StudentGroup, period_start: datetime, period_end: datetime
) -> dict:
    """Full persisted summary for one group and one closed week."""
    return {
        "group_id": group.pk,
        "group_name": group.name,
        "period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "label": period_label(period_start, period_end),
            "timezone": reporting_timezone_name(),
        },
        "attendance": attendance_summary(group, period_start, period_end),
        "essays": essays_summary(group, period_start, period_end),
        "tests": tests_summary(group, period_start, period_end),
        "finance": finance_block(group, period_start, period_end),
    }


def build_student_summary(
    student, period_start: datetime, period_end: datetime
) -> dict:
    """One student's permitted week — the only content a parent ever receives."""
    start_date, end_date = period_dates(period_start, period_end)
    attendance = attendance_services.student_attendance_report(
        student,
        start=start_date,
        end=end_date,
    )
    from apps.results.models import Result
    from apps.tests.models import TestAttempt

    attempts = TestAttempt.objects.filter(
        student=student,
        started_at__gte=period_start,
        started_at__lt=period_end_exclusive(period_end),
        status=TestAttempt.Status.COMPLETED,
    )
    results = Result.objects.filter(attempt__in=attempts)
    submissions = EssaySubmission.objects.filter(
        student=student,
        status__in=group_reports.GRADED_STATUSES,
    ).filter(
        Q(submitted_at__date__gte=start_date, submitted_at__date__lte=end_date)
        | Q(
            submitted_at__isnull=True,
            updated_at__date__gte=start_date,
            updated_at__date__lte=end_date,
        )
    )
    return {
        "student_id": student.pk,
        "student_name": student.get_full_name() or student.email,
        "period": {
            "start": period_start.isoformat(),
            "end": period_end.isoformat(),
            "label": period_label(period_start, period_end),
            "timezone": reporting_timezone_name(),
        },
        "attendance": {
            "present": attendance["present"],
            "late": attendance["late"],
            "excused_absences": attendance["excused"],
            "unexcused_absences": attendance["unexcused_absent"],
            "attendance_percentage": attendance["attendance_percentage"],
        },
        "essays": {
            "graded": submissions.count(),
            "average_raw_score": _student_average(submissions),
        },
        "tests": {
            "completed_attempts": attempts.count(),
            "average_practice_percentage": _student_practice(results),
            "score_basis": "practice",
        },
    }


def _student_average(submissions) -> float | None:
    value = submissions.aggregate(value=Avg("total_score"))["value"]
    return round(float(value), 2) if value is not None else None


def _student_practice(results) -> float | None:
    value = results.aggregate(value=Avg("percentage"))["value"]
    return round(float(value), 1) if value is not None else None


# ---------------------------------------------------------------------------
# Generation (idempotent) and explicit regeneration (versioned)
# ---------------------------------------------------------------------------


def _current_version(model, **filters) -> int:
    value = (
        model.objects.filter(is_current=True, **filters)
        .order_by("-version")
        .values_list("version", flat=True)
        .first()
    )
    return int(value or 0)


def generate_group_report(
    group: StudentGroup,
    period_start: datetime,
    period_end: datetime,
    *,
    actor=None,
    reason: str = "",
    regenerate: bool = False,
) -> WeeklyGroupReport:
    """Generate (or explicitly regenerate) one group's report for a closed week.

    Calling this twice for the same week returns the *same* row unless
    ``regenerate`` is set — that is what makes the Celery beat tick, a manual
    re-run and a bot retry all converge on one report.
    """
    ensure_complete(period_end)
    with transaction.atomic():
        # Row-lock the stable group row as well as any current report. The
        # report row does not exist on first generation, so locking only the
        # filtered report cannot serialize two simultaneous first writers.
        StudentGroup.objects.select_for_update().get(pk=group.pk)
        existing = (
            WeeklyGroupReport.objects.select_for_update()
            .filter(group=group, period_start=period_start, is_current=True)
            .first()
        )
        if existing is not None and not regenerate:
            return existing
        version = (
            (existing.version + 1)
            if existing is not None
            else max(
                1,
                _current_version(
                    WeeklyGroupReport, group=group, period_start=period_start
                )
                + 1,
            )
        )
        summary = build_group_summary(group, period_start, period_end)
        if existing is not None:
            WeeklyGroupReport.objects.filter(pk=existing.pk).update(is_current=False)
        report = WeeklyGroupReport.objects.create(
            group=group,
            period_start=period_start,
            period_end=period_end,
            period_label=period_label(period_start, period_end),
            version=version,
            is_current=True,
            supersedes=existing,
            generation_reason=reason[:200],
            generated_by=actor,
            summary=summary,
        )
    return report


def generate_student_report(
    student,
    period_start: datetime,
    period_end: datetime,
    *,
    actor=None,
    reason: str = "",
    regenerate: bool = False,
) -> WeeklyStudentReport:
    ensure_complete(period_end)
    with transaction.atomic():
        # Serialize first generation on the stable user row (there is no
        # report row yet for select_for_update to lock).
        type(student).objects.select_for_update().get(pk=student.pk)
        existing = (
            WeeklyStudentReport.objects.select_for_update()
            .filter(student=student, period_start=period_start, is_current=True)
            .first()
        )
        if existing is not None and not regenerate:
            return existing
        version = (
            (existing.version + 1)
            if existing is not None
            else max(
                1,
                _current_version(
                    WeeklyStudentReport,
                    student=student,
                    period_start=period_start,
                )
                + 1,
            )
        )
        summary = build_student_summary(student, period_start, period_end)
        if existing is not None:
            WeeklyStudentReport.objects.filter(pk=existing.pk).update(is_current=False)
        report = WeeklyStudentReport.objects.create(
            student=student,
            period_start=period_start,
            period_end=period_end,
            period_label=period_label(period_start, period_end),
            version=version,
            is_current=True,
            supersedes=existing,
            generation_reason=reason[:200],
            generated_by=actor,
            summary=summary,
        )
    return report


def generate_all_reports(
    period_start: datetime, period_end: datetime, *, now: datetime | None = None
) -> dict:
    """Generate every group report (and parent-facing student reports).

    Missed-job recovery: the job is idempotent for a given week, so an operator
    can safely re-run it for the previous week after an outage.
    """
    ensure_complete(period_end, now=now)
    groups_created = 0
    groups_reused = 0
    for group in StudentGroup.objects.all().order_by("pk"):
        before = WeeklyGroupReport.objects.filter(
            group=group,
            period_start=period_start,
            is_current=True,
        ).exists()
        generate_group_report(group, period_start, period_end)
        if before:
            groups_reused += 1
        else:
            groups_created += 1

    students_created = students_reused = 0
    for student in _students_needing_reports():
        before = WeeklyStudentReport.objects.filter(
            student=student,
            period_start=period_start,
            is_current=True,
        ).exists()
        generate_student_report(student, period_start, period_end)
        if before:
            students_reused += 1
        else:
            students_created += 1

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "groups_created": groups_created,
        "groups_reused": groups_reused,
        "students_created": students_created,
        "students_reused": students_reused,
    }


def _students_needing_reports():
    """Students a verified parent is linked to (a private report has a reader)."""
    from apps.accounts.models import ParentStudentLink

    from apps.attendance.models import NotificationPreference

    ids = (
        ParentStudentLink.objects.filter(
            is_approved=True,
            parent__is_active=True,
            student__is_active=True,
        )
        .values_list("student_id", flat=True)
        .distinct()
    )
    from django.contrib.auth import get_user_model

    return list(
        get_user_model().objects.filter(
            pk__in=list(ids),
            is_active=True,
            role="student",
        )
    )


def regenerate(report: ReportPeriodMixin, *, actor, reason: str) -> ReportPeriodMixin:
    """Explicit, versioned regeneration. Never silently rewrites a report."""
    if isinstance(report, WeeklyGroupReport):
        return generate_group_report(
            report.group,
            report.period_start,
            report.period_end,
            actor=actor,
            reason=reason,
            regenerate=True,
        )
    return generate_student_report(
        report.student,
        report.period_start,
        report.period_end,
        actor=actor,
        reason=reason,
        regenerate=True,
    )
