"""Tests for 5-minute placement quiz, smart onboarding and cohort analytics."""

from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.courses.models import Course
from apps.tests.models import Choice, Question, Test

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def student_user(db):
    user = User.objects.create_user(
        email="test_onboard_student@example.com",
        password="Password123!",
        first_name="Ali",
        last_name="Valiyev",
        role="student",
    )
    Profile.objects.get_or_create(user=user)
    return user


@pytest.fixture
def admin_user(db):
    user = User.objects.create_superuser(
        email="test_onboard_admin@example.com",
        password="AdminPassword123!",
        first_name="Admin",
        last_name="Super",
    )
    Profile.objects.get_or_create(user=user)
    return user


@pytest.fixture
def sample_questions(db):
    teacher = User.objects.create_user(
        email="test_teacher_onboard@example.com",
        password="Password123!",
        first_name="Ustoz",
        last_name="Test",
        role="teacher",
    )
    course = Course.objects.create(
        teacher=teacher,
        title="Ona tili kursi",
        slug="ona-tili-onboard",
    )
    test_milliy = Test.objects.create(
        title="Ona tili va Adabiyot — BMB Rasmiy Mock Test",
        course=course,
        status=Test.Status.PUBLISHED,
        time_limit_minutes=180,
    )
    test_attest = Test.objects.create(
        title="Attestatsiya 2026 Ona tili",
        course=course,
        status=Test.Status.PUBLISHED,
        time_limit_minutes=100,
    )

    questions = []
    # Create 5 questions for milliy
    for i in range(1, 6):
        q = Question.objects.create(
            test=test_milliy,
            text=f"Milliy Savol {i}",
            question_type=Question.QuestionType.SINGLE_CHOICE,
            points=1,
            position=i,
        )
        c1 = Choice.objects.create(question=q, text="A javob", is_correct=True)
        c2 = Choice.objects.create(question=q, text="B javob", is_correct=False)
        questions.append((q, c1, c2))

    # Create 5 questions for attest
    for i in range(1, 6):
        q = Question.objects.create(
            test=test_attest,
            text=f"Attestatsiya Savol {i}",
            question_type=Question.QuestionType.SINGLE_CHOICE,
            points=1,
            position=i,
        )
        c1 = Choice.objects.create(question=q, text="To'g'ri variant", is_correct=True)
        c2 = Choice.objects.create(
            question=q, text="Noto'g'ri variant", is_correct=False
        )
        questions.append((q, c1, c2))

    return questions


@pytest.mark.django_db
def test_get_placement_quiz_questions(api_client, sample_questions):
    url = "/api/v1/tests/placement-quiz/?target=national_certificate"
    resp = api_client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["target"] == "national_certificate"
    assert data["time_limit_seconds"] == 300
    assert len(data["questions"]) == 5
    for q in data["questions"]:
        assert "text" in q
        assert "choices" in q
        assert len(q["choices"]) >= 2
        for c in q["choices"]:
            assert "is_correct" not in c


@pytest.mark.django_db
def test_submit_placement_quiz_and_profile_plan(
    api_client, student_user, sample_questions
):
    api_client.force_authenticate(user=student_user)

    # Pick 5 questions and answers
    answers = []
    for q, correct_c, _ in sample_questions[:5]:
        answers.append(
            {
                "question_id": q.id,
                "selected_choice_id": correct_c.id,
            }
        )

    payload = {
        "target": "national_certificate",
        "target_timeline_months": 3,
        "target_grade": "A+",
        "answers": answers,
    }

    url = "/api/v1/tests/placement-quiz/submit/"
    resp = api_client.post(url, payload, format="json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["score"] == 5
    assert data["total"] == 5
    assert data["percentage"] == 100.0
    assert data["onboarding_completed"] is True
    assert "daily_plan" in data
    assert data["daily_plan"]["tests_per_day"] == 1
    assert data["daily_plan"]["essays_per_week"] == 2

    # Check profile
    profile = Profile.objects.get(user=student_user)
    assert profile.onboarding_completed is True
    assert profile.exam_target == "national_certificate"
    assert profile.target_timeline_months == 3
    assert profile.target_grade == "A+"
    assert profile.placement_score == Decimal("5.00")
    assert profile.daily_plan_summary["tests_per_day"] == 1


@pytest.mark.django_db
def test_cohort_analytics_view(api_client, admin_user, student_user):
    # Set student profile
    profile = Profile.objects.get(user=student_user)
    profile.onboarding_completed = True
    profile.exam_target = "national_certificate"
    profile.target_timeline_months = 3
    profile.placement_score = Decimal("4.00")
    profile.save()

    api_client.force_authenticate(user=admin_user)
    url = "/api/v1/panel/analytics/cohorts/"
    resp = api_client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_onboarded"] >= 1
    assert "segmentation" in data
    assert data["segmentation"]["national_certificate"]["count"] >= 1
    assert "timeline_breakdown" in data
    assert data["timeline_breakdown"]["months_3"]["count"] >= 1
