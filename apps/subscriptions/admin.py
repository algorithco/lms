from django.contrib import admin
from .models import PaymentReceipt, FraudLog


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "plan_type",
        "amount",
        "payment_system",
        "transaction_id",
        "is_verified",
        "created_at",
    )
    list_filter = ("plan_type", "payment_system", "is_verified", "created_at")
    search_fields = ("user__email", "user__first_name", "user__last_name", "transaction_id", "receipt_hash")
    readonly_fields = ("created_at",)


@admin.register(FraudLog)
class FraudLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "reason",
        "strike_count",
        "banned",
        "transaction_id",
        "created_at",
    )
    list_filter = ("banned", "strike_count", "created_at")
    search_fields = ("user__email", "user__first_name", "user__last_name", "transaction_id", "receipt_hash", "reason")
    readonly_fields = ("created_at",)
