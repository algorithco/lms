"""Serializers for the React API — explicit fields, no behavior changes."""
from rest_framework import serializers

from apps.accounts.models import ParentStudentLink, User
from apps.courses.models import Course, StudentGroup
from apps.essays.models import EssayTopic
from apps.games.models import Game, GameLevel, UserGameScore
from apps.payments.models import PaymentHistory, SubscriptionPlan, UserSubscription
from apps.tests.models import Choice, Question, Test


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------
class GameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Game
        fields = [
            "id", "name", "slug", "description", "icon_emoji",
            "xp_per_correct", "coins_per_correct", "combo_multiplier",
            "sort_order",
        ]


class GameLevelMetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = GameLevel
        fields = ["id", "title", "difficulty", "hint", "time_limit_seconds", "sort_order"]


class UserGameScoreSerializer(serializers.ModelSerializer):
    game_slug = serializers.CharField(source="game.slug", read_only=True)
    game_name = serializers.CharField(source="game.name", read_only=True)

    class Meta:
        model = UserGameScore
        fields = [
            "game_slug", "game_name", "total_xp", "total_coins",
            "games_played", "correct_answers", "wrong_answers",
            "best_streak", "high_score",
        ]


# ---------------------------------------------------------------------------
# Panel — tests / questions / topics / users
# ---------------------------------------------------------------------------
class CourseMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ["id", "title"]


class TestAdminSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source="course.title", read_only=True)
    q_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Test
        fields = [
            "id", "title", "description", "course", "course_title",
            "module", "time_limit_minutes", "max_attempts", "pass_percentage",
            "difficulty", "status", "is_active", "show_results_immediately",
            "shuffle_questions", "shuffle_choices", "q_count",
            "created_at", "updated_at",
        ]


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ["id", "text", "is_correct", "position"]


class QuestionAdminSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id", "test", "passage", "text", "question_type",
            "correct_text", "points", "explanation", "position", "choices",
        ]


class EssayTopicSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=""
    )

    class Meta:
        model = EssayTopic
        fields = [
            "id", "title", "description", "category",
            "word_limit_min", "word_limit_max", "time_limit_minutes",
            "sample_outline", "grammar_strictness", "national_cert_scale",
            "password", "is_active", "created_by", "created_by_name",
            "created_at",
        ]
        extra_kwargs = {"password": {"write_only": True, "required": False}}


class UserAdminSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name",
            "role", "is_active", "date_joined",
        ]
        read_only_fields = ["email", "date_joined"]


# ---------------------------------------------------------------------------
# Billing
# ---------------------------------------------------------------------------
class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = [
            "id", "name", "plan_type", "description",
            "price_monthly", "price_yearly",
            "max_tests_per_day", "max_essays_per_week", "max_ai_grading",
            "detailed_analytics", "pdf_certificate", "priority_support",
            "unlimited_tests", "unlimited_essays", "sort_order",
        ]


class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = UserSubscription
        fields = [
            "id", "plan", "status", "expires_at",
            "days_remaining", "is_trial", "created_at",
        ]


class PaymentHistorySerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = PaymentHistory
        fields = [
            "id", "plan_name", "amount", "currency",
            "payment_method", "status", "created_at",
        ]


# ---------------------------------------------------------------------------
# School — groups / parent links
# ---------------------------------------------------------------------------
class GroupMemberSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "full_name"]


class StudentGroupSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(
        source="teacher.get_full_name", read_only=True
    )
    student_count = serializers.IntegerField(read_only=True)
    students = GroupMemberSerializer(many=True, read_only=True)

    class Meta:
        model = StudentGroup
        fields = [
            "id", "name", "description", "teacher", "teacher_name",
            "student_count", "students", "created_at",
        ]
        read_only_fields = ["teacher"]


class ParentChildSerializer(serializers.ModelSerializer):
    student = GroupMemberSerializer(read_only=True)
    student_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = ParentStudentLink
        fields = [
            "id", "student", "student_id", "relationship",
            "is_approved", "created_at",
        ]
