"""Essays admin."""
from django.contrib import admin
from .models import (
    EssayTopic,
    EssaySubmission,
    AIEvaluation,
    TeacherReview,
    EssayCriterionScore,
    EssayGradingCache,
)


# ---------------------------------------------------------------------------
# Inline: 12-mezon criterion scores
# ---------------------------------------------------------------------------


class EssayCriterionScoreInline(admin.TabularInline):
    model = EssayCriterionScore
    extra = 0
    fields = ["criterion_id", "name", "score", "reason"]
    readonly_fields = ["criterion_id", "name"]
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# Model admins
# ---------------------------------------------------------------------------


@admin.register(EssayTopic)
class EssayTopicAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "word_limit_min", "word_limit_max", "time_limit_minutes", "has_password", "is_active"]
    list_filter = ["category", "is_active"]
    search_fields = ["title"]
    fields = [
        "title", "description", "category",
        "word_limit_min", "word_limit_max", "time_limit_minutes",
        "password", "is_active", "created_by",
    ]

    def has_password(self, obj: EssayTopic) -> bool:
        return bool(obj.password)
    has_password.short_description = "🔒 Parol"
    has_password.boolean = True


@admin.register(EssaySubmission)
class EssaySubmissionAdmin(admin.ModelAdmin):
    list_display = ["student", "topic", "word_count", "status", "total_score", "max_score", "auto_submitted", "graded_at", "password_verified_at"]
    list_filter = ["status", "auto_submitted"]
    search_fields = ["student__email", "topic__title", "essay_text"]
    raw_id_fields = ["student", "topic"]
    readonly_fields = ["total_score", "max_score", "graded_at", "raw_result", "error_message"]
    inlines = [EssayCriterionScoreInline]


@admin.register(AIEvaluation)
class AIEvaluationAdmin(admin.ModelAdmin):
    list_display = ["submission", "total_score", "model_used", "evaluated_at"]
    raw_id_fields = ["submission"]


@admin.register(TeacherReview)
class TeacherReviewAdmin(admin.ModelAdmin):
    list_display = ["submission", "teacher", "final_score", "reviewed_at"]
    raw_id_fields = ["submission", "teacher"]


@admin.register(EssayCriterionScore)
class EssayCriterionScoreAdmin(admin.ModelAdmin):
    list_display = ["submission", "criterion_id", "name", "score", "reason"]
    list_filter = ["criterion_id"]
    search_fields = ["submission__student__email", "name"]
    raw_id_fields = ["submission"]


@admin.register(EssayGradingCache)
class EssayGradingCacheAdmin(admin.ModelAdmin):
    list_display = [
        "short_hash_display",
        "total_score",
        "max_score",
        "hit_count",
        "created_at",
        "last_used_at",
    ]
    list_filter = ["max_score"]
    search_fields = ["text_hash", "essay_text"]
    readonly_fields = [
        "text_hash",
        "essay_text",
        "raw_result",
        "total_score",
        "max_score",
        "hit_count",
        "created_at",
        "last_used_at",
    ]
    ordering = ["-hit_count", "-last_used_at"]

    def short_hash_display(self, obj: EssayGradingCache) -> str:
        """Hashning qisqartirilgan ko'rinishi."""
        return obj.text_hash[:12] + "…"
    short_hash_display.short_description = "Hash"

    def has_add_permission(self, request) -> bool:
        return False  # Cache only created by code, not manually

    def has_change_permission(self, request, obj=None) -> bool:
        return False  # Cache is read-only in admin
