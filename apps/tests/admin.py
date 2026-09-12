"""Admin configuration for tests app."""
from django.contrib import admin

from .models import Choice, Question, StudentAnswer, Test, TestAttempt


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 2
    ordering = ["position"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "test", "question_type", "points", "position")
    list_filter = ("question_type", "test")
    inlines = [ChoiceInline]


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = (
        "title", "course", "difficulty",
        "time_limit_minutes", "max_attempts", "is_active",
    )
    list_filter = ("difficulty", "is_active", "course")
    search_fields = ("title",)


class StudentAnswerInline(admin.TabularInline):
    model = StudentAnswer
    extra = 0
    readonly_fields = ("question", "is_correct", "answered_at")


@admin.register(TestAttempt)
class TestAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "student", "test", "status",
        "score", "percentage", "is_passed",
        "started_at",
    )
    list_filter = ("status", "is_passed")
    search_fields = ("student__email", "test__title")
    inlines = [StudentAnswerInline]


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ("attempt", "question", "is_correct", "answered_at")
    list_filter = ("is_correct",)
