"""
Unit & Integration Tests for Stage 8.1.0:
- RBAC Root Admin Immunity (No Paywalls, Unlimited Quotas, Correct Serializer Output)
- Teacher Mistake Inspector APIs (Analytics & Attempt Details with RBAC Guards)
"""

from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.serializers import UserProfileSerializer
from apps.courses.models import Category, Course
from apps.payments.ai_quota import get_user_plan_tier
from apps.payments.entitlements import get_effective_entitlement
from apps.subscriptions.services.quota import QuotaService
from apps.tests.models import Choice, Question, StudentAnswer, Test, TestAttempt

User = get_user_model()


@pytest.mark.django_db
class TestAdminRootImmunity:
    def test_superuser_and_admin_entitlements_unlimited(self):
        admin_user = User.objects.create_user(
            email="admin_immunity@grandec.uz",
            role=User.Role.ADMIN,
            is_staff=True,
            is_superuser=True,
        )
        ent = get_effective_entitlement(admin_user)
        assert ent.is_active is True
        assert ent.plan_type == "admin"
        assert ent.plan_name == "Tizim Administratori"
        assert ent.is_unlimited_tests is True
        assert ent.is_unlimited_text_essays is True
        assert ent.is_unlimited_image_essays is True

    def test_admin_and_staff_plan_tier(self):
        staff_user = User.objects.create_user(
            email="staff_tier@grandec.uz",
            role=User.Role.TEACHER,
            is_staff=True,
        )
        assert get_user_plan_tier(staff_user) == "premium"

    def test_admin_quota_service_bypasses(self):
        admin_user = User.objects.create_user(
            email="admin_quota@grandec.uz",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        # Test quota check
        allowed, msg, details = QuotaService.check_test_quota(admin_user)
        assert allowed is True
        assert details["tier"] == "admin"
        assert details["allowed"] is True

        # Essay quota check
        allowed, msg, details = QuotaService.check_essay_quota(admin_user)
        assert allowed is True
        assert details["tier"] == "admin"
        assert details["allowed"] is True

        # Arena quota check
        allowed, msg, details = QuotaService.check_arena_quota(admin_user)
        assert allowed is True
        assert details["tier"] == "admin"
        assert details["allowed"] is True

    def test_admin_serializer_plan_and_tariff(self):
        admin_user = User.objects.create_user(
            email="admin_serializer@grandec.uz",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        ser = UserProfileSerializer(admin_user)
        data = ser.data
        assert data["plan"] == "ADMIN_UNLIMITED"
        assert data["tariff"] == "ADMIN"
        assert data["is_paid"] is True
        assert data["is_premium"] is True
        assert data["has_pro_access"] is True


@pytest.mark.django_db
class TestTeacherMistakeInspector:
    @pytest.fixture
    def setup_data(self):
        teacher = User.objects.create_user(
            email="teacher_inspector@grandec.uz",
            role=User.Role.TEACHER,
            first_name="Ustoz",
            last_name="Valiyev",
        )
        student1 = User.objects.create_user(
            email="student_one@grandec.uz",
            role=User.Role.STUDENT,
            first_name="Ali",
            last_name="Aliyev",
        )
        student2 = User.objects.create_user(
            email="student_two@grandec.uz",
            role=User.Role.STUDENT,
            first_name="Vali",
            last_name="Valiyev",
        )
        cat = Category.objects.create(name="Ona tili", slug="ona-tili-cat")
        course = Course.objects.create(
            teacher=teacher,
            category=cat,
            title="Ona tili kursi",
            slug="ona-tili-kursi",
        )
        test = Test.objects.create(
            course=course,
            title="Ona tili Mock #1",
            subject="uzbek",
        )
        q1 = Question.objects.create(
            test=test,
            text="Fe'l so'z turkumi nimani bildiradi?",
            question_type=Question.QuestionType.SINGLE_CHOICE,
            points=2,
            explanation="Fe'l harakat va holatni bildiradi.",
            current_rasch_weight=2.5,
            position=1,
        )
        c1_1 = Choice.objects.create(question=q1, text="Harakat va holat", is_correct=True, position=1)
        c1_2 = Choice.objects.create(question=q1, text="Narsaning belgisini", is_correct=False, position=2)

        q2 = Question.objects.create(
            test=test,
            text="Qaysi qatorda sifat qatnashgan?",
            question_type=Question.QuestionType.SINGLE_CHOICE,
            points=2,
            explanation="Qizil - sifat.",
            current_rasch_weight=3.0,
            position=2,
        )
        c2_1 = Choice.objects.create(question=q2, text="Qizil olma", is_correct=True, position=1)
        c2_2 = Choice.objects.create(question=q2, text="Tez yugurdi", is_correct=False, position=2)

        # Attempt for student1: answered q1 correctly, q2 incorrectly
        att1 = TestAttempt.objects.create(
            test=test,
            student=student1,
            status=TestAttempt.Status.COMPLETED,
            raw_score=1,
            score=Decimal("2.00"),
            percentage=Decimal("50.00"),
            rasch_score=Decimal("45.00"),
            rasch_grade="B",
        )
        ans1 = StudentAnswer.objects.create(
            attempt=att1,
            question=q1,
            is_correct=True,
        )
        ans1.selected_choices.add(c1_1)

        ans2 = StudentAnswer.objects.create(
            attempt=att1,
            question=q2,
            is_correct=False,
        )
        ans2.selected_choices.add(c2_2)

        # Update question attempt stats
        q1.total_attempts = 1
        q1.correct_attempts = 1
        q1.save()

        q2.total_attempts = 1
        q2.correct_attempts = 0
        q2.save()

        return {
            "teacher": teacher,
            "student1": student1,
            "student2": student2,
            "test": test,
            "q1": q1,
            "q2": q2,
            "att1": att1,
        }

    def test_teacher_test_analytics_endpoint(self, setup_data):
        client = APIClient()
        client.force_authenticate(user=setup_data["teacher"])

        url = reverse("webapi:webapi-teacher-test-analytics", kwargs={"test_id": setup_data["test"].id})
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data["test_id"] == setup_data["test"].id
        assert data["total_questions"] == 2
        assert len(data["questions"]) == 2
        assert len(data["top_5_hardest"]) == 2
        # q2 has 100% failure rate, so it must be first in hardest
        assert data["top_5_hardest"][0]["question_id"] == setup_data["q2"].id
        assert data["top_5_hardest"][0]["failure_percentage"] == 100.0

    def test_teacher_attempt_details_endpoint(self, setup_data):
        client = APIClient()
        client.force_authenticate(user=setup_data["teacher"])

        url = reverse("webapi:webapi-teacher-attempt-details", kwargs={"attempt_id": setup_data["att1"].id})
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.data
        assert data["attempt_id"] == setup_data["att1"].id
        assert data["student"]["full_name"] == "Ali Aliyev"
        assert data["raw_score"] == 1
        assert data["correct_count"] == 1
        assert data["mistake_count"] == 1

        # Check question breakdown
        q_details = data["questions"]
        assert len(q_details) == 2

        # Q1 should be correct
        q1_detail = next(q for q in q_details if q["question_id"] == setup_data["q1"].id)
        assert q1_detail["is_correct"] is True
        correct_choice = next(c for c in q1_detail["choices"] if c["is_correct"])
        assert correct_choice["is_selected"] is True

        # Q2 should be incorrect
        q2_detail = next(q for q in q_details if q["question_id"] == setup_data["q2"].id)
        assert q2_detail["is_correct"] is False
        assert q2_detail["explanation"] == "Qizil - sifat."
        wrong_choice = next(c for c in q2_detail["choices"] if not c["is_correct"])
        assert wrong_choice["is_selected"] is True

    def test_unauthorized_student_cannot_inspect_others(self, setup_data):
        client = APIClient()
        # Student2 tries to inspect Student1's attempt
        client.force_authenticate(user=setup_data["student2"])

        url = reverse("webapi:webapi-teacher-attempt-details", kwargs={"attempt_id": setup_data["att1"].id})
        response = client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
