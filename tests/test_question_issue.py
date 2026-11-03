"""'Problem with this question?': submit, duplicates, threshold + single Telegram summary, permissions, XSS."""

import json
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.courses.models import Course
from apps.notifications.models import UserFeedback
from apps.tests.models import (
    Choice,
    ExamPart,
    ExamSection,
    Question,
    QuestionGroup,
    Test,
    TestAttempt,
)

User = get_user_model()
URL = "/api/v1/feedback/question-issue/"
SECRET_KEY_TEXT = "Zanzibar-is-the-secret-key"


def make_user(email, role="student"):
    user = User.objects.create_user(email=email, password="x-Pass-123!", role=role, first_name="Komiljon", last_name="Roziyev")
    Profile.objects.get_or_create(user=user)
    return user


def client(user=None):
    c = APIClient()
    if user:
        c.force_authenticate(user)
    return c


@pytest.fixture(autouse=True)
def _fresh_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def world(db):
    teacher = make_user("qi_teacher@example.test", "teacher")
    course = Course.objects.create(teacher=teacher, title="QI", slug="qi-course")
    test = Test.objects.create(title="Issue test", course=course, is_active=True, max_attempts=0, status="published")
    section = ExamSection.objects.create(test=test, name="Reading", code="READING", order=1, duration_minutes=30)
    part = ExamPart.objects.create(section=section, number="3", order=1)
    group = QuestionGroup.objects.create(part=part, title="Headings", order=1)
    question = Question.objects.create(
        test=test, section=section, group=group, text="Which heading fits paragraph B?", position=1,
        question_type="MULTIPLE_CHOICE", config={"number": 1}, explanation=SECRET_KEY_TEXT,
    )
    Choice.objects.create(question=question, text="Wrong one", is_correct=False, position=1)
    Choice.objects.create(question=question, text=SECRET_KEY_TEXT, is_correct=True, position=2)

    def student(n):
        user = make_user(f"qi_student{n}@example.test")
        TestAttempt.objects.create(test=test, student=user)
        return user

    admin = User.objects.create_superuser(email="qi_admin@example.test", password="x-Pass-123!")
    return dict(test=test, question=question, student=student, admin=admin, teacher=teacher)


def report(user, question, reason="wrong_key", **extra):
    return client(user).post(URL, {"question_id": question.id, "reason": reason, **extra}, format="json")


@pytest.mark.django_db
def test_report_is_stored_with_context_and_without_the_answer_key(world):
    user = world["student"](1)
    res = report(user, world["question"], comment="Heading B looks wrong", given="Wrong one")
    assert res.status_code == 201, res.content
    fb = UserFeedback.objects.get(pk=res.json()["id"])
    assert fb.category == "question_issue" and fb.reason == "wrong_key" and fb.question_id == world["question"].id
    assert fb.rating == 0 and fb.user == user and fb.message == "Heading B looks wrong"
    assert fb.context["test_id"] == world["test"].id
    assert fb.context["section"] == "Reading" and fb.context["part"] == "3" and fb.context["number"] == "1"
    assert fb.context["given"] == "Wrong one"
    assert SECRET_KEY_TEXT not in json.dumps(fb.context) and SECRET_KEY_TEXT not in fb.message


@pytest.mark.django_db
def test_reason_validation_and_other_needs_a_comment(world):
    user = world["student"](1)
    assert report(user, world["question"], reason="nonsense").status_code == 400
    assert report(user, world["question"], reason="other").status_code == 400
    assert report(user, world["question"], reason="other", comment="The audio cuts off").status_code == 201


@pytest.mark.django_db
def test_only_people_who_sat_the_test_can_report(world):
    outsider = make_user("qi_outsider@example.test")
    assert report(outsider, world["question"]).status_code == 403
    assert client().post(URL, {"question_id": world["question"].id, "reason": "unclear"}, format="json").status_code in (401, 403)
    assert report(world["teacher"], world["question"], reason="unclear").status_code == 201
    assert UserFeedback.objects.count() == 1


@pytest.mark.django_db
def test_one_active_report_per_user_and_question(world):
    user = world["student"](1)
    first = report(user, world["question"])
    second = report(user, world["question"], reason="unclear")
    assert first.status_code == 201 and second.status_code == 200 and second.json()["duplicate"] is True
    assert UserFeedback.objects.filter(user=user, question=world["question"]).count() == 1
    # Once an admin resolves it, the same user may report again.
    UserFeedback.objects.update(status="resolved")
    assert report(user, world["question"]).status_code == 201


@pytest.mark.django_db
def test_three_reports_flag_the_question_and_send_exactly_one_summary(world, django_capture_on_commit_callbacks):
    q = world["question"]
    with patch("apps.notifications.tasks.notify_admin_question_needs_review.delay") as summary, patch(
        "apps.notifications.tasks.notify_admin_new_feedback.delay"
    ) as per_report:
        for n in (1, 2):
            with django_capture_on_commit_callbacks(execute=True):
                assert report(world["student"](n), q).status_code == 201
        q.refresh_from_db()
        assert q.needs_review is False and summary.call_count == 0
        for n in (3, 4, 5):
            with django_capture_on_commit_callbacks(execute=True):
                assert report(world["student"](n), q, reason="unclear").status_code == 201
        q.refresh_from_db()
    assert q.needs_review is True
    summary.assert_called_once_with(q.id)  # not once per report
    per_report.assert_not_called()  # no per-report Telegram message either


@pytest.mark.django_db
def test_summary_task_sends_one_message_without_key_or_names(world):
    q = world["question"]
    for n in (1, 2, 3):
        report(world["student"](n), q, comment="<b>bad</b> key")
    sent = []
    with patch("apps.notifications.tasks.TelegramService", create=True), patch(
        "apps.notifications.services.telegram_service.TelegramService.send_message",
        side_effect=lambda **kw: sent.append(kw),
    ), patch("django.conf.settings.ADMIN_TELEGRAM_ID", 12345, create=True):
        from apps.notifications.tasks import notify_admin_question_needs_review

        out = notify_admin_question_needs_review.apply(args=[q.id]).get()
    assert out["status"] == "sent" and len(sent) == 1
    text = sent[0]["text"]
    assert "3 ta faol shikoyat" in text and f"/panel/tests/{world['test'].id}/questions" in text
    assert SECRET_KEY_TEXT not in text and "Komiljon" not in text and "<b>bad</b>" not in text


@pytest.mark.django_db
def test_xss_in_comment_is_stripped_and_escaped_in_admin_data(world):
    res = report(world["student"](1), world["question"], reason="other", comment='<script>alert(1)</script>Broken <img src=x onerror=1>')
    fb = UserFeedback.objects.get(pk=res.json()["id"])
    assert "<" not in fb.message and ">" not in fb.message and fb.message.endswith("Broken")


@pytest.mark.django_db
def test_general_endpoint_refuses_question_issue_category(world):
    res = client(world["student"](1)).post(
        "/api/v1/feedback/", {"rating": 3, "category": "question_issue", "message": "no question here"}, format="json"
    )
    assert res.status_code == 400 and res.json()["error"] == "bad_category"


@pytest.mark.django_db
def test_admin_groups_filter_and_privacy(world):
    q = world["question"]
    mine = world["student"](1)
    report(mine, q)
    report(world["student"](2), q, reason="unclear")

    admin = client(world["admin"])
    groups = admin.get("/api/v1/panel/feedback/questions/").json()
    assert groups["threshold"] == 3
    row = groups["results"][0]
    assert row["question_id"] == q.id and row["active"] == 2 and row["total"] == 2
    assert row["reasons"] == {"wrong_key": 1, "unclear": 1} and row["edit_path"] == f"/panel/tests/{world['test'].id}/questions"
    assert SECRET_KEY_TEXT not in json.dumps(groups)

    inbox = admin.get("/api/v1/panel/feedback/", {"category": "question_issue"}).json()
    assert inbox["count"] == 2 and all(r["category"] == "question_issue" and r["question_id"] == q.id for r in inbox["results"])
    assert inbox["stats"]["average_rating"] == 0  # reports do not skew the rating

    assert client(mine).get("/api/v1/panel/feedback/questions/").status_code == 403
    assert client().get("/api/v1/panel/feedback/questions/").status_code in (401, 403)
    # a student sees only their own report, never someone else's
    own = client(mine).get("/api/v1/feedback/mine/").json()["results"]
    assert len(own) == 1 and own[0]["reason"] == "wrong_key"
    # and a question report can never be published on the landing page
    assert client().get("/api/v1/feedback/public/").json()["count"] == 0


@pytest.mark.django_db
def test_rate_limit(world):
    user = world["student"](1)
    codes = [report(user, world["question"]).status_code for _ in range(31)]
    assert codes[0] == 201 and 429 in codes[-3:]
