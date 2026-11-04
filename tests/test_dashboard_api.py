"""Dashboard API: only real data, scoped by subject, same tier as /me."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.courses.models import Course
from apps.results.models import Result
from apps.tests.models import (
    Choice,
    ExamPart,
    ExamSection,
    Question,
    QuestionGroup,
    StudentAnswer,
    Test,
    TestAttempt,
)

User = get_user_model()
URL = "/api/v1/dashboard/"


def make_user(email, role="student"):
    user = User.objects.create_user(email=email, password="x-Pass-123!", role=role, first_name="komiljon", last_name="ROZIYEV")
    Profile.objects.get_or_create(user=user)
    return user


def client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def world(db):
    teacher = make_user("db_teacher@example.test", "teacher")
    course = Course.objects.create(teacher=teacher, title="DB", slug="db-course")
    student = make_user("db_student@example.test")
    other = make_user("db_other@example.test")

    def new_test(title, subject, **kw):
        return Test.objects.create(title=title, course=course, is_active=True, max_attempts=0, status="published", subject=subject, **kw)

    def finish(user, test, pct, *, section_scores=None, trial=False, preview=False):
        attempt = TestAttempt.objects.create(
            test=test, student=user, status="completed", is_preview=preview, section_scores=section_scores or {}
        )
        result = Result.objects.create(
            attempt=attempt, student=user, test=test, course=course, total_questions=10,
            correct_answers=int(pct / 10), wrong_answers=10 - int(pct / 10), score=Decimal(pct), max_score=Decimal(100),
            percentage=Decimal(pct), is_passed=pct >= 50,
        )
        return attempt, result

    return dict(teacher=teacher, course=course, student=student, other=other, new_test=new_test, finish=finish)


@pytest.mark.django_db
def test_new_user_gets_empty_data_not_demo_numbers(world):
    data = client(world["student"]).get(URL, {"subject": "english"}).json()
    assert data["subject"] == "english"
    assert data["resume"] is None and data["recent"] == [] and data["weak_parts"] == [] and data["goal"] is None
    ind = data["indicators"]
    assert ind["tests_taken"] == 0
    assert ind["average_percentage"] is None and ind["best_percentage"] is None and ind["best_grade"] is None
    assert ind["best_sections"] == {} and ind["best_overall"] is None
    assert ind["essays"] == {"count": 0, "last_score": None, "last_max": None, "recent": []}


@pytest.mark.django_db
def test_requires_login():
    assert APIClient().get(URL).status_code in (401, 403)


@pytest.mark.django_db
def test_tier_is_the_same_function_as_me(world):
    c = client(world["student"])
    assert c.get(URL).json()["tier"].upper() == c.get("/api/auth/me/").json()["plan"]


@pytest.mark.django_db
def test_subjects_never_mix_and_other_users_are_invisible(world):
    uz = world["new_test"]("BMB mock", "uzbek")
    en = world["new_test"]("English mock", "english")
    world["finish"](world["student"], uz, 80)
    world["finish"](world["student"], en, 40)
    world["finish"](world["other"], en, 100)

    d_uz = client(world["student"]).get(URL, {"subject": "uzbek"}).json()
    d_en = client(world["student"]).get(URL, {"subject": "english"}).json()
    assert d_uz["indicators"]["tests_taken"] == 1 and d_uz["indicators"]["average_percentage"] == 80.0
    assert [r["title"] for r in d_uz["recent"]] == ["BMB mock"] and d_uz["recent"][0]["kind"] == "bmb"
    assert d_en["indicators"]["tests_taken"] == 1 and d_en["indicators"]["best_percentage"] == 40.0
    assert [r["title"] for r in d_en["recent"]] == ["English mock"] and d_en["recent"][0]["kind"] == "general"
    assert d_uz["indicators"]["best_grade"] is not None and d_en["indicators"]["best_grade"] is None


@pytest.mark.django_db
def test_previews_and_free_trials_do_not_count(world):
    en = world["new_test"]("CEFR mock", "english", exam_type="cefr_multilevel")
    world["finish"](world["student"], en, 90, preview=True)
    data = client(world["student"]).get(URL, {"subject": "english"}).json()
    assert data["indicators"]["tests_taken"] == 0 and data["recent"] == []


@pytest.mark.django_db
def test_recent_is_capped_at_three_and_cefr_shows_section_scores(world):
    en = world["new_test"]("CEFR mock", "english", exam_type="cefr_multilevel")
    for i in range(4):
        world["finish"](world["student"], en, 50 + i)
    data = client(world["student"]).get(URL, {"subject": "english"}).json()
    assert len(data["recent"]) == 3 and data["recent"][0]["kind"] == "cefr"
    assert data["indicators"]["tests_taken"] == 4


@pytest.mark.django_db
def test_resume_points_to_the_right_screen(world):
    uz = world["new_test"]("BMB mock", "uzbek")
    en = world["new_test"]("English mock", "english")
    a_uz = TestAttempt.objects.create(test=uz, student=world["student"])
    a_en = TestAttempt.objects.create(test=en, student=world["student"])
    c = client(world["student"])
    assert c.get(URL, {"subject": "uzbek"}).json()["resume"]["route"] == f"/take/{a_uz.id}"
    assert c.get(URL, {"subject": "english"}).json()["resume"]["route"] == f"/english-exam/{a_en.id}"
    assert client(world["other"]).get(URL, {"subject": "uzbek"}).json()["resume"] is None


@pytest.mark.django_db
def test_weak_parts_come_from_real_answers_by_part(world):
    test = world["new_test"]("English mock", "english")
    reading = ExamSection.objects.create(test=test, name="Reading", code="READING", order=1, duration_minutes=30)
    parts = {}
    for number in ("1", "3"):
        part = ExamPart.objects.create(section=reading, number=number, order=int(number))
        group = QuestionGroup.objects.create(part=part, order=1)
        parts[number] = [
            Question.objects.create(test=test, section=reading, group=group, text=f"Q{number}.{i}", position=int(number) * 10 + i,
                                    question_type="MULTIPLE_CHOICE")
            for i in range(3)
        ]
    attempt, _ = world["finish"](world["student"], test, 50)
    # Part 1: 3/3 right. Part 3: 1/3 right, one skipped.
    for q in parts["1"]:
        StudentAnswer.objects.create(attempt=attempt, question=q, is_correct=True)
    StudentAnswer.objects.create(attempt=attempt, question=parts["3"][0], is_correct=True)
    StudentAnswer.objects.create(attempt=attempt, question=parts["3"][1], is_correct=False)

    weak = client(world["student"]).get(URL, {"subject": "english"}).json()["weak_parts"]
    assert len(weak) == 1  # part 1 is perfect, not weak
    assert weak[0]["part"] == "3" and weak[0]["section_code"] == "READING"
    assert (weak[0]["correct"], weak[0]["total"]) == (1, 3)  # the skipped question counts as a miss


@pytest.mark.django_db
def test_weak_parts_need_two_groups_to_compare(world):
    test = world["new_test"]("Flat test", "uzbek")
    qs = [Question.objects.create(test=test, text=f"Q{i}", position=i, question_type="single") for i in range(4)]
    attempt, _ = world["finish"](world["student"], test, 50)
    for q in qs[:2]:
        StudentAnswer.objects.create(attempt=attempt, question=q, is_correct=True)
    assert client(world["student"]).get(URL, {"subject": "uzbek"}).json()["weak_parts"] == []


@pytest.mark.django_db
def test_goal_only_for_the_goal_subject_and_compared_with_results(world):
    profile = world["student"].profile
    profile.exam_target, profile.target_grade, profile.onboarding_completed = "national_certificate", "A", True
    profile.save()
    uz = world["new_test"]("BMB mock", "uzbek")
    world["finish"](world["student"], uz, 90)
    c = client(world["student"])
    goal = c.get(URL, {"subject": "uzbek"}).json()["goal"]
    assert goal["target"] == "A" and goal["current"] == "A+" and goal["reached"] is True
    assert c.get(URL, {"subject": "english"}).json()["goal"] is None  # a BMB goal is not an English goal

    profile.onboarding_completed = False
    profile.save()
    assert c.get(URL, {"subject": "uzbek"}).json()["goal"] is None  # no onboarding, no goal


@pytest.mark.django_db
def test_invalid_subject_falls_back_instead_of_failing(world):
    assert client(world["student"]).get(URL, {"subject": "klingon"}).json()["subject"] == "uzbek"


@pytest.mark.django_db
def test_recent_essays_are_real_per_subject_and_pending_has_no_score(world):
    from apps.essays.models import EssaySubmission, EssayTopic

    uz_topic = EssayTopic.objects.create(title="Kitob", description="d", subject="uzbek")
    en_topic = EssayTopic.objects.create(title="IELTS T2", description="d", subject="english", category="ielts_task2", rubric_type="ielts_task2")
    EssaySubmission.objects.create(student=world["student"], topic=uz_topic, status="graded", total_score=48, max_score=60)
    EssaySubmission.objects.create(student=world["student"], topic=None, custom_title="O'z mavzum", status="pending")
    EssaySubmission.objects.create(student=world["student"], topic=en_topic, status="graded", total_score=6.5, max_score=9)
    EssaySubmission.objects.create(student=world["other"], topic=uz_topic, status="graded", total_score=60, max_score=60)

    uz = client(world["student"]).get(URL, {"subject": "uzbek"}).json()["indicators"]["essays"]
    titles = [e["title"] for e in uz["recent"]]
    assert sorted(titles) == ["Kitob", "O'z mavzum"]  # max two, own essays only, no English
    pending = next(e for e in uz["recent"] if e["title"] == "O'z mavzum")
    assert pending["total_score"] is None and pending["max_score"] is None  # nothing invented while grading

    en = client(world["student"]).get(URL, {"subject": "english"}).json()["indicators"]["essays"]
    assert [e["title"] for e in en["recent"]] == ["IELTS T2"] and en["recent"][0]["overall_band"] == 6.5
