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

def _order_questions(queryset, shuffle: bool) -> list:
    """Deterministic order unless the test shuffles (display-only)."""
    items = list(queryset)
    if shuffle:
        import random
        random.shuffle(items)
    return items


def _passage_payload(passage) -> dict[str, Any] | None:
    """Passage content for students — text only, never answer keys."""
    if passage is None:
        return None
    return {
        "id": passage.id,
        "title": passage.title,
        "content": passage.content,
        "source": passage.source,
        "order": passage.order,
    }


def _student_question_payload(
    q, *, shuffle_choices: bool, saved: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One question for student APIs. NEVER includes answer keys:
    no is_correct, no accepted gap answers, no matching mappings."""
    saved = saved or {}
    choices = list(q.choices.all())
    if shuffle_choices:
        import random
        random.shuffle(choices)
    payload: dict[str, Any] = {
        "id": q.id,
        "text": q.text,
        "question_type": q.question_type,
        "points": q.points,
        "position": q.position,
        "section_id": q.section_id,
        "passage": _passage_payload(getattr(q, "reading_passage", None)),
        "choices": [
            {"id": c.id, "text": c.text, "position": c.position}
            for c in choices
        ],
    }
    if q.question_type == "gap_fill":
        payload["gaps"] = [
            {"position": pos} for pos in sorted({b.position for b in q.gap_blanks.all()})
        ]
        payload["gap_answers"] = saved.get("gap_answers", {})
    elif q.question_type == "matching":
        payload["prompts"] = [
            {"id": p.id, "text": p.text, "position": p.position}
            for p in sorted(q.matching_prompts.all(), key=lambda p: p.position)
        ]
        options = list(q.matching_options.all())
        if shuffle_choices:
            import random
            random.shuffle(options)
        payload["matching_options"] = [
            {"id": o.id, "text": o.text} for o in options
        ]
        payload["matching"] = saved.get("matching", {})
    elif q.question_type == "written":
        cfg = q.config or {}
        payload["written"] = {
            "min_words": int(cfg.get("min_words", 0) or 0),
            "max_words": int(cfg.get("max_words", 0) or 0),
        }
        payload["written_text"] = saved.get("written_text", "")
        payload["written_word_count"] = saved.get("written_word_count", 0)
    else:
        payload["selected_choice_ids"] = saved.get("selected_choice_ids", [])
        payload["text_answer"] = saved.get("text_answer", "")
    return payload


def _sections_payload(test) -> list[dict[str, Any]]:
    return [
        {
            "id": s.id, "name": s.name, "code": s.code,
            "order": s.order, "duration_minutes": s.duration_minutes,
            "weight": str(s.weight),
        }
        for s in test.sections.order_by("order")
    ]


def _passages_payload(test) -> list[dict[str, Any]]:
    return [
        p for p in (
            _passage_payload(p) for p in test.passages.order_by("order")
        ) if p is not None
    ]


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
    sections = serializers.SerializerMethodField()
    passages = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = [
            "id", "title", "description", "course",
            "difficulty", "time_limit_minutes", "max_attempts",
            "pass_percentage", "total_questions", "total_points",
            "has_time_limit", "shuffle_questions", "shuffle_choices",
            "show_results_immediately", "questions", "sections", "passages",
        ]

    def get_questions(self, obj: Test) -> list[dict[str, Any]]:
        """
        Savollarni olish — shuffle=True bo'lsa tasodifiy tartibda.
        shuffle_choices=True bo'lsa variantlar ham aralashtiriladi.
        Kalitlar (to'g'ri javoblar) hech qachon chiqmaydi.
        """
        queryset = obj.questions.select_related(
            "section", "reading_passage",
        ).prefetch_related(
            "choices", "gap_blanks", "matching_prompts", "matching_options",
        ).order_by("position")
        questions_list = _order_questions(queryset, bool(obj.shuffle_questions))
        return [
            _student_question_payload(q, shuffle_choices=bool(obj.shuffle_choices))
            for q in questions_list
        ]

    def get_sections(self, obj: Test) -> list[dict[str, Any]]:
        return _sections_payload(obj)

    def get_passages(self, obj: Test) -> list[dict[str, Any]]:
        return _passages_payload(obj)


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
    sections = serializers.SerializerMethodField()
    passages = serializers.SerializerMethodField()
    section_progress = serializers.SerializerMethodField()

    class Meta:
        model = TestAttempt
        fields = [
            "id", "test", "test_title", "status",
            "started_at", "completed_at",
            "score", "percentage", "is_passed",
            "remaining_seconds", "questions", "answered_count",
            "sections", "passages", "section_progress",
        ]
        read_only_fields = fields

    def get_remaining_seconds(self, obj: TestAttempt) -> int | None:
        return obj.remaining_seconds

    def get_answered_count(self, obj: TestAttempt) -> int:
        return obj.answers.count()

    def get_sections(self, obj: TestAttempt) -> list[dict[str, Any]]:
        return _sections_payload(obj.test)

    def get_passages(self, obj: TestAttempt) -> list[dict[str, Any]]:
        return _passages_payload(obj.test)

    def get_section_progress(self, obj: TestAttempt) -> list[dict[str, Any]]:
        out = []
        for progress in obj.section_progress.select_related("section"):
            out.append({
                "section_id": progress.section_id,
                "remaining_seconds": progress.remaining_seconds,
                "is_expired": progress.is_expired,
                "completed": progress.completed_at is not None,
            })
        return out

    def get_questions(self, obj: TestAttempt) -> list[dict[str, Any]]:
        """
        Savollar + oldingi javoblar bilan (barcha turlar).
        Student qaysi variantlarni tanlaganini ko'radi; kalitlar chiqmaydi.
        """
        test = obj.test
        questions = test.questions.select_related(
            "section", "reading_passage",
        ).prefetch_related(
            "choices", "gap_blanks", "matching_prompts", "matching_options",
            "student_answers", "student_answers__selected_choices",
        ).order_by("position")
        questions_list = _order_questions(questions, bool(test.shuffle_questions))

        # Oldingi javoblar xaritasi (bitta query to'plami, Python'da)
        saved_map: dict[int, dict[str, Any]] = {}
        answers = list(
            obj.answers.select_related("question").prefetch_related(
                "selected_choices", "gap_responses", "matching_responses",
            )
        )
        for answer in answers:
            choice_ids = list(
                answer.selected_choices.values_list("id", flat=True)
            )
            saved_map[answer.question_id] = {
                "selected_choice_ids": choice_ids,
                "text_answer": answer.text_answer,
                "gap_answers": {
                    str(gr.blank_position): gr.response_text
                    for gr in answer.gap_responses.all()
                },
                "matching": {
                    str(mr.prompt_id): mr.selected_option_id
                    for mr in answer.matching_responses.all()
                },
                "written_text": answer.written_text,
                "written_word_count": answer.written_word_count,
            }

        return [
            _student_question_payload(
                q,
                shuffle_choices=bool(test.shuffle_choices),
                saved=saved_map.get(q.id),
            )
            for q in questions_list
        ]


# ---------------------------------------------------------------------------
# SaveAnswer Serializer
# ---------------------------------------------------------------------------

class SaveAnswerSerializer(serializers.Serializer):
    """Javobni auto-save qilish uchun serializer (barcha savol turlari)."""

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
    gap_answers = serializers.DictField(
        child=serializers.CharField(allow_blank=True, max_length=200),
        required=False,
        default=dict,
        help_text="GAP_FILL: {bo'shliq_pozitsiyasi: javob_matni}.",
    )
    matching = serializers.DictField(
        required=False,
        default=dict,
        help_text="MATCHING: {prompt_id: option_id}.",
    )
    written_text = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="WRITTEN qoralama matni (uzun; autosave).",
    )

    def validate_choice_ids(self, value: list[int]) -> list[int]:
        """Choice ID lar musbat son ekanligini tekshirish."""
        if any(cid <= 0 for cid in value):
            raise serializers.ValidationError(
                "Variant ID lari musbat son bo'lishi kerak."
            )
        return value

    def validate_matching(self, value: dict) -> dict:
        """Matching mapping shakli: {prompt_id: option_id|null}."""
        cleaned: dict[int, int | None] = {}
        for raw_pid, raw_oid in (value or {}).items():
            try:
                pid = int(raw_pid)
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    "Prompt ID butun son bo'lishi kerak."
                )
            if pid <= 0:
                raise serializers.ValidationError(
                    "Prompt ID musbat son bo'lishi kerak."
                )
            if raw_oid in (None, ""):
                cleaned[pid] = None
                continue
            try:
                oid = int(raw_oid)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    "Option ID butun son bo'lishi kerak."
                )
            if oid <= 0:
                raise serializers.ValidationError(
                    "Option ID musbat son bo'lishi kerak."
                )
            cleaned[pid] = oid
        return cleaned

    def validate_gap_answers(self, value: dict) -> dict:
        """Gap mapping shakli: {position: matn}."""
        cleaned: dict[int, str] = {}
        for raw_pos, raw_text in (value or {}).items():
            try:
                pos = int(raw_pos)
            except (TypeError, ValueError):
                raise serializers.ValidationError(
                    "Bo'shliq pozitsiyasi butun son bo'lishi kerak."
                )
            if pos < 0:
                raise serializers.ValidationError(
                    "Bo'shliq pozitsiyasi manfiy bo'lmasligi kerak."
                )
            cleaned[pos] = str(raw_text or "")[:200]
        return cleaned
