"""Admin configuration for payments app."""
from django.contrib import admin

from .access import can_manage_payments
from .models import PaymentHistory, PaymentRequest, SubscriptionPlan, UserSubscription


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name", "plan_type", "price_monthly", "price_yearly",
        "max_tests_per_day", "max_essays_per_week", "is_active",
    )
    list_filter = ("is_active", "plan_type")
    search_fields = ("name",)


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user", "plan", "status", "started_at", "expires_at",
        "payment_method", "is_trial",
    )
    list_filter = ("status", "plan", "is_trial")
    search_fields = ("user__email", "user__first_name")
    raw_id_fields = ("user", "plan")


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = (
        "user", "plan", "amount", "status", "reviewed_by",
        "created_at", "reviewed_at",
    )
    list_filter = ("status", "plan")
    search_fields = ("user__email", "user__first_name")
    raw_id_fields = ("user", "plan")
    readonly_fields = ("screenshot_file_id", "telegram_message_id")

    def has_change_permission(self, request, obj=None):
        return can_manage_payments(request.user) and super().has_change_permission(request, obj)

    def has_add_permission(self, request):
        return can_manage_payments(request.user) and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return can_manage_payments(request.user) and super().has_delete_permission(request, obj)


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "user", "plan", "amount", "currency", "payment_method",
        "status", "created_at",
    )
    list_filter = ("status", "payment_method", "currency")
    search_fields = ("user__email", "payment_id")
    raw_id_fields = ("user", "plan")
