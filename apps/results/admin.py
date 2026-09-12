"""Admin configuration for results app."""
from django.contrib import admin

from .models import Certificate, Result


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = (
        "student", "test", "course",
        "score", "max_score", "percentage",
        "is_passed", "calculated_at",
    )
    list_filter = ("is_passed", "course")
    search_fields = ("student__email", "test__title")


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = (
        "certificate_number", "student", "course",
        "status", "issued_at",
    )
    list_filter = ("status", "course")
    search_fields = ("certificate_number", "student__email")
    readonly_fields = ("certificate_number",)
