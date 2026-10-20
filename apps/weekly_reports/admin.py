"""Admin console for automated weekly reports.

Conventions follow ``apps.attendance.admin``: every mutating action (regenerate,
retry, generate now) delegates to ``services``/``delivery`` so the admin never
reimplements domain logic, and gating reuses the project's shared
``has_platform_permission`` policy.
"""

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from apps.accounts.access import has_platform_permission

from . import delivery, services
from .models import (
    WeeklyGroupReport,
    WeeklyReportDelivery,
    WeeklyReportSettings,
    WeeklyStudentReport,
)


def can_manage_reports(user) -> bool:
    return has_platform_permission(user, "weekly_reports.change_weeklygroupreport")


def can_view_reports(user) -> bool:
    return has_platform_permission(user, "weekly_reports.view_weeklygroupreport")


@admin.register(WeeklyReportSettings)
class WeeklyReportSettingsAdmin(admin.ModelAdmin):
    """The schedule. One row, edited in place."""

    list_display = (
        "is_enabled",
        "send_weekday",
        "send_hour",
        "send_minute",
        "timezone_name",
        "next_run_display",
        "retry_failed_deliveries",
    )
    readonly_fields = ("updated_at", "updated_by")

    def has_add_permission(self, request) -> bool:
        # Singleton: the row is created on first read, never added by hand.
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def has_module_permission(self, request) -> bool:
        return can_manage_reports(request.user)

    def has_view_permission(self, request, obj=None) -> bool:
        return can_view_reports(request.user)

    def has_change_permission(self, request, obj=None) -> bool:
        return can_manage_reports(request.user)

    def save_model(self, request, obj, form, change) -> None:
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    @admin.display(description="Keyingi yuborish")
    def next_run_display(self, obj):
        try:
            return timezone.localtime(services.next_run_at()).strftime("%Y-%m-%d %H:%M")
        except Exception:  # pragma: no cover - defensive
            return "—"


@admin.register(WeeklyGroupReport)
class WeeklyGroupReportAdmin(admin.ModelAdmin):
    """Versioned, read-only history of what was reported."""

    list_display = (
        "group",
        "period_label",
        "version",
        "is_current",
        "status",
        "generated_at",
        "attendance_display",
        "grades_display",
    )
    list_filter = ("is_current", "status", "group")
    search_fields = ("group__name", "period_label")
    date_hierarchy = "period_start"
    readonly_fields = (
        "group",
        "period_start",
        "period_end",
        "period_label",
        "version",
        "is_current",
        "supersedes",
        "generation_reason",
        "status",
        "summary",
        "generated_at",
        "generated_by",
    )
    actions = ("regenerate_selected", "send_selected")

    def has_add_permission(self, request) -> bool:
        # A report is generated from real data, never typed in.
        return False

    def has_module_permission(self, request) -> bool:
        return can_manage_reports(request.user)

    def has_view_permission(self, request, obj=None) -> bool:
        return can_view_reports(request.user)

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(description="Davomat")
    def attendance_display(self, obj):
        attendance = (obj.summary or {}).get("attendance") or {}
        return f"{attendance.get('attendance_percentage', '—')}%"

    @admin.display(description="Esse / test")
    def grades_display(self, obj):
        summary = obj.summary or {}
        essays = summary.get("essays") or {}
        tests = summary.get("tests") or {}
        return f"{essays.get('graded', 0)} / {tests.get('completed_attempts', 0)}"

    @admin.action(description="Tanlangan hisobotlarni qayta tayyorlash (yangi versiya)")
    def regenerate_selected(self, request, queryset):
        made = 0
        for report in queryset:
            services.regenerate(
                report,
                actor=request.user,
                reason="Admin panel orqali qayta tayyorlandi",
            )
            made += 1
        self.message_user(
            request,
            f"{made} ta hisobot yangi versiya bilan qayta tayyorlandi.",
            messages.SUCCESS,
        )

    @admin.action(description="Tanlangan hisobotlarni qabul qiluvchilarga yuborish")
    def send_selected(self, request, queryset):
        sent = failed = 0
        for report in queryset.filter(is_current=True):
            for recipient in delivery.recipients_for_group(report.group):
                if not delivery.preference_allows(
                    recipient, delivery.PREFERENCE_TEACHER_WEEKLY
                ):
                    continue
                result = delivery.deliver_group_report(report, recipient)
                sent += result.status == result.Status.SENT
                failed += result.status == result.Status.FAILED
        self.message_user(
            request,
            f"Yuborildi: {sent}, xatolik: {failed}.",
            messages.SUCCESS if not failed else messages.WARNING,
        )


@admin.register(WeeklyStudentReport)
class WeeklyStudentReportAdmin(admin.ModelAdmin):
    list_display = ("student", "period_label", "version", "is_current", "generated_at")
    list_filter = ("is_current",)
    search_fields = ("student__email", "student__first_name", "period_label")
    readonly_fields = (
        "student",
        "period_start",
        "period_end",
        "period_label",
        "version",
        "is_current",
        "supersedes",
        "generation_reason",
        "status",
        "summary",
        "generated_at",
        "generated_by",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_module_permission(self, request) -> bool:
        return can_manage_reports(request.user)

    def has_view_permission(self, request, obj=None) -> bool:
        return can_view_reports(request.user)

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(WeeklyReportDelivery)
class WeeklyReportDeliveryAdmin(admin.ModelAdmin):
    """Delivery audit: one row per (report version, recipient, channel)."""

    list_display = (
        "recipient",
        "channel",
        "status",
        "retry_count",
        "sent_at",
        "last_attempt_at",
        "dedup_short",
    )
    list_filter = ("channel", "status")
    search_fields = ("recipient__email", "dedup_key")
    readonly_fields = tuple(field.name for field in WeeklyReportDelivery._meta.fields)
    actions = ("retry_selected",)

    def has_add_permission(self, request) -> bool:
        return False

    def has_module_permission(self, request) -> bool:
        return can_manage_reports(request.user)

    def has_view_permission(self, request, obj=None) -> bool:
        return can_view_reports(request.user)

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(description="Kalit")
    def dedup_short(self, obj):
        return format_html("<code>{}</code>", obj.dedup_key[:48])

    @admin.action(description="Tanlangan yuborishlarni qayta urinish")
    def retry_selected(self, request, queryset):
        ids = list(queryset.values_list("pk", flat=True))
        if not ids:
            self.message_user(request, "Tanlangan yuborish yo'q.", messages.WARNING)
            return
        sent = failed = 0
        for row in WeeklyReportDelivery.objects.filter(pk__in=ids).select_related(
            "report",
            "student_report",
            "recipient",
        ):
            target = row.target
            if target is None:
                continue
            if isinstance(target, WeeklyGroupReport):
                finance = delivery._may_see_finance(row.recipient)
                text = delivery.group_report_text(target, include_finance=finance)
                buttons = delivery.report_buttons(target, include_finance=finance)
            else:
                text = delivery.student_report_text(target)
                buttons = None
            refreshed = delivery._deliver(
                report=target,
                recipient=row.recipient,
                text=text,
                buttons=buttons,
                channel=row.channel,
                dedup_key=row.dedup_key,
            )
            sent += refreshed.status == refreshed.Status.SENT
            failed += refreshed.status == refreshed.Status.FAILED
        self.message_user(
            request,
            f"Yuborildi: {sent}, xatolik: {failed}.",
            messages.SUCCESS if not failed else messages.WARNING,
        )
