"""Essays admin."""
from django.contrib import admin, messages
from django.db.models import Q
from django.utils import timezone

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
    list_display = [
        "student", "topic", "word_count", "status", "total_score", "max_score",
        "grading_source", "auto_submitted", "graded_at", "password_verified_at",
    ]
    list_filter = ["status", "grading_source", "auto_submitted"]
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
    """Operational console for the shared (cross-account) grading cache.

    Read-only by construction. The rows are immutable from the admin so a
    misfired form can never fake or corrupt a grade; every mutation goes
    through the auditable service layer (invalidate / retry / purge), exposed
    here as admin actions.

    Why ``has_change_permission`` is no longer a hard ``False``
    ----------------------------------------------------------
    Django only offers admin *actions* to users with change permission
    (``ModelAdmin.get_actions()`` filters by ``allowed_permissions`` — each
    action below declares ``permissions=("change",)``), and the changelist only
    builds the action form when the user has change permission. A hard ``False``
    therefore hid the whole operational console from everyone. Immutability is
    instead guaranteed by: every field listed in ``readonly_fields`` (the admin
    form has no editable input at all), ``has_add_permission`` /
    ``has_delete_permission`` returning False, and a no-op ``save_model``.
    Permission checks are still delegated to Django, so only staff with the
    real ``essays.change_essaygradingcache`` permission can operate the cache.
    """

    list_display = [
        "short_hash_display",
        "status",
        "score_display",
        "hit_count",
        "reuse_count_display",
        "failure_count",
        "waiting_count",
        "lease_active_display",
        "rubric_version",
        "model_identifier",
        "created_at",
        "completed_at",
        "last_used_at",
    ]
    list_filter = ["status", "provider", "cache_schema_version", "invalidated_at"]
    search_fields = ["text_hash", "essay_text"]
    date_hierarchy = "created_at"
    ordering = ["-hit_count", "-last_used_at"]
    actions = [
        "invalidate_selected",
        "retry_failed_entries",
        "recover_stale_leases",
        "purge_obsolete",
    ]
    readonly_fields = [
        "text_hash",
        "status",
        "score_display",
        "hit_count",
        "reuse_count_display",
        "failure_count",
        "waiting_count",
        "error_summary",
        "lease_active_display",
        "lease_owner",
        "lease_expires_at",
        "invalidated_at",
        "invalidated_reason",
        "text_fingerprint",
        "grading_context_fingerprint",
        "grading_context",
        "rubric_version",
        "prompt_version",
        "model_identifier",
        "provider",
        "cache_schema_version",
        "completed_at",
        "essay_text",
        "raw_result",
        "created_at",
        "last_used_at",
    ]

    # -- read-only columns ---------------------------------------------------

    @admin.display(description="Kesh kaliti", ordering="text_hash")
    def short_hash_display(self, obj: EssayGradingCache) -> str:
        """Hashning qisqartirilgan ko'rinishi."""
        return obj.text_hash[:12] + "…"

    @admin.display(description="Ball", ordering="total_score")
    def score_display(self, obj: EssayGradingCache) -> str:
        return f"{obj.total_score}/{obj.max_score}"

    @admin.display(description="Qayta ishlatilgan", ordering="-hit_count")
    def reuse_count_display(self, obj: EssayGradingCache) -> int:
        """hit_count - 1: dastlabki baholashdan tashqari qayta ishlatishlar."""
        return obj.reuse_count

    @admin.display(description="Ijara faol", boolean=True)
    def lease_active_display(self, obj: EssayGradingCache) -> bool:
        """True when a live worker currently owns the grading lease."""
        return obj.lease_is_active()

    # -- permission / immutability guards -----------------------------------

    def has_add_permission(self, request) -> bool:
        return False  # Cache only created by code, not manually

    def has_delete_permission(self, request, obj=None) -> bool:
        # Also removes the built-in "delete_selected" action: clearing obsolete
        # rows must go through the audited purge action (never a raw bulk delete).
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        # Delegates to Django's real change permission. Actions are gated by it
        # (see the class docstring); the rows themselves stay immutable.
        return super().has_change_permission(request, obj)

    def save_model(self, request, obj, form, change) -> None:
        # No-op on purpose: every field is readonly, so a stray POST must not
        # touch the row (obj.save() would bump last_used_at and fake an access).
        # Mutations belong to the service layer / the actions below.
        pass

    # -- operational actions (change permission only) -----------------------

    @admin.action(
        description="Tanlangan baholarni bekor qilish (invalidate)",
        permissions=("change",),
    )
    def invalidate_selected(self, request, queryset):
        """Stop the selected entries from being reused (history is preserved).

        The evaluation row is kept for audit but is flagged invalid, so the
        next submission for the same cache key is graded again.
        """
        # Lazy import (repo convention for service layer in entrypoints).
        from .services import invalidate_cache_entry

        invalidated = 0
        for entry in queryset:
            invalidate_cache_entry(entry, reason="admin action: invalidate selected")
            invalidated += 1
        self.message_user(
            request,
            f"{invalidated} ta kesh yozuvi bekor qilindi (tarix saqlanadi; "
            "keyingi topshirish qayta baholanadi).",
            level=messages.SUCCESS,
        )

    @admin.action(
        description="Tanlangan xatolik yozuvlarini qayta baholashga tayyorlash",
        permissions=("change",),
    )
    def retry_failed_entries(self, request, queryset):
        """Clear the lease of FAILED entries so grading can be retried.

        Only coordination state is reset — never a score, and never an entry
        whose lease is currently held by a live worker (that would allow two
        workers to grade the same key). The next submission for the key claims
        the row and calls the AI provider again.
        """
        now = timezone.now()
        retryable = (
            Q(status=EssayGradingCache.Status.FAILED)
            | Q(status=EssayGradingCache.Status.PROCESSING, lease_expires_at__lte=now)
            | Q(status=EssayGradingCache.Status.PROCESSING, lease_expires_at__isnull=True)
        )
        total = queryset.count()
        retried = queryset.filter(retryable).update(
            status=EssayGradingCache.Status.PENDING,
            lease_owner="",
            lease_expires_at=None,
        )
        skipped = total - retried
        message = f"{retried} ta yozuv qayta baholash uchun navbatga tushirildi."
        if skipped:
            message += f" {skipped} ta yozuv o'tkazib yuborildi (faol ijara yoki yakunlangan)."
        self.message_user(request, message, level=messages.SUCCESS)

    @admin.action(
        description="Eskirgan (stale) ijaralarni bo'shatish",
        permissions=("change",),
    )
    def recover_stale_leases(self, request, queryset):
        """Release every abandoned PROCESSING lease (selection is ignored).

        A worker that dies mid-request would otherwise leave its cache key
        stuck in PROCESSING forever; recovery is global by design.
        """
        from .services import recover_stale_grading_cache_entries

        recovered = recover_stale_grading_cache_entries()
        self.message_user(
            request,
            f"{recovered} ta eskirgan ijara bo'shatildi (qayta baholash mumkin).",
            level=messages.SUCCESS,
        )

    @admin.action(
        description="Eskirgan kesh yozuvlarini tozalash (purge)",
        permissions=("change",),
    )
    def purge_obsolete(self, request, queryset):
        """Delete entries that can never be reused (selection is ignored).

        Obsolete = older cache schema version, invalidated, or past the cache
        lifetime. Completed, schema-current rows are preserved, and a row with
        a live lease is never deleted.
        """
        from .services import purge_obsolete_cache_entries

        deleted = purge_obsolete_cache_entries()
        self.message_user(
            request,
            f"{deleted} ta eskirgan kesh yozuvi o'chirildi.",
            level=messages.SUCCESS,
        )
