"""Unit and integration tests for OMR Scanner, AI Speaking Simulator, Gamification & White-Label B2B."""
from datetime import date, timedelta
from decimal import Decimal
import io
from unittest.mock import MagicMock, patch
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageDraw
from rest_framework.test import APIClient

from apps.accounts.gamification import (
    record_user_activity,
)
from apps.accounts.models import Profile
from apps.courses.models import Course, StudentGroup
from apps.speaking.models import SpeakingSubmission, SpeakingTopic
from apps.speaking.services import evaluate_speaking_submission
from apps.tests.models import Choice, Question, Test, TestAttempt
from apps.tests.omr_service import grade_omr_sheet

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def student_user(db):
    user = User.objects.create_user(
        email="gamification_student@example.com",
        password="Password123!",
        first_name="Anvar",
        last_name="Aliyev",
        role="student",
    )
    Profile.objects.get_or_create(user=user)
    return user


@pytest.fixture
def teacher_user(db):
    user = User.objects.create_user(
        email="gamification_teacher@example.com",
        password="Password123!",
        first_name="Nilufar",
        last_name="Rahimova",
        role="teacher",
    )
    Profile.objects.get_or_create(user=user)
    return user


@pytest.fixture
def sample_course(db, teacher_user):
    return Course.objects.create(
        teacher=teacher_user,
        title="Ona tili va Adabiyot Mock Kursi",
        slug="ona-tili-mock-kursi",
        description="BMB va attestatsiya mock imtihonlari kursi",
    )


@pytest.fixture
def student_group(db, teacher_user, student_user):
    group = StudentGroup.objects.create(
        name="Grandec FastTrack 2026",
        teacher=teacher_user,
        invite_code="GRAND26",
    )
    group.students.add(student_user)
    return group


@pytest.fixture
def sample_test_with_questions(db, teacher_user, sample_course):
    test_obj = Test.objects.create(
        course=sample_course,
        title="Mock Test #42",
        time_limit_minutes=30,
        pass_percentage=60,
        mock_code="MOCK-42",
        status=Test.Status.PUBLISHED,
    )
    q1 = Question.objects.create(
        test=test_obj,
        text="O'zbekiston poytaxti qaysi shahar?",
        position=1,
    )
    Choice.objects.create(question=q1, text="Toshkent", is_correct=True, position=1)
    Choice.objects.create(question=q1, text="Samarqand", is_correct=False, position=2)
    Choice.objects.create(question=q1, text="Buxoro", is_correct=False, position=3)
    Choice.objects.create(question=q1, text="Xiva", is_correct=False, position=4)

    q2 = Question.objects.create(
        test=test_obj,
        text="Alisher Navoiy qaysi asr mutafakkiri?",
        position=2,
    )
    Choice.objects.create(question=q2, text="XIV asr", is_correct=False, position=1)
    Choice.objects.create(question=q2, text="XV asr", is_correct=True, position=2)
    Choice.objects.create(question=q2, text="XVI asr", is_correct=False, position=3)
    Choice.objects.create(question=q2, text="XVII asr", is_correct=False, position=4)

    return test_obj


# ==============================================================================
# 1. GAMIFICATION & STREAK TESTS
# ==============================================================================
@pytest.mark.django_db
def test_streak_calculation_first_day(student_user):
    profile = student_user.profile
    profile.current_streak = 0
    profile.last_activity_date = None
    profile.save()

    info = record_user_activity(student_user, xp_amount=20)
    student_user.profile.refresh_from_db()

    assert info["current_streak"] == 1
    assert student_user.profile.current_streak == 1
    assert student_user.profile.last_activity_date == date.today()
    assert student_user.profile.xp_points == 20


@pytest.mark.django_db
def test_streak_increment_consecutive_day(student_user):
    profile = student_user.profile
    profile.current_streak = 3
    profile.longest_streak = 3
    profile.last_activity_date = date.today() - timedelta(days=1)
    profile.save()

    info = record_user_activity(student_user, xp_amount=15)
    student_user.profile.refresh_from_db()

    assert info["current_streak"] == 4
    assert student_user.profile.current_streak == 4
    assert student_user.profile.longest_streak == 4


@pytest.mark.django_db
def test_streak_freeze_usage(student_user):
    profile = student_user.profile
    profile.current_streak = 5
    profile.longest_streak = 5
    profile.last_activity_date = date.today() - timedelta(days=2)
    profile.streak_freeze_count = 1
    profile.save()

    info = record_user_activity(student_user, xp_amount=25)
    student_user.profile.refresh_from_db()

    # Freeze preserved the streak and advanced it
    assert info["current_streak"] == 6
    assert student_user.profile.streak_freeze_count == 0


@pytest.mark.django_db
def test_gamification_api_endpoints(api_client, student_user):
    api_client.force_authenticate(user=student_user)

    res_streak = api_client.get("/api/v1/gamification/streak/")
    assert res_streak.status_code == 200
    data = res_streak.json()
    assert "current_streak" in data
    assert "xp_points" in data
    assert "weekly_league" in data

    res_league = api_client.get("/api/v1/gamification/league/")
    assert res_league.status_code == 200
    ldata = res_league.json()
    assert "league" in ldata
    assert "participants" in ldata


# ==============================================================================
# 2. AI SPEAKING SIMULATOR TESTS
# ==============================================================================
@pytest.mark.django_db
def test_speaking_topics_list_and_seeder(api_client, student_user):
    api_client.force_authenticate(user=student_user)

    res = api_client.get("/api/v1/speaking/topics/")
    assert res.status_code == 200
    data = res.json()
    topics = data.get("results", data)
    assert len(topics) >= 3
    parts = {t["part"] for t in topics}
    assert "part1" in parts or "part2" in parts


@pytest.mark.django_db
def test_speaking_submission_evaluation(student_user):
    topic = SpeakingTopic.objects.create(
        title="Describe an influential teacher",
        part="part2",
        prompt="Describe an influential teacher that made a difference in your life.",
        bullet_points=["Who they were", "What subject they taught", "Why they influenced you"],
        prep_time_seconds=60,
        speak_time_seconds=120,
    )

    dummy_audio = SimpleUploadedFile("speech.webm", b"RIFF....dummy_webm_data", content_type="audio/webm")

    mock_payload = {
        "fluency_score": 7.0,
        "lexical_score": 7.5,
        "grammar_score": 6.5,
        "pronunciation_score": 7.0,
        "overall_band": 7.0,
        "transcript": "Today I would like to talk about my mathematics teacher...",
        "feedback": {
            "summary": "Great speech",
            "vocabulary_suggestions": [{"original": "good teacher", "improved": "inspiring pedagogue"}],
            "grammar_corrections": [{"incorrect": "he teach me", "corrected": "he taught me"}],
        },
    }

    with patch("apps.speaking.services._gemini_evaluate_audio", return_value=mock_payload):
        evaluated_sub = evaluate_speaking_submission(
            audio_file=dummy_audio,
            topic_id=topic.id,
            user=student_user,
            duration_seconds=90,
        )

        assert evaluated_sub.status == "completed"
        assert evaluated_sub.overall_band == Decimal("7.0")
        assert evaluated_sub.fluency_score == Decimal("7.0")
        assert evaluated_sub.lexical_score == Decimal("7.5")
        assert len(evaluated_sub.feedback.get("vocabulary_suggestions", [])) == 1


# ==============================================================================
# 3. OMR TITUL VARAQA SCANNER TESTS
# ==============================================================================
@pytest.mark.django_db
def test_omr_answer_evaluation(sample_test_with_questions, student_user):
    img = Image.new("RGB", (300, 300), color=(255, 255, 255))
    img_io = io.BytesIO()
    img.save(img_io, format="JPEG")
    img_io.seek(0)
    uploaded = SimpleUploadedFile("test_sheet.jpg", img_io.read(), content_type="image/jpeg")

    mock_extracted = {
        "test_code": "MOCK-42",
        "student_id": "101",
        "answers": {"1": "A", "2": "B"},
    }

    with patch("apps.tests.omr_service._extract_answers_with_gemini", return_value=mock_extracted):
        report = grade_omr_sheet(uploaded, test_id=sample_test_with_questions.id, user=student_user)

        assert report["ok"] is True
        assert report["total_score"] == 2
        assert report["total_questions"] == 2
        assert report["percentage"] == 100.0
        assert report["is_passed"] is True
        assert len(report["breakdown"]) == 2
        assert report["breakdown"][0]["is_correct"] is True
        assert report["breakdown"][1]["is_correct"] is True


@pytest.mark.django_db
def test_omr_scan_endpoint_with_image(api_client, student_user, sample_test_with_questions):
    api_client.force_authenticate(user=student_user)

    img = Image.new("RGB", (400, 600), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "#MOCK-42", fill=(0, 0, 0))

    img_io = io.BytesIO()
    img.save(img_io, format="JPEG")
    img_io.seek(0)
    uploaded = SimpleUploadedFile("omr_test.jpg", img_io.read(), content_type="image/jpeg")

    mock_extracted = {
        "test_code": "MOCK-42",
        "student_id": "101",
        "answers": {"1": "A", "2": "B"},
    }

    with patch("apps.tests.omr_service._extract_answers_with_gemini", return_value=mock_extracted):
        res = api_client.post(
            "/api/v1/tests/scan-omr/",
            {"image": uploaded, "mock_code": "MOCK-42"},
            format="multipart",
        )

        assert res.status_code == 200
        data = res.json()
        assert data["ok"] is True
        assert data["total_score"] == 2
        assert data["percentage"] == 100.0


# ==============================================================================
# 4. WHITE-LABEL B2B REPORTS & BRANDING TESTS
# ==============================================================================
@pytest.mark.django_db
def test_whitelabel_branding_api(api_client, teacher_user):
    api_client.force_authenticate(user=teacher_user)

    # GET initial
    res = api_client.get("/api/v1/organizations/branding/")
    assert res.status_code == 200
    assert res.json()["success"] is True

    # POST update
    update_res = api_client.post(
        "/api/v1/organizations/branding/",
        {
            "center_name": "Cambridge Academy Samarkand",
            "header_title": "OYLIK RASMIY HISOBOT 2026",
            "brand_color": "#047857",
        },
    )
    assert update_res.status_code == 200
    u_data = update_res.json()
    assert u_data["center_name"] == "Cambridge Academy Samarkand"
    assert u_data["brand_color"] == "#047857"


@pytest.mark.django_db
def test_whitelabel_monthly_report_pdf(api_client, teacher_user, student_group, sample_test_with_questions, student_user):
    api_client.force_authenticate(user=teacher_user)

    # Create a completed test attempt for student
    TestAttempt.objects.create(
        student=student_user,
        test=sample_test_with_questions,
        status=TestAttempt.Status.COMPLETED,
        score=2,
        percentage=100.0,
        is_passed=True,
    )

    url = f"/api/v1/school/groups/{student_group.id}/export/monthly-report-pdf/"
    res = api_client.get(url)

    assert res.status_code == 200
    assert res["Content-Type"] == "application/pdf"
    assert "monthly-report-group-" in res["Content-Disposition"]
    assert len(res.content) > 1000
    # PDF starts with %PDF-
    assert res.content.startswith(b"%PDF-")
