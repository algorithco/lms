"""Serializers for the React API — explicit fields, no behavior changes."""
from decimal import Decimal

from rest_framework import serializers

from apps.accounts.models import ParentStudentLink, User
from apps.attendance.models import (
    AttendanceRecord,
    AttendanceSession,
    ClassroomObservation,
    GroupNotificationDestination,
    NotificationPreference,
)
from apps.courses.models import Course, StudentGroup
from apps.core.validators import validate_attachment_upload
from apps.tuition.models import CourseBillingPolicy, PaymentMethod
from apps.essays.models import EssayTopic
from apps.games.models import Game, GameLevel, UserGameScore
from apps.payments.models import PaymentHistory, PaymentReceipt, SubscriptionPlan, UserSubscription
from apps.tests.models import Choice, ExamSection, Question, ReadingPassage, Test


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
            "current_streak", "best_streak", "high_score",
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
            "shuffle_questions", "shuffle_choices", "q_count", "scoring_profile",
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
            "id", "test", "section", "reading_passage", "passage", "text",
            "question_type", "correct_text", "points", "explanation",
            "position", "config", "choices",
        ]


class ExamSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamSection
        fields = [
            "id", "test", "name", "code", "order",
            "duration_minutes", "weight",
        ]


class ReadingPassageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReadingPassage
        fields = ["id", "test", "section", "title", "content", "source", "order"]


class EssayTopicSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(
        source="created_by.get_full_name", read_only=True, default=""
    )
    has_password = serializers.SerializerMethodField()

    class Meta:
        model = EssayTopic
        fields = [
            "id", "title", "description", "category",
            "word_limit_min", "word_limit_max", "time_limit_minutes",
            "sample_outline", "grammar_strictness", "national_cert_scale",
            "password", "has_password", "is_active", "created_by",
            "created_by_name", "created_at",
        ]
        extra_kwargs = {"password": {"write_only": True, "required": False}}

    def get_has_password(self, obj: EssayTopic) -> bool:
        return bool(obj.password)


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
    # Model *properties* (not DB columns) used by the commercial plan cards.
    code = serializers.ReadOnlyField()
    price_uzs = serializers.ReadOnlyField()
    display_order = serializers.ReadOnlyField()

    class Meta:
        model = SubscriptionPlan
        fields = [
            "id", "name", "plan_type", "code", "description",
            "price_monthly", "price_uzs", "price_yearly",
            "max_tests_per_day", "max_essays_per_week", "max_ai_grading",
            "detailed_analytics", "pdf_certificate", "priority_support",
            "unlimited_tests", "unlimited_essays", "sort_order",
            "display_order",
            # Commercial quota configuration (START / PRO / sponsored).
            "duration_days", "is_public", "telegram_stars_price",
            "image_essay_weekly_limit", "text_essay_weekly_limit",
            "text_essay_cooldown_hours", "test_limit",
            "is_unlimited_image_essays", "is_unlimited_text_essays",
            "is_unlimited_tests",
        ]


class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer(read_only=True)
    days_remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = UserSubscription
        fields = [
            "id", "plan", "status", "expires_at",
            "days_remaining", "is_trial", "created_at",
            "purchase_source",
        ]


class PaymentHistorySerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = PaymentHistory
        fields = [
            "id", "plan_name", "amount", "currency",
            "payment_method", "status", "created_at",
        ]


class PaymentReceiptSerializer(serializers.ModelSerializer):
    receipt_image_url = serializers.SerializerMethodField()

    class Meta:
        model = PaymentReceipt
        fields = [
            "id",
            "plan",
            "amount",
            "receipt_image",
            "receipt_image_url",
            "status",
            "source",
            "admin_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "source", "admin_note", "created_at", "updated_at"]

    def get_receipt_image_url(self, obj: PaymentReceipt) -> str:
        if obj.receipt_image:
            return obj.receipt_image.url
        return ""


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
            "invite_code", "student_count", "students", "created_at",
        ]
        read_only_fields = ["teacher", "invite_code"]


# ---------------------------------------------------------------------------
# Attendance / observations / notification routing
# ---------------------------------------------------------------------------
class AttendanceSessionSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    time_label = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceSession
        fields = [
            "id", "group", "group_name", "teacher", "lesson_date",
            "start_time", "end_time", "time_label", "status", "status_label",
            "title", "created_at", "finalized_at",
        ]
        read_only_fields = ["teacher"]

    def get_time_label(self, obj) -> str:
        return obj.local_time_label()


class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = [
            "id", "session", "student", "student_name", "status",
            "status_label", "late_minutes", "note", "marked_by",
            "marked_at", "updated_at",
        ]


class ClassroomObservationSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.get_full_name", read_only=True)
    observation_type_label = serializers.CharField(
        source="get_observation_type_display", read_only=True,
    )
    notification_status_label = serializers.CharField(
        source="get_notification_status_display", read_only=True,
    )
    is_confirmed = serializers.BooleanField(read_only=True)

    class Meta:
        model = ClassroomObservation
        fields = [
            "id", "student", "student_name", "session", "teacher",
            "observation_type", "observation_type_label", "neutral_description",
            "notification_status", "notification_status_label", "is_confirmed",
            "confirmed_at", "sent_at", "created_at", "updated_at",
        ]


class GroupNotificationDestinationSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source="group.name", read_only=True)
    destination_type_label = serializers.CharField(
        source="get_destination_type_display", read_only=True,
    )
    is_usable = serializers.BooleanField(read_only=True)

    class Meta:
        model = GroupNotificationDestination
        fields = [
            "id", "group", "group_name", "chat_id", "title",
            "destination_type", "destination_type_label", "is_enabled",
            "is_approved", "is_usable", "approved_by", "approved_at",
            "allowed_categories", "created_at", "updated_at",
        ]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            "telegram_enabled", "attendance_alerts", "essay_graded_alerts",
            "test_result_alerts", "observation_alerts", "teacher_new_essay",
            "teacher_grading_completed", "teacher_grading_failed",
            "teacher_attendance_reminder", "updated_at",
        ]


class ParentChildSerializer(serializers.ModelSerializer):
    student = GroupMemberSerializer(read_only=True)
    student_id = serializers.IntegerField(write_only=True, required=False)

    class Meta:
        model = ParentStudentLink
        fields = [
            "id", "student", "student_id", "relationship",
            "is_approved", "created_at",
        ]


# ---------------------------------------------------------------------------
# Course tuition
# ---------------------------------------------------------------------------
class TuitionPaymentSubmissionSerializer(serializers.Serializer):
    invoice_id = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    method = serializers.ChoiceField(choices=PaymentMethod.choices, required=False)
    reference = serializers.CharField(max_length=120, required=False, allow_blank=True)
    note = serializers.CharField(max_length=500, required=False, allow_blank=True)
    proof = serializers.FileField(
        required=False, allow_empty_file=False, validators=[validate_attachment_upload],
    )


class CourseBillingPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = CourseBillingPolicy
        fields = [
            "id", "name", "course", "group", "amount_uzs", "billing_frequency",
            "due_day", "grace_days", "mid_month_policy", "installment_allowed",
            "installments", "effective_from", "effective_until", "payment_instructions",
            "accepted_methods", "reminder_policy", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        instance = self.instance
        course = attrs.get("course", instance.course if instance else None)
        group = attrs.get("group", instance.group if instance else None)
        if course is None and group is None:
            raise serializers.ValidationError("Kurs yoki guruh tanlanishi kerak.")

        due_day = attrs.get("due_day", instance.due_day if instance else 10)
        if not 1 <= int(due_day) <= 31:
            raise serializers.ValidationError({"due_day": "Qiymat 1 va 31 orasida bo'lishi kerak."})
        installments = attrs.get("installments", instance.installments if instance else 1)
        allowed = attrs.get("installment_allowed", instance.installment_allowed if instance else False)
        if int(installments) < 1 or (allowed and int(installments) < 2):
            raise serializers.ValidationError({"installments": "Bo'lib to'lash uchun kamida 2 qism kiriting."})
        effective_from = attrs.get("effective_from", instance.effective_from if instance else None)
        effective_until = attrs.get("effective_until", instance.effective_until if instance else None)
        if effective_from and effective_until and effective_until < effective_from:
            raise serializers.ValidationError({"effective_until": "Tugash sanasi boshlanish sanasidan oldin bo'lmasligi kerak."})

        accepted = attrs.get("accepted_methods", instance.accepted_methods if instance else [])
        valid_methods = {value for value, _label in PaymentMethod.choices}
        if not isinstance(accepted, list) or any(method not in valid_methods for method in accepted):
            raise serializers.ValidationError({"accepted_methods": "Noto'g'ri to'lov usuli."})

        reminder = attrs.get("reminder_policy", instance.reminder_policy if instance else {})
        if not isinstance(reminder, dict):
            raise serializers.ValidationError({"reminder_policy": "JSON obyekt bo'lishi kerak."})
        try:
            for stage in ("before", "due", "overdue"):
                offsets = reminder.get(stage, [])
                if not isinstance(offsets, list) or any(
                    isinstance(offset, bool) or int(offset) < 0 or int(offset) > 365
                    for offset in offsets
                ):
                    raise ValueError
            for hour in ("quiet_start", "quiet_end"):
                if hour in reminder and not 0 <= int(reminder[hour]) <= 23:
                    raise ValueError
        except (TypeError, ValueError):
            raise serializers.ValidationError({"reminder_policy": "Eslatma kunlari 0–365, sokin soatlar 0–23 oralig'ida bo'lishi kerak."})
        return attrs


class TuitionPolicyAuditSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3, max_length=200)


class InvoiceDueDateSerializer(serializers.Serializer):
    due_date = serializers.DateField()
    grace_until = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        grace_until = attrs.get("grace_until")
        if grace_until and grace_until < attrs["due_date"]:
            raise serializers.ValidationError({"grace_until": "Imtiyoz sanasi to'lov muddatidan oldin bo'lmasligi kerak."})
        return attrs
