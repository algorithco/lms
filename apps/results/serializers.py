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

    class Meta:
        model = Result
        fields = [
            "id", "test", "test_title", "course", "course_title",
            "student_name", "score", "max_score", "percentage",
            "is_passed", "time_taken_seconds", "calculated_at",
        ]

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

    class Meta:
        model = Result
        fields = [
            "id", "test", "test_title", "course", "course_title",
            "student_name", "total_questions", "correct_answers",
            "wrong_answers", "unanswered", "score", "max_score",
            "percentage", "is_passed", "time_taken_seconds",
            "question_details", "certificate_info", "calculated_at",
        ]

    def get_student_name(self, obj: Result) -> str:
        return obj.student.get_full_name()

    def get_question_details(self, obj: Result) -> list[dict[str, Any]]:
        """
        Har bir savol uchun batafsil ma'lumot:
        - Savol matni
        - Student tanlagan variantlar
        - To'g'ri javoblar
        - Ball olinganmi?
        """
        attempt = obj.attempt

        # Barcha savollarni olish
        questions = obj.test.questions.prefetch_related(
            "choices", "student_answers", "student_answers__selected_choices",
        ).order_by("position")

        # Student javoblari xaritasi
        answers_map: dict[int, Any] = {}
        for answer in attempt.answers.select_related("question").prefetch_related(
            "selected_choices"
        ):
            answers_map[answer.question_id] = answer

        result = []
        for q in questions:
            answer = answers_map.get(q.id)

            # To'g'ri javoblar
            correct_choices = list(
                q.choices.filter(is_correct=True).values("id", "text")
            )

            # Student tanlangan
            selected = []
            is_correct = None
            if answer:
                selected = list(
                    answer.selected_choices.values("id", "text")
                )
                is_correct = answer.is_correct

            result.append({
                "question_id": q.id,
                "question_text": q.text,
                "question_type": q.question_type,
                "points": q.points,
                "correct_choices": correct_choices,
                "selected_choices": selected,
                "is_correct": is_correct,
                "explanation": q.explanation if is_correct is False else "",
            })

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
