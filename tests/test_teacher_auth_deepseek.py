import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.serializers import RegisterSerializer
from apps.essays.deepseek_grader import (
    DeepSeekGrader,
    get_deepseek_client,
    grade_bmb_essay_deepseek,
    grade_ielts_essay_deepseek,
)
from apps.speaking.models import SpeakingTopic
from apps.speaking.services import (
    _fallback_speaking_evaluation,
    evaluate_speaking_submission,
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

    def test_deepseek_r1_model_name(self):
        model = DeepSeekGrader.get_model()
        assert model == "deepseek/deepseek-r1-0528"
        assert (
            getattr(settings, "AI_EVALUATION_MODEL", "") == "deepseek/deepseek-r1-0528"
        )
        assert (
            getattr(settings, "AUDIO_STREAM_MODEL", "")
            == "fish-audio/s2.1-pro-free:free"
        )

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


@pytest.mark.django_db
class TestSpeakingModelIntegration:
    """Ensure speaking evaluation with fish-audio and deepseek-r1 works properly."""

    def test_speaking_fallback_evaluation(self):
        topic = SpeakingTopic.objects.create(
            title="Describe an influential teacher",
            part=SpeakingTopic.PartChoice.PART2,
            prompt="Talk about a teacher who influenced your life.",
            bullet_points=[
                "Who they were",
                "What subject they taught",
                "Why they influenced you",
            ],
        )
        eval_res = _fallback_speaking_evaluation(topic, duration_seconds=60)
        assert "fluency_score" in eval_res
        assert "lexical_score" in eval_res
        assert "grammar_score" in eval_res
        assert "pronunciation_score" in eval_res
        assert eval_res["overall_band"] >= 1.0

    def test_evaluate_speaking_submission(self):
        user = User.objects.create_user(
            email="speaking_student@grandec.uz",
            password="SecurePassword123!",
            role=User.Role.STUDENT,
        )
        topic = SpeakingTopic.objects.create(
            title="Hometown",
            part=SpeakingTopic.PartChoice.PART1,
            prompt="Tell me about your hometown.",
        )
        dummy_audio = SimpleUploadedFile(
            "response.wav", b"RIFF....WAVEfmt ...data...", content_type="audio/wav"
        )

        submission = evaluate_speaking_submission(
            audio_file=dummy_audio,
            topic_id=topic.pk,
            user=user,
            duration_seconds=45,
        )
        assert submission.pk is not None
        assert submission.overall_band >= 1.0
        assert submission.user == user


class TestStrictModelBinding:
    """The whole evaluation chain must resolve to exactly one model."""

    def test_candidate_chain_is_single_deepseek_r1(self):
        from apps.essays.services import _model_candidates

        assert _model_candidates() == ["deepseek/deepseek-r1-0528"]

    def test_all_openrouter_model_settings_point_to_r1(self):
        r1 = "deepseek/deepseek-r1-0528"
        assert settings.AI_EVALUATION_MODEL == r1
        assert settings.ESSAY_AI_MODEL == r1
        assert settings.OPENROUTER_AI_MODEL == r1
        assert settings.ESSAY_GRADER_MODEL == r1
        assert settings.OPENROUTER_FALLBACK_MODELS == [r1]

    def test_prompts_use_deduction_method(self):
        from apps.essays.prompts import ESSAY_GRADING_SYSTEM_PROMPT
        from apps.essays.services import IELTS_SYSTEM_PROMPT

        assert "DEDUKSIYA" in ESSAY_GRADING_SYSTEM_PROMPT
        assert "DEDUCTION" in IELTS_SYSTEM_PROMPT
