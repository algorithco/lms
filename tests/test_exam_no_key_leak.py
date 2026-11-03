"""Answer keys never reach the browser while an exam is running (start, attempt, test detail, save-answer)."""

import json
import re

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.courses.models import Course
from apps.tests.models import Choice, GapBlank, Question, Test

User = get_user_model()
SUSPECT = re.compile(
    r'"(is_correct|correct_choice|correct_choices|correct_text|correct_answer|answer_key|correct_option|correct_pair|explanation)"'
)


@pytest.fixture
def exam(db):
    teacher = User.objects.create_user(email="leak_t@example.test", password="x-Pass-123!", role="teacher")
    student = User.objects.create_user(email="leak_s@example.test", password="x-Pass-123!", role="student")
    Profile.objects.get_or_create(user=student)
    course = Course.objects.create(teacher=teacher, title="K", slug="key-leak")
    test = Test.objects.create(title="Leak exam", course=course, is_active=True, max_attempts=0, status="published")
    mc = Question.objects.create(test=test, text="2+2?", position=1, points=1, explanation="Because four", question_type="single")
    for i, (txt, ok) in enumerate((("3", False), ("4", True)), start=1):
        Choice.objects.create(question=mc, text=txt, is_correct=ok, position=i)
    gap = Question.objects.create(
        test=test, text="Fill (1) ____", position=2, points=1, question_type="INLINE_GAP_FILL", correct_text="secret"
    )
    GapBlank.objects.create(question=gap, position=1, answer_text="secret")
    return test, student, mc


def keys_in(payload) -> set[str]:
    return set(SUSPECT.findall(json.dumps(payload)))


@pytest.mark.django_db
def test_no_answer_keys_in_any_exam_response(exam):
    test, student, mc = exam
    c = APIClient()
    c.force_authenticate(student)
    started = c.post(f"/api/tests/{test.id}/start/", {"mode": "strict"}, format="json")
    assert started.status_code in (200, 201), started.content
    aid = started.json().get("id") or started.json().get("attempt_id")
    assert keys_in(started.json()) == set()
    assert keys_in(c.get(f"/api/tests/{test.id}/").json()) == set()
    assert keys_in(c.get(f"/api/tests/attempts/{aid}/").json()) == set()
    raw = json.dumps(c.get(f"/api/tests/attempts/{aid}/").json())
    assert "secret" not in raw and "Because four" not in raw

    choice = mc.choices.get(is_correct=True)
    saved = c.post(
        f"/api/tests/attempts/{aid}/save-answer/", {"question_id": mc.id, "choice_ids": [choice.id]}, format="json"
    )
    assert saved.status_code == 200, saved.content
    assert keys_in(saved.json()) == set()
    assert "is_correct" not in json.dumps(saved.json())
