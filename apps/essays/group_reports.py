"""Teacher-facing group essay results and assignment completion reporting.

Two hard rules shape this module:

1. **Explicit context, never inferred membership.** A student may belong to
   several groups, so an essay is linked to a group through an explicit
   :class:`EssayAssignment` — or through the student's own explicit
   ``group_visibility`` opt-in. Belonging to a group is *not* enough.
2. **Ownership scoping.** Queries always start from the teacher's own groups.
   A teacher can never enumerate another teacher's students or essays, and a
   platform admin sees only what their administrative scope already allows.

Reporting also keeps the distinct concepts distinct: the AI raw score, the
converted practice score and the teacher-adjusted final grade are separate
fields, and a practice score is never presented as an official Rasch result.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone

from apps.accounts.access import is_platform_admin
from apps.courses.models import StudentGroup

from .models import EssayAssignment, EssaySubmission

logger = logging.getLogger(__name__)

#: Statuses that mean "the AI/teacher result exists".
GRADED_STATUSES = (
    EssaySubmission.Status.GRADED,
    EssaySubmission.Status.TEACHER_REVIEWED,
    EssaySubmission.Status.AI_EVALUATED,
)

#: Statuses that mean "the student sent it and we are still working".
PENDING_STATUSES = (
    EssaySubmission.Status.PENDING,
    EssaySubmission.Status.PENDING_TEACHER,
)

#: Statuses that mean the grading pipeline itself failed (NOT a non-submission).
FAILED_STATUSES = (EssaySubmission.Status.ERROR,)

SOURCE_LABELS = {
    EssaySubmission.Source.WEB: "WEB",
    EssaySubmission.Source.TELEGRAM: "TELEGRAM",
    EssaySubmission.Source.TMA: "TMA",
    EssaySubmission.Source.EXAM: "EXAM",
}


def teacher_groups(user):
    """Groups *user* may report on (admins all, teachers their own)."""
    if user is None or not getattr(user, "is_authenticated", False):
        return StudentGroup.objects.none()
    if is_platform_admin(user):
        return StudentGroup.objects.all()
    return StudentGroup.objects.filter(teacher=user)


def assert_group_access(user, group) -> None:
    from django.core.exceptions import PermissionDenied

    if not teacher_groups(user).filter(pk=group.pk).exists():
        raise PermissionDenied("Bu guruh sizga tegishli emas.")


def _visible_submissions(group, *, include_group_visible: bool = True):
    """Submissions reportable for *group*.

    ``assignment_only`` submissions are reached through an explicit assignment
    for this group; ``group_visible`` ones are the student's explicit opt-in.
    ``private`` submissions are never included.
    """
    query = Q(assignment__group=group)
    if include_group_visible:
        query |= Q(
            group_visibility=EssaySubmission.GroupVisibility.GROUP_VISIBLE,
            student__student_groups=group,
        )
    return EssaySubmission.objects.filter(query).exclude(
        group_visibility=EssaySubmission.GroupVisibility.PRIVATE,
    )


def submitted_on(submission: EssaySubmission):
    """When the student handed the essay in.

    ``EssaySubmission`` has no ``created_at``; ``submitted_at`` is set when the
    grading job is accepted, and ``updated_at`` is the fallback for rows that
    predate that field or were saved as drafts.
    """
    return submission.submitted_at or submission.updated_at


def _row(submission: EssaySubmission) -> dict:
    """One report row. Contains no other student's data."""
    effective = (
        submission.final_score
        if submission.final_score is not None
        else submission.total_score
    )
    return {
        "submission_id": submission.pk,
        "student_id": submission.student_id,
        "student_name": submission.student.get_full_name() or submission.student.email,
        "topic_title": submission.topic.title if submission.topic_id else "Umumiy esse",
        "topic_id": submission.topic_id,
        "assignment_id": submission.assignment_id,
        "submitted_at": (
            submitted_on(submission).isoformat() if submitted_on(submission) else None
        ),
        "source": submission.source,
        "source_label": SOURCE_LABELS.get(submission.source, submission.source.upper()),
        "status": submission.status,
        "status_label": submission.get_status_display(),
        "is_graded": submission.status in GRADED_STATUSES,
        "is_pending": submission.status in PENDING_STATUSES,
        "is_failed": submission.status in FAILED_STATUSES,
        # Raw AI total and the teacher-adjusted grade stay separate; the
        # converted practice score is explicitly a practice value.
        "ai_total_score": float(submission.total_score)
        if submission.total_score is not None
        else None,
        "max_score": submission.max_score,
        "final_score": float(submission.final_score)
        if submission.final_score is not None
        else None,
        "effective_score": float(effective) if effective is not None else None,
        "converted_practice_score": converted_practice_score(submission),
        "grading_source": submission.grading_source,
        "is_off_topic": submission.is_off_topic,
        "teacher_review_required": (
            submission.status == EssaySubmission.Status.PENDING_TEACHER
            or submission.teacher_review_requested
        ),
        "teacher_review_requested": submission.teacher_review_requested,
        "graded_at": submission.graded_at.isoformat() if submission.graded_at else None,
        "result_url": f"/essays/result/{submission.pk}/",
    }


def converted_practice_score(submission: EssaySubmission) -> int | None:
    """Practice-scale conversion — the ONE canonical rule.

    Delegates to :attr:`EssaySubmission.converted_score` so the report, the
    result page and the leaderboard can never disagree. The property applies
    the documented ``score / max_score * ESSAY_TARGET_SCALE`` formula with the
    teacher grade first, then the off-topic override, then the AI score.

    This is a *practice* score. It is never an official Rasch/Milliy result.
    """
    return submission.converted_score


def group_essay_results(
    group: StudentGroup,
    *,
    student_id: int | None = None,
    start: date | None = None,
    end: date | None = None,
    state: str | None = None,
    source: str | None = None,
    review_required: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Filtered, paginated essay results for one teacher group."""
    qs = _visible_submissions(group).select_related("student", "topic", "assignment")

    if student_id:
        qs = qs.filter(student_id=student_id)
    # Date ranges use the hand-in date; rows without ``submitted_at`` fall back
    # to ``updated_at`` so a legacy row is not silently filtered out.
    if start:
        qs = qs.filter(
            Q(submitted_at__date__gte=start)
            | Q(submitted_at__isnull=True, updated_at__date__gte=start)
        )
    if end:
        qs = qs.filter(
            Q(submitted_at__date__lte=end)
            | Q(submitted_at__isnull=True, updated_at__date__lte=end)
        )
    if state == "graded":
        qs = qs.filter(status__in=GRADED_STATUSES)
    elif state == "pending":
        qs = qs.filter(status__in=PENDING_STATUSES)
    elif state == "failed":
        qs = qs.filter(status__in=FAILED_STATUSES)
    if source:
        qs = qs.filter(source=source)
    if review_required:
        qs = qs.filter(
            Q(status=EssaySubmission.Status.PENDING_TEACHER)
            | Q(teacher_review_requested=True)
        )

    total = qs.count()
    rows = [
        _row(s)
        for s in qs.order_by("-submitted_at", "-updated_at", "-id")[
            offset : offset + limit
        ]
    ]

    stats = qs.aggregate(
        graded=Count("id", filter=Q(status__in=GRADED_STATUSES)),
        pending=Count("id", filter=Q(status__in=PENDING_STATUSES)),
        failed=Count("id", filter=Q(status__in=FAILED_STATUSES)),
        avg_ai=Avg("total_score", filter=Q(status__in=GRADED_STATUSES)),
    )
    return {
        "group_id": group.pk,
        "group_name": group.name,
        "total": total,
        "shown": len(rows),
        "limit": limit,
        "offset": offset,
        "graded": stats["graded"] or 0,
        "pending": stats["pending"] or 0,
        "failed": stats["failed"] or 0,
        "average_ai_score": (
            round(float(stats["avg_ai"]), 2) if stats["avg_ai"] is not None else None
        ),
        "results": rows,
    }


def group_essay_summary(
    group: StudentGroup, *, assignment: EssayAssignment | None = None
) -> dict:
    """Compact graded/pending/not-submitted counts for the bot's group header."""
    if assignment is not None:
        completion = assignment_completion(assignment)
        return {
            "group_id": group.pk,
            "group_name": group.name,
            "assignment_id": assignment.pk,
            "roster_size": completion["expected"],
            "graded": completion["graded"],
            "pending": completion["pending"],
            "failed": completion["failed"],
            "not_submitted": completion["not_submitted"],
            "average_ai_score": completion["average_ai_score"],
        }
    qs = _visible_submissions(group)
    stats = qs.aggregate(
        graded=Count("id", filter=Q(status__in=GRADED_STATUSES)),
        pending=Count("id", filter=Q(status__in=PENDING_STATUSES)),
        failed=Count("id", filter=Q(status__in=FAILED_STATUSES)),
        avg_ai=Avg("total_score", filter=Q(status__in=GRADED_STATUSES)),
    )
    roster_size = group.students.filter(is_active=True).count()
    submitted_students = qs.values("student_id").distinct().count()
    return {
        "group_id": group.pk,
        "group_name": group.name,
        "assignment_id": None,
        "roster_size": roster_size,
        "graded": stats["graded"] or 0,
        "pending": stats["pending"] or 0,
        "failed": stats["failed"] or 0,
        "not_submitted": max(0, roster_size - submitted_students),
        "average_ai_score": (
            round(float(stats["avg_ai"]), 2) if stats["avg_ai"] is not None else None
        ),
    }


def assignment_completion(assignment: EssayAssignment) -> dict:
    """Completion tracking for one assignment.

    An AI/grading failure is reported as ``failed``, never as a missing
    submission — the student did submit, and the teacher has to know the
    difference to act on it.

    Membership is evaluated live, so a student who joins the group after the
    assignment was created is included and one who left is not.
    """
    expected_students = list(
        assignment.group.students.filter(is_active=True).order_by(
            "first_name", "last_name"
        )
    )
    submissions = EssaySubmission.objects.filter(assignment=assignment).select_related(
        "student"
    )
    by_student: dict[int, EssaySubmission] = {}
    for submission in submissions:
        # If a student somehow has several, keep the most recent.
        current = by_student.get(submission.student_id)
        if current is None or submission.pk > current.pk:
            by_student[submission.student_id] = submission

    graded = pending = failed = 0
    scores: list[float] = []
    submitted_rows = []
    missing_rows = []

    for student in expected_students:
        submission = by_student.get(student.pk)
        name = student.get_full_name() or student.email
        if submission is None:
            missing_rows.append({"student_id": student.pk, "name": name})
            continue
        if submission.status in GRADED_STATUSES:
            graded += 1
            score = (
                submission.final_score
                if submission.final_score is not None
                else submission.total_score
            )
            if score is not None:
                scores.append(float(score))
        elif submission.status in PENDING_STATUSES:
            pending += 1
        elif submission.status in FAILED_STATUSES:
            failed += 1
        else:
            # draft / not yet submitted by the student
            missing_rows.append({"student_id": student.pk, "name": name})
            continue
        submitted_rows.append(
            {
                "student_id": student.pk,
                "name": name,
                "submission_id": submission.pk,
                "status": submission.status,
                "status_label": submission.get_status_display(),
                "source": submission.source,
                "source_label": SOURCE_LABELS.get(
                    submission.source, submission.source.upper()
                ),
            }
        )

    # Students from other groups who nonetheless submitted this assignment are
    # reported rather than silently dropped.
    expected_ids = {student.pk for student in expected_students}
    for student_id, submission in by_student.items():
        if student_id in expected_ids:
            continue
        submitted_rows.append(
            {
                "student_id": student_id,
                "name": submission.student.get_full_name() or submission.student.email,
                "submission_id": submission.pk,
                "status": submission.status,
                "status_label": submission.get_status_display(),
                "source": submission.source,
                "source_label": SOURCE_LABELS.get(
                    submission.source, submission.source.upper()
                ),
                "outside_roster": True,
            }
        )

    return {
        "assignment_id": assignment.pk,
        "group_id": assignment.group_id,
        "group_name": assignment.group.name,
        "topic_id": assignment.topic_id,
        "topic_title": assignment.topic.title if assignment.topic_id else "",
        "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
        "is_active": assignment.is_active,
        "expected": len(expected_students),
        "graded": graded,
        "pending": pending,
        "failed": failed,
        "not_submitted": len(missing_rows),
        "average_ai_score": round(sum(scores) / len(scores), 2) if scores else None,
        "submitted": submitted_rows,
        "missing": missing_rows,
    }


def teacher_essay_overview(user, *, days: int = 30) -> dict:
    """Per-group essay statistics for every group the teacher owns."""
    since = timezone.now() - timedelta(days=days)
    rows = []
    for group in teacher_groups(user).order_by("name"):
        qs = _visible_submissions(group).filter(
            Q(submitted_at__gte=since)
            | Q(submitted_at__isnull=True, updated_at__gte=since)
        )
        stats = qs.aggregate(
            graded=Count("id", filter=Q(status__in=GRADED_STATUSES)),
            pending=Count("id", filter=Q(status__in=PENDING_STATUSES)),
            failed=Count("id", filter=Q(status__in=FAILED_STATUSES)),
            avg_ai=Avg("total_score", filter=Q(status__in=GRADED_STATUSES)),
        )
        rows.append(
            {
                "group_id": group.pk,
                "group_name": group.name,
                "roster_size": group.students.filter(is_active=True).count(),
                "graded": stats["graded"] or 0,
                "pending": stats["pending"] or 0,
                "failed": stats["failed"] or 0,
                "average_ai_score": (
                    round(float(stats["avg_ai"]), 2)
                    if stats["avg_ai"] is not None
                    else None
                ),
            }
        )
    return {"days": days, "groups": rows}


def create_assignment(
    *, topic, group, assigned_by, due_at=None, instructions: str = "", actor=None
) -> EssayAssignment:
    """Assign a topic to a group (idempotent per topic+group)."""
    assert_group_access(assigned_by, group)
    assignment, created = EssayAssignment.objects.get_or_create(
        topic=topic,
        group=group,
        defaults={
            "assigned_by": assigned_by,
            "due_at": due_at,
            "instructions": instructions,
        },
    )
    if not created and (due_at is not None or instructions):
        assignment.due_at = due_at if due_at is not None else assignment.due_at
        if instructions:
            assignment.instructions = instructions
        assignment.is_active = True
        assignment.save(
            update_fields=["due_at", "instructions", "is_active", "updated_at"]
        )
    return assignment


def overdue_assignments(user=None, *, as_of=None) -> list[dict]:
    """Active assignments past their due date that still have missing work.

    Powers the teacher reminder task; used with ``transaction.on_commit`` so a
    reminder never describes a state that rolled back.
    """
    as_of = as_of or timezone.now()
    qs = EssayAssignment.objects.filter(
        is_active=True,
        due_at__isnull=False,
        due_at__lt=as_of,
    ).select_related("group", "topic")
    if user is not None and not is_platform_admin(user):
        qs = qs.filter(group__teacher=user)
    out = []
    for assignment in qs:
        completion = assignment_completion(assignment)
        if completion["not_submitted"]:
            out.append(
                {
                    "assignment_id": assignment.pk,
                    "group_name": assignment.group.name,
                    "topic_title": completion["topic_title"],
                    "due_at": assignment.due_at.isoformat(),
                    "not_submitted": completion["not_submitted"],
                    "expected": completion["expected"],
                    "teacher_id": assignment.group.teacher_id,
                }
            )
    return out
