"""Cost and abuse control: OCR, autosave, daily AI caps, XP farming and the OMR scanner."""

from __future__ import annotations

import io
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.essays.models import EssaySubmission
from apps.payments import ai_quota
from apps.payments.models import SubscriptionPlan
from apps.payments.subscriptions import grant_subscription
from apps.tests import xp_rules

User = get_user_model()


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def _user(email, role="student"):
    u = User.objects.create_user(email=email, password="x-Pass-123!", role=role)
    Profile.objects.get_or_create(user=u)
    return u


def _plan(plan_type, **fields):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        plan_type=plan_type, defaults={"name": plan_type.title(), "price_monthly": Decimal("15000"), **fields}
    )
    return plan


def _subscribed(email, plan_type, **fields):
    u = _user(email)
    admin = User.objects.create_superuser(email=f"adm_{email}", password="x-Pass-123!")
    grant_subscription(u, _plan(plan_type, **fields), kind="admin", actor=admin, days=30, reason="test")
    return u


def _api(user=None):
    c = APIClient()
    if user:
        c.force_authenticate(user)
    return c


def _page(content_type="image/jpeg", size=10):
    return SimpleUploadedFile("p.jpg", b"x" * size, content_type=content_type)


class _OCR:
    text = "text"
    is_probably_incomplete = False
    warnings: list = []


OCR_URL = "/api/v1/essays/ocr/"


# --------------------------------------------------------------------------
# OCR
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_ocr_requires_login():
    assert _api().post(OCR_URL, {"pages": [_page()]}, format="multipart").status_code in (401, 403)


@pytest.mark.django_db
def test_ocr_refuses_free_and_starter_plans_without_calling_the_provider():
    free = _user("ocr_free@example.test")
    starter = _subscribed("ocr_starter@example.test", "starter", image_essay_weekly_limit=0)
    with patch("apps.essays.ocr.extract_text", return_value=_OCR()) as ocr:
        for u in (free, starter):
            res = _api(u).post(OCR_URL, {"pages": [_page()]}, format="multipart")
            assert res.status_code == 403 and res.json()["code"] == "plan_required"
    ocr.assert_not_called()


@pytest.mark.django_db
def test_pro_gets_five_ocr_calls_a_day_then_429():
    pro = _subscribed("ocr_pro@example.test", "pro", image_essay_weekly_limit=15)
    with patch("apps.essays.ocr.extract_text", return_value=_OCR()) as ocr:
        codes = [_api(pro).post(OCR_URL, {"pages": [_page()]}, format="multipart").status_code for _ in range(6)]
    assert codes == [200, 200, 200, 200, 200, 429]
    assert ocr.call_count == 5


@pytest.mark.django_db
def test_ocr_provider_failure_returns_the_daily_call():
    from apps.essays.ocr import OCRUnavailable

    pro = _subscribed("ocr_pro2@example.test", "pro", image_essay_weekly_limit=15)
    with patch("apps.essays.ocr.extract_text", side_effect=OCRUnavailable("down")):
        for _ in range(8):  # more failures than the cap: none of them used a call
            assert _api(pro).post(OCR_URL, {"pages": [_page()]}, format="multipart").status_code == 503
    with patch("apps.essays.ocr.extract_text", return_value=_OCR()):
        assert _api(pro).post(OCR_URL, {"pages": [_page()]}, format="multipart").status_code == 200


@pytest.mark.django_db
def test_ocr_checks_type_size_and_page_count_before_taking_a_call(settings):
    pro = _subscribed("ocr_pro3@example.test", "pro", image_essay_weekly_limit=15)
    settings.ESSAY_IMAGE_MAX_BYTES = 100
    settings.ESSAY_IMAGE_MAX_PAGES = 2
    with patch("apps.essays.ocr.extract_text", return_value=_OCR()) as ocr:
        pdf = _page("application/pdf")
        assert _api(pro).post(OCR_URL, {"pages": [pdf]}, format="multipart").status_code == 400
        big = _page(size=500)
        assert _api(pro).post(OCR_URL, {"pages": [big]}, format="multipart").status_code == 413
        three = [_page(), _page(), _page()]
        assert _api(pro).post(OCR_URL, {"pages": three}, format="multipart").status_code == 400
    ocr.assert_not_called()
    assert ai_quota.consume_feature_cap(pro, "ocr")[0]  # nothing above used a call; the cap is still full


def test_ocr_has_a_rate_limit_and_a_daily_cap_table_entry():
    from django.conf import settings

    assert "essay-ocr" in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert ai_quota.FEATURE_DAILY_CAPS["ocr"]["pro"] == 5 and ai_quota.FEATURE_DAILY_CAPS["ocr"]["free"] == 0


# --------------------------------------------------------------------------
# Autosave
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_autosave_writes_only_the_owners_draft():
    owner, other = _user("as_owner@example.test"), _user("as_other@example.test")
    draft = EssaySubmission.objects.create(student=owner, essay_text="mine", status=EssaySubmission.Status.DRAFT)
    url = f"/api/v1/essays/{draft.pk}/autosave/"
    # Another account: indistinguishable from "not found", and nothing is written.
    res = _api(other).post(url, {"essay_text": "hijacked"}, format="json")
    assert res.status_code == 404
    draft.refresh_from_db()
    assert draft.essay_text == "mine"
    assert _api().post(url, {"essay_text": "x"}, format="json").status_code in (401, 403)
    ok = _api(owner).post(url, {"essay_text": "better words here"}, format="json")
    assert ok.status_code == 200 and ok.json()["saved"] is True
    draft.refresh_from_db()
    assert draft.essay_text == "better words here"


@pytest.mark.django_db
def test_autosave_has_a_size_limit_and_never_touches_a_submitted_essay():
    from apps.essays.views import MAX_ESSAY_LENGTH

    owner = _user("as_owner2@example.test")
    draft = EssaySubmission.objects.create(student=owner, essay_text="x", status=EssaySubmission.Status.DRAFT)
    url = f"/api/v1/essays/{draft.pk}/autosave/"
    assert _api(owner).post(url, {"essay_text": "a" * (MAX_ESSAY_LENGTH + 1)}, format="json").status_code == 400
    pending = EssaySubmission.objects.create(student=owner, essay_text="locked", status=EssaySubmission.Status.PENDING)
    res = _api(owner).post(f"/api/v1/essays/{pending.pk}/autosave/", {"essay_text": "changed"}, format="json")
    assert res.status_code == 409
    pending.refresh_from_db()
    assert pending.essay_text == "locked"


def test_autosave_is_rate_limited():
    from django.conf import settings

    from apps.webapi.views_essay_studio import AutosaveThrottle, essay_autosave_view

    assert AutosaveThrottle.scope == "essay-autosave"
    assert "essay-autosave" in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert AutosaveThrottle in essay_autosave_view.cls.throttle_classes


# --------------------------------------------------------------------------
# Every AI endpoint has a cap
# --------------------------------------------------------------------------
def test_every_ai_feature_has_a_daily_cap_for_every_tier():
    tiers = {"free", "starter", "pro", "premium"}
    for feature in ("ocr", "speaking", "omr", "converter", "vocab"):
        assert tiers <= set(ai_quota.FEATURE_DAILY_CAPS[feature]), feature


@pytest.mark.django_db
def test_feature_cap_counts_per_user_refunds_and_exempts_admins():
    a, b = _user("cap_a@example.test"), _user("cap_b@example.test")
    assert ai_quota.consume_feature_cap(a, "speaking") == (True, 1)  # FREE: 1 a day
    assert ai_quota.consume_feature_cap(a, "speaking") == (False, 1)
    assert ai_quota.consume_feature_cap(b, "speaking")[0] is True  # another user is unaffected
    ai_quota.refund_feature_cap(a, "speaking")
    assert ai_quota.consume_feature_cap(a, "speaking")[0] is True
    admin = User.objects.create_superuser(email="cap_admin@example.test", password="x-Pass-123!")
    assert all(ai_quota.consume_feature_cap(admin, "speaking") == (True, None) for _ in range(50))


@pytest.mark.django_db
def test_cap_override_from_settings(settings):
    settings.AI_FEATURE_DAILY_CAPS = {"speaking": {"free": 3}}
    u = _user("cap_override@example.test")
    assert [ai_quota.consume_feature_cap(u, "speaking")[0] for _ in range(4)] == [True, True, True, False]


# --------------------------------------------------------------------------
# XP
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "kwargs, expected",
    [
        (dict(total_questions=40, answered=40, time_taken_seconds=1200, passed=True), 25),
        (dict(total_questions=40, answered=40, time_taken_seconds=1200, passed=False), 15),
        (dict(total_questions=40, answered=11, time_taken_seconds=1200, passed=True), 0),  # < 30 % answered
        (dict(total_questions=40, answered=12, time_taken_seconds=1200, passed=False), 15),  # exactly 30 %
        (dict(total_questions=0, answered=0, time_taken_seconds=1200, passed=True), 0),
        (dict(total_questions=40, answered=40, time_taken_seconds=30, passed=True), 0),  # clicked through
        (dict(total_questions=40, answered=40, time_taken_seconds=120, passed=True), 25),  # 3 s a question
        (dict(total_questions=5, answered=5, time_taken_seconds=10, passed=True), 0),  # never under 20 s
        (dict(total_questions=40, answered=40, time_taken_seconds=1200, passed=True, xp_already_today=40), 0),
        (dict(total_questions=40, answered=40, time_taken_seconds=1200, passed=True, xp_already_today=25), 15),
    ],
)
def test_xp_rules(kwargs, expected):
    assert xp_rules.xp_for_result(**kwargs) == expected


@pytest.mark.django_db
def test_one_test_pays_out_at_most_its_daily_ceiling():
    user = _user("xp_user@example.test")

    class _Attempt:
        test_id = 77

    class _Result:
        total_questions = 20
        correct_answers = 15
        wrong_answers = 5
        time_taken_seconds = 900
        is_passed = True

    paid = [xp_rules.award_test_xp(user, _Result, _Attempt) for _ in range(4)]
    assert paid == [25, 15, 0, 0]
    _Attempt.test_id = 78  # a different test has its own ceiling
    assert xp_rules.award_test_xp(user, _Result, _Attempt) == 25


# --------------------------------------------------------------------------
# OMR
# --------------------------------------------------------------------------
SCAN_URL = "/api/v1/tests/scan-omr/"


def _sheet():
    img = Image.new("RGB", (900, 1200), "white")
    for x in range(100, 800, 40):
        for y in range(100, 1100, 60):
            img.paste((30, 30, 30), (x, y, x + 12, y + 12))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return SimpleUploadedFile("sheet.png", buf.getvalue(), content_type="image/png")


@pytest.fixture
def omr_test(db):
    from apps.courses.models import Course
    from apps.tests.models import Choice, Question, Test

    teacher = _user("omr_t@example.test", "teacher")
    course = Course.objects.create(teacher=teacher, title="O", slug="omr-ab")
    test = Test.objects.create(title="Open", course=course, mock_code="OPEN-1", subject="uzbek", status=Test.Status.PUBLISHED, is_active=True)
    for i in range(1, 4):
        q = Question.objects.create(test=test, text=f"Q{i}", position=1000 + i, points=1)
        for idx, letter in enumerate("ABCD", start=1):
            Choice.objects.create(question=q, text=f"Option {letter}", is_correct=(letter == "B"), position=idx)
    return test


def _read(rows=None):
    def reader(_img, _mime, keys):
        return {"is_answer_sheet": True, "test_code": "", "answers": {k: ["B"] for k in keys}}

    return reader


@pytest.mark.django_db
def test_omr_scan_daily_cap_blocks_before_any_vision_call(omr_test):
    student = _user("omr_cap@example.test")
    with patch("apps.tests.omr_service.read_marks", side_effect=_read()) as vision:
        codes = [_api(student).post(SCAN_URL, {"image": _sheet(), "test_id": omr_test.id}, format="multipart").status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429  # FREE: 3 scans a day
    assert vision.call_count == 3


@pytest.mark.django_db
def test_omr_images_rejected_for_free_do_not_use_a_scan(omr_test):
    student = _user("omr_free_reject@example.test")
    junk = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
    for _ in range(5):
        assert _api(student).post(SCAN_URL, {"image": junk, "test_id": omr_test.id}, format="multipart").status_code == 400
        junk.seek(0)
    with patch("apps.tests.omr_service.read_marks", side_effect=_read()):
        assert _api(student).post(SCAN_URL, {"image": _sheet(), "test_id": omr_test.id}, format="multipart").status_code == 200


@pytest.mark.django_db
def test_omr_reader_outage_returns_the_scan_and_is_not_a_default_answer(omr_test):
    from apps.tests.omr_service import OmrError

    student = _user("omr_out@example.test")
    boom = OmrError("scanner_unavailable", "down", 422)
    with patch("apps.tests.omr_service.read_marks", side_effect=boom):
        for _ in range(5):
            res = _api(student).post(SCAN_URL, {"image": _sheet(), "test_id": omr_test.id}, format="multipart")
            assert res.status_code == 422 and res.json()["code"] == "scanner_unavailable"
    with patch("apps.tests.omr_service.read_marks", side_effect=_read()):
        assert _api(student).post(SCAN_URL, {"image": _sheet(), "test_id": omr_test.id}, format="multipart").status_code == 200


@pytest.mark.django_db
def test_omr_does_not_list_or_read_tests_the_student_cannot_open(omr_test):
    from apps.courses.models import Course, StudentGroup
    from apps.tests.models import Test

    teacher = omr_test.course.teacher
    group = StudentGroup.objects.create(name="Private", teacher=teacher)
    private = Test.objects.create(
        title="Private group test", course=omr_test.course, mock_code="PRIV-1", subject="uzbek",
        status=Test.Status.PUBLISHED, is_active=True, access_type=Test.AccessType.STUDENTS_ONLY, assigned_group=group,
    )
    pin = Test.objects.create(
        title="Pin test", course=omr_test.course, mock_code="PIN-1", subject="uzbek",
        status=Test.Status.PUBLISHED, is_active=True, access_pin="1234",
    )
    from apps.tests.models import Choice, Question

    for t in (private, pin):
        q = Question.objects.create(test=t, text="Q", position=1001, points=1)
        for idx, letter in enumerate("AB", start=1):
            Choice.objects.create(question=q, text=f"Option {letter}", is_correct=(letter == "A"), position=idx)

    outsider, member = _user("omr_out2@example.test"), _user("omr_member@example.test")
    group.students.add(member)
    listed = lambda u: {t["title"] for t in _api(u).get(SCAN_URL).json()["tests"]}  # noqa: E731
    assert listed(outsider) == {"Open"}
    assert listed(member) == {"Open", "Private group test"}
    with patch("apps.tests.omr_service.read_marks", side_effect=_read()) as vision:
        res = _api(outsider).post(SCAN_URL, {"image": _sheet(), "test_id": private.id}, format="multipart")
    assert res.status_code == 404 and vision.call_count == 0


@pytest.mark.django_db
def test_omr_scan_grades_nothing_and_a_mostly_unreadable_sheet_is_refused(omr_test, settings):
    from apps.results.models import Result
    from apps.tests.models import TestAttempt

    student = _user("omr_proof@example.test")
    with patch("apps.tests.omr_service.read_marks", side_effect=_read()):
        ok = _api(student).post(SCAN_URL, {"image": _sheet(), "test_id": omr_test.id}, format="multipart")
    body = ok.json()
    assert ok.status_code == 200
    # Questions are shown by sequence number so the student can check each row.
    assert [i["number"] for i in body["items"]] == [1, 2, 3]
    # Step 1 only reads: no attempt, no result, no XP until the student confirms.
    assert not TestAttempt.objects.filter(student=student).exists() and not Result.objects.filter(student=student).exists()
    assert Profile.objects.get(user=student).xp_points == 0

    settings.OMR_MAX_UNREAD_RATIO = 0.3

    def blurry(_img, _mime, keys):
        return {"is_answer_sheet": True, "answers": {k: None for k in keys}}

    with patch("apps.tests.omr_service.read_marks", side_effect=blurry):
        res = _api(student).post(SCAN_URL, {"image": _sheet(), "test_id": omr_test.id}, format="multipart")
    assert res.status_code == 400 and res.json()["code"] == "unreadable"


def test_omr_has_rate_limits_and_no_xp_path():
    from config.settings import base  # the test settings trim the table; production uses base

    from apps.tests import omr_service

    rates = base.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert rates["omr-scan"] and rates["omr-confirm"]
    source = open(omr_service.__file__, encoding="utf-8").read()
    assert "record_user_activity" not in source and '"xp_earned": 0' in source
