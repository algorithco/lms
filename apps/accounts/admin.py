"""Admin configuration for accounts app."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group

from .models import Profile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom admin for the User model with role display."""

    model = User
    list_display = (
        "email", "first_name", "last_name", "role",
        "is_active", "is_staff", "created_at",
    )
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("-created_at",)

    # Fields shown when editing an existing user
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "role")}),
        ("Telegram", {"fields": ("telegram_chat_id", "telegram_identity_verified_at")}),
        (
            "Permissions",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
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
                    "email", "first_name", "last_name", "role",
                    "password1", "password2",
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
