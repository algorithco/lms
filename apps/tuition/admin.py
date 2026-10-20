"""Administrator console for course tuition.

This is where an administrator actually *operates* the billing domain: sets the
price, grants a scholarship, confirms or rejects a receipt, adjusts an invoice
and reads the correction audit. Every mutating action delegates to
``apps.tuition.services`` so the admin cannot drift from the API or the bot.

Two safety properties are enforced here rather than in the services layer:

* Payments can only be confirmed through an explicit action, and the actor is
  always recorded. There is no "mark paid" button that skips verification.
* Invoices, payments and the audit trail are read-only in the change view; the
  actions are the only way to change state, so every change is attributed.
"""

from django.contrib import admin, messages
from django.utils.html import format_html

from apps.accounts.access import has_platform_permission

from . import services
from .models import (
    CourseBillingPolicy,
    CourseInvoice,
    CoursePayment,
    PaymentReminderLog,
    StudentTuitionAgreement,
    TuitionAuditLog,
)


def can_manage_tuition(user) -> bool:
    return has_platform_permission(user, "tuition.change_courseinvoice")


@admin.register(CourseBillingPolicy)
class CourseBillingPolicyAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "scope_display",
        "amount_uzs",
        "billing_frequency",
        "due_day",
        "grace_days",
        "installments",
        "is_active",
        "effective_from",
        "effective_until",
    )
    list_filter = ("is_active", "billing_frequency", "mid_month_policy")
    search_fields = ("name", "course__title", "group__name")
    autocomplete_fields = ("course", "group")
    readonly_fields = ("created_at", "updated_at")

    def has_module_permission(self, request) -> bool:
        return can_manage_tuition(request.user)

    def has_view_permission(self, request, obj=None) -> bool:
        return can_manage_tuition(request.user)

    def has_change_permission(self, request, obj=None) -> bool:
        return can_manage_tuition(request.user)

    def has_add_permission(self, request) -> bool:
        return can_manage_tuition(request.user)

    def has_delete_permission(self, request, obj=None) -> bool:
        return can_manage_tuition(request.user)

    def save_model(self, request, obj, form, change) -> None:
        super().save_model(request, obj, form, change)
        TuitionAuditLog.objects.create(
            actor=request.user,
            action=(
                TuitionAuditLog.Action.POLICY_UPDATED
                if change
                else TuitionAuditLog.Action.POLICY_CREATED
            ),
            policy=obj,
            new_value=f"{obj.amount_uzs}",
            reason="Admin panel",
        )

    @admin.display(description="Qamrov")
    def scope_display(self, obj):
        if obj.group_id:
            return f"Guruh: {obj.group.name}"
        if obj.course_id:
            return f"Kurs: {obj.course.title}"
        return "—"


@admin.register(StudentTuitionAgreement)
class StudentTuitionAgreementAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "billing_policy",
        "negotiated_amount_uzs",
        "discount_kind",
        "discount_percent",
        "discount_amount_uzs",
        "status",
        "effective_from",
        "effective_until",
    )
    list_filter = ("status", "discount_kind")
    search_fields = ("student__email", "student__first_name", "scholarship_note")
    autocomplete_fields = ("student", "billing_policy")

    def has_module_permission(self, request) -> bool:
        return can_manage_tuition(request.user)

    def has_view_permission(self, request, obj=None) -> bool:
        return can_manage_tuition(request.user)

    def has_change_permission(self, request, obj=None) -> bool:
        return can_manage_tuition(request.user)

    def has_add_permission(self, request) -> bool:
        return can_manage_tuition(request.user)

    def save_model(self, request, obj, form, change) -> None:
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        TuitionAuditLog.objects.create(
            actor=request.user,
            action=(
                TuitionAuditLog.Action.AGREEMENT_UPDATED
                if change
                else TuitionAuditLog.Action.AGREEMENT_CREATED
            ),
            agreement=obj,
            student=obj.student,
            policy=obj.billing_policy,
            new_value=obj.discount_kind,
            reason="Admin panel",
        )


@admin.register(CourseInvoice)
class CourseInvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "period_label",
        "scope_key",
        "amount_due_uzs",
        "paid_amount_uzs",
        "pending_amount_uzs",
        "balance_display",
        "due_date",
        "status",
    )
    list_filter = ("status", "is_installment", "due_date")
    search_fields = (
        "student__email",
        "student__first_name",
        "period_label",
        "scope_key",
    )
    date_hierarchy = "billing_period_start"
    readonly_fields = (
        "student",
        "policy",
        "course",
        "enrollment",
        "agreement",
        "scope_key",
        "billing_period_start",
        "billing_period_end",
        "period_label",
        "base_amount_uzs",
        "discount_amount_uzs",
        "discount_kind",
        "paid_amount_uzs",
        "pending_amount_uzs",
        "is_installment",
        "installment_number",
        "due_date",
        "grace_until",
        "created_by",
        "created_at",
        "updated_at",
    )
    actions = ("action_mark_overdue", "action_cancel")

    def has_module_permission(self, request) -> bool:
        return can_manage_tuition(request.user)

    def has_view_permission(self, request, obj=None) -> bool:
        return can_manage_tuition(request.user)

    def has_change_permission(self, request, obj=None) -> bool:
        return can_manage_tuition(request.user)

    def has_add_permission(self, request) -> bool:
        # Invoices are generated from a policy, never typed in by hand.
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.display(description="Qoldiq")
    def balance_display(self, obj):
        return format_html("<b>{}</b>", obj.balance_uzs)

    @admin.action(description="Muddati o'tgan deb belgilash")
    def action_mark_overdue(self, request, queryset):
        marked = 0
        for invoice in queryset:
            if invoice.paid_amount_uzs >= invoice.amount_due_uzs:
                continue
            old = invoice.status
            invoice.status = CourseInvoice.Status.OVERDUE
            invoice.save(update_fields=["status", "updated_at"])
            TuitionAuditLog.objects.create(
                actor=request.user,
                action=TuitionAuditLog.Action.INVOICE_MARKED_OVERDUE,
                invoice=invoice,
                student=invoice.student,
                old_value=old,
                new_value=invoice.status,
                reason="Admin panel",
            )
            marked += 1
        self.message_user(request, f"{marked} ta hisob belgilandi.", messages.SUCCESS)

    @admin.action(description="Hisob-fakturani bekor qilish")
    def action_cancel(self, request, queryset):
        cancelled = 0
        for invoice in queryset:
            services.cancel_invoice(invoice, actor=request.user, reason="Admin panel")
            cancelled += 1
        self.message_user(
            request, f"{cancelled} ta hisob bekor qilindi.", messages.SUCCESS
        )


@admin.register(CoursePayment)
class CoursePaymentAdmin(admin.ModelAdmin):
    """The verification queue: receipts are confirmed or rejected here."""

    list_display = (
        "student",
        "invoice",
        "amount_uzs",
        "method",
        "reference",
        "status",
        "submitted_by",
        "verified_by",
        "verified_at",
        "created_at",
    )
    list_filter = ("status", "method")
    search_fields = ("student__email", "reference", "note")
    readonly_fields = (
        "student",
        "invoice",
        "amount_uzs",
        "method",
        "reference",
        "proof",
        "note",
        "submitted_by",
        "verified_by",
        "verified_at",
        "status",
        "rejection_reason",
        "created_at",
        "updated_at",
    )
    actions = ("action_verify", "action_reject", "action_refund")

    def has_module_permission(self, request) -> bool:
        return can_manage_tuition(request.user)

    def has_view_permission(self, request, obj=None) -> bool:
        return can_manage_tuition(request.user)

    def has_change_permission(self, request, obj=None) -> bool:
        return can_manage_tuition(request.user)

    def has_add_permission(self, request) -> bool:
        # A payment claim always comes from a student/parent submission or the
        # bot; recording it by hand would bypass the audit trail.
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    @admin.action(description="Tanlangan to'lovlarni tasdiqlash")
    def action_verify(self, request, queryset):
        verified = 0
        for payment in queryset:
            services.verify_payment(payment, actor=request.user, reason="Admin panel")
            verified += 1
        self.message_user(
            request, f"{verified} ta to'lov tasdiqlandi.", messages.SUCCESS
        )

    @admin.action(description="Tanlangan to'lovlarni rad etish")
    def action_reject(self, request, queryset):
        rejected = 0
        for payment in queryset:
            services.reject_payment(payment, actor=request.user, reason="Admin panel")
            rejected += 1
        self.message_user(
            request, f"{rejected} ta to'lov rad etildi.", messages.WARNING
        )

    @admin.action(description="Tanlangan to'lovlarni qaytarish")
    def action_refund(self, request, queryset):
        refunded = 0
        for payment in queryset.filter(status=CoursePayment.Status.VERIFIED):
            services.refund_payment(payment, actor=request.user, reason="Admin panel")
            refunded += 1
        self.message_user(
            request, f"{refunded} ta to'lov qaytarildi.", messages.WARNING
        )


@admin.register(PaymentReminderLog)
class PaymentReminderLogAdmin(admin.ModelAdmin):
    list_display = ("invoice", "recipient", "stage", "channel", "status", "sent_at")
    list_filter = ("stage", "channel", "status")
    search_fields = ("idempotency_key", "invoice__student__email")
    readonly_fields = tuple(field.name for field in PaymentReminderLog._meta.fields)

    def has_add_permission(self, request) -> bool:
        return False

    def has_module_permission(self, request) -> bool:
        return can_manage_tuition(request.user)

    def has_view_permission(self, request, obj=None) -> bool:
        return can_manage_tuition(request.user)

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(TuitionAuditLog)
class TuitionAuditLogAdmin(admin.ModelAdmin):
    """Append-only: the trail is the point."""

    list_display = (
        "created_at",
        "action",
        "actor",
        "student",
        "invoice",
        "payment",
        "field",
        "old_value",
        "new_value",
        "reason",
    )
    list_filter = ("action",)
    search_fields = ("reason", "student__email", "field")
    date_hierarchy = "created_at"
    readonly_fields = tuple(field.name for field in TuitionAuditLog._meta.fields)

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def has_module_permission(self, request) -> bool:
        return can_manage_tuition(request.user)

    def has_view_permission(self, request, obj=None) -> bool:
        return can_manage_tuition(request.user)
