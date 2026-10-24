from django.contrib import admin
from .models import VocabularyPack, StudentWordMistake


@admin.register(VocabularyPack)
class VocabularyPackAdmin(admin.ModelAdmin):
    list_display = ("title", "teacher", "group", "word_count", "created_at")
    search_fields = (
        "title",
        "teacher__email",
        "teacher__first_name",
        "teacher__last_name",
    )
    list_filter = ("created_at", "subject")


@admin.register(StudentWordMistake)
class StudentWordMistakeAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "word",
        "translation_uz",
        "mistake_count",
        "consecutive_correct_streak",
        "is_mastered",
        "next_review_at",
    )
    search_fields = ("student__email", "student__first_name", "word", "translation_uz")
    list_filter = ("is_mastered", "consecutive_correct_streak")
