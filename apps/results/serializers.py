"""
Results serializers — Result list, detail, and analytics.

Read-only serializers for the analytics dashboard and student result views.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .models import Certificate, Result


# ---------------------------------------------------------------------------
# Result Serializers
# ---------------------------------------------------------------------------


class ResultListSerializer(serializers.ModelSerializer):
    """
    Natija list serializer — tez yuklash uchun lightweight.
    Dashboard'da ishlatiladi.
    """

    test_title = serializers.CharField(source="test.title", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    student_name = serializers.SerializerMethodField()
    certificate_status = serializers.SerializerMethodField()
    bmb_grade = serializers.CharField(read_only=True)
    bmb_info = serializers.DictField(read_only=True)

    class Meta:
        model = Result
        fields = [
            "id",
            "test",
            "test_title",
            "course",
            "course_title",
            "student_name",
            "score",
            "max_score",
            "percentage",
            "is_passed",
            "time_taken_seconds",
            "calculated_at",
            "grading_status",
            "certificate_status",
            "bmb_grade",
            "bmb_info",
        ]

    def get_certificate_status(self, obj: Result) -> str:
        from apps.certificates.services.generation import (
            certificate_status,
            resolve_profile,
        )

        is_milliy = getattr(obj, "is_milliy", None)
        profile = None
        if is_milliy:
            profile = getattr(obj.test, "scoring_profile", None)
            if profile is None:
                # Resolve the shared fallback once per page, not once per row.
                profile = self.context.get("default_scoring_profile")
                if profile is None:
                    profile = resolve_profile(obj.test)
                    self.context["default_scoring_profile"] = profile
        return certificate_status(obj, is_milliy=is_milliy, profile=profile)

    def get_student_name(self, obj: Result) -> str:
        return obj.student.get_full_name()


class ResultDetailSerializer(serializers.ModelSerializer):
    """
    Natija detail serializer — to'liq tafsilotlar.
    Qaysi savollarda xato qilganini ko'rsatadi.
    """

    test_title = serializers.CharField(source="test.title", read_only=True)
    course_title = serializers.CharField(source="course.title", read_only=True)
    student_name = serializers.SerializerMethodField()
    question_details = serializers.SerializerMethodField()
    certificate_info = serializers.SerializerMethodField()
    section_scores = serializers.SerializerMethodField()
    certificate_status = serializers.SerializerMethodField()
    bmb_grade = serializers.CharField(read_only=True)
    bmb_info = serializers.DictField(read_only=True)

    class Meta:
        model = Result
        fields = [
            "id",
            "test",
            "test_title",
            "course",
            "course_title",
            "student_name",
            "total_questions",
            "correct_answers",
            "wrong_answers",
            "unanswered",
            "score",
            "max_score",
            "percentage",
            "is_passed",
            "time_taken_seconds",
            "grading_status",
            "objective_score",
            "writing_score",
            "scoring_version",
            "rubric_version",
            "question_details",
            "section_scores",
            "certificate_status",
            "certificate_info",
            "calculated_at",
            "bmb_grade",
            "bmb_info",
        ]

    def get_student_name(self, obj: Result) -> str:
        return obj.student.get_full_name()

    def get_section_scores(self, obj: Result) -> list[dict[str, Any]]:
        """Bo'lim kesimidagi ballar (obyektiv + yozma)."""
        return [
            {
                "section_code": s.section_code,
                "section_name": s.section_name,
                "earned": str(s.earned),
                "maximum": str(s.maximum),
                "weight": str(s.weight),
            }
            for s in obj.section_scores.order_by("id")
        ]

    def get_certificate_status(self, obj: Result) -> str:
        """Canonical eligibility state (eligible only with verified rules)."""
        from apps.certificates.services.generation import certificate_status

        return certificate_status(obj)

    def get_question_details(self, obj: Result) -> list[dict[str, Any]]:
        """
        Har bir savol uchun batafsil ma'lumot:
        - Savol matni
        - Student tanlagan variantlar
        - To'g'ri javoblar
        - Ball olinganmi?
        """
        attempt = obj.attempt
        request = self.context.get("request")
        user = getattr(request, "user", None)
        reveal_answers = bool(obj.test.show_results_immediately)
        if not reveal_answers and user:
            from apps.accounts.access import is_platform_admin

            reveal_answers = is_platform_admin(user) or (
                getattr(user, "role", None) == "teacher"
                and obj.course.teacher_id == user.pk
            )

        # Barcha savollarni olish
        questions = (
            obj.test.questions.select_related(
                "section",
            )
            .prefetch_related(
                "choices",
                "student_answers",
                "student_answers__selected_choices",
                "gap_blanks",
                "matching_prompts__correct_pair",
                "matching_prompts__correct_pair__correct_option",
                "matching_options",
            )
            .order_by("position")
        )

        # Student javoblari xaritasi
        answers_map: dict[int, Any] = {}
        for answer in attempt.answers.select_related("question").prefetch_related(
            "selected_choices",
            "gap_responses",
            "matching_responses",
        ):
            answers_map[answer.question_id] = answer

        result = []
        for q in questions:
            answer = answers_map.get(q.id)

            # Respect the instructor's answer-release setting. Students and
            # parents must not infer answer keys or per-question correctness
            # while feedback is withheld; authorized course staff can review.
            correct_choices = (
                list(q.choices.filter(is_correct=True).values("id", "text"))
                if reveal_answers
                else []
            )

            # Student tanlangan
            selected = []
            is_correct = None
            gap_review: list[dict[str, Any]] = []
            matching_review: list[dict[str, Any]] = []
            written_review: dict[str, Any] | None = None
            student_text_answer = ""
            correct_text_answer = ""

            if reveal_answers and q.correct_text:
                raw_keys = [k.strip() for k in q.correct_text.split("|") if k.strip()]
                correct_text_answer = raw_keys[0] if raw_keys else q.correct_text
                if not correct_choices:
                    correct_choices = [{"id": 0, "text": correct_text_answer}]

            if answer:
                student_text_answer = (answer.text_answer or "").strip()
                selected = list(answer.selected_choices.values("id", "text"))
                if not selected and student_text_answer:
                    selected = [{"id": 0, "text": student_text_answer}]

                is_correct = answer.is_correct if reveal_answers else None
                if q.question_type == "matching":
                    option_text = {o.id: o.text for o in q.matching_options.all()}
                    for prompt in q.matching_prompts.all().order_by("position"):
                        pair = getattr(prompt, "correct_pair", None)
                        correct_id = pair.correct_option_id if pair else None
                        chosen = None
                        try:
                            mr = answer.matching_responses.get(prompt=prompt)
                            chosen = mr.selected_option_id
                        except Exception:
                            chosen = None
                        matching_review.append(
                            {
                                "prompt_id": prompt.id,
                                "prompt_text": prompt.text,
                                "selected_option_id": chosen,
                                "selected_text": option_text.get(chosen, "")
                                if chosen
                                else "",
                                "correct_option_id": correct_id
                                if reveal_answers
                                else None,
                                "correct_text": (
                                    option_text.get(correct_id, "")
                                    if reveal_answers and correct_id
                                    else ""
                                ),
                            }
                        )
                elif q.question_type == "gap_fill":
                    accepted: dict[int, list[str]] = {}
                    for blank in q.gap_blanks.all():
                        accepted.setdefault(blank.position, []).append(
                            blank.answer_text
                        )
                    given = {
                        gr.blank_position: gr.response_text
                        for gr in answer.gap_responses.all()
                    }
                    for pos in sorted(accepted):
                        gap_review.append(
                            {
                                "position": pos,
                                "response": given.get(pos, ""),
                                "accepted": accepted[pos] if reveal_answers else [],
                            }
                        )
                elif q.question_type == "written":
                    written_review = {
                        "text": answer.written_text,
                        "word_count": answer.written_word_count,
                    }

            result.append(
                {
                    "question_id": q.id,
                    "question_text": q.text,
                    "question_type": q.question_type,
                    "points": q.points,
                    "section_id": q.section_id,
                    "correct_choices": correct_choices,
                    "selected_choices": selected,
                    "student_answer_text": student_text_answer,
                    "correct_text": correct_text_answer,
                    "gap_review": gap_review,
                    "matching_review": matching_review,
                    "written_review": written_review,
                    "is_correct": is_correct,
                    "explanation": (
                        q.explanation if reveal_answers and is_correct is False else ""
                    ),
                }
            )

        return result

    def get_certificate_info(self, obj: Result) -> dict[str, Any] | None:
        """Agar sertifikat bo'lsa, uning ma'lumotlarini qaytarish."""
        try:
            cert = obj.certificate
            return {
                "certificate_number": cert.certificate_number,
                "status": cert.status,
                "issued_at": cert.issued_at,
                "file_url": cert.file.url if cert.file else None,
            }
        except Certificate.DoesNotExist:
            return None


class ResultStatsSerializer(serializers.Serializer):
    """
    Umumiy statistika — dashboard uchun.
    """

    total_tests_taken = serializers.IntegerField()
    total_passed = serializers.IntegerField()
    total_failed = serializers.IntegerField()
    average_percentage = serializers.FloatField()
    best_percentage = serializers.FloatField()
    total_time_spent_seconds = serializers.IntegerField()
