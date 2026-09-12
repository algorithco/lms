"""Admin configuration for notifications app."""
from django.contrib import admin

from .models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = (
        "recipient", "channel", "notification_type",
        "title", "status", "created_at",
    )
    list_filter = ("channel", "status", "notification_type")
    search_fields = ("recipient__email", "title")
    readonly_fields = (
        "recipient", "channel", "notification_type",
        "title", "message", "external_id", "error_message",
        "created_at", "sent_at",
    )

    def has_add_permission(self, request) -> bool:
        return False  # Logs are created by the system, not manually

    def has_change_permission(self, request, obj=None) -> bool:
        return False  # Immutable audit trail
