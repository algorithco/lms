"""Admin configuration for the attendance, observation and routing domain.

The owner's operational console for teacher groups' attendance. Conventions are
taken from ``apps/payments/admin.py``:

* Mutating operations delegate to ``apps.attendance.services`` / ``.notifications``
  (imported lazily) so the admin never reimplements domain logic.
* Permission gating reuses ``apps.accounts.access.has_platform_permission``, the
  same policy ``can_manage_payments`` already used, so a delegated permission
  works for staff who are not platform admins.
* Append-only operational tables (the correction audit trail) are read-only by
  construction.

Teachers take attendance through the teacher panel API and the Telegram bot;
the Django admin is the *administrator's* inspection and correction surface.
"""

from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.utils import timezone

from apps.accounts.access import has_platform_permission

from .models import (
    AttendanceAuditLog,
    AttendanceRecord,
    AttendanceSession,
    ClassroomObservation,
    GroupNotificationDestination,
    NotificationPreference,
)


def can_manage_attendance(user) -> bool:
    """Platform admins, or staff explicitly granted the attendance permission.

    Mirrors ``apps.payments.access.can_manage_payments`` so the two sensitive
    consoles are gated by one consistent rule.
    """
    return has_platform_permission(user, "attendance.change_attendancesession")


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    """One lesson register per group.

    ``finalize_selected`` never invents absences: if any student is still
    unmarked the session is reported as skipped instead of finalized, and a
    separate, explicitly-named action is required to record those students as
    absent. That keeps an unfinished register from silently becoming a full
    absence for the whole group.
    """

    list_display = (
        "id",
        "group",
        "teacher",
        "lesson_date",
        "time_label",
        "status",
        "counts_display",
        "finalized_at",
    )
    list_filter = ("status", "group__teacher", "lesson_date")
    search_fields = ("group__name", "teacher__email", "teacher__first_name", "title")
    raw_id_fields = ("group", "teacher", "created_by", "finalized_by")
    date_hierarchy = "lesson_date"
    ordering = ("-lesson_date", "-start_time", "-id")
    list_select_related = ("group", "teacher")
    readonly_fields = (
        "time_label",
        "counts_display",
        "created_at",
        "updated_at",
        # Finalization is a service operation with audit semantics; it must not
        # be hand-edited through a form.
        "finalized_at",
        "finalized_by",
    )
    fieldsets = (
        (
            "Dars",
            {
                "fields": (
                    "group",
                    "teacher",
                    "lesson_date",
                    "start_time",
                    "end_time",
                    "title",
                ),
            },
        ),
        (
            "Holat",
            {
                "fields": ("status", "counts_display", "finalized_at", "finalized_by"),
            },
        ),
        (
            "Meta",
            {
                "fields": ("created_by", "created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
    actions = (
        "finalize_selected",
        "finalize_selected_marking_unmarked_absent",
        "cancel_selected",
    )

    def get_queryset(self, request):
        # Counts for the changelist without a per-row query.
        return (
            super()
            .get_queryset(request)
            .annotate(
                _roster=Count("group__students", distinct=True),
                _marked=Count("records", distinct=True),
            )
        )

    @admin.display(description="Boshlanish", ordering="start_time")
    def time_label(self, obj: AttendanceSession) -> str:
        return obj.local_time_label() if obj else "—"

    @admin.display(description="Belgilangan / ro'yxat")
    def counts_display(self, obj: AttendanceSession) -> str:
        if not obj:
            return "—"
        roster = getattr(obj, "_roster", None)
        marked = getattr(obj, "_marked", None)
        if roster is None or marked is None:
            return f"{obj.records.count()} yozuv"
        return f"{marked} / {roster}"

    def has_change_permission(self, request, obj=None) -> bool:
        return can_manage_attendance(request.user) and super().has_change_permission(
            request,
            obj,
        )

    def has_add_permission(self, request) -> bool:
        return can_manage_attendance(request.user) and super().has_add_permission(
            request
        )

    def has_delete_permission(self, request, obj=None) -> bool:
        # Deleting a register would destroy the attendance history and the
        # correction audit that hangs off it.
        return False

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    # -- actions -------------------------------------------------------------

    @admin.action(
        description="Tanlangan darslarni yakunlash (belgilanmaganlar tegilmaydi)",
        permissions=("change",),
    )
    def finalize_selected(self, request, queryset):
        from .services import finalize

        finalized = 0
        skipped_unmarked = 0
        for session in queryset.select_related("group").filter(
            status=AttendanceSession.Status.DRAFT,
        ):
            result = finalize(session, actor=request.user)
            if result.get("ok"):
                finalized += 1
            elif result.get("reason") == "unmarked_students":
                skipped_unmarked += 1
        skipped_done = queryset.exclude(
            status=AttendanceSession.Status.DRAFT,
        ).count()

        if skipped_unmarked:
            self.message_user(
                request,
                f"{skipped_unmarked} ta dars yakunlanmadi: belgilanmagan o'quvchilar "
                'bor. Ular avtomatik ravishda "kelmadi" qilib belgilanmaydi — '
                "avval ro'yxatni to'ldiring yoki alohida amaldan foydalaning.",
                level=messages.WARNING,
            )
        self.message_user(
            request,
            f"{finalized} ta davomat darsi yakunlandi"
            + (
                f", {skipped_done} tasi allaqachon yakunlangan edi."
                if skipped_done
                else "."
            ),
            level=messages.SUCCESS,
        )

    @admin.action(
        description=(
            "Tanlangan darslarni yakunlash va belgilanmaganlarni KELMADI deb yozish"
        ),
        permissions=("change",),
    )
    def finalize_selected_marking_unmarked_absent(self, request, queryset):
        from .services import finalize_and_notify

        finalized = 0
        for session in queryset.select_related("group").filter(
            status=AttendanceSession.Status.DRAFT,
        ):
            result = finalize_and_notify(
                session,
                actor=request.user,
                mark_unmarked_as_absent=True,
                reason="admin action: finalize and mark unmarked absent",
            )
            if result.get("ok"):
                finalized += 1
        self.message_user(
            request,
            f"{finalized} ta dars yakunlandi; belgilanmagan o'quvchilar KELMADI "
            "sifatida yozildi va ota-onalarga xabar yuborish navbatga qo'yildi.",
            level=messages.SUCCESS,
        )

    @admin.action(
        description="Tanlangan darslarni bekor qilish",
        permissions=("change",),
    )
    def cancel_selected(self, request, queryset):
        cancelled = queryset.exclude(
            status=AttendanceSession.Status.FINALIZED,
        ).update(status=AttendanceSession.Status.CANCELLED, updated_at=timezone.now())
        self.message_user(
            request,
            f"{cancelled} ta dars bekor qilindi (yakunlangan darslar o'zgartirilmadi).",
            level=messages.SUCCESS,
        )


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    """Individual student markings — the administrator's correction surface.

    Editing here bypasses the service audit trail, so only platform admins may
    change a row; teachers correct attendance through their own flows (which do
    write an ``AttendanceAuditLog`` entry).
    """

    list_display = (
        "id",
        "student",
        "group_display",
        "lesson_date",
        "status",
        "late_minutes",
        "marked_by",
        "marked_at",
    )
    list_filter = ("status", "late_minutes", "session__group")
    search_fields = (
        "student__email",
        "student__first_name",
        "student__last_name",
        "session__group__name",
        "note",
    )
    raw_id_fields = ("session", "student", "marked_by")
    date_hierarchy = "marked_at"
    list_select_related = ("student", "session", "session__group", "marked_by")
    ordering = ("-marked_at",)
    readonly_fields = ("updated_at",)

    @admin.display(description="Guruh", ordering="session__group__name")
    def group_display(self, obj: AttendanceRecord) -> str:
        return obj.session.group.name if obj.session_id else "—"

    @admin.display(description="Dars sanasi", ordering="session__lesson_date")
    def lesson_date(self, obj: AttendanceRecord):
        return obj.session.lesson_date if obj.session_id else None

    def has_change_permission(self, request, obj=None) -> bool:
        return can_manage_attendance(request.user) and super().has_change_permission(
            request,
            obj,
        )

    def has_add_permission(self, request) -> bool:
        return can_manage_attendance(request.user) and super().has_add_permission(
            request
        )

    def has_delete_permission(self, request, obj=None) -> bool:
        return can_manage_attendance(request.user) and super().has_delete_permission(
            request,
            obj,
        )


# ---------------------------------------------------------------------------
# Correction audit — append-only
# ---------------------------------------------------------------------------


@admin.register(AttendanceAuditLog)
class AttendanceAuditLogAdmin(admin.ModelAdmin):
    """Append-only trail of every attendance correction.

    Fully read-only for everyone, including administrators: it is the evidence
    that explains why a student's final attendance differs from the first
    marking.
    """

    list_display = (
        "created_at",
        "session",
        "student",
        "field",
        "old_value",
        "new_value",
        "actor",
        "reason",
    )
    list_filter = ("field", "session__group")
    search_fields = (
        "student__email",
        "student__first_name",
        "student__last_name",
        "actor__email",
        "session__group__name",
        "reason",
    )
    raw_id_fields = ("session", "record", "student", "actor")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    readonly_fields = (
        "session",
        "record",
        "student",
        "actor",
        "field",
        "old_value",
        "new_value",
        "reason",
        "created_at",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def save_model(self, request, obj, form, change):
        # Defensive no-op: nothing here is editable, so a stray POST is ignored.
        pass


# ---------------------------------------------------------------------------
# Classroom observations
# ---------------------------------------------------------------------------


@admin.register(ClassroomObservation)
class ClassroomObservationAdmin(admin.ModelAdmin):
    """Neutral teacher notes about classroom conduct.

    An observation is a description, not a sanction: there is no automatic
    punishment and no student ranking anywhere in this model. Nothing reaches a
    parent until the recording teacher runs one of the confirmation actions
    below, and ``notify_parents_of_observation`` refuses an unconfirmed row on
    its own as well.
    """

    list_display = (
        "id",
        "student",
        "teacher",
        "observation_type",
        "notification_status",
        "is_confirmed_display",
        "confirmed_at",
        "sent_at",
        "created_at",
    )
    list_filter = ("observation_type", "notification_status")
    search_fields = (
        "student__email",
        "student__first_name",
        "student__last_name",
        "teacher__email",
        "neutral_description",
    )
    raw_id_fields = ("student", "session", "teacher", "confirmed_by")
    date_hierarchy = "created_at"
    list_select_related = ("student", "teacher")
    actions = ("confirm_and_send_selected", "confirm_without_sending_selected")

    @admin.display(description="Tasdiqlangan", boolean=True)
    def is_confirmed_display(self, obj: ClassroomObservation) -> bool:
        return bool(obj and obj.is_confirmed)

    def has_change_permission(self, request, obj=None) -> bool:
        return can_manage_attendance(request.user) and super().has_change_permission(
            request,
            obj,
        )

    def has_add_permission(self, request) -> bool:
        return can_manage_attendance(request.user) and super().has_add_permission(
            request
        )

    def has_delete_permission(self, request, obj=None) -> bool:
        return can_manage_attendance(request.user) and super().has_delete_permission(
            request,
            obj,
        )

    @admin.action(
        description="Tasdiqlash va ota-onaga yuborish (tasdiqlangan kuzatuvlar)",
        permissions=("change",),
    )
    def confirm_and_send_selected(self, request, queryset):
        from .notifications import notify_parents_of_observation
        from .services import AttendanceError, confirm_observation

        confirmed = 0
        delivered = 0
        failed = 0
        rejected = 0
        for observation in queryset.select_related("student", "teacher"):
            try:
                confirm_observation(observation, actor=request.user, send=True)
            except (AttendanceError, PermissionDenied) as exc:
                rejected += 1
                self.message_user(
                    request,
                    f"#{observation.pk} tasdiqlanmadi: {exc}",
                    level=messages.WARNING,
                )
                continue
            confirmed += 1
            # A transport failure must never roll back the confirmation; the
            # observation simply stays queued for a retry.
            try:
                notify_parents_of_observation(observation)
                delivered += 1
            except Exception as exc:  # noqa: BLE001 - delivery is best-effort
                failed += 1
                self.message_user(
                    request,
                    f"#{observation.pk} yuborilmadi: {exc}",
                    level=messages.WARNING,
                )
        self.message_user(
            request,
            f"{confirmed} ta kuzatuv tasdiqlandi, {delivered} tasi yuborishga "
            f"qo'yildi, {failed} tasida yetkazishda xatolik, {rejected} tasi "
            "rad etildi.",
            level=messages.SUCCESS,
        )

    @admin.action(
        description="Tasdiqlash, lekin ota-onaga YUBORMASLIK",
        permissions=("change",),
    )
    def confirm_without_sending_selected(self, request, queryset):
        from .services import AttendanceError, confirm_observation

        confirmed = 0
        for observation in queryset.select_related("student"):
            try:
                confirm_observation(observation, actor=request.user, send=False)
                confirmed += 1
            except (AttendanceError, PermissionDenied) as exc:
                self.message_user(
                    request,
                    f"#{observation.pk} tasdiqlanmadi: {exc}",
                    level=messages.WARNING,
                )
        self.message_user(
            request,
            f"{confirmed} ta kuzatuv tasdiqlandi va ota-onaga yuborilmaydi.",
            level=messages.SUCCESS,
        )


# ---------------------------------------------------------------------------
# Group notification routing
# ---------------------------------------------------------------------------


@admin.register(GroupNotificationDestination)
class GroupNotificationDestinationAdmin(admin.ModelAdmin):
    """Approved Telegram destinations for group notices.

    A chat id typed by a teacher is NEVER a delivery target: the row only
    becomes usable after an administrator runs ``approve_selected``. A
    ``PARENT_PUBLIC`` destination receives aggregate summaries only and never a
    named student's absence or conduct note — those go to a verified private
    parent chat.
    """

    list_display = (
        "id",
        "title",
        "group_display",
        "chat_id",
        "destination_type",
        "is_enabled",
        "is_approved",
        "is_usable_display",
        "allowed_categories",
        "approved_by",
        "approved_at",
    )
    list_filter = ("destination_type", "is_enabled", "is_approved")
    search_fields = ("title", "chat_id", "group__name")
    raw_id_fields = ("group", "approved_by")
    readonly_fields = (
        "is_usable_display",
        "created_at",
        "updated_at",
        "approved_at",
        "approved_by",
    )
    actions = ("approve_selected", "revoke_selected")

    @admin.display(description="Guruh", ordering="group__name")
    def group_display(self, obj: GroupNotificationDestination) -> str:
        return obj.group.name if obj.group_id else "Barcha guruhlar"

    @admin.display(description="Ishlatilishi mumkin", boolean=True)
    def is_usable_display(self, obj: GroupNotificationDestination) -> bool:
        return bool(obj and obj.is_usable)

    def has_change_permission(self, request, obj=None) -> bool:
        return can_manage_attendance(request.user) and super().has_change_permission(
            request,
            obj,
        )

    def has_add_permission(self, request) -> bool:
        # A destination is only meaningful once an administrator approves it,
        # so creation runs through the same gate.
        return can_manage_attendance(request.user) and super().has_add_permission(
            request
        )

    def has_delete_permission(self, request, obj=None) -> bool:
        return can_manage_attendance(request.user) and super().has_delete_permission(
            request,
            obj,
        )

    def save_model(self, request, obj, form, change):
        """Stamp the approving administrator whenever a row becomes approved.

        ``approved_by``/``approved_at`` are read-only in the form, so approval
        through ``is_approved`` would otherwise record no approver at all — and
        the delivery guard depends on an approval being attributable.
        """
        if obj.is_approved and (not obj.approved_by_id or obj.approved_at is None):
            obj.approved_by = request.user
            obj.approved_at = timezone.now()
        elif not obj.is_approved:
            obj.approved_by = None
            obj.approved_at = None
        super().save_model(request, obj, form, change)

    @admin.action(
        description="Tanlangan manzillarni tasdiqlash (approve)",
        permissions=("change",),
    )
    def approve_selected(self, request, queryset):
        now = timezone.now()
        approved = queryset.filter(is_approved=False).update(
            is_approved=True,
            approved_by=request.user,
            approved_at=now,
            updated_at=now,
        )
        self.message_user(
            request,
            f"{approved} ta xabar manzili tasdiqlandi. Faqat tasdiqlangan "
            "manzillarga xabar yuboriladi.",
            level=messages.SUCCESS,
        )

    @admin.action(
        description="Tanlangan manzillarni bekor qilish (revoke)",
        permissions=("change",),
    )
    def revoke_selected(self, request, queryset):
        revoked = queryset.filter(is_approved=True).update(
            is_approved=False,
            approved_by=None,
            approved_at=None,
            updated_at=timezone.now(),
        )
        self.message_user(
            request,
            f"{revoked} ta manzil bekor qilindi — endi unga hech narsa yuborilmaydi.",
            level=messages.SUCCESS,
        )


# ---------------------------------------------------------------------------
# Notification preferences
# ---------------------------------------------------------------------------


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Per-user notification switches.

    Registered here (and only here) so the notification domain has a single
    place to configure opt-outs. Every switch that concerns a user's own
    account or their own child defaults to ON.
    """

    list_display = (
        "user",
        "role_display",
        "telegram_enabled",
        "attendance_alerts",
        "essay_graded_alerts",
        "test_result_alerts",
        "observation_alerts",
        "teacher_new_essay",
        "teacher_grading_failed",
        "updated_at",
    )
    list_filter = (
        "telegram_enabled",
        "attendance_alerts",
        "essay_graded_alerts",
        "observation_alerts",
    )
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
    )
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="Rol", ordering="user__role")
    def role_display(self, obj: NotificationPreference) -> str:
        if not obj.user_id:
            return "—"
        return (
            obj.user.get_role_display()
            if hasattr(
                obj.user,
                "get_role_display",
            )
            else obj.user.role
        )

    def has_change_permission(self, request, obj=None) -> bool:
        return can_manage_attendance(request.user) and super().has_change_permission(
            request,
            obj,
        )

    def has_add_permission(self, request) -> bool:
        return can_manage_attendance(request.user) and super().has_add_permission(
            request
        )

    def has_delete_permission(self, request, obj=None) -> bool:
        # Preferences are recreated on demand; deleting them would silently
        # reset a user's choices back to the defaults.
        return False
