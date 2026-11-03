"""OMR answer sheet scanner: image validation, honest mark statuses,
student review step, no XP, and CEFR parity with the online pipeline."""

import io
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.contrib.auth import get_user_model
from PIL import Image, ImageDraw
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.courses.models import Course
from apps.results.models import Result
from apps.tests.models import Choice, GapBlank, Question, Test, TestAttempt
from apps.tests.numbering import number_questions
from apps.tests.services import SaveAnswerService, StartAttemptService, SubmitAttemptService

User = get_user_model()
SCAN_URL = "/api/v1/tests/scan-omr/"
CONFIRM_URL = "/api/v1/tests/scan-omr/confirm/"
READ_MARKS = "apps.tests.omr_service.read_marks"


@pytest.fixture
def student(db):
    user = User.objects.create_user(
        email="omr_student@example.com", password="testpassword123", first_name="Ali", role="student"
    )
    Profile.objects.get_or_create(user=user)
    return user


@pytest.fixture
def client(student):
    c = APIClient()
    c.force_authenticate(user=student)
    return c


@pytest.fixture
def mc_test(db):
    teacher = User.objects.create_user(
        email="omr_teacher@example.com", password="testpassword123", first_name="Nilufar", role="teacher"
    )
    course = Course.objects.create(teacher=teacher, title="OMR Prep Course", slug="omr-prep")
    test = Test.objects.create(
        title="BMB Mock 101", course=course, mock_code="BMB-101", subject="uzbek",
        status=Test.Status.PUBLISHED, is_active=True, max_attempts=0,
    )
    for i in range(1, 6):
        q = Question.objects.create(test=test, text=f"Question {i}", position=1000 + i, points=2)
        for idx, letter in enumerate("ABCD", start=1):
            Choice.objects.create(question=q, text=f"Option {letter}", is_correct=(letter == "B"), position=idx)
    return test


def sheet_photo(size=(1200, 1600), color="white", name="sheet.jpg"):
    img = Image.new("RGB", size, color=color)
    draw = ImageDraw.Draw(img)
    for row in range(10):
        draw.rectangle((100, 100 + row * 120, 160, 160 + row * 120), outline="black", width=4)
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


def vision(answers, is_sheet=True):
    return {"is_answer_sheet": is_sheet, "test_code": "", "answers": answers}


# -- Image validation ---------------------------------------------------------


@pytest.mark.django_db
def test_dark_widescreen_screenshot_is_rejected_before_any_ai_call(client, mc_test):
    with patch(READ_MARKS) as read:
        res = client.post(SCAN_URL, {"image": sheet_photo((1920, 1080), color=(32, 33, 36)), "test_id": mc_test.id},
                          format="multipart")
    assert res.status_code == 400
    assert res.json()["code"] == "not_a_sheet"
    read.assert_not_called()


@pytest.mark.django_db
def test_uniform_blank_frame_is_rejected(client, mc_test):
    blank = Image.new("RGB", (1200, 1600), "white")
    buf = io.BytesIO()
    blank.save(buf, "JPEG")
    upload = SimpleUploadedFile("blank.jpg", buf.getvalue(), content_type="image/jpeg")
    with patch(READ_MARKS) as read:
        res = client.post(SCAN_URL, {"image": upload, "test_id": mc_test.id}, format="multipart")
    assert res.status_code == 400
    read.assert_not_called()


@pytest.mark.django_db
def test_non_image_file_is_rejected(client, mc_test):
    upload = SimpleUploadedFile("sheet.jpg", b"%PDF-1.4 not an image", content_type="image/jpeg")
    res = client.post(SCAN_URL, {"image": upload, "test_id": mc_test.id}, format="multipart")
    assert res.status_code == 400
    assert res.json()["code"] == "bad_format"


@pytest.mark.django_db
def test_file_size_limit(client, mc_test, settings):
    settings.OMR_MAX_UPLOAD_BYTES = 1024
    res = client.post(SCAN_URL, {"image": sheet_photo(), "test_id": mc_test.id}, format="multipart")
    assert res.status_code == 400
    assert res.json()["code"] == "file_too_large"


@pytest.mark.django_db
def test_vision_says_not_a_sheet(client, mc_test):
    with patch(READ_MARKS, return_value=vision({"1": ["A"]}, is_sheet=False)):
        res = client.post(SCAN_URL, {"image": sheet_photo(), "test_id": mc_test.id}, format="multipart")
    assert res.status_code == 400
    assert res.json()["code"] == "not_a_sheet"


@pytest.mark.django_db
def test_scan_requires_login(mc_test):
    res = APIClient().post(SCAN_URL, {"image": sheet_photo(), "test_id": mc_test.id}, format="multipart")
    assert res.status_code in (401, 403)


# -- Mark statuses ------------------------------------------------------------


@pytest.mark.django_db
def test_blank_multiple_and_unread_never_become_a(client, mc_test, student):
    marks = {"1": ["B"], "2": [], "3": ["A", "C"], "4": None, "5": ["Z"]}
    with patch(READ_MARKS, return_value=vision(marks)):
        res = client.post(SCAN_URL, {"image": sheet_photo(), "test_id": mc_test.id}, format="multipart")
    # 2 unread of 5 = 40% > 20% threshold → no result
    assert res.status_code == 400
    assert res.json()["code"] == "unreadable"

    marks["5"] = ["D"]
    with patch(READ_MARKS, return_value=vision(marks)):
        res = client.post(SCAN_URL, {"image": sheet_photo(), "test_id": mc_test.id}, format="multipart")
    assert res.status_code == 200
    items = res.json()["items"]
    assert [i["key"] for i in items] == ["1", "2", "3", "4", "5"]  # test order, not position 1001…
    assert [(i["status"], i["value"]) for i in items] == [
        ("clear", "B"), ("blank", ""), ("multiple", ""), ("unread", ""), ("clear", "D"),
    ]
    # Scanning alone grades nothing and gives no XP.
    assert not TestAttempt.objects.filter(student=student).exists()
    assert Profile.objects.get(user=student).xp_points == 0


@pytest.mark.django_db
def test_archived_test_is_not_offered(client, mc_test):
    Test.objects.filter(pk=mc_test.pk).update(status=Test.Status.ARCHIVED)
    data = client.get(SCAN_URL).json()
    assert mc_test.id not in [t["id"] for t in data["tests"]]


# -- Confirm step -------------------------------------------------------------


@pytest.mark.django_db
def test_confirm_grades_reviewed_answers_without_xp(client, mc_test, student):
    qs = [nq.question for nq in number_questions(mc_test)]
    answers = {str(qs[0].id): "B", str(qs[1].id): "B", str(qs[2].id): "A", str(qs[3].id): ""}
    res = client.post(CONFIRM_URL, {"test_id": mc_test.id, "answers": answers}, format="json")
    assert res.status_code == 200, res.json()
    body = res.json()
    assert body["xp_earned"] == 0
    result = Result.objects.get(pk=body["result_id"])
    assert (result.correct_answers, result.wrong_answers, result.unanswered) == (2, 1, 2)

    # A FREE student's one free test is now used: a second sheet hits the
    # same plan limit as starting the test online.
    res = client.post(CONFIRM_URL, {"test_id": mc_test.id, "answers": answers}, format="json")
    assert res.status_code == 403
    assert res.json()["code"] == "LIMIT_EXCEEDED"

    # With a plan, a second sheet is a second attempt — still without XP.
    unlimited = (True, "", {"tier": "pro", "allowed": True})
    with patch("apps.subscriptions.services.quota.QuotaService.check_test_quota", return_value=unlimited):
        res = client.post(CONFIRM_URL, {"test_id": mc_test.id, "answers": answers}, format="json")
    assert res.status_code == 200
    assert Profile.objects.get(user=student).xp_points == 0


@pytest.mark.django_db
def test_confirm_rejects_foreign_question_and_bad_letter(client, mc_test):
    qs = [nq.question for nq in number_questions(mc_test)]
    res = client.post(CONFIRM_URL, {"test_id": mc_test.id, "answers": {"999999": "A"}}, format="json")
    assert res.status_code == 400
    res = client.post(CONFIRM_URL, {"test_id": mc_test.id, "answers": {str(qs[0].id): "F"}}, format="json")
    assert res.status_code == 400
    assert not TestAttempt.objects.exists()


# -- CEFR parity ----------------------------------------------------------------


@pytest.fixture
def cefr_test(db):
    User.objects.create_superuser(email="omr_admin@example.com", password="x-Pass-123!")
    call_command("import_cd_mock", "record_mock_1", "--publish", stdout=StringIO())
    return Test.objects.get(mock_code="CEFR-RECORD-1-CD")


def _key(q):
    if q.question_type == Question.QuestionType.INLINE_GAP_FILL:
        return GapBlank.objects.filter(question=q).order_by("position").first().answer_text
    choices = sorted(q.choices.all(), key=lambda c: (c.position, c.id))
    return "ABCDEFGHIJ"[[c.is_correct for c in choices].index(True)]


@pytest.mark.django_db
def test_cefr_numbering_has_70_objective_questions(cefr_test):
    numbered = number_questions(cefr_test)
    assert cefr_test.questions.count() == 81  # incl. 3 writing tasks + 8 speaking prompts
    assert len(numbered) == 70
    assert [n.key for n in numbered][:2] == ["L1", "L2"]
    assert numbered[35].key == "R1" and numbered[-1].key == "R35"


@pytest.mark.django_db
def test_cefr_omr_and_online_give_the_same_result(client, cefr_test, student):
    numbered = number_questions(cefr_test)
    # 20 right in Listening, 30 right in Reading, rest blank.
    chosen = [nq for nq in numbered if nq.section_code == "LISTENING"][:20] + [
        nq for nq in numbered if nq.section_code == "READING"
    ][:30]
    answers = {str(nq.question.id): _key(nq.question) for nq in chosen}

    res = client.post(CONFIRM_URL, {"test_id": cefr_test.id, "answers": answers}, format="json")
    assert res.status_code == 200, res.json()
    omr_attempt = TestAttempt.objects.get(pk=res.json()["attempt_id"])

    online = StartAttemptService.execute(test_id=cefr_test.id, student=student)
    for nq in chosen:
        q = nq.question
        if q.question_type == Question.QuestionType.INLINE_GAP_FILL:
            SaveAnswerService.execute(attempt_id=online.id, question_id=q.id, student=student,
                                      text_answer=_key(q))
        else:
            right = q.choices.get(is_correct=True)
            SaveAnswerService.execute(attempt_id=online.id, question_id=q.id, student=student,
                                      choice_ids=[right.id])
    SubmitAttemptService.execute(attempt_id=online.id, student=student)
    online.refresh_from_db()

    for attempt in (omr_attempt, online):
        assert attempt.band_score is None
        assert attempt.section_scores["LISTENING"]["earned"] == 20
        assert attempt.section_scores["READING"]["earned"] == 30
        result = Result.objects.get(attempt=attempt)
        assert result.total_questions == 70
        assert result.correct_answers == 50
        assert int(result.max_score) == 70
    assert omr_attempt.section_scores == online.section_scores

    detail = client.get(f"/api/results/{Result.objects.get(attempt=omr_attempt).id}/detail/").json()
    assert detail["exam_type"] == "cefr_multilevel"
    assert "band" not in str(detail["cefr_summary"]).lower()
    numbered_keys = [q["number_key"] for q in detail["question_details"] if q["number_key"]]
    assert len(numbered_keys) == 70 and numbered_keys[0] == "L1"
