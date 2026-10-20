"""Admin configuration for tests app."""

from django.contrib import admin

from .models import (
    AttemptSectionProgress,
    Choice,
    ExamScoringProfile,
    ExamSection,
    ExamWrittenBridge,
    GapBlank,
    GapResponse,
    MatchingOption,
    MatchingPair,
    MatchingPrompt,
    MatchingResponse,
    Question,
    ReadingPassage,
    StudentAnswer,
    Test,
    TestAttempt,
)


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 2
    ordering = ["position"]


class GapBlankInline(admin.TabularInline):
    model = GapBlank
    extra = 1
    ordering = ["position"]


class MatchingPromptInline(admin.TabularInline):
    model = MatchingPrompt
    extra = 2
    ordering = ["position"]


class MatchingOptionInline(admin.TabularInline):
    model = MatchingOption
    extra = 2
    ordering = ["position"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "test", "question_type", "points", "position")
    list_filter = ("question_type", "test")
    search_fields = ("text",)

    def get_inlines(self, request, obj=None):
        if obj is None:
            return [ChoiceInline]
        if obj.question_type == "gap_fill":
            return [GapBlankInline]
        if obj.question_type == "matching":
            return [MatchingPromptInline, MatchingOptionInline]
        if obj.question_type in ("single", "multiple"):
            return [ChoiceInline]
        return []


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "course",
        "difficulty",
        "time_limit_minutes",
        "max_attempts",
        "is_active",
        "scoring_profile",
    )
    list_filter = ("difficulty", "is_active", "course")
    search_fields = ("title",)


class StudentAnswerInline(admin.TabularInline):
    model = StudentAnswer
    extra = 0
    readonly_fields = ("question", "is_correct", "answered_at")


@admin.register(ExamSection)
class ExamSectionAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "test", "order", "duration_minutes", "weight")
    list_filter = ("code", "test")


@admin.register(ReadingPassage)
class ReadingPassageAdmin(admin.ModelAdmin):
    list_display = ("title", "test", "section", "order")
    list_filter = ("test",)


@admin.register(GapBlank)
class GapBlankAdmin(admin.ModelAdmin):
    list_display = ("question", "position", "answer_text")
    list_filter = ("question__test",)


@admin.register(MatchingPrompt)
class MatchingPromptAdmin(admin.ModelAdmin):
    list_display = ("question", "position", "text")


@admin.register(MatchingOption)
class MatchingOptionAdmin(admin.ModelAdmin):
    list_display = ("question", "position", "text")


@admin.register(MatchingPair)
class MatchingPairAdmin(admin.ModelAdmin):
    list_display = ("prompt", "correct_option")


@admin.register(ExamWrittenBridge)
class ExamWrittenBridgeAdmin(admin.ModelAdmin):
    list_display = (
        "attempt",
        "question",
        "essay_submission",
        "rubric_version",
        "created_at",
    )
    readonly_fields = ("attempt", "question", "answer", "created_at")


@admin.register(AttemptSectionProgress)
class AttemptSectionProgressAdmin(admin.ModelAdmin):
    list_display = ("attempt", "section", "started_at", "completed_at")
    readonly_fields = ("attempt", "section", "started_at")


@admin.register(ExamScoringProfile)
class ExamScoringProfileAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "version",
        "is_active",
        "is_verified",
        "certificate_min_percentage",
        "created_at",
    )
    list_filter = ("is_active", "is_verified")


@admin.register(GapResponse)
class GapResponseAdmin(admin.ModelAdmin):
    list_display = ("answer", "blank_position", "response_text")
    readonly_fields = ("answer",)


@admin.register(MatchingResponse)
class MatchingResponseAdmin(admin.ModelAdmin):
    list_display = ("answer", "prompt", "selected_option")
    readonly_fields = ("answer",)


@admin.register(TestAttempt)
class TestAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "test",
        "status",
        "score",
        "percentage",
        "is_passed",
        "started_at",
    )
    list_filter = ("status", "is_passed")
    search_fields = ("student__email", "test__title")
    inlines = [StudentAnswerInline]


@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ("attempt", "question", "is_correct", "answered_at")
    list_filter = ("is_correct",)
    readonly_fields = ("written_word_count",)
