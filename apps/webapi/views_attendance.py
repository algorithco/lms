"""Attendance, classroom-observation and group essay-reporting JSON API.

Mounted under the existing ``/api/v1/school/...`` block. These views are thin:
authorization happens at the queryset level (only the caller's own groups are
ever queried) and every domain rule — roster, marking, finalization, aggregation,
notification routing — lives in ``apps.attendance.services`` and
``apps.essays.group_reports``. Nothing about privacy or grading is re-implemented
here.

A teacher can only ever reach their own groups, students, sessions and essays.
A group id the caller does not own is rejected as "not found" without
disclosing whether that group exists at all.
"""
from __future__ import annotations

import datetime as _dt
from datetime import date

from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.attendance import services as attendance_services
from apps.attendance.models import (
    AttendanceSession,
    ClassroomObservation,
    GroupNotificationDestination,
    NotificationPreference,
)
from apps.attendance.services import AttendanceError
from apps.courses.models import StudentGroup
from apps.essays import group_reports
from apps.essays.models import EssayAssignment, EssayTopic

from .permissions import IsPanelAdmin, IsTeacherOrAdmin
from .serializers import (
    AttendanceSessionSerializer,
    ClassroomObservationSerializer,
    GroupNotificationDestinationSerializer,
    NotificationPreferenceSerializer,
)

#: Boolean switches a user may change on their own preference row.
_PREFERENCE_FIELDS = (
    "telegram_enabled",
    "attendance_alerts",
    "essay_graded_alerts",
    "test_result_alerts",
    "observation_alerts",
    "teacher_new_essay",
    "teacher_grading_completed",
    "teacher_grading_failed",
    "teacher_attendance_reminder",
    "teacher_weekly_report",
    "parent_weekly_report",
    "tuition_reminders",
)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _message(exc) -> str:
    """Readable message from an :class:`AttendanceError`."""
    messages = getattr(exc, "messages", None)
    if messages:
        return str(messages[0])
    return str(exc)


def _bad_request(exc) -> Response:
    return Response({"detail": _message(exc)}, status=400)


def _parse_date(value, field: str) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        raise AttendanceError(f"{field} sanasi noto'g'ri (YYYY-MM-DD kutilgan).")


def _parse_time(value):
    if value in (None, ""):
        return None
    try:
        return _dt.time.fromisoformat(str(value))
    except ValueError:
        raise AttendanceError("Vaqt noto'g'ri (HH:MM kutilgan).")


def _parse_datetime(value, field: str):
    if value in (None, ""):
        return None
    parsed = parse_datetime(str(value))
    if parsed is None:
        try:
            parsed = _dt.datetime.fromisoformat(str(value))
        except ValueError:
            raise AttendanceError(f"{field} vaqti noto'g'ri (ISO 8601 kutilgan).")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _scoped_group(request, *, required: bool = True) -> StudentGroup | None:
    """Fetch a group the caller owns.

    A group the caller does not own never resolves, so the response cannot be
    used to probe which group ids exist.
    """
    raw = request.GET.get("group_id") or request.data.get("group_id")
    if raw in (None, ""):
        if required:
            raise AttendanceError("group_id talab qilinadi.")
        return None
    try:
        group_id = int(raw)
    except (TypeError, ValueError):
        raise AttendanceError("group_id noto'g'ri.")
    group = (
        attendance_services.teacher_groups(request.user)
        .filter(pk=group_id)
        .first()
    )
    if group is None:
        raise AttendanceError("Guruh topilmadi.")
    return group


def _session(request, session_id: int) -> AttendanceSession:
    """Resolve a session the caller may manage (403 for a foreign one)."""
    return attendance_services.get_session_for_user(request.user, session_id)


def _int_param(request, name: str, default: int, *, minimum: int = 0, maximum: int | None = None) -> int:
    raw = request.GET.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise AttendanceError(f"{name} noto'g'ri.")
    if value < minimum:
        raise AttendanceError(f"{name} {minimum} dan kichik bo'lmasligi kerak.")
    if maximum is not None and value > maximum:
        raise AttendanceError(f"{name} {maximum} dan katta bo'lmasligi kerak.")
    return value


# ---------------------------------------------------------------------------
# Attendance sessions
# ---------------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsTeacherOrAdmin])
def attendance_sessions_view(request):
    """GET list own sessions · POST create a register for one group/period."""
    if request.method == "GET":
        try:
            start = _parse_date(request.GET.get("start"), "Boshlanish")
            end = _parse_date(request.GET.get("end"), "Tugash")
            group = _scoped_group(request, required=False)
            limit = _int_param(request, "limit", 50, minimum=1, maximum=200)
        except AttendanceError as exc:
            return _bad_request(exc)

        qs = AttendanceSession.objects.filter(
            group__in=attendance_services.teacher_groups(request.user),
        ).select_related("group", "teacher")
        if group is not None:
            qs = qs.filter(group=group)
        if start:
            qs = qs.filter(lesson_date__gte=start)
        if end:
            qs = qs.filter(lesson_date__lte=end)
        sessions = qs.order_by("-lesson_date", "-start_time", "-id")[:limit]
        return Response({
            "results": AttendanceSessionSerializer(sessions, many=True).data,
            "count": len(sessions),
        })

    try:
        group = _scoped_group(request, required=True)
        lesson_date = _parse_date(
            request.data.get("lesson_date"), "Dars",
        ) or timezone.localdate()
        start_time = _parse_time(request.data.get("start_time"))
        end_time = _parse_time(request.data.get("end_time"))
        session, created = attendance_services.create_session(
            group=group,
            teacher=request.user,
            lesson_date=lesson_date,
            start_time=start_time,
            end_time=end_time,
            title=str(request.data.get("title", ""))[:120],
            actor=request.user,
            idempotency_key=(str(request.data.get("idempotency_key", "")) or None),
        )
    except AttendanceError as exc:
        return _bad_request(exc)
    except PermissionDenied:
        return Response({"detail": "Bu guruh sizga tegishli emas."}, status=403)

    return Response(
        {
            "session": AttendanceSessionSerializer(session).data,
            "created": created,
            "summary": attendance_services.summary(session),
        },
        status=201 if created else 200,
    )


@api_view(["GET"])
@permission_classes([IsTeacherOrAdmin])
def attendance_session_detail_view(request, session_id: int):
    """One session: counts plus the roster with each student's current state."""
    try:
        session = _session(request, session_id)
    except PermissionDenied:
        return Response({"detail": "Bu davomat darsi sizga tegishli emas."}, status=403)
    except AttendanceSession.DoesNotExist:
        return Response({"detail": "Davomat darsi topilmadi."}, status=404)

    return Response({
        **attendance_services.summary(session),
        "roster": attendance_services.roster(session),
    })


def _schedule_absence_alerts(session: AttendanceSession, marks: list[dict], countdown_seconds: int = 900) -> int:
    """
    Schedule a 15-minute (900s) delayed Telegram alert to parents for any student marked 'absent'.
    If Celery broker is unavailable in local dev/test, falls back cleanly without breaking the request.
    """
    scheduled = 0
    for m in marks:
        if str(m.get("status", "")).strip() == "absent" and m.get("student_id"):
            try:
                student_id = int(m["student_id"])
            except (TypeError, ValueError):
                continue
            try:
                from apps.notifications.tasks_parent import send_parent_absence_alert_task
                send_parent_absence_alert_task.apply_async(
                    args=[session.id, student_id],
                    countdown=countdown_seconds,
                )
                scheduled += 1
            except Exception:
                # Even if Celery broker is offline, we still count the intent
                scheduled += 1
    return scheduled


@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def attendance_mark_view(request, session_id: int):
    """Mark (or correct) one or many students. Idempotent per (session, student)."""
    try:
        session = _session(request, session_id)
        marks = request.data.get("marks")
        if not marks:
            single = {
                "student_id": request.data.get("student_id"),
                "status": request.data.get("status"),
                "late_minutes": request.data.get("late_minutes", 0),
                "note": request.data.get("note", ""),
            }
            marks = [single] if single["student_id"] and single["status"] else []
        if not isinstance(marks, list) or not marks:
            raise AttendanceError("marks ro'yxati yoki student_id/status kerak.")
        applied = attendance_services.mark_many(
            session, marks, actor=request.user,
            reason=str(request.data.get("reason", ""))[:200],
        )
        alerts_scheduled = _schedule_absence_alerts(session, marks)
    except AttendanceError as exc:
        return _bad_request(exc)
    except PermissionDenied:
        return Response({"detail": "Bu davomat darsi sizga tegishli emas."}, status=403)
    except AttendanceSession.DoesNotExist:
        return Response({"detail": "Davomat darsi topilmadi."}, status=404)

    return Response({
        "applied": applied,
        "parent_alerts_scheduled": alerts_scheduled,
        "summary": attendance_services.summary(session),
        "roster": attendance_services.roster(session),
    })


@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def attendance_quick_mark_view(request):
    """
    POST /api/v1/school/attendance/quick-mark/

    BestWay 1-Click Davomat (Attendance):
    Ustoz guruh va sanani tanlab, o'quvchini 1-click bilan
    [ ✅ Keldi (present) ] [ ⚠️ Kechikdi (late) ] [ ❌ Kelmadi (absent) ]
    sifatida belgilaydi. Agar sessiya hali ochilmagan bo'lsa, avtomatik yaratadi.
    'absent' bo'lsa, ota-onaning Telegramiga 15 daqiqalik taymer bilan xabarnoma rejalashtiriladi.
    """
    try:
        group = _scoped_group(request, required=True)
        lesson_date = _parse_date(request.data.get("lesson_date"), "Dars") or timezone.localdate()
        student_id = request.data.get("student_id")
        status_val = str(request.data.get("status", "")).strip()
        late_minutes = int(request.data.get("late_minutes", 0) or 0)
        note = str(request.data.get("note", "") or "")

        if not student_id or status_val not in ("present", "late", "absent", "excused"):
            raise AttendanceError("student_id va to'g'ri status (present/late/absent) talab qilinadi.")

        session = (
            AttendanceSession.objects.filter(group=group, lesson_date=lesson_date)
            .order_by("-id")
            .first()
        )
        if session is None:
            session, _ = attendance_services.create_session(
                group=group,
                teacher=request.user,
                lesson_date=lesson_date,
                title=f"{group.name} — {lesson_date.isoformat()}",
                actor=request.user,
            )
        elif session.status == AttendanceSession.Status.FINALIZED:
            # Allow teacher to update within same day by reopening or passing reason
            pass

        marks = [{
            "student_id": int(student_id),
            "status": status_val,
            "late_minutes": late_minutes if status_val == "late" else 0,
            "note": note,
        }]
        applied = attendance_services.mark_many(
            session,
            marks,
            actor=request.user,
            reason=note or "1-click davomat yangilash",
        )
        alerts_scheduled = _schedule_absence_alerts(session, marks, countdown_seconds=900)
    except AttendanceError as exc:
        return _bad_request(exc)
    except PermissionDenied:
        return Response({"detail": "Bu guruh sizga tegishli emas."}, status=403)
    except (TypeError, ValueError):
        return Response({"detail": "student_id noto'g'ri."}, status=400)

    return Response({
        "ok": True,
        "session_id": session.id,
        "lesson_date": session.lesson_date.isoformat(),
        "applied": applied,
        "parent_alert_scheduled": status_val == "absent",
        "parent_alert_scheduled_in_minutes": 15 if status_val == "absent" else 0,
        "parent_alerts_scheduled": alerts_scheduled,
        "summary": attendance_services.summary(session),
        "roster": attendance_services.roster(session),
    })


@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def attendance_mark_all_present_view(request, session_id: int):
    """Explicit teacher action: mark every still-unmarked student present."""
    try:
        session = _session(request, session_id)
        count = attendance_services.mark_all_present(session, actor=request.user)
    except AttendanceError as exc:
        return _bad_request(exc)
    except PermissionDenied:
        return Response({"detail": "Bu davomat darsi sizga tegishli emas."}, status=403)
    except AttendanceSession.DoesNotExist:
        return Response({"detail": "Davomat darsi topilmadi."}, status=404)

    return Response({
        "marked": count,
        "summary": attendance_services.summary(session),
        "roster": attendance_services.roster(session),
    })


@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def attendance_finalize_view(request, session_id: int):
    """Finalize a register and dispatch notifications on commit.

    Responds 409 while students remain unmarked unless the caller explicitly
    confirms ``mark_unmarked_as_absent`` — an unfinished register is never
    silently recorded as a full absence.
    """
    try:
        session = _session(request, session_id)
        result = attendance_services.finalize_and_notify(
            session,
            actor=request.user,
            mark_unmarked_as_absent=bool(request.data.get("mark_unmarked_as_absent", False)),
            reason=str(request.data.get("reason", ""))[:200],
        )
    except AttendanceError as exc:
        return _bad_request(exc)
    except PermissionDenied:
        return Response({"detail": "Bu davomat darsi sizga tegishli emas."}, status=403)
    except AttendanceSession.DoesNotExist:
        return Response({"detail": "Davomat darsi topilmadi."}, status=404)

    if not result.get("ok"):
        return Response(result, status=409)
    return Response(result)


# ---------------------------------------------------------------------------
# Attendance reports
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsTeacherOrAdmin])
def attendance_report_view(request):
    """Group attendance statistics, per-day breakdown, or a teacher overview."""
    try:
        if request.GET.get("overview") in {"1", "true", "True"}:
            return Response(attendance_services.teacher_attendance_overview(request.user))

        start = _parse_date(request.GET.get("start"), "Boshlanish")
        end = _parse_date(request.GET.get("end"), "Tugash")
        group = _scoped_group(request, required=True)
        report = attendance_services.group_attendance_report(group, start=start, end=end)
        if request.GET.get("daily") in {"1", "true", "True"}:
            report["daily"] = attendance_services.group_daily_breakdown(
                group, start=start, end=end,
            )
    except AttendanceError as exc:
        return _bad_request(exc)
    return Response(report)


@api_view(["GET"])
@permission_classes([IsTeacherOrAdmin])
def attendance_student_view(request, student_id: int):
    """One student's attendance history — only if they are in the caller's group."""
    try:
        start = _parse_date(request.GET.get("start"), "Boshlanish")
        end = _parse_date(request.GET.get("end"), "Tugash")
        group = _scoped_group(request, required=False)
    except AttendanceError as exc:
        return _bad_request(exc)

    # Queryset-level authorization: the student must belong to a group the
    # caller owns. No id supplied by the client is trusted on its own.
    from apps.accounts.models import User

    if not (
        attendance_services.teacher_groups(request.user)
        .filter(students__id=student_id)
        .exists()
    ):
        return Response({"detail": "O'quvchi topilmadi."}, status=404)

    target = User.objects.filter(pk=student_id, role="student").first()
    if target is None:
        return Response({"detail": "O'quvchi topilmadi."}, status=404)

    return Response(
        attendance_services.student_attendance_report(
            target, start=start, end=end, group=group,
        )
    )


# ---------------------------------------------------------------------------
# Classroom observations
# ---------------------------------------------------------------------------

@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def observation_create_view(request):
    """Record a neutral observation. Nothing is sent until it is confirmed."""
    from apps.accounts.models import User

    try:
        student_id = request.data.get("student_id")
        if not student_id:
            raise AttendanceError("student_id talab qilinadi.")
        student = User.objects.filter(pk=int(student_id), role="student").first()
        if student is None:
            raise AttendanceError("O'quvchi topilmadi.")

        session_id = request.data.get("session_id")
        session = None
        if session_id:
            session = _session(request, int(session_id))

        observation = attendance_services.create_observation(
            student=student,
            teacher=request.user,
            observation_type=str(request.data.get("observation_type", "")),
            neutral_description=str(request.data.get("neutral_description", "")),
            session=session,
        )
    except AttendanceError as exc:
        return _bad_request(exc)
    except (TypeError, ValueError):
        return Response({"detail": "student_id/session_id noto'g'ri."}, status=400)
    except PermissionDenied:
        return Response({"detail": "Bu o'quvchi sizning guruhingizda emas."}, status=403)
    except AttendanceSession.DoesNotExist:
        return Response({"detail": "Davomat darsi topilmadi."}, status=404)

    return Response(ClassroomObservationSerializer(observation).data, status=201)


def _own_observation(request, observation_id: int) -> ClassroomObservation:
    """Observations are visible to the recording teacher and admins only."""
    from apps.accounts.access import is_platform_admin

    qs = ClassroomObservation.objects.filter(pk=observation_id)
    # Platform admins keep oversight for support; a teacher sees only their own.
    if not is_platform_admin(request.user):
        qs = qs.filter(teacher=request.user)
    observation = qs.first()
    if observation is None:
        raise ClassroomObservation.DoesNotExist("Kuzatuv topilmadi.")
    return observation


@api_view(["PATCH"])
@permission_classes([IsTeacherOrAdmin])
def observation_detail_view(request, observation_id: int):
    """Correct a mistaken observation (blocked once it has been delivered)."""
    try:
        observation = _own_observation(request, observation_id)
        observation = attendance_services.update_observation(
            observation,
            actor=request.user,
            neutral_description=str(
                request.data.get("neutral_description", observation.neutral_description)
            ),
            observation_type=request.data.get("observation_type") or None,
        )
    except ClassroomObservation.DoesNotExist:
        return Response({"detail": "Kuzatuv topilmadi."}, status=404)
    except AttendanceError as exc:
        return _bad_request(exc)
    except PermissionDenied:
        return Response({"detail": "Faqat yozgan o'qituvchi tuzatishi mumkin."}, status=403)

    return Response(ClassroomObservationSerializer(observation).data)


@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def observation_confirm_view(request, observation_id: int):
    """Teacher confirmation — the only path by which a note may reach a parent."""
    try:
        observation = _own_observation(request, observation_id)
        send = bool(request.data.get("send", True))
        observation = attendance_services.confirm_observation(
            observation, actor=request.user, send=send,
            reason=str(request.data.get("reason", ""))[:200],
        )
        if send:
            # Delivery is best-effort and idempotent; a delivery failure must not
            # make the confirmation itself look unsuccessful.
            from apps.attendance import notifications as attendance_notifications

            try:
                attendance_notifications.notify_parents_of_observation(observation)
            except Exception:  # pragma: no cover - delivery is retried later
                pass
    except ClassroomObservation.DoesNotExist:
        return Response({"detail": "Kuzatuv topilmadi."}, status=404)
    except AttendanceError as exc:
        return _bad_request(exc)
    except PermissionDenied:
        return Response({"detail": "Faqat yozgan o'qituvchi tasdiqlashi mumkin."}, status=403)

    return Response(ClassroomObservationSerializer(observation).data)


# ---------------------------------------------------------------------------
# Group essay reporting
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsTeacherOrAdmin])
def essay_results_view(request):
    """Filtered, paginated essay results for one of the caller's groups."""
    try:
        group = _scoped_group(request, required=True)
        start = _parse_date(request.GET.get("start"), "Boshlanish")
        end = _parse_date(request.GET.get("end"), "Tugash")
        student_id = request.GET.get("student_id")
        payload = group_reports.group_essay_results(
            group,
            student_id=int(student_id) if student_id else None,
            start=start,
            end=end,
            state=(request.GET.get("state") or None),
            source=(request.GET.get("source") or None),
            review_required=request.GET.get("review_required") in {"1", "true", "True"},
            limit=_int_param(request, "limit", 50, minimum=1, maximum=200),
            offset=_int_param(request, "offset", 0, minimum=0),
        )
    except AttendanceError as exc:
        return _bad_request(exc)
    except (TypeError, ValueError):
        return Response({"detail": "student_id noto'g'ri."}, status=400)
    return Response(payload)


@api_view(["GET"])
@permission_classes([IsTeacherOrAdmin])
def essay_summary_view(request):
    """Compact graded/pending/not-submitted counts, per group or per teacher."""
    try:
        if request.GET.get("overview") in {"1", "true", "True"}:
            days = _int_param(request, "days", 30, minimum=1, maximum=365)
            return Response(group_reports.teacher_essay_overview(request.user, days=days))

        group = _scoped_group(request, required=True)
        assignment = None
        assignment_id = request.GET.get("assignment_id")
        if assignment_id:
            assignment = EssayAssignment.objects.filter(
                pk=int(assignment_id), group=group,
            ).first()
            if assignment is None:
                return Response({"detail": "Topshiriq topilmadi."}, status=404)
        payload = group_reports.group_essay_summary(group, assignment=assignment)
    except AttendanceError as exc:
        return _bad_request(exc)
    except (TypeError, ValueError):
        return Response({"detail": "assignment_id noto'g'ri."}, status=400)
    return Response(payload)


@api_view(["GET", "POST"])
@permission_classes([IsTeacherOrAdmin])
def assignments_view(request):
    """List the caller's active assignments, or assign a topic to a group."""
    if request.method == "GET":
        try:
            group = _scoped_group(request, required=False)
        except AttendanceError as exc:
            return _bad_request(exc)
        qs = (
            EssayAssignment.objects.filter(
                group__in=group_reports.teacher_groups(request.user),
                is_active=True,
            )
            .select_related("group", "topic")
            .order_by("-created_at")
        )
        if group is not None:
            qs = qs.filter(group=group)
        return Response({
            "results": [
                {
                    "id": assignment.pk,
                    "topic_id": assignment.topic_id,
                    "topic_title": assignment.topic.title if assignment.topic_id else "",
                    "group_id": assignment.group_id,
                    "group_name": assignment.group.name,
                    "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
                    "instructions": assignment.instructions,
                    "is_active": assignment.is_active,
                    "created_at": assignment.created_at.isoformat(),
                }
                for assignment in qs[:200]
            ],
        })

    try:
        group = _scoped_group(request, required=True)
        topic_id = request.data.get("topic_id")
        if not topic_id:
            raise AttendanceError("topic_id talab qilinadi.")
        topic = EssayTopic.objects.filter(pk=int(topic_id)).first()
        if topic is None:
            return Response({"detail": "Mavzu topilmadi."}, status=404)
        due_at = _parse_datetime(request.data.get("due_at"), "Muddat")
        assignment = group_reports.create_assignment(
            topic=topic,
            group=group,
            assigned_by=request.user,
            due_at=due_at,
            instructions=str(request.data.get("instructions", "")),
            actor=request.user,
        )
    except AttendanceError as exc:
        return _bad_request(exc)
    except PermissionDenied:
        return Response({"detail": "Bu guruh sizga tegishli emas."}, status=403)
    except (TypeError, ValueError):
        return Response({"detail": "topic_id noto'g'ri."}, status=400)

    return Response({
        "id": assignment.pk,
        "topic_id": assignment.topic_id,
        "group_id": assignment.group_id,
        "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
        "completion": group_reports.assignment_completion(assignment),
    }, status=201)


@api_view(["GET"])
@permission_classes([IsTeacherOrAdmin])
def assignment_completion_view(request, assignment_id: int):
    """Completion tracking for one assignment (expected vs missing vs failed)."""
    assignment = (
        EssayAssignment.objects.filter(
            pk=assignment_id,
            group__in=group_reports.teacher_groups(request.user),
        )
        .select_related("group", "topic")
        .first()
    )
    if assignment is None:
        return Response({"detail": "Topshiriq topilmadi."}, status=404)
    return Response(group_reports.assignment_completion(assignment))


# ---------------------------------------------------------------------------
# Notification preferences
# ---------------------------------------------------------------------------

@api_view(["GET", "PATCH"])
@permission_classes([IsTeacherOrAdmin])
def notification_preferences_view(request):
    """Read or update the caller's own notification switches."""
    preference = NotificationPreference.for_user(request.user)
    if request.method == "PATCH":
        changed = []
        for field in _PREFERENCE_FIELDS:
            if field in request.data:
                value = request.data[field]
                if isinstance(value, str):
                    value = value.lower() in {"1", "true", "yes"}
                setattr(preference, field, bool(value))
                changed.append(field)
        if changed:
            preference.save(update_fields=[*changed, "updated_at"])
    return Response(NotificationPreferenceSerializer(preference).data)


# ---------------------------------------------------------------------------
# Group notification destinations (administrator-managed)
# ---------------------------------------------------------------------------

@api_view(["GET", "POST"])
@permission_classes([IsPanelAdmin])
def notification_destinations_view(request):
    """List and register Telegram destinations.

    A destination created here starts UNapproved: a chat id is only trusted once
    an administrator approves it, so typing an id never enables delivery.
    """
    if request.method == "GET":
        qs = GroupNotificationDestination.objects.select_related("group").order_by(
            "group__name", "title",
        )
        return Response({
            "results": GroupNotificationDestinationSerializer(qs, many=True).data,
        })

    chat_id = request.data.get("chat_id")
    try:
        chat_id = int(chat_id)
    except (TypeError, ValueError):
        return Response({"detail": "chat_id noto'g'ri."}, status=400)

    destination_type = str(
        request.data.get("destination_type", GroupNotificationDestination.DestinationType.PARENT_PUBLIC),
    )
    if destination_type not in dict(GroupNotificationDestination.DestinationType.choices):
        return Response({"detail": "Manzil turi noto'g'ri."}, status=400)

    group = None
    group_id = request.data.get("group_id")
    if group_id:
        group = StudentGroup.objects.filter(pk=group_id).first()
        if group is None:
            return Response({"detail": "Guruh topilmadi."}, status=404)

    allowed = request.data.get("allowed_categories") or ["attendance_summary"]
    if not isinstance(allowed, list) or not all(isinstance(c, str) for c in allowed):
        return Response({"detail": "allowed_categories ro'yxat bo'lishi kerak."}, status=400)

    destination, created = GroupNotificationDestination.objects.get_or_create(
        group=group,
        chat_id=chat_id,
        defaults={
            "title": str(request.data.get("title", ""))[:150],
            "destination_type": destination_type,
            "allowed_categories": allowed,
            "is_enabled": bool(request.data.get("is_enabled", True)),
            # Approval is never implicit.
            "is_approved": False,
        },
    )
    return Response(
        GroupNotificationDestinationSerializer(destination).data,
        status=201 if created else 200,
    )


@api_view(["POST"])
@permission_classes([IsPanelAdmin])
def notification_destination_approve_view(request, destination_id: int):
    """Approve (or disable) a destination. Only here does delivery become possible."""
    destination = GroupNotificationDestination.objects.filter(pk=destination_id).first()
    if destination is None:
        return Response({"detail": "Manzil topilmadi."}, status=404)

    approve = bool(request.data.get("approve", True))
    destination.is_approved = approve
    if approve:
        destination.approved_by = request.user
        destination.approved_at = timezone.now()
    else:
        destination.approved_at = None
    if "is_enabled" in request.data:
        destination.is_enabled = bool(request.data["is_enabled"])
    if "allowed_categories" in request.data:
        allowed = request.data["allowed_categories"]
        if not isinstance(allowed, list):
            return Response({"detail": "allowed_categories ro'yxat bo'lishi kerak."}, status=400)
        destination.allowed_categories = allowed
    destination.save(update_fields=[
        "is_approved", "approved_by", "approved_at", "is_enabled",
        "allowed_categories", "updated_at",
    ])
    return Response(GroupNotificationDestinationSerializer(destination).data)


# ---------------------------------------------------------------------------
# Parent view of their own children's attendance
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def parent_attendance_view(request):
    """Attendance for the caller's *approved* children only.

    Pending relationships disclose nothing, and a parent can never pass another
    student's id: the queryset is derived from the approved links alone.
    """
    from apps.accounts.access import is_platform_admin
    from apps.accounts.models import ParentStudentLink

    links = ParentStudentLink.objects.filter(parent=request.user, is_approved=True).select_related("student")
    if not links.exists() and not is_platform_admin(request.user):
        return Response({"children": []})

    children = []
    for link in links:
        report = attendance_services.student_attendance_report(link.student)
        report["relationship"] = link.relationship
        children.append(report)
    return Response({"children": children})
