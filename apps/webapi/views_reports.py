"""Weekly academic report JSON API.

The website surfaces exactly what the Telegram message contains, from the same
persisted rows — a teacher reading the dashboard and a teacher reading the bot
message can never be looking at different numbers.

Authorization is queryset-level: a teacher's own groups only, and the tuition
block is stripped per reader by ``weekly_reports.delivery.visible_summary``, so
the financial section simply does not exist in a response to an unauthorized
reader rather than being hidden in the client.
"""
from __future__ import annotations

from datetime import datetime

from django.core.exceptions import ValidationError

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.access import is_platform_admin
from apps.accounts.models import ParentStudentLink
from apps.attendance.services import teacher_groups
from apps.weekly_reports import delivery, services
from apps.weekly_reports.models import (
    WeeklyGroupReport,
    WeeklyReportDelivery,
    WeeklyReportSettings,
    WeeklyStudentReport,
)

from .permissions import IsTeacherOrAdmin


def _report_payload(report: WeeklyGroupReport, user) -> dict:
    summary = delivery.visible_summary(report, user)
    return {
        "id": report.pk,
        "group_id": report.group_id,
        "group_name": report.group.name,
        "period_start": report.period_start.isoformat(),
        "period_end": report.period_end.isoformat(),
        "period_label": report.period_label,
        "version": report.version,
        "is_current": report.is_current,
        "status": report.status,
        "generated_at": report.generated_at.isoformat(),
        "generated_by": report.generated_by_id,
        "generation_reason": report.generation_reason,
        "text": delivery.group_report_text(
            report, include_finance=summary.get("finance_visible", False),
        ),
        "summary": summary,
    }


def _owns(user, group) -> bool:
    return is_platform_admin(user) or group.teacher_id == getattr(user, "pk", None)


@api_view(["GET", "POST"])
@permission_classes([IsTeacherOrAdmin])
def weekly_report_list_view(request):
    """Current weekly reports for the caller's groups (newest first)."""
    if request.method == "POST":
        return weekly_report_generate_view(request)
    qs = WeeklyGroupReport.objects.filter(
        group__in=teacher_groups(request.user), is_current=True,
    ).select_related("group", "generated_by")
    group_id = request.query_params.get("group_id")
    if group_id:
        qs = qs.filter(group_id=group_id)
    if request.query_params.get("include_history") == "1":
        # Owning a group is enough to see current reports, not a permanent
        # archive of superseded versions; history needs explicit audit access.
        if not is_platform_admin(request.user) and not request.user.has_perm(
            "weekly_reports.view_weeklygroupreport",
        ) and not request.user.has_perm("weekly_reports.change_weeklygroupreport"):
            return Response({"detail": "Hisobotlar tarixini ko'rish huquqi yo'q."}, status=403)
        qs = WeeklyGroupReport.objects.filter(group__in=teacher_groups(request.user))
    else:
        period_start = request.query_params.get("period_start")
        if period_start:
            qs = qs.filter(period_start__date=period_start)
    if not is_platform_admin(request.user):
        # Belt and braces: the queryset already scopes to the caller's groups.
        qs = qs.filter(group__teacher=request.user)
    limit = min(max(int(request.query_params.get("limit", 20) or 20), 1), 100)
    offset = max(int(request.query_params.get("offset", 0) or 0), 0)
    count = qs.distinct().count()
    rows = list(qs.distinct().order_by("-period_start", "-version")[offset:offset + limit])
    return Response({
        "count": count,
        "results": [_report_payload(report, request.user) for report in rows],
    })


@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def weekly_report_generate_view(request):
    """Generate a completed week only for groups the caller may access."""
    group_id = request.data.get("group_id")
    if not group_id:
        return Response({"detail": "Guruh ID talab qilinadi."}, status=400)
    group = teacher_groups(request.user).filter(pk=group_id).first()
    if group is None:
        return Response({"detail": "Guruh topilmadi."}, status=404)
    start_raw = request.data.get("period_start")
    end_raw = request.data.get("period_end")
    if not start_raw and not end_raw:
        start, end = services.previous_week_bounds()
    elif start_raw and end_raw:
        start, end = parse_datetime(str(start_raw)), parse_datetime(str(end_raw))
        if start is None or end is None:
            return Response({"detail": "Davr ISO-8601 formatida bo'lishi kerak."}, status=400)
        if timezone.is_naive(start):
            start = timezone.make_aware(start, services.reporting_timezone())
        if timezone.is_naive(end):
            end = timezone.make_aware(end, services.reporting_timezone())
    else:
        return Response({"detail": "Boshlanish va tugash sanasi birga berilishi kerak."}, status=400)

    report_id = request.data.get("report_id")
    reason = str(request.data.get("reason") or "").strip()
    try:
        if report_id is not None:
            prior = WeeklyGroupReport.objects.filter(
                pk=report_id, group=group, is_current=True,
            ).first()
            if prior is None:
                return Response({"detail": "Hisobot topilmadi."}, status=404)
            if len(reason) < 3:
                return Response({"detail": "Qayta tayyorlash sababini yozing (kamida 3 belgi)."}, status=400)
            report = services.regenerate(prior, actor=request.user, reason=reason)
        else:
            report = services.generate_group_report(
                group, start, end, actor=request.user,
            )
    except (ValueError, ValidationError) as exc:
        return Response({"detail": str(exc)}, status=400)
    return Response({"report": _report_payload(report, request.user)}, status=201)


@api_view(["GET"])
@permission_classes([IsTeacherOrAdmin])
def weekly_report_detail_view(request, report_id: int):
    report = WeeklyGroupReport.objects.filter(pk=report_id).select_related("group").first()
    if report is None or not _owns(request.user, report.group):
        # A group id the caller does not own is "not found", never "forbidden".
        return Response({"detail": "Hisobot topilmadi."}, status=404)
    payload = _report_payload(report, request.user)
    payload["deliveries"] = [
        {
            "recipient_id": row.recipient_id,
            "recipient_name": row.recipient.get_full_name() or row.recipient.email,
            "channel": row.channel,
            "status": row.status,
            "retry_count": row.retry_count,
            "last_error": row.last_error,
            "sent_at": row.sent_at.isoformat() if row.sent_at else None,
        }
        for row in report.deliveries.select_related("recipient").order_by("-created_at")
    ]
    payload["history"] = [
        {
            "id": older.pk,
            "version": older.version,
            "generated_at": older.generated_at.isoformat(),
            "reason": older.generation_reason,
        }
        for older in WeeklyGroupReport.objects.filter(
            group=report.group, period_start=report.period_start,
        ).order_by("-version")
    ]
    return Response(payload)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def weekly_student_report_detail_view(request, report_id: int):
    report = WeeklyStudentReport.objects.filter(pk=report_id).select_related("student").first()
    if report is None or not report.is_current:
        return Response({"detail": "Hisobot topilmadi."}, status=404)
    role = getattr(request.user, "role", None)
    allowed = is_platform_admin(request.user)
    if role == "parent":
        allowed = ParentStudentLink.objects.filter(
            parent=request.user, student_id=report.student_id, is_approved=True,
        ).exists()
    elif role == "teacher":
        allowed = report.student.student_groups.filter(teacher=request.user).exists()
    elif role == "student":
        allowed = report.student_id == request.user.pk
    if not allowed:
        return Response({"detail": "Hisobot topilmadi."}, status=404)
    return _weekly_student_report_detail_payload(report)


def _weekly_student_report_detail_payload(report):
    versions = WeeklyStudentReport.objects.filter(
        student_id=report.student_id, period_start=report.period_start,
    ).order_by("-version")
    return Response({
        "id": report.pk,
        "student_id": report.student_id,
        "student_name": report.summary.get("student_name", ""),
        "period_label": report.period_label,
        "period_start": report.period_start.isoformat(),
        "period_end": report.period_end.isoformat(),
        "version": report.version,
        "generated_at": report.generated_at.isoformat(),
        "summary": report.summary,
        "text": delivery.student_report_text(report),
        "history": list(versions.values("id", "version", "generated_at", "generation_reason")),
    })


@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def weekly_report_regenerate_view(request, report_id: int):
    """Explicit, versioned regeneration after a correction."""
    report = WeeklyGroupReport.objects.filter(pk=report_id).select_related("group").first()
    if report is None or not _owns(request.user, report.group):
        return Response({"detail": "Hisobot topilmadi."}, status=404)
    reason = str(request.data.get("reason") or "").strip()
    if len(reason) < 3:
        return Response(
            {"detail": "Qayta tayyorlash sababini yozing (kamida 3 belgi)."}, status=400,
        )
    if not is_platform_admin(request.user) and not request.user.has_perm(
        "weekly_reports.change_weeklygroupreport",
    ) and report.group.teacher_id != request.user.pk:
        return Response({"detail": "Hisobotni qayta tayyorlash huquqi yo'q."}, status=403)
    replacement = services.regenerate(report, actor=request.user, reason=reason)
    return Response(
        {"report": _report_payload(replacement, request.user), "superseded_id": report.pk},
        status=201,
    )


@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def weekly_student_report_regenerate_view(request, report_id: int):
    report = WeeklyStudentReport.objects.filter(pk=report_id).select_related("student").first()
    if report is None or not report.is_current:
        return Response({"detail": "Hisobot topilmadi."}, status=404)
    user = request.user
    if not is_platform_admin(user) and not user.has_perm(
        "weekly_reports.change_weeklystudentreport",
    ):
        return Response({"detail": "Hisobotni qayta tayyorlash huquqi yo'q."}, status=403)
    reason = str(request.data.get("reason") or "").strip()
    if len(reason) < 3:
        return Response({"detail": "Sabab kamida 3 belgidan iborat bo'lishi kerak."}, status=400)
    replacement = services.regenerate(report, actor=user, reason=reason)
    return Response({"report_id": replacement.pk, "version": replacement.version}, status=201)


@api_view(["POST"])
@permission_classes([IsTeacherOrAdmin])
def weekly_report_send_view(request, report_id: int):
    """Send the current report to its recipients again (dedup-keyed)."""
    report = WeeklyGroupReport.objects.filter(pk=report_id, is_current=True).select_related(
        "group",
    ).first()
    if report is None or not _owns(request.user, report.group):
        return Response({"detail": "Hisobot topilmadi."}, status=404)
    if not is_platform_admin(request.user) and not request.user.has_perm(
        "weekly_reports.change_weeklygroupreport",
    ) and report.group.teacher_id != request.user.pk:
        return Response({"detail": "Hisobotni yuborish huquqi yo'q."}, status=403)
    results = []
    sent = failed = skipped = 0
    for recipient in delivery.recipients_for_group(report.group):
        if not delivery.preference_allows(recipient, delivery.PREFERENCE_TEACHER_WEEKLY):
            skipped += 1
            continue
        row = delivery.deliver_group_report(report, recipient)
        attempted = bool(getattr(row, "attempted", False))
        sent += attempted and row.status == row.Status.SENT
        failed += attempted and row.status == row.Status.FAILED
        results.append({
            "recipient_id": recipient.pk, "status": row.status,
            "detail": row.last_error,
        })
    return Response({"sent": sent, "failed": failed, "skipped": skipped, "results": results})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_weekly_reports_view(request):
    """Own/approved-child reports or reports for the caller's teacher groups."""
    role = getattr(request.user, "role", None)
    if role == "teacher" or is_platform_admin(request.user):
        group_ids = teacher_groups(request.user).values_list("pk", flat=True)
        rows = WeeklyGroupReport.objects.filter(
            group_id__in=group_ids, is_current=True,
        ).select_related("group").order_by("-period_start")[:40]
        out = []
        for report in rows:
            out.append(_report_payload(report, request.user))
        return Response({"count": len(out), "results": out[:100]})

    student_ids = [request.user.pk]
    if role == "parent":
        student_ids += list(
            ParentStudentLink.objects.filter(
                parent=request.user, is_approved=True,
            ).values_list("student_id", flat=True)
        )
    reports = WeeklyStudentReport.objects.filter(
        student_id__in=student_ids, is_current=True,
    ).select_related("student").order_by("-period_start")[:20]
    return Response({
        "count": len(reports),
        "results": [
            {
                "id": report.pk,
                "student_id": report.student_id,
                "student_name": report.summary.get("student_name", ""),
                "period_label": report.period_label,
                "period_start": report.period_start.isoformat(),
                "period_end": report.period_end.isoformat(),
                "version": report.version,
                "generated_at": report.generated_at.isoformat(),
                "summary": report.summary,
                "text": delivery.student_report_text(report),
            }
            for report in reports
        ],
    })


@api_view(["GET", "PATCH", "PUT"])
@permission_classes([IsAuthenticated])
def report_schedule_view(request):
    """The administrator-configurable schedule, plus the next run instant."""
    user = request.user
    if request.method != "GET":
        if not is_platform_admin(user) and not user.has_perm(
            "weekly_reports.change_weeklyreportsettings",
        ):
            return Response({"detail": "Hisobot jadvalini o'zgartirish huquqi yo'q."}, status=403)
        config = WeeklyReportSettings.load()
        old = {
            "is_enabled": config.is_enabled,
            "send_weekday": config.send_weekday,
            "send_hour": config.send_hour,
            "send_minute": config.send_minute,
            "retry_failed_deliveries": config.retry_failed_deliveries,
            "max_delivery_attempts": config.max_delivery_attempts,
        }
        allowed = set(old) | {"timezone_name"}
        unknown = set(request.data) - allowed
        if unknown:
            return Response({"detail": "Noma'lum maydon: " + ", ".join(sorted(unknown))}, status=400)
        values = dict(old)
        values.update(request.data)
        timezone_name = request.data.get("timezone_name")
        if timezone_name is not None:
            try:
                from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
                ZoneInfo(str(timezone_name))
            except (ZoneInfoNotFoundError, ValueError):
                return Response({"detail": "Vaqt zonasi noto'g'ri."}, status=400)
        try:
            weekday, hour, minute, attempts = (
                int(values["send_weekday"]), int(values["send_hour"]),
                int(values["send_minute"]), int(values["max_delivery_attempts"]),
            )
            if not (0 <= weekday <= 6 and 0 <= hour <= 23 and 0 <= minute <= 59 and 1 <= attempts <= 20):
                raise ValueError
            if not isinstance(values["is_enabled"], bool) or not isinstance(values["retry_failed_deliveries"], bool):
                raise ValueError
        except (TypeError, ValueError):
            return Response({"detail": "Jadval maydonlari yaroqsiz."}, status=400)
        config.is_enabled = values["is_enabled"]
        config.send_weekday = weekday
        config.send_hour = hour
        config.send_minute = minute
        config.retry_failed_deliveries = values["retry_failed_deliveries"]
        config.max_delivery_attempts = attempts
        if timezone_name is not None:
            config.timezone_name = str(timezone_name)
        config.updated_by = user
        config.save()
        return Response({"status": "updated", "next_run_at": services.next_run_at().isoformat()})
    if is_platform_admin(user):
        config = WeeklyReportSettings.load()
        return Response({
            "is_enabled": config.is_enabled,
            "max_delivery_attempts": config.max_delivery_attempts,
            "send_weekday": config.send_weekday,
            "send_hour": config.send_hour,
            "send_minute": config.send_minute,
            "timezone": config.timezone_name,
            "retry_failed_deliveries": config.retry_failed_deliveries,
            "next_run_at": services.next_run_at().isoformat(),
            "my_preference": delivery.preference_allows(
                user, delivery.PREFERENCE_TEACHER_WEEKLY,
            ),
        })
    return Response({
        "is_enabled": True,
        "timezone": services.reporting_timezone_name(),
        "next_run_at": services.next_run_at().isoformat(),
        "my_preference": delivery.preference_allows(
            user, delivery.PREFERENCE_TEACHER_WEEKLY,
        ),
    })


@api_view(["GET", "POST"])
@permission_classes([IsTeacherOrAdmin])
def report_delivery_log_view(request):
    """Delivery audit for one report (dedup key, attempts, last error)."""
    if request.method == "POST":
        if not is_platform_admin(request.user) and not request.user.has_perm(
            "weekly_reports.change_weeklygroupreport",
        ):
            return Response({"detail": "Hisobot yuborishlarini qayta urinish huquqi yo'q."}, status=403)

        try:
            limit = min(max(int(request.data.get("limit", 100)), 1), 500)
        except (TypeError, ValueError):
            return Response({"detail": "limit noto'g'ri."}, status=400)
        report_id = request.data.get("report_id")
        if report_id is not None:
            report = WeeklyGroupReport.objects.filter(pk=report_id).select_related("group").first()
            if report is None or not _owns(request.user, report.group):
                return Response({"detail": "Hisobot topilmadi."}, status=404)
            rows = list(WeeklyReportDelivery.objects.filter(
                report=report, channel="telegram", status__in=("failed", "deferred"),
            ).select_related("recipient", "student_report", "report")[:limit])
            sent = failed = 0
            for prior in rows:
                target = prior.target
                if target is None:
                    continue
                if prior.report_id:
                    finance = delivery._may_see_finance(prior.recipient)
                    text = delivery.group_report_text(target, include_finance=finance)
                    buttons = delivery.report_buttons(target, include_finance=finance)
                else:
                    text = delivery.student_report_text(target)
                    buttons = None
                refreshed = delivery._deliver(
                    report=target, recipient=prior.recipient, text=text, buttons=buttons,
                    channel=prior.channel, dedup_key=prior.dedup_key,
                )
                attempted = bool(getattr(refreshed, "attempted", False))
                sent += bool(attempted and refreshed.status == WeeklyReportDelivery.Status.SENT)
                failed += bool(attempted and refreshed.status == WeeklyReportDelivery.Status.FAILED)
            return Response({"retried": len(rows), "sent": sent, "failed": failed})
        result = delivery.retry_failed_deliveries(limit=limit)
        return Response(result)
    report_id = request.query_params.get("report_id")
    qs = WeeklyReportDelivery.objects.select_related("recipient", "report")
    report = None
    if report_id:
        report = WeeklyGroupReport.objects.filter(pk=report_id).select_related("group").first()
        if report is None or not _owns(request.user, report.group):
            return Response({"detail": "Hisobot topilmadi."}, status=404)
        qs = qs.filter(report=report)
    elif not is_platform_admin(request.user):
        qs = qs.filter(report__group__teacher=request.user)
    limit = min(max(int(request.query_params.get("limit", 50) or 50), 1), 200)
    offset = max(int(request.query_params.get("offset", 0) or 0), 0)
    count = qs.count()
    rows = list(qs.order_by("-created_at")[offset:offset + limit])
    return Response({
        "count": count,
        "results": [
            {
                "id": row.pk,
                "report_id": row.report_id,
                "student_report_id": row.student_report_id,
                "recipient_id": row.recipient_id,
                "channel": row.channel,
                "status": row.status,
                "retry_count": row.retry_count,
                "dedup_key": row.dedup_key,
                "last_error": row.last_error,
                "sent_at": row.sent_at.isoformat() if row.sent_at else None,
            }
            for row in rows
        ],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def report_period_preview_view(request):
    """What the next scheduled run would cover (read-only, no side effects).

    Any authenticated user may ask; the answer contains only period boundaries
    and the caller's own report preference.
    """
    now_raw = request.query_params.get("now")
    now: datetime | None = parse_datetime(now_raw) if now_raw else None
    start, end = services.previous_week_bounds(now)
    return Response({
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "period_label": services.period_label(start, end),
        "is_complete": services.is_period_complete(end, now=now),
        "next_run_at": services.next_run_at(now).isoformat(),
        "timezone": services.reporting_timezone_name(),
    })
