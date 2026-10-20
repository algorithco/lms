"""Admin configuration for the commercial subscription system.

This module is the project owner's control surface: prices, Telegram Stars
prices, essay/test quotas, cooldowns, sponsored access and per-student
overrides are all editable here without touching source code.

Conventions kept from the original file
---------------------------------------
* Mutating operations are delegated to the service layer (lazily imported) so
  the admin never reimplements entitlement logic.
* Permission gating reuses ``apps.payments.access.can_manage_payments``, the
  same policy ``PaymentRequestAdmin`` already used.
* Append-only operational tables (usage ledger, orders, audit log) are
  read-only by construction: every field is in ``readonly_fields``, add/delete
  are refused, and ``save_model`` is a no-op — a stray POST can never rewrite
  billing history.
"""

from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from .access import can_manage_payments
from .models import (
    EntitlementAuditLog,
    PaymentHistory,
    PaymentReceipt,
    PaymentRequest,
    SubscriptionOverride,
    SubscriptionPlan,
    SubscriptionUsage,
    TeacherSponsorship,
    TelegramOrder,
    UserSubscription,
)


# ---------------------------------------------------------------------------
# Plans — the commercial catalogue
# ---------------------------------------------------------------------------


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """START / PRO / TEACHER_SPONSORED configuration.

    Quota field semantics (also stated in each field's help_text): an empty
    value means "inherit the platform default", ``0`` means "explicitly none
    allowed", a positive number is a hard cap. Unlimited access is expressed
    with the ``is_unlimited_*`` flags — never by a ``0`` in a limit field.
    """

    list_display = (
        "name",
        "code_display",
        "price_monthly",
        "telegram_stars_price",
        "image_essay_weekly_limit",
        "text_essay_weekly_limit",
        "text_essay_cooldown_hours",
        "test_limit",
        "is_public",
        "is_active",
    )
    list_filter = ("is_active", "is_public", "plan_type")
    search_fields = ("name", "plan_type")
    ordering = ("sort_order", "price_monthly")
    readonly_fields = (
        "code_display",
        "price_uzs_display",
        "purchasable_display",
        "quota_snapshot_display",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "Identifikatsiya va narx",
            {
                "fields": (
                    "name",
                    "plan_type",
                    "description",
                    "price_monthly",
                    "price_yearly",
                    "price_uzs_display",
                    "duration_days",
                    "quota_period_days",
                ),
            },
        ),
        (
            "Telegram Stars (XTR)",
            {
                "fields": ("telegram_stars_price",),
                "description": (
                    "Telegram ichida raqamli tovar uchun faqat Stars qabul "
                    "qilinadi. Bu yerga haqiqiy yechib olinadigan butun Stars "
                    "sonini kiriting — valyuta kursi avtomatik hisoblanmaydi. "
                    "Bo'sh qoldirilsa, reja Telegram orqali sotilmaydi."
                ),
            },
        ),
        (
            "Esse kvotalari",
            {
                "fields": (
                    "image_essay_weekly_limit",
                    "text_essay_weekly_limit",
                    "text_essay_cooldown_hours",
                ),
                "description": (
                    "Bo'sh = platforma standarti, 0 = umuman ruxsat yo'q, "
                    "musbat son = haftalik qat'iy chegara."
                ),
            },
        ),
        (
            "Test kvotasi",
            {"fields": ("test_limit",)},
        ),
        (
            "Cheksiz imkoniyatlar",
            {
                "fields": (
                    "is_unlimited_image_essays",
                    "is_unlimited_text_essays",
                    "is_unlimited_tests",
                ),
                "description": (
                    "Cheksizlikni chegarani 0 qilib emas, shu belgilar bilan ifodalang."
                ),
            },
        ),
        (
            "Qo'shimcha imkoniyatlar",
            {
                "fields": (
                    "max_tests_per_day",
                    "max_essays_per_week",
                    "max_ai_grading",
                    "detailed_analytics",
                    "pdf_certificate",
                    "priority_support",
                    "unlimited_tests",
                    "unlimited_essays",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Sotuv va ko'rinish",
            {
                "fields": (
                    "is_public",
                    "is_active",
                    "sort_order",
                    "purchasable_display",
                ),
            },
        ),
        (
            "Nusxa (sotib olinganda muzlatiladi)",
            {
                "fields": (
                    "quota_snapshot_display",
                    "code_display",
                    "created_at",
                    "updated_at",
                ),
                "description": (
                    "Sotib olingan obuna shu konfiguratsiyani o'zida saqlaydi — "
                    "keyin rejani o'zgartirish eski xaridga ta'sir qilmaydi."
                ),
                "classes": ("collapse",),
            },
        ),
    )

    # -- read-only computed columns ------------------------------------------

    @admin.display(description="Kod", ordering="plan_type")
    def code_display(self, obj: SubscriptionPlan) -> str:
        return obj.code if obj else "—"

    @admin.display(description="Narx (UZS)")
    def price_uzs_display(self, obj: SubscriptionPlan) -> str:
        return f"{obj.price_uzs:,} UZS" if obj else "—"

    @admin.display(description="Sotuvda", boolean=True)
    def purchasable_display(self, obj: SubscriptionPlan) -> bool:
        return bool(obj and obj.is_purchasable)

    @admin.display(description="Kvota nusxasi")
    def quota_snapshot_display(self, obj: SubscriptionPlan) -> str:
        """Exactly what a purchase freezes onto the subscription row."""
        if not obj:
            return "—"
        import json

        return json.dumps(obj.quota_snapshot(), ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    """Search a student's plan, expiry, payment source and frozen snapshot.

    ``plan_snapshot`` / ``entitlement_snapshot`` are read-only: editing a plan
    must never retroactively rewrite what a student already paid for.
    """

    list_display = (
        "user",
        "plan",
        "status",
        "purchase_source",
        "started_at",
        "expires_at",
        "payment_method",
        "payment_reference",
        "is_trial",
    )
    list_filter = ("status", "plan", "purchase_source", "payment_method", "is_trial")
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "payment_id",
        "payment_reference",
    )
    raw_id_fields = ("user", "plan")
    date_hierarchy = "started_at"
    readonly_fields = (
        "payment_id",
        "payment_reference",
        "plan_snapshot",
        "entitlement_snapshot",
        "created_at",
        "updated_at",
    )
    actions = ("revoke_selected", "mark_expired")

    def has_change_permission(self, request, obj=None):
        return can_manage_payments(request.user) and super().has_change_permission(
            request,
            obj,
        )

    def has_delete_permission(self, request, obj=None):
        # Subscriptions are never deleted: history and audit depend on them.
        return False

    @admin.action(
        description="Tanlangan obunalarni bekor qilish (revoke)",
        permissions=("change",),
    )
    def revoke_selected(self, request, queryset):
        from .subscriptions import revoke_subscription

        revoked = 0
        for subscription in queryset.select_related("user"):
            if revoke_subscription(
                subscription.user,
                actor=request.user,
                reason="admin action: revoke selected",
            ):
                revoked += 1
        self.message_user(
            request,
            f"{revoked} ta obuna bekor qilindi (tarix va topshirilgan esselar "
            "saqlanadi).",
            level=messages.SUCCESS,
        )

    @admin.action(
        description="Muddati o'tgan obunalarni EXPIRED qilish",
        permissions=("change",),
    )
    def mark_expired(self, request, queryset):
        from .subscriptions import expire_overdue_subscriptions

        expired = expire_overdue_subscriptions()
        self.message_user(
            request,
            f"{expired} ta muddati o'tgan obuna EXPIRED holatiga o'tkazildi.",
            level=messages.SUCCESS,
        )


# ---------------------------------------------------------------------------
# Usage ledger — append-only
# ---------------------------------------------------------------------------


@admin.register(SubscriptionUsage)
class SubscriptionUsageAdmin(admin.ModelAdmin):
    """Read-only view of commercial quota consumption.

    The ledger is the audit trail for support and refunds, so rows can never be
    added, edited or deleted from the admin — not even by an administrator.
    ``counts_towards_quota`` distinguishes rows created for
    unlimited/sponsored tiers (recorded for audit, not charged).
    """

    list_display = (
        "user",
        "kind",
        "status",
        "counts_towards_quota",
        "period_start",
        "plan_type_snapshot",
        "source",
        "submission",
        "test_attempt",
        "created_at",
        "committed_at",
        "released_at",
    )
    list_filter = (
        "kind",
        "status",
        "counts_towards_quota",
        "source",
        "plan_type_snapshot",
    )
    search_fields = ("user__email", "idempotency_key", "note")
    raw_id_fields = ("user", "submission", "test_attempt")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    readonly_fields = (
        "user",
        "kind",
        "status",
        "idempotency_key",
        "period_start",
        "counts_towards_quota",
        "plan_type_snapshot",
        "source",
        "submission",
        "test_attempt",
        "created_at",
        "committed_at",
        "released_at",
        "note",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        # Immutable rows; only platform managers may even open a row.
        return can_manage_payments(request.user)

    def save_model(self, request, obj, form, change):
        # No-op: every field is readonly, so a stray POST must not touch the row.
        pass


# ---------------------------------------------------------------------------
# Per-student administrator override
# ---------------------------------------------------------------------------


@admin.register(SubscriptionOverride)
class SubscriptionOverrideAdmin(admin.ModelAdmin):
    """Highest-priority entitlement override for one student.

    Every quota field is nullable and **NULL means "inherit"** — an override
    that sets only the image limit keeps the student's paid text-essay
    allowance. ``0`` is an explicit "none allowed". Leaving a field empty can
    therefore never disable an entire paid subscription.
    """

    list_display = (
        "user",
        "is_active",
        "image_essay_weekly_limit",
        "text_essay_weekly_limit",
        "text_essay_cooldown_hours",
        "test_limit",
        "is_unlimited_text_essays",
        "expires_at",
        "granted_by",
        "updated_at",
    )
    list_filter = (
        "is_active",
        "is_unlimited_image_essays",
        "is_unlimited_text_essays",
        "is_unlimited_tests",
    )
    search_fields = ("user__email", "user__first_name", "user__last_name", "reason")
    raw_id_fields = ("user", "granted_by")
    date_hierarchy = "created_at"
    actions = ("revoke_selected",)

    def has_change_permission(self, request, obj=None):
        return can_manage_payments(request.user) and super().has_change_permission(
            request,
            obj,
        )

    def has_add_permission(self, request):
        return can_manage_payments(request.user) and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return can_manage_payments(request.user) and super().has_delete_permission(
            request,
            obj,
        )

    def save_model(self, request, obj, form, change):
        """Record the granting administrator and log the change."""
        if not obj.granted_by_id:
            obj.granted_by = request.user
        super().save_model(request, obj, form, change)
        EntitlementAuditLog.objects.create(
            actor=request.user,
            student=obj.user,
            action=(
                EntitlementAuditLog.Action.UPDATE_OVERRIDE
                if change
                else EntitlementAuditLog.Action.GRANT_OVERRIDE
            ),
            details={
                "image_essay_weekly_limit": obj.image_essay_weekly_limit,
                "text_essay_weekly_limit": obj.text_essay_weekly_limit,
                "text_essay_cooldown_hours": obj.text_essay_cooldown_hours,
                "test_limit": obj.test_limit,
                "is_unlimited_image_essays": obj.is_unlimited_image_essays,
                "is_unlimited_text_essays": obj.is_unlimited_text_essays,
                "is_unlimited_tests": obj.is_unlimited_tests,
                "expires_at": obj.expires_at.isoformat() if obj.expires_at else None,
            },
        )

    @admin.action(
        description="Tanlangan ustunliklarni bekor qilish (revoke)",
        permissions=("change",),
    )
    def revoke_selected(self, request, queryset):
        logs = []
        now = timezone.now()
        for override in queryset.filter(is_active=True).select_related("user"):
            override.is_active = False
            override.save(update_fields=["is_active", "updated_at"])
            logs.append(
                EntitlementAuditLog(
                    actor=request.user,
                    student=override.user,
                    action=EntitlementAuditLog.Action.REVOKE_OVERRIDE,
                    details={"revoked_at": now.isoformat()},
                )
            )
        if logs:
            EntitlementAuditLog.objects.bulk_create(logs)
        self.message_user(
            request,
            f"{len(logs)} ta admin ustunligi bekor qilindi (obuna va esselar "
            "o'zgarishsiz qoladi).",
            level=messages.SUCCESS,
        )


# ---------------------------------------------------------------------------
# Teacher sponsorship
# ---------------------------------------------------------------------------


@admin.register(TeacherSponsorship)
class TeacherSponsorshipAdmin(admin.ModelAdmin):
    """Free access for students of approved teacher groups.

    A teacher adding a student to a group is *not* enough: the sponsorship only
    becomes effective once an administrator runs ``approve_selected`` (which
    stamps ``approved_at``/``approved_by``). That is what stops a teacher from
    self-granting unlimited free access.
    """

    list_display = (
        "student",
        "group_display",
        "teacher_display",
        "is_active",
        "approved_at",
        "expires_at",
        "image_essay_weekly_limit",
        "text_essay_weekly_limit",
        "created_at",
    )
    list_filter = ("is_active", "approved_at", "expires_at")
    search_fields = (
        "student__email",
        "student__first_name",
        "student__last_name",
        "group__name",
        "group__teacher__email",
        "note",
    )
    raw_id_fields = ("student", "group", "approved_by")
    date_hierarchy = "created_at"
    actions = ("approve_selected", "revoke_selected")

    @admin.display(description="Guruh", ordering="group__name")
    def group_display(self, obj: TeacherSponsorship) -> str:
        return obj.group.name if obj.group_id else "—"

    @admin.display(description="Ustoz", ordering="group__teacher__email")
    def teacher_display(self, obj: TeacherSponsorship) -> str:
        if not obj.group_id:
            return "—"
        teacher = obj.group.teacher
        return teacher.get_full_name() or teacher.email

    def has_change_permission(self, request, obj=None):
        return can_manage_payments(request.user) and super().has_change_permission(
            request,
            obj,
        )

    def has_add_permission(self, request):
        return can_manage_payments(request.user) and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return can_manage_payments(request.user) and super().has_delete_permission(
            request,
            obj,
        )

    @admin.action(
        description="Tanlangan homiyliklarni tasdiqlash (approve)",
        permissions=("change",),
    )
    def approve_selected(self, request, queryset):
        now = timezone.now()
        logs = []
        approved = 0
        for sponsorship in queryset.select_related("student"):
            if sponsorship.approved_at is None or not sponsorship.is_active:
                sponsorship.approved_at = now
                sponsorship.approved_by = request.user
                sponsorship.is_active = True
                sponsorship.revoked_at = None
                sponsorship.save(
                    update_fields=[
                        "approved_at",
                        "approved_by",
                        "is_active",
                        "revoked_at",
                        "updated_at",
                    ]
                )
                approved += 1
                logs.append(
                    EntitlementAuditLog(
                        actor=request.user,
                        student=sponsorship.student,
                        action=EntitlementAuditLog.Action.APPROVE_SPONSORSHIP,
                        details={
                            "group": sponsorship.group_id,
                            "expires_at": (
                                sponsorship.expires_at.isoformat()
                                if sponsorship.expires_at
                                else None
                            ),
                        },
                    )
                )
        if logs:
            EntitlementAuditLog.objects.bulk_create(logs)
        self.message_user(
            request,
            f"{approved} ta homiylik tasdiqlandi. "
            f"{queryset.count() - approved} ta allaqachon faol edi.",
            level=messages.SUCCESS,
        )

    @admin.action(
        description="Tanlangan homiyliklarni bekor qilish (revoke)",
        permissions=("change",),
    )
    def revoke_selected(self, request, queryset):
        now = timezone.now()
        logs = []
        for sponsorship in queryset.filter(is_active=True).select_related("student"):
            sponsorship.is_active = False
            sponsorship.revoked_at = now
            sponsorship.save(update_fields=["is_active", "revoked_at", "updated_at"])
            logs.append(
                EntitlementAuditLog(
                    actor=request.user,
                    student=sponsorship.student,
                    action=EntitlementAuditLog.Action.REVOKE_SPONSORSHIP,
                    details={"group": sponsorship.group_id},
                )
            )
        if logs:
            EntitlementAuditLog.objects.bulk_create(logs)
        self.message_user(
            request,
            f"{len(logs)} ta homiylik bekor qilindi. O'quvchi hisobi, esselari "
            "va alohida sotib olingan obunasi o'chirilmaydi.",
            level=messages.SUCCESS,
        )


# ---------------------------------------------------------------------------
# Telegram Stars orders — append-only
# ---------------------------------------------------------------------------


@admin.register(TelegramOrder)
class TelegramOrderAdmin(admin.ModelAdmin):
    """Read-only Telegram Stars purchase records.

    A purchase becomes PAID only after a verified ``successful_payment``
    update; ``telegram_payment_charge_id`` is UNIQUE, so a replayed Telegram
    update cannot double-activate a subscription.
    """

    list_display = (
        "payload",
        "user",
        "plan",
        "amount_stars",
        "currency",
        "status",
        "telegram_payment_charge_id",
        "created_at",
        "paid_at",
    )
    list_filter = ("status", "currency", "plan")
    search_fields = (
        "payload",
        "telegram_payment_charge_id",
        "provider_payment_charge_id",
        "user__email",
    )
    raw_id_fields = ("user", "plan")
    date_hierarchy = "created_at"
    readonly_fields = (
        "user",
        "plan",
        "payload",
        "amount_stars",
        "currency",
        "status",
        "telegram_payment_charge_id",
        "provider_payment_charge_id",
        "raw_payload",
        "created_at",
        "updated_at",
        "paid_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return can_manage_payments(request.user)

    def save_model(self, request, obj, form, change):
        # No-op: orders are written only by the payment service layer.
        pass


# ---------------------------------------------------------------------------
# Entitlement audit log — append-only
# ---------------------------------------------------------------------------


@admin.register(EntitlementAuditLog)
class EntitlementAuditLogAdmin(admin.ModelAdmin):
    """Append-only record of every entitlement grant, change and revocation."""

    list_display = ("created_at", "action", "student", "actor")
    list_filter = ("action",)
    search_fields = ("student__email", "actor__email")
    raw_id_fields = ("actor", "student")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)
    readonly_fields = ("actor", "student", "action", "details", "created_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# Existing payment flows (unchanged policy, extended reporting)
# ---------------------------------------------------------------------------


@admin.register(PaymentRequest)
class PaymentRequestAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "amount",
        "status",
        "reviewed_by",
        "created_at",
        "reviewed_at",
    )
    list_filter = ("status", "plan")
    search_fields = ("user__email", "user__first_name")
    raw_id_fields = ("user", "plan")
    readonly_fields = ("screenshot_file_id", "telegram_message_id")

    def has_change_permission(self, request, obj=None):
        return can_manage_payments(request.user) and super().has_change_permission(
            request,
            obj,
        )

    def has_add_permission(self, request):
        return can_manage_payments(request.user) and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return can_manage_payments(request.user) and super().has_delete_permission(
            request,
            obj,
        )


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "plan",
        "amount",
        "currency",
        "payment_method",
        "status",
        "created_at",
    )
    list_filter = ("status", "payment_method", "currency")
    search_fields = ("user__email", "payment_id")
    raw_id_fields = ("user", "plan")


@admin.register(PaymentReceipt)
class PaymentReceiptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "plan",
        "amount_display",
        "receipt_preview",
        "status",
        "source",
        "created_at",
    )
    list_filter = ("status", "plan", "source", "created_at")
    search_fields = ("user__email", "user__first_name", "user__last_name", "admin_note")
    raw_id_fields = ("user",)
    readonly_fields = ("receipt_preview_large", "created_at", "updated_at")
    actions = ["approve_selected", "reject_selected"]

    @admin.display(description="Summa")
    def amount_display(self, obj: PaymentReceipt):
        return f"{int(obj.amount):,} so'm"

    @admin.display(description="Chek rasmi")
    def receipt_preview(self, obj: PaymentReceipt):
        if obj.receipt_image:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-height: 50px; border-radius: 4px; border: 1px solid #ddd;" />'
                "</a>",
                obj.receipt_image.url,
                obj.receipt_image.url,
            )
        return "—"

    @admin.display(description="Chek rasmi (kattalashtirilgan)")
    def receipt_preview_large(self, obj: PaymentReceipt):
        if obj.receipt_image:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width: 480px; max-height: 600px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);" />'
                "</a>",
                obj.receipt_image.url,
                obj.receipt_image.url,
            )
        return "—"

    @admin.action(description="Tanlangan cheklarni tasdiqlash va obunani yoqish")
    def approve_selected(self, request, queryset):
        from .services import approve_payment_receipt

        approved_count = 0
        for receipt in queryset:
            if receipt.status != PaymentReceipt.Status.APPROVED:
                approve_payment_receipt(receipt, admin_user=request.user)
                approved_count += 1
        self.message_user(
            request,
            f"{approved_count} ta to'lov cheki tasdiqlandi va tegishli obunalar faollashtirildi.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Tanlangan cheklarni rad etish")
    def reject_selected(self, request, queryset):
        from .services import reject_payment_receipt

        rejected_count = 0
        for receipt in queryset:
            if receipt.status == PaymentReceipt.Status.PENDING:
                reject_payment_receipt(
                    receipt, note="Admin tomonidan rad etildi", admin_user=request.user
                )
                rejected_count += 1
        self.message_user(
            request,
            f"{rejected_count} ta to'lov cheki rad etildi.",
            level=messages.WARNING,
        )

    def has_change_permission(self, request, obj=None):
        return can_manage_payments(request.user) and super().has_change_permission(
            request, obj
        )

    def has_add_permission(self, request):
        return can_manage_payments(request.user) and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return can_manage_payments(request.user) and super().has_delete_permission(
            request, obj
        )
