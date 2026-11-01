"""Admin configuration for accounts app."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group

from .models import Profile, ReferralHistory, TeacherProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for the User model with role display."""

    model = User
    list_display = (
        "email",
        "first_name",
        "last_name",
        "role",
        "subscription_plan_display",
        "can_create_essay_topic",
        "can_create_test",
        "is_active",
        "is_staff",
        "created_at",
    )
    actions = (
        "grant_pro_30_days",
        "grant_pro_1_year",
        "grant_premium_1_year",
    )

    @admin.display(description="Obuna (Tarif)")
    def subscription_plan_display(self, obj):
        if getattr(obj, "is_superuser", False) or getattr(obj, "role", "") == "admin":
            return "👑 Admin (Cheksiz)"
        sub = getattr(obj, "subscription", None)
        if sub and getattr(sub, "is_active", False) and getattr(sub, "plan", None):
            exp = sub.expires_at.strftime("%Y-%m-%d") if sub.expires_at else ""
            return f"⭐ {sub.plan.plan_type.upper()} ({exp})"
        if getattr(obj, "has_pro_access", False):
            return "⭐ PRO (Ustoz/Guruh)"
        return "Free"

    @admin.action(description="⭐ Tanlanganlarga 30 kunlik PRO obuna berish")
    def grant_pro_30_days(self, request, queryset):
        from apps.payments.models import SubscriptionPlan, UserSubscription
        from apps.payments.subscriptions import grant_subscription
        from django.contrib import messages

        plan = SubscriptionPlan.objects.filter(plan_type="pro").first()
        if not plan:
            self.message_user(request, "PRO tarif rejasi topilmadi.", level=messages.ERROR)
            return
        count = 0
        for user in queryset:
            grant_subscription(
                user=user,
                plan=plan,
                days=30,
                source=UserSubscription.Source.ADMIN,
                payment_method="admin_grant",
                actor=request.user,
                reason="Django admin action: grant PRO 30 days",
            )
            if hasattr(user, "profile") and user.profile:
                user.profile.plan = "pro"
                user.profile.save(update_fields=["plan"])
            count += 1
        self.message_user(request, f"{count} ta foydalanuvchiga 30 kunlik PRO obuna berildi.", level=messages.SUCCESS)

    @admin.action(description="⭐ Tanlanganlarga 1 yillik (365 kun) PRO obuna berish")
    def grant_pro_1_year(self, request, queryset):
        from apps.payments.models import SubscriptionPlan, UserSubscription
        from apps.payments.subscriptions import grant_subscription
        from django.contrib import messages

        plan = SubscriptionPlan.objects.filter(plan_type="pro").first()
        if not plan:
            self.message_user(request, "PRO tarif rejasi topilmadi.", level=messages.ERROR)
            return
        count = 0
        for user in queryset:
            grant_subscription(
                user=user,
                plan=plan,
                days=365,
                source=UserSubscription.Source.ADMIN,
                payment_method="admin_grant",
                actor=request.user,
                reason="Django admin action: grant PRO 365 days",
            )
            if hasattr(user, "profile") and user.profile:
                user.profile.plan = "pro"
                user.profile.save(update_fields=["plan"])
            count += 1
        self.message_user(request, f"{count} ta foydalanuvchiga 1 yillik PRO obuna berildi.", level=messages.SUCCESS)

    @admin.action(description="💎 Tanlanganlarga 1 yillik (365 kun) PREMIUM obuna berish")
    def grant_premium_1_year(self, request, queryset):
        from apps.payments.models import SubscriptionPlan, UserSubscription
        from apps.payments.subscriptions import grant_subscription
        from django.contrib import messages

        plan = SubscriptionPlan.objects.filter(plan_type="premium").first() or SubscriptionPlan.objects.filter(plan_type="pro").first()
        if not plan:
            self.message_user(request, "PREMIUM tarif rejasi topilmadi.", level=messages.ERROR)
            return
        count = 0
        for user in queryset:
            grant_subscription(
                user=user,
                plan=plan,
                days=365,
                source=UserSubscription.Source.ADMIN,
                payment_method="admin_grant",
                actor=request.user,
                reason="Django admin action: grant PREMIUM 365 days",
            )
            if hasattr(user, "profile") and user.profile:
                user.profile.plan = plan.plan_type
                user.profile.save(update_fields=["plan"])
            count += 1
        self.message_user(request, f"{count} ta foydalanuvchiga 1 yillik PREMIUM obuna berildi.", level=messages.SUCCESS)
    list_filter = (
        "role",
        "is_active",
        "is_staff",
        "can_create_essay_topic",
        "can_create_test",
    )
    search_fields = ("email", "first_name", "last_name")
    ordering = ("-created_at",)

    # Fields shown when editing an existing user
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "role")}),
        ("Telegram", {"fields": ("telegram_chat_id", "telegram_identity_verified_at")}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Teacher creation permissions",
            {"fields": ("can_create_essay_topic", "can_create_test")},
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    readonly_fields = ("telegram_identity_verified_at",)

    # Fields shown when creating a new user via admin
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone")
    search_fields = ("user__email", "phone")


# Unregister Group — we don't use Django's default groups
admin.site.unregister(Group)


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = (
        "teacher",
        "pro_quota_balance",
        "premium_quota_balance",
        "created_at",
    )
    search_fields = ("teacher__email", "teacher__first_name", "teacher__last_name")


@admin.register(ReferralHistory)
class ReferralHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "referrer",
        "referred_user",
        "referral_code",
        "reward_given",
        "created_at",
    )
    search_fields = (
        "referrer__email",
        "referred_user__email",
        "referral_code",
    )
    list_filter = ("reward_given", "created_at")
