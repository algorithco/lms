"""Paywall honesty and the free trial of one CEFR mock part.

- Teachers and admins are never quota-limited.
- Quota messages quote the configured prices, not hardcoded ones.
- A FREE student with a used-up quota may open Reading Part 1 once: only
  that part is served, saved and graded, as a preview, with no estimate.
- CEFR cards count 70 questions and carry the B1 rule.
"""

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.results.models import Result
from apps.subscriptions.services.quota import QuotaService
from apps.tests.models import Question, Test, TestAttempt

User = get_user_model()


@pytest.fixture
def cefr_test(db):
    User.objects.create_superuser(email="trial_admin@example.com", password="x-Pass-123!")
    call_command("import_cd_mock", "record_mock_1", "--publish", stdout=StringIO())
    return Test.objects.get(mock_code="CEFR-RECORD-1-CD")


@pytest.fixture
def free_student(db, cefr_test):
    user = User.objects.create_user(email="trial_student@example.com", password="x-Pass-123!", role="student")
    Profile.objects.get_or_create(user=user)
    # The one free test is already used on another test.
    other = Test.objects.exclude(pk=cefr_test.pk).first() or Test.objects.create(
        title="Other", course=cefr_test.course, is_active=True
    )
    TestAttempt.objects.create(test=other, student=user, status=TestAttempt.Status.COMPLETED)
    return user


def client_for(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
def test_teacher_is_not_quota_limited():
    teacher = User.objects.create_user(email="t@example.com", password="x-Pass-123!", role="teacher")
    allowed, _msg, details = QuotaService.check_test_quota(teacher)
    assert allowed is True
    assert details["tier"] == "admin"


@pytest.mark.django_db
@override_settings(PLAN_STARTER_PRICE=7000, PLAN_PRO_PRICE=15000)
def test_quota_message_uses_configured_prices(free_student):
    allowed, msg, _ = QuotaService.check_test_quota(free_student)
    assert allowed is False
    assert "7 000" in msg and "15 000" in msg
    assert "49 000" not in msg


@pytest.mark.django_db
def test_cefr_card_counts_70_questions_and_b1_rule(free_student, cefr_test):
    data = client_for(free_student).get(f"/api/tests/{cefr_test.id}/").json()
    assert data["total_questions"] == 70
    assert data["cefr_scale"] == {"scale_max": 75, "level": "B1", "min": 38}
    assert data["free_trial"]["section_code"] == "READING"
    assert data["free_trial"]["part"] == "1"
    assert data["free_trial"]["used"] is False

    listed = client_for(free_student).get("/api/tests/?page_size=100").json()
    rows = listed.get("results", listed)
    row = next(r for r in rows if r["id"] == cefr_test.id)
    assert row["total_questions"] == 70


@pytest.mark.django_db
def test_free_trial_opens_only_reading_part_1(free_student, cefr_test):
    c = client_for(free_student)
    assert c.post(f"/api/tests/{cefr_test.id}/start/", {"mode": "strict"}, format="json").status_code == 403

    res = c.post(f"/api/tests/{cefr_test.id}/start/", {"mode": "practice", "trial": True}, format="json")
    assert res.status_code in (200, 201), res.json()
    attempt_id = res.json().get("id") or res.json().get("attempt_id")
    attempt = TestAttempt.objects.get(pk=attempt_id)
    assert attempt.trial_part is not None and attempt.is_preview

    detail = c.get(f"/api/tests/attempts/{attempt_id}/").json()
    assert detail["is_trial"] is True
    assert len(detail["questions"]) == 6
    assert [p["number"] for s in detail["structure"] for p in s["parts"]] == ["1"]

    listening_q = Question.objects.filter(test=cefr_test, section__code="LISTENING").first()
    bad = c.post(
        f"/api/tests/attempts/{attempt_id}/save-answer/",
        {"question_id": listening_q.id, "choice_ids": [listening_q.choices.first().id]},
        format="json",
    )
    assert bad.status_code == 400

    q = Question.objects.get(pk=detail["questions"][0]["id"])
    word = q.gap_blanks.order_by("position").first().answer_text
    ok = c.post(
        f"/api/tests/attempts/{attempt_id}/save-answer/",
        {"question_id": q.id, "text_answer": word, "gap_answers": {"1": word}},
        format="json",
    )
    assert ok.status_code == 200, ok.json()

    assert c.post(f"/api/tests/attempts/{attempt_id}/submit/", format="json").status_code == 200
    assert Profile.objects.get(user=free_student).xp_points == 0  # trial is a preview: no XP
    attempt.refresh_from_db()
    assert attempt.band_score is None
    assert not attempt.section_scores
    result = Result.objects.get(attempt=attempt)
    assert result.total_questions == 6
    assert result.correct_answers == 1

    body = c.get(f"/api/results/{result.id}/detail/").json()
    assert body["cefr_summary"] is None
    assert body["trial_part"]["part"] == "1"
    assert len(body["question_details"]) == 6

    # Once per test.
    again = c.post(f"/api/tests/{cefr_test.id}/start/", {"mode": "practice", "trial": True}, format="json")
    assert again.status_code == 403
    assert client_for(free_student).get(f"/api/tests/{cefr_test.id}/").json()["free_trial"]["used"] is True
