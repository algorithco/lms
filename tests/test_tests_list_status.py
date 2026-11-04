"""Tests list: each card carries the caller's own state (not started / in progress / submitted) and section names."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.courses.models import Course
from apps.results.models import Result
from apps.tests.models import ExamSection, Test, TestAttempt

User = get_user_model()


def make_user(email, role="student"):
    user = User.objects.create_user(email=email, password="x-Pass-123!", role=role)
    Profile.objects.get_or_create(user=user)
    return user


@pytest.fixture
def world(db):
    teacher = make_user("tl_teacher@example.test", "teacher")
    course = Course.objects.create(teacher=teacher, title="TL", slug="tl-course")
    student = make_user("tl_student@example.test")
    other = make_user("tl_other@example.test")

    def new_test(title, subject="uzbek", **kw):
        return Test.objects.create(title=title, course=course, is_active=True, max_attempts=0, status="published", subject=subject, **kw)

    return dict(course=course, student=student, other=other, new_test=new_test)


def listing(user, subject):
    c = APIClient()
    c.force_authenticate(user)
    res = c.get("/api/tests/", {"subject": subject})
    assert res.status_code == 200, res.content
    return {r["id"]: r for r in res.json()["results"]}


@pytest.mark.django_db
def test_status_none_in_progress_done_and_per_user(world):
    fresh = world["new_test"]("Fresh")
    running = world["new_test"]("Running")
    done = world["new_test"]("Done")
    english = world["new_test"]("English one", subject="english", exam_type="cefr_multilevel")
    ExamSection.objects.create(test=english, name="Listening", code="LISTENING", order=1)
    ExamSection.objects.create(test=english, name="Reading", code="READING", order=2)

    TestAttempt.objects.create(test=running, student=world["student"])
    attempt = TestAttempt.objects.create(test=done, student=world["student"], status="completed")
    Result.objects.create(
        attempt=attempt, student=world["student"], test=done, course=world["course"], total_questions=10,
        correct_answers=7, wrong_answers=3, score=Decimal(7), max_score=Decimal(10), percentage=Decimal(70), is_passed=True,
    )
    en_attempt = TestAttempt.objects.create(test=english, student=world["student"])

    mine = listing(world["student"], "uzbek")
    assert mine[fresh.id]["my_status"] == {"state": "none"}
    assert mine[running.id]["my_status"]["state"] == "in_progress"
    assert mine[running.id]["my_status"]["route"].startswith("/take/")
    assert mine[done.id]["my_status"] == {
        "state": "done", "result_id": Result.objects.get(attempt=attempt).id, "percentage": 70.0, "correct": 7, "total": 10,
    }

    en = listing(world["student"], "english")[english.id]
    assert en["my_status"]["route"] == f"/english-exam/{en_attempt.id}"
    assert en["section_names"] == ["Listening", "Reading"]

    # Someone else's attempts never show up on my cards.
    theirs = listing(world["other"], "uzbek")
    assert all(r["my_status"] == {"state": "none"} for r in theirs.values())


@pytest.mark.django_db
def test_previews_do_not_count_as_taken(world):
    test = world["new_test"]("Preview only")
    TestAttempt.objects.create(test=test, student=world["student"], is_preview=True)
    assert listing(world["student"], "uzbek")[test.id]["my_status"] == {"state": "none"}


@pytest.mark.django_db
def test_guest_gets_no_status(world):
    test = world["new_test"]("Public")
    res = APIClient().get("/api/tests/", {"subject": "uzbek"})
    assert res.status_code == 200
    row = next(r for r in res.json()["results"] if r["id"] == test.id)
    assert row["my_status"] == {"state": "none"}
