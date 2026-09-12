"""
Tests serializers — Test, Question, Attempt, SaveAnswer.

Architecture:
    - TestListSerializer: lightweight for list views.
    - TestDetailSerializer: nested questions + choices (for student view).
    - AttemptSerializer: attempt status + timer info.
    - SaveAnswerSerializer: validates choice_ids.
    - QuestionResultSerializer: per-question grading result.
"""
from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .models import Choice, Question, StudentAnswer, Test, TestAttempt


# ---------------------------------------------------------------------------
# Choice Serializer
# ---------------------------------------------------------------------------

class ChoiceSerializer(serializers.ModelSerializer):
    """Variant serializer — student uchun is_correct yashirilgan."""

    class Meta:
        model = Choice
        fields = ["id", "text", "position"]


class ChoiceDetailSerializer(serializers.ModelSerializer):
    """Variant serializer — admin/teacher uchun is_correct ko'rinadi."""

    class Meta:
        model = Choice
        fields = ["id", "text", "is_correct", "position"]


# ---------------------------------------------------------------------------
# Question Serializers
# ---------------------------------------------------------------------------

class QuestionStudentSerializer(serializers.ModelSerializer):
    """
    Savol serializer — student ko'rinishi.
    To'g'ri javob yashirilgan, variantlar aralashtirilgan bo'lishi mumkin.
    """

    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ["id", "passage", "text", "question_type", "points", "position", "choices"]


class QuestionAdminSerializer(serializers.ModelSerializer):
    """Savol serializer — admin/teacher ko'rinishi."""

    choices = ChoiceDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id", "text", "question_type", "points",
            "explanation", "position", "choices",
        ]


# ---------------------------------------------------------------------------
# Test Serializers
# ---------------------------------------------------------------------------

class TestListSerializer(serializers.ModelSerializer):
    """Test list serializer — lightweight, serveralarda ishlatiladi."""

    total_questions = serializers.IntegerField(read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)

    class Meta:
        model = Test
        fields = [
            "id", "title", "description", "course", "course_title",
            "difficulty", "time_limit_minutes", "max_attempts",
            "pass_percentage", "total_questions", "is_active",
            "created_at",
        ]


class TestDetailSerializer(serializers.ModelSerializer):
    """
    Test detail serializer — student uchun savollar bilan.
    shuffle_questions=True bo'lsa, savollar tartibi aralashtirilgan.
    """

    questions = serializers.SerializerMethodField()
    total_questions = serializers.IntegerField(read_only=True)
    total_points = serializers.IntegerField(read_only=True)
    has_time_limit = serializers.BooleanField(read_only=True)

    class Meta:
        model = Test
        fields = [
            "id", "title", "description", "course",
            "difficulty", "time_limit_minutes", "max_attempts",
            "pass_percentage", "total_questions", "total_points",
            "has_time_limit", "shuffle_questions", "shuffle_choices",
            "show_results_immediately", "questions",
        ]

    def get_questions(self, obj: Test) -> list[dict[str, Any]]:
        """
        Savollarni olish — shuffle=True bo'lsa tasodifiy tartibda.
        shuffle_choices=True bo'lsa variantlar ham aralashtiriladi.
        """
        queryset = obj.questions.prefetch_related("choices").order_by("position")

        # Savollarni aralashtirish
        if obj.shuffle_questions:
            questions_list = list(queryset)
            import random
            random.shuffle(questions_list)
        else:
            questions_list = list(queryset)

        result = []
        for q in questions_list:
            choices = q.choices.all()
            if obj.shuffle_choices:
                choices = list(choices)
                import random
                random.shuffle(choices)

            result.append({
                "id": q.id,
                "text": q.text,
                "question_type": q.question_type,
                "points": q.points,
                "position": q.position,
                "choices": [
                    {"id": c.id, "text": c.text, "position": c.position}
                    for c in choices
                ],
            })

        return result


# ---------------------------------------------------------------------------
# Attempt Serializers
# ---------------------------------------------------------------------------

class AttemptCreateSerializer(serializers.Serializer):
    """Attempt yaratish uchun — faqat test_id kerak."""

    test_id = serializers.IntegerField(
        help_text="Boshlamoqchi bo'lgan test ID si.",
    )


class AttemptSerializer(serializers.ModelSerializer):
    """
    Attempt serializer — status, timer, scoring info.
    Student uchun asosiy ma'lumot manbai.
    """

    test_title = serializers.CharField(source="test.title", read_only=True)
    remaining_seconds = serializers.SerializerMethodField()
    time_limit_minutes = serializers.IntegerField(
        source="test.time_limit_minutes", read_only=True,
    )
    total_questions = serializers.IntegerField(
        source="test.total_questions", read_only=True,
    )
    answered_count = serializers.SerializerMethodField()

    class Meta:
        model = TestAttempt
        fields = [
            "id", "test", "test_title", "status",
            "started_at", "completed_at",
            "score", "percentage", "is_passed",
            "remaining_seconds", "time_limit_minutes",
            "total_questions", "answered_count",
        ]
        read_only_fields = fields

    def get_remaining_seconds(self, obj: TestAttempt) -> int | None:
        """Qolgan vaqt (soniyalarda)."""
        return obj.remaining_seconds

    def get_answered_count(self, obj: TestAttempt) -> int:
        """Nechta savolga javob berilgan."""
        return obj.answers.count()


class AttemptDetailSerializer(serializers.ModelSerializer):
    """
    Attempt detail — savollar va javoblar bilan.
    Aktiv attempt uchun: savollar + oldingi javoblar.
    """

    test_title = serializers.CharField(source="test.title", read_only=True)
    remaining_seconds = serializers.SerializerMethodField()
    questions = serializers.SerializerMethodField()
    answered_count = serializers.SerializerMethodField()

    class Meta:
        model = TestAttempt
        fields = [
            "id", "test", "test_title", "status",
            "started_at", "completed_at",
            "score", "percentage", "is_passed",
            "remaining_seconds", "questions", "answered_count",
        ]
        read_only_fields = fields

    def get_remaining_seconds(self, obj: TestAttempt) -> int | None:
        return obj.remaining_seconds

    def get_answered_count(self, obj: TestAttempt) -> int:
        return obj.answers.count()

    def get_questions(self, obj: TestAttempt) -> list[dict[str, Any]]:
        """
        Savollar + oldingi javoblar bilan.
        Student qaysi variantlarni tanlaganini ko'radi.
        """
        test = obj.test
        questions = test.questions.prefetch_related(
            "choices", "student_answers", "student_answers__selected_choices",
        ).order_by("position")

        if test.shuffle_questions:
            questions_list = list(questions)
            import random
            random.shuffle(questions_list)
        else:
            questions_list = list(questions)

        # Oldingi javoblar xaritasi
        answers_map: dict[int, set[int]] = {}
        for answer in obj.answers.select_related("question").prefetch_related(
            "selected_choices"
        ):
            choice_ids = set(
                answer.selected_choices.values_list("id", flat=True)
            )
            answers_map[answer.question_id] = choice_ids

        result = []
        for q in questions_list:
            choices = q.choices.all()
            if test.shuffle_choices:
                choices = list(choices)
                import random
                random.shuffle(choices)
            else:
                choices = list(choices)

            result.append({
                "id": q.id,
                "text": q.text,
                "question_type": q.question_type,
                "points": q.points,
                "position": q.position,
                "choices": [
                    {
                        "id": c.id,
                        "text": c.text,
                        "position": c.position,
                    }
                    for c in choices
                ],
                "selected_choice_ids": list(answers_map.get(q.id, set())),
            })

        return result


# ---------------------------------------------------------------------------
# SaveAnswer Serializer
# ---------------------------------------------------------------------------

class SaveAnswerSerializer(serializers.Serializer):
    """Javobni auto-save qilish uchun serializer."""

    question_id = serializers.IntegerField(
        help_text="Javob berilayotgan savol ID si.",
    )
    choice_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        help_text="Tanlangan variant ID lari ro'yxati (choice savollari uchun).",
    )
    text_answer = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        max_length=500,
        help_text="Matnli javob (TEXT_MATCH savollari uchun).",
    )

    def validate_choice_ids(self, value: list[int]) -> list[int]:
        """Choice ID lar musbat son ekanligini tekshirish."""
        if any(cid <= 0 for cid in value):
            raise serializers.ValidationError(
                "Variant ID lari musbat son bo'lishi kerak."
            )
        return value
