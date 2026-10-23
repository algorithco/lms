import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.serializers import RegisterSerializer
from apps.essays.deepseek_grader import (
    DeepSeekGrader,
    get_deepseek_client,
    grade_bmb_essay_deepseek,
    grade_ielts_essay_deepseek,
)

User = get_user_model()


@pytest.mark.django_db
class TestRegistrationRoleSecurity:
    """Ensure public registration cannot grant teacher or admin role."""

    def test_registration_forces_student_role_even_if_teacher_requested(self):
        data = {
            "email": "intruder_teacher@grandec.uz",
            "password": "SecurePassword123!",
            "password_confirm": "SecurePassword123!",
            "first_name": "Intruder",
            "last_name": "Teacher",
            "role": "teacher",
        }
        serializer = RegisterSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()

        # Must strictly be student
        assert user.role == User.Role.STUDENT
        assert user.can_create_test is False
        assert user.can_create_essay_topic is False

    def test_registration_endpoint_via_client(self):
        client = APIClient()
        response = client.post(
            "/api/auth/register/",
            {
                "email": "intruder_api@grandec.uz",
                "password": "SecurePassword123!",
                "password_confirm": "SecurePassword123!",
                "first_name": "API",
                "last_name": "Student",
                "role": "admin",
            },
            format="json",
        )
        assert response.status_code == 201
        created_user = User.objects.get(email="intruder_api@grandec.uz")
        assert created_user.role == User.Role.STUDENT


@pytest.mark.django_db
class TestAdminTeacherCreation:
    """Ensure teachers can only be created by authenticated administrators."""

    def test_anonymous_cannot_create_teacher(self):
        client = APIClient()
        response = client.post(
            "/api/v1/panel/teachers/create/",
            {
                "email": "teacher1@grandec.uz",
                "password": "SecurePassword123!",
                "first_name": "Sherzod",
                "last_name": "Ustoz",
            },
            format="json",
        )
        assert response.status_code in (401, 403)

    def test_student_cannot_create_teacher(self):
        student = User.objects.create_user(
            email="regular_student@grandec.uz",
            password="SecurePassword123!",
            role=User.Role.STUDENT,
        )
        client = APIClient()
        client.force_authenticate(user=student)

        response = client.post(
            "/api/v1/panel/teachers/create/",
            {
                "email": "teacher2@grandec.uz",
                "password": "SecurePassword123!",
                "first_name": "Sherzod",
                "last_name": "Ustoz",
            },
            format="json",
        )
        assert response.status_code == 403

    def test_admin_can_create_verified_teacher(self):
        admin = User.objects.create_superuser(
            email="admin_creator@grandec.uz",
            password="SecurePassword123!",
        )
        client = APIClient()
        client.force_authenticate(user=admin)

        response = client.post(
            "/api/v1/panel/teachers/create/",
            {
                "email": "verified_teacher@grandec.uz",
                "password": "TeacherPassword123!",
                "first_name": "Alisher",
                "last_name": "Navoiy",
                "phone": "+998901234567",
                "can_create_test": True,
                "can_create_essay_topic": True,
            },
            format="json",
        )
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "verified_teacher@grandec.uz"
        assert data["role"] == "teacher"
        assert data["can_create_test"] is True
        assert data["can_create_essay_topic"] is True

        teacher = User.objects.get(email="verified_teacher@grandec.uz")
        assert teacher.role == User.Role.TEACHER
        assert teacher.can_create_test is True
        assert teacher.can_create_essay_topic is True
        assert teacher.is_active is True
        assert teacher.profile.phone == "+998901234567"


class TestDeepSeekGraderIntegration:
    """Ensure DeepSeek client initialization and fallback work without errors."""

    def test_deepseek_client_init(self):
        client = get_deepseek_client()
        assert client is not None
        assert client.api_key.startswith("sk-")

    def test_deepseek_model_name(self):
        model = DeepSeekGrader.get_model()
        assert "deepseek" in model.lower()

    def test_bmb_essay_grading_fallback(self):
        result = grade_bmb_essay_deepseek(
            "Ona tili milliy qadriyatimiz va ma'naviyatimiz ko'zgusidir.",
            topic_title="Ona tili haqida",
        )
        assert isinstance(result, dict)
        assert "criteria" in result
        assert len(result["criteria"]) == 12
        assert "total_score" in result

    def test_ielts_essay_grading_fallback(self):
        result = grade_ielts_essay_deepseek(
            "Technological advancement has transformed the modern educational landscape significantly. "
            "Students now have unprecedented access to learning materials online.",
            topic_title="Impact of Technology on Education",
            task_type="ielts_task2",
        )
        assert isinstance(result, dict)
        assert "criteria" in result
        assert len(result["criteria"]) == 4
        assert "overall_band" in result
