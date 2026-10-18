"""Tests for Multi-Subject Ecosystem (Uzbek / English IELTS), Strict Exam Mode, and 1-Click Attendance."""
from decimal import Decimal
from unittest.mock import patch
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.courses.models import Course, StudentGroup
from apps.essays.models import EssayCriterionScore, EssaySubmission, EssayTopic
from apps.essays.services import grade_ielts_essay
from apps.tests.models import Choice, Question, Test, TestAttempt

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def student_user(db):
    user = User.objects.create_user(
        email="student_multi_subject@example.com",
        password="Password123!",
        first_name="Jasur",
        last_name="Karimov",
        role="student",
    )
    Profile.objects.get_or_create(user=user)
    return user


@pytest.fixture
def teacher_user(db):
    user = User.objects.create_user(
        email="teacher_multi_subject@example.com",
        password="Password123!",
        first_name="Sardor",
        last_name="Ustoz",
        role="teacher",
    )
    Profile.objects.get_or_create(user=user)
    return user


@pytest.fixture
def student_group(db, teacher_user, student_user):
    group = StudentGroup.objects.create(
        name="IELTS Intensive Group A1",
        teacher=teacher_user,
        invite_code="IELTS99",
    )
    group.students.add(student_user)
    return group


@pytest.fixture
def strict_test(db, teacher_user):
    course = Course.objects.create(
        teacher=teacher_user,
        title="IELTS Mock Exam Course",
        slug="ielts-mock-exam-course",
    )
    test = Test.objects.create(
        course=course,
        title="IELTS Academic Reading & Listening CBT Mock",
        subject="english",
        difficulty=Test.Difficulty.HARD,
        time_limit_minutes=60,
        pass_percentage=60,
        is_active=True,
        is_strict_mode=True,
    )
    q1 = Question.objects.create(
        test=test,
        text="According to the passage, the global temperature has risen by 1.1°C.",
        question_type=Question.QuestionType.SINGLE_CHOICE,
        points=1,
        position=1,
    )
    Choice.objects.create(question=q1, text="True", is_correct=True, position=1)
    Choice.objects.create(question=q1, text="False", is_correct=False, position=2)
    Choice.objects.create(question=q1, text="Not Given", is_correct=False, position=3)
    return test


# ---------------------------------------------------------------------------
# 1. Subject Switcher Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_subjects_list_api(api_client, student_user):
    api_client.force_authenticate(user=student_user)
    res = api_client.get("/api/v1/subjects/")
    assert res.status_code == 200
    data = res.json()
    assert "subjects" in data
    slugs = [s["slug"] for s in data["subjects"]]
    assert "uzbek" in slugs
    assert "english" in slugs
    assert data["active_subject"] == "uzbek"


@pytest.mark.django_db
def test_switch_subject_api(api_client, student_user):
    api_client.force_authenticate(user=student_user)

    # Switch to English
    res = api_client.post("/api/v1/profile/switch-subject/", {"subject": "english"}, format="json")
    assert res.status_code == 200
    assert res.json()["active_subject"] == "english"

    student_user.profile.refresh_from_db()
    assert student_user.profile.active_subject == "english"

    # Switch back to Uzbek
    res = api_client.post("/api/v1/profile/switch-subject/", {"subject": "uzbek"}, format="json")
    assert res.status_code == 200
    assert res.json()["active_subject"] == "uzbek"

    # Invalid subject rejected
    res = api_client.post("/api/v1/profile/switch-subject/", {"subject": "russian"}, format="json")
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# 2. IELTS Writing Grader Tests (4 Official Criteria)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_grade_ielts_essay_unit(student_user):
    from apps.essays.services import apply_ai_result

    topic = EssayTopic.objects.create(
        title="IELTS Academic Task 2: Remote Work vs Office",
        description="Some people believe that remote work increases productivity, while others disagree.",
        subject="english",
        rubric_type="ielts_task2",
        word_limit_min=250,
        word_limit_max=500,
    )
    sample_text = (
        "In recent years, the advancement of modern technology has revolutionized workplace dynamics. "
        "While some individuals argue that telecommuting significantly boosts productivity by eliminating daily commutes, "
        "others believe that traditional office settings foster indispensable collaboration and structure. "
        "This essay examines both perspectives and provides a reasoned conclusion.\n\n"
        "On the one hand, remote work offers employees unprecedented autonomy and temporal flexibility. "
        "Without the burden of long journeys in traffic, workers can allocate more mental energy directly towards their responsibilities. "
        "Furthermore, contemporary digital platforms enable seamless video conferencing and asynchronous documentation, "
        "allowing global enterprises to operate around the clock without physical barriers.\n\n"
        "On the other hand, the spontaneous synergy of physical office presence cannot be wholly replicated in virtual spaces. "
        "Creative brainstorming sessions often rely on informal hallway conversations and immediate non-verbal feedback. "
        "Additionally, junior staff members frequently benefit from direct observation and mentorship from senior colleagues, "
        "which can be significantly diminished when working in isolation.\n\n"
        "In conclusion, while working remotely undeniably fosters individual focus and efficiency, "
        "a hybrid paradigm balancing remote focus with occasional in-person collaboration represents the optimal strategy. "
        "Organizations that judiciously combine these two models will invariably enjoy higher retention rates, "
        "elevated employee satisfaction, and sustained long-term operational excellence in an increasingly globalized world."
    )
    submission = EssaySubmission.objects.create(
        student=student_user,
        topic=topic,
        max_score=9,
        essay_text=sample_text,
        status=EssaySubmission.Status.PENDING,
    )

    result = grade_ielts_essay(
        essay_text=submission.essay_text,
        topic_title=topic.title,
        task_type="ielts_task2",
        min_words=250,
    )

    assert result["overall_band"] >= 5.0
    assert result["cefr_level"] in ("B1", "B2", "C1", "C2")
    assert len(result["criteria"]) == 4

    # Apply result to submission
    apply_ai_result(submission, result)

    submission.refresh_from_db()
    assert float(submission.total_score) == result["overall_band"]
    assert submission.status == EssaySubmission.Status.GRADED

    criteria_scores = list(submission.criteria.order_by("criterion_id"))
    assert len(criteria_scores) == 4
    # Criterion 1: Task Achievement / Response
    assert criteria_scores[0].name == "Task Achievement / Task Response"
    # Criterion 2: Coherence and Cohesion
    assert criteria_scores[1].name == "Coherence and Cohesion"
    # Criterion 3: Lexical Resource
    assert criteria_scores[2].name == "Lexical Resource"
    # Criterion 4: Grammatical Range and Accuracy
    assert criteria_scores[3].name == "Grammatical Range and Accuracy"


# ---------------------------------------------------------------------------
# 3. Strict Exam Mode & Anti-Cheat Violation Tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_strict_mode_violation_auto_submit(api_client, student_user, strict_test):
    api_client.force_authenticate(user=student_user)

    # Start attempt
    attempt = TestAttempt.objects.create(
        test=strict_test,
        student=student_user,
        status=TestAttempt.Status.IN_PROGRESS,
    )
    assert attempt.violation_count == 0
    assert attempt.cheating_detected is False

    # 1st violation
    url = f"/api/tests/attempts/{attempt.id}/report-violation/"
    res1 = api_client.post(url, {"type": "tab_switch"}, format="json")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["violation_count"] == 1
    assert data1["cheating_detected"] is False
    assert data1["terminated"] is False

    # 2nd violation
    res2 = api_client.post(url, {"type": "window_blur"}, format="json")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["violation_count"] == 2
    assert data2["cheating_detected"] is False

    # 3rd violation -> triggers automatic submission and marks cheating_detected
    res3 = api_client.post(url, {"type": "tab_switch"}, format="json")
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["violation_count"] == 3
    assert data3["cheating_detected"] is True
    assert data3["terminated"] is True

    attempt.refresh_from_db()
    assert attempt.cheating_detected is True
    assert attempt.status == TestAttempt.Status.COMPLETED
    assert len(attempt.violation_logs) == 3


# ---------------------------------------------------------------------------
# 4. 1-Click Attendance with Delayed Absence Alert
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_attendance_quick_mark_present_and_absent(api_client, teacher_user, student_user, student_group):
    api_client.force_authenticate(user=teacher_user)

    # 1. Quick mark 'present'
    payload_present = {
        "group_id": student_group.id,
        "student_id": student_user.id,
        "status": "present",
        "lesson_date": "2026-10-18",
    }
    res = api_client.post("/api/v1/school/attendance/quick-mark/", payload_present, format="json")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["applied"] == 1
    assert data["parent_alert_scheduled"] is False

    # 2. Quick mark 'absent' -> schedules alert
    payload_absent = {
        "group_id": student_group.id,
        "student_id": student_user.id,
        "status": "absent",
        "lesson_date": "2026-10-18",
    }
    with patch("apps.notifications.tasks_parent.send_parent_absence_alert_task.apply_async") as mock_task:
        res_absent = api_client.post("/api/v1/school/attendance/quick-mark/", payload_absent, format="json")
        assert res_absent.status_code == 200
        data_absent = res_absent.json()
        assert data_absent["ok"] is True
        assert data_absent["parent_alert_scheduled"] is True
        assert data_absent["parent_alert_scheduled_in_minutes"] == 15
        mock_task.assert_called_once()
