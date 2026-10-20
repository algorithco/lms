"""Admin configuration for notifications app.

Only ``NotificationLog`` is registered here. The attendance domain's
``NotificationPreference`` is registered in ``apps/attendance/admin.py`` so it
is configured in exactly one place — do not register it again here.
"""

from django.contrib import admin

from .models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """Immutable audit trail of every notification attempt.

    ``dedup_key`` is the idempotency guard added for attendance and parent
    notifications: it is UNIQUE where non-empty, so a replayed Telegram webhook
    or a retried Celery task cannot send a duplicate message. Seeing the same
    key twice with a single row is therefore expected and healthy, not a bug.
    """

    list_display = (
        "recipient",
        "channel",
        "notification_type",
        "title",
        "status",
        "dedup_key",
        "created_at",
        "sent_at",
    )
    list_filter = ("channel", "status", "notification_type", "created_at")
    search_fields = ("recipient__email", "recipient__first_name", "title", "dedup_key")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    list_select_related = ("recipient",)
    readonly_fields = (
        "recipient",
        "channel",
        "notification_type",
        "title",
        "message",
        "status",
        "external_id",
        "error_message",
        "dedup_key",
        "related_test_attempt",
        "related_certificate",
        "related_essay_submission",
        "created_at",
        "sent_at",
    )

    def has_add_permission(self, request) -> bool:
        return False  # Logs are created by the system, not manually

    def has_change_permission(self, request, obj=None) -> bool:
        return False  # Immutable audit trail

    # ``has_delete_permission`` is intentionally left at Django's default: the
    # original registration did not restrict deletion and existing behaviour
    # must not change. Only the display and the new ``dedup_key`` listing were
    # added.
