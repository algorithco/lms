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

import logging

from typing import Any

from rest_framework import serializers

from .models import Choice, Question, StudentAnswer, Test, TestAttempt

logger = logging.getLogger(__name__)


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
        fields = [
            "id",
            "passage",
            "text",
            "question_type",
            "points",
            "position",
            "choices",
        ]


class QuestionAdminSerializer(serializers.ModelSerializer):
    """Savol serializer — admin/teacher ko'rinishi."""

    choices = ChoiceDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "text",
            "question_type",
            "points",
            "explanation",
            "position",
            "choices",
        ]


# ---------------------------------------------------------------------------
# Test Serializers
# ---------------------------------------------------------------------------


def _order_questions(queryset, shuffle: bool) -> list:
    """Deterministic order unless the test shuffles (display-only)."""
    try:
        items = list(queryset)
        if shuffle:
            import random

            random.shuffle(items)
        return items
    except Exception as exc:
        logger.warning("Error ordering questions: %s", exc)
        return []


def _passage_payload(passage) -> dict[str, Any] | None:
    """Passage content for students — text only, never answer keys."""
    if not passage:
        return None
    try:
        if isinstance(passage, str):
            if not passage.strip():
                return None
            return {
                "id": 0,
                "title": "",
                "content": passage,
                "audio_url": "",
                "source": "",
                "order": 0,
            }
        return {
            "id": getattr(passage, "id", 0) or 0,
            "title": getattr(passage, "title", "") or "",
            "content": getattr(passage, "content", "") or "",
            "audio_url": getattr(passage, "audio_url", "") or "",
            "source": getattr(passage, "source", "") or "",
            "order": getattr(passage, "order", 0) or 0,
        }
    except Exception as exc:
        logger.warning("Error serializing passage: %s", exc)
        return None


def _student_question_payload(
    q,
    *,
    shuffle_choices: bool,
    saved: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One question for student APIs. NEVER includes answer keys:
    no is_correct, no accepted gap answers, no matching mappings."""
    saved = saved or {}
    try:
        choices = list(q.choices.all())
    except Exception:
        choices = []
    if shuffle_choices:
        import random

        random.shuffle(choices)

    passage_obj = getattr(q, "reading_passage", None)
    if not passage_obj and getattr(q, "passage", None):
        passage_obj = q.passage

    payload: dict[str, Any] = {
        "id": getattr(q, "id", 0),
        "text": getattr(q, "text", "") or "",
        "question_type": getattr(q, "question_type", "single") or "single",
        "points": getattr(q, "points", 1) or 1,
        "position": getattr(q, "position", 1) or 1,
        "section_id": getattr(q, "section_id", None),
        "passage": _passage_payload(passage_obj),
        "choices": [
            {
                "id": getattr(c, "id", 0),
                "text": getattr(c, "text", "") or "",
                "position": getattr(c, "position", 0) or 0,
            }
            for c in choices
        ],
    }

    qtype = getattr(q, "question_type", "single")
    if qtype == "gap_fill":
        gap_blanks = getattr(q, "gap_blanks", None)
        try:
            payload["gaps"] = (
                [
                    {"position": pos}
                    for pos in sorted(
                        {getattr(b, "position", 1) for b in gap_blanks.all()}
                    )
                ]
                if gap_blanks
                else []
            )
        except Exception:
            payload["gaps"] = []
        payload["gap_answers"] = saved.get("gap_answers", {})
    elif qtype == "matching":
        matching_prompts = getattr(q, "matching_prompts", None)
        try:
            payload["prompts"] = (
                [
                    {
                        "id": getattr(p, "id", 0),
                        "text": getattr(p, "text", "") or "",
                        "position": getattr(p, "position", 0) or 0,
                    }
                    for p in sorted(
                        matching_prompts.all(), key=lambda p: getattr(p, "position", 0)
                    )
                ]
                if matching_prompts
                else []
            )
        except Exception:
            payload["prompts"] = []

        matching_options = getattr(q, "matching_options", None)
        try:
            options = list(matching_options.all()) if matching_options else []
        except Exception:
            options = []
        if shuffle_choices:
            import random

            random.shuffle(options)
        payload["matching_options"] = [
            {"id": getattr(o, "id", 0), "text": getattr(o, "text", "") or ""}
            for o in options
        ]
        payload["matching"] = saved.get("matching", {})
    elif qtype == "written":
        cfg = getattr(q, "config", None) or {}
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
    if not test or not hasattr(test, "sections"):
        return []
    try:
        return [
            {
                "id": getattr(s, "id", 0),
                "name": getattr(s, "name", "") or "",
                "code": getattr(s, "code", "") or "",
                "audio_url": getattr(s, "audio_url", "") or "",
                "order": getattr(s, "order", 0) or 0,
                "duration_minutes": getattr(s, "duration_minutes", 0) or 0,
                "weight": str(getattr(s, "weight", 1)),
            }
            for s in test.sections.order_by("order")
        ]
    except Exception as exc:
        logger.warning("Error serializing sections: %s", exc)
        return []


def _passages_payload(test) -> list[dict[str, Any]]:
    if not test or not hasattr(test, "passages"):
        return []
    try:
        return [
            p
            for p in (_passage_payload(p) for p in test.passages.order_by("order"))
            if p is not None
        ]
    except Exception as exc:
        logger.warning("Error serializing passages: %s", exc)
        return []


class TestListSerializer(serializers.ModelSerializer):
    """Test list serializer — lightweight, serveralarda ishlatiladi."""

    total_questions = serializers.IntegerField(read_only=True)
    course_title = serializers.CharField(
        source="course.title", read_only=True, default=""
    )
    category_slug = serializers.CharField(
        source="course.category.slug", read_only=True, default=""
    )
    category_name = serializers.CharField(
        source="course.category.name", read_only=True, default=""
    )
    subject = serializers.SerializerMethodField()
    exam_type = serializers.CharField(read_only=True)
    audio_url = serializers.SerializerMethodField()
    is_strict_mode = serializers.SerializerMethodField()
    has_pin = serializers.SerializerMethodField()
    strict_anti_cheat = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = [
            "id",
            "subject",
            "title",
            "description",
            "course",
            "course_title",
            "category_slug",
            "category_name",
            "mock_code",
            "audio_url",
            "is_strict_mode",
            "exam_type",
            "difficulty",
            "time_limit_minutes",
            "max_attempts",
            "pass_percentage",
            "total_questions",
            "access_type",
            "has_pin",
            "strict_anti_cheat",
            "auto_archive_on_completion",
            "is_active",
            "created_at",
        ]

    def get_subject(self, obj: Test) -> str:
        return getattr(obj, "subject", "uzbek") or "uzbek"

    def get_audio_url(self, obj: Test) -> str:
        return getattr(obj, "audio_url", "") or ""

    def get_is_strict_mode(self, obj: Test) -> bool:
        return bool(getattr(obj, "is_strict_mode", False) or getattr(obj, "strict_anti_cheat", False))

    def get_has_pin(self, obj: Test) -> bool:
        return bool(obj.access_pin and obj.access_pin.strip())

    def get_strict_anti_cheat(self, obj: Test) -> bool:
        return bool(getattr(obj, "strict_anti_cheat", False) or getattr(obj, "is_strict_mode", False))


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
    subject = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()
    is_strict_mode = serializers.SerializerMethodField()
    has_pin = serializers.SerializerMethodField()
    requires_pin = serializers.SerializerMethodField()
    strict_anti_cheat = serializers.SerializerMethodField()
    assigned_group_name = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = [
            "id",
            "subject",
            "title",
            "description",
            "course",
            "audio_url",
            "is_strict_mode",
            "difficulty",
            "time_limit_minutes",
            "max_attempts",
            "pass_percentage",
            "total_questions",
            "total_points",
            "has_time_limit",
            "shuffle_questions",
            "shuffle_choices",
            "show_results_immediately",
            "access_type",
            "has_pin",
            "requires_pin",
            "strict_anti_cheat",
            "auto_archive_on_completion",
            "assigned_group",
            "assigned_group_name",
            "questions",
            "sections",
            "passages",
        ]

    def get_subject(self, obj: Test) -> str:
        return getattr(obj, "subject", "uzbek") or "uzbek"

    def get_audio_url(self, obj: Test) -> str:
        return getattr(obj, "audio_url", "") or ""

    def get_is_strict_mode(self, obj: Test) -> bool:
        return bool(getattr(obj, "is_strict_mode", False) or getattr(obj, "strict_anti_cheat", False))

    def get_has_pin(self, obj: Test) -> bool:
        return bool(obj.access_pin and obj.access_pin.strip())

    def get_requires_pin(self, obj: Test) -> bool:
        return bool(obj.access_pin and obj.access_pin.strip())

    def get_strict_anti_cheat(self, obj: Test) -> bool:
        return bool(getattr(obj, "strict_anti_cheat", False) or getattr(obj, "is_strict_mode", False))

    def get_assigned_group_name(self, obj: Test) -> str:
        return obj.assigned_group.name if obj.assigned_group else ""

    def get_questions(self, obj: Test) -> list[dict[str, Any]]:
        """
        Savollarni olish — shuffle=True bo'lsa tasodifiy tartibda.
        shuffle_choices=True bo'lsa variantlar ham aralashtiriladi.
        Kalitlar (to'g'ri javoblar) hech qachon chiqmaydi.
        """
        try:
            queryset = (
                obj.questions.select_related(
                    "section",
                    "reading_passage",
                )
                .prefetch_related(
                    "choices",
                    "gap_blanks",
                    "matching_prompts",
                    "matching_options",
                )
                .order_by("position")
            )
            questions_list = _order_questions(
                queryset, bool(getattr(obj, "shuffle_questions", False))
            )
            return [
                _student_question_payload(
                    q, shuffle_choices=bool(getattr(obj, "shuffle_choices", True))
                )
                for q in questions_list
            ]
        except Exception as exc:
            logger.exception(
                "Error serializing test questions for test %s: %s",
                getattr(obj, "id", None),
                exc,
            )
            return []

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

    test_title = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()
    is_strict_mode = serializers.SerializerMethodField()
    remaining_seconds = serializers.SerializerMethodField()
    time_limit_minutes = serializers.SerializerMethodField()
    total_questions = serializers.SerializerMethodField()
    answered_count = serializers.SerializerMethodField()

    class Meta:
        model = TestAttempt
        fields = [
            "id",
            "test",
            "test_title",
            "subject",
            "audio_url",
            "is_strict_mode",
            "mode",
            "raw_score",
            "band_score",
            "cefr_level",
            "section_scores",
            "status",
            "started_at",
            "completed_at",
            "score",
            "percentage",
            "is_passed",
            "violation_count",
            "cheating_detected",
            "remaining_seconds",
            "time_limit_minutes",
            "total_questions",
            "answered_count",
        ]
        read_only_fields = fields

    def get_test_title(self, obj: TestAttempt) -> str:
        test = getattr(obj, "test", None)
        return getattr(test, "title", "") if test else ""

    def get_subject(self, obj: TestAttempt) -> str:
        test = getattr(obj, "test", None)
        return getattr(test, "subject", "uzbek") or "uzbek" if test else "uzbek"

    def get_audio_url(self, obj: TestAttempt) -> str:
        test = getattr(obj, "test", None)
        return getattr(test, "audio_url", "") or "" if test else ""

    def get_is_strict_mode(self, obj: TestAttempt) -> bool:
        if getattr(obj, "mode", None) == "practice":
            return False
        test = getattr(obj, "test", None)
        if test and (getattr(test, "is_strict_mode", False) or getattr(test, "strict_anti_cheat", False)):
            return True
        return getattr(obj, "mode", None) == "strict" 

    def get_time_limit_minutes(self, obj: TestAttempt) -> int:
        test = getattr(obj, "test", None)
        return getattr(test, "time_limit_minutes", 0) or 0 if test else 0

    def get_total_questions(self, obj: TestAttempt) -> int:
        test = getattr(obj, "test", None)
        return getattr(test, "total_questions", 0) or 0 if test else 0

    def get_remaining_seconds(self, obj: TestAttempt) -> int | None:
        """Qolgan vaqt (soniyalarda)."""
        return getattr(obj, "remaining_seconds", None)

    def get_answered_count(self, obj: TestAttempt) -> int:
        """Nechta savolga javob berilgan."""
        return obj.answers.count() if hasattr(obj, "answers") else 0


class AttemptDetailSerializer(serializers.ModelSerializer):
    """
    Attempt detail — savollar va javoblar bilan.
    Aktiv attempt uchun: savollar + oldingi javoblar.
    """

    test_title = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()
    audio_url = serializers.SerializerMethodField()
    is_strict_mode = serializers.SerializerMethodField()
    remaining_seconds = serializers.SerializerMethodField()
    questions = serializers.SerializerMethodField()
    answered_count = serializers.SerializerMethodField()
    sections = serializers.SerializerMethodField()
    passages = serializers.SerializerMethodField()
    section_progress = serializers.SerializerMethodField()

    class Meta:
        model = TestAttempt
        fields = [
            "id",
            "test",
            "test_title",
            "subject",
            "audio_url",
            "is_strict_mode",
            "status",
            "started_at",
            "completed_at",
            "score",
            "percentage",
            "is_passed",
            "violation_count",
            "cheating_detected",
            "remaining_seconds",
            "questions",
            "answered_count",
            "sections",
            "passages",
            "section_progress",
        ]
        read_only_fields = fields

    def get_test_title(self, obj: TestAttempt) -> str:
        test = getattr(obj, "test", None)
        return getattr(test, "title", "") if test else ""

    def get_subject(self, obj: TestAttempt) -> str:
        test = getattr(obj, "test", None)
        return getattr(test, "subject", "uzbek") or "uzbek" if test else "uzbek"

    def get_audio_url(self, obj: TestAttempt) -> str:
        test = getattr(obj, "test", None)
        return getattr(test, "audio_url", "") or "" if test else ""

    def get_is_strict_mode(self, obj: TestAttempt) -> bool:
        test = getattr(obj, "test", None)
        return bool(getattr(test, "is_strict_mode", False)) if test else False

    def get_remaining_seconds(self, obj: TestAttempt) -> int | None:
        return getattr(obj, "remaining_seconds", None)

    def get_answered_count(self, obj: TestAttempt) -> int:
        return obj.answers.count() if hasattr(obj, "answers") else 0

    def get_sections(self, obj: TestAttempt) -> list[dict[str, Any]]:
        test = getattr(obj, "test", None)
        return _sections_payload(test) if test else []

    def get_passages(self, obj: TestAttempt) -> list[dict[str, Any]]:
        test = getattr(obj, "test", None)
        return _passages_payload(test) if test else []

    def get_section_progress(self, obj: TestAttempt) -> list[dict[str, Any]]:
        out = []
        if not hasattr(obj, "section_progress"):
            return []
        try:
            for progress in obj.section_progress.select_related("section"):
                out.append(
                    {
                        "section_id": getattr(progress, "section_id", None),
                        "remaining_seconds": getattr(
                            progress, "remaining_seconds", None
                        ),
                        "is_expired": bool(getattr(progress, "is_expired", False)),
                        "completed": getattr(progress, "completed_at", None)
                        is not None,
                    }
                )
        except Exception as exc:
            logger.warning(
                "Error getting section_progress for attempt %s: %s",
                getattr(obj, "id", None),
                exc,
            )
        return out

    def get_questions(self, obj: TestAttempt) -> list[dict[str, Any]]:
        """
        Savollar + oldingi javoblar bilan (barcha turlar).
        Student qaysi variantlarni tanlaganini ko'radi; kalitlar chiqmaydi.
        """
        try:
            test = getattr(obj, "test", None)
            if not test:
                return []
            questions = (
                test.questions.select_related(
                    "section",
                    "reading_passage",
                )
                .prefetch_related(
                    "choices",
                    "gap_blanks",
                    "matching_prompts",
                    "matching_options",
                    "student_answers",
                    "student_answers__selected_choices",
                )
                .order_by("position")
            )
            questions_list = _order_questions(
                questions, bool(getattr(test, "shuffle_questions", False))
            )

            # Oldingi javoblar xaritasi (bitta query to'plami, Python'da)
            saved_map: dict[int, dict[str, Any]] = {}
            if hasattr(obj, "answers"):
                answers = list(
                    obj.answers.select_related("question").prefetch_related(
                        "selected_choices",
                        "gap_responses",
                        "matching_responses",
                    )
                )
                for answer in answers:
                    choice_ids = list(
                        answer.selected_choices.values_list("id", flat=True)
                    )
                    saved_map[answer.question_id] = {
                        "selected_choice_ids": choice_ids,
                        "text_answer": getattr(answer, "text_answer", "") or "",
                        "gap_answers": {
                            str(getattr(gr, "blank_position", "")): getattr(
                                gr, "response_text", ""
                            )
                            for gr in getattr(answer, "gap_responses", []).all()
                        }
                        if hasattr(answer, "gap_responses")
                        else {},
                        "matching": {
                            str(getattr(mr, "prompt_id", "")): getattr(
                                mr, "selected_option_id", None
                            )
                            for mr in getattr(answer, "matching_responses", []).all()
                        }
                        if hasattr(answer, "matching_responses")
                        else {},
                        "written_text": getattr(answer, "written_text", "") or "",
                        "written_word_count": getattr(answer, "written_word_count", 0)
                        or 0,
                    }

            return [
                _student_question_payload(
                    q,
                    shuffle_choices=bool(getattr(test, "shuffle_choices", True)),
                    saved=saved_map.get(q.id),
                )
                for q in questions_list
            ]
        except Exception as exc:
            logger.exception(
                "Error serializing questions for attempt %s: %s",
                getattr(obj, "id", None),
                exc,
            )
            return []


# ---------------------------------------------------------------------------
# SaveAnswer Serializer
# ---------------------------------------------------------------------------


class SaveAnswerSerializer(serializers.Serializer):
    """Javobni auto-save qilish uchun serializer (barcha savol turlari)."""

    question_id = serializers.IntegerField(
        help_text="Javob berilayotgan savol ID si.",
    )
    test_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Test ID si (ixtiyoriy tekshirish uchun).",
    )
    choice_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        help_text="Tanlangan variant ID lari ro'yxati (choice savollari uchun).",
    )
    selected_option_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Bitta variant tanlanganda (backward compat).",
    )
    selected_choice_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Bitta variant tanlanganda (backward compat).",
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

    def validate(self, attrs):
        choice_ids = list(attrs.get("choice_ids") or [])
        single_opt = attrs.get("selected_option_id") or attrs.get("selected_choice_id")
        if single_opt and single_opt not in choice_ids:
            choice_ids.append(single_opt)
        attrs["choice_ids"] = choice_ids
        return attrs

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
                raise serializers.ValidationError("Prompt ID butun son bo'lishi kerak.")
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
                raise serializers.ValidationError("Option ID butun son bo'lishi kerak.")
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
