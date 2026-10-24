from rest_framework import serializers
from .models import VocabularyPack, StudentWordMistake


class VocabularyPackSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.get_full_name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True, default="")

    class Meta:
        model = VocabularyPack
        fields = [
            "id",
            "title",
            "subject",
            "raw_words_text",
            "word_count",
            "exercises_data",
            "group",
            "group_name",
            "teacher",
            "teacher_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "word_count", "teacher", "created_at", "updated_at"]


class StudentWordMistakeSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)

    class Meta:
        model = StudentWordMistake
        fields = [
            "id",
            "student",
            "student_name",
            "word",
            "definition",
            "translation_uz",
            "mistake_count",
            "consecutive_correct_streak",
            "is_mastered",
            "last_reviewed_at",
            "next_review_at",
        ]
        read_only_fields = ["id", "student", "last_reviewed_at"]
