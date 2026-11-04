"""Essay studio web endpoints: OCR (free), photo essay (IMAGE quota), own topic (TEXT quota, Ona tili)."""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.essays.models import EssaySubmission, EssayTopic
from apps.payments.entitlements import QuotaDenied
from apps.payments.models import SubscriptionUsage

User = get_user_model()
ESSAY = (
    "Kitob inson hayotida muhim o'rin tutadi. Har bir kitob yangi dunyo eshigini ochadi, fikrni boyitadi va "
    "insonni yaxshilikka chorlaydi. Yoshlar kitob o'qish orqali o'z dunyoqarashini kengaytiradi, nutqini "
    "boyitadi va mustaqil fikrlashni o'rganadi. Shuning uchun har kuni ozgina bo'lsa ham kitob o'qish "
    "foydalidir. Kitob do'st kabi yo'l ko'rsatadi, qiyin paytda dalda beradi va bilim beradi. Men ham har "
    "kuni kitob o'qishga harakat qilaman va bu odat menga katta foyda keltirmoqda deb o'ylayman."
)


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def pro_student(db):
    from decimal import Decimal

    from apps.payments.models import SubscriptionPlan
    from apps.payments.subscriptions import grant_subscription

    user = User.objects.create_user(email="es_pro@example.test", password="x-Pass-123!", role="student")
    Profile.objects.get_or_create(user=user)
    admin = User.objects.create_superuser(email="es_admin@example.test", password="x-Pass-123!")
    plan, _ = SubscriptionPlan.objects.get_or_create(
        plan_type=SubscriptionPlan.PlanType.PRO,
        defaults={"name": "Pro", "price_monthly": Decimal("15000"), "test_limit": 30, "image_essay_weekly_limit": 5},
    )
    grant_subscription(user, plan, kind="admin", actor=admin, days=30, reason="test")
    return user


@pytest.fixture
def student(db):
    user = User.objects.create_user(email="es_student@example.test", password="x-Pass-123!", role="student")
    Profile.objects.get_or_create(user=user)
    return user


def client(user=None):
    c = APIClient()
    if user:
        c.force_authenticate(user)
    return c


@pytest.fixture
def queued():
    """Grading dispatch accepted without running any AI."""
    with patch("apps.essays.services.start_grading", return_value={"success": True}) as start:
        yield start


class _OCR:
    text = "Recognised essay text"
    is_probably_incomplete = False
    warnings: list = []


@pytest.mark.django_db
def test_ocr_returns_text_and_never_charges_or_grades(student):
    page = SimpleUploadedFile("p1.jpg", b"fake-bytes", content_type="image/jpeg")
    with patch("apps.essays.ocr.extract_text", return_value=_OCR()) as ocr:
        res = client(student).post("/api/v1/essays/ocr/", {"pages": [page]}, format="multipart")
    assert res.status_code == 200, res.content
    assert res.json() == {"text": "Recognised essay text", "incomplete": False, "warnings": []}
    ocr.assert_called_once()
    assert EssaySubmission.objects.count() == 0 and SubscriptionUsage.objects.count() == 0


@pytest.mark.django_db
def test_ocr_errors_are_reported_not_faked(student):
    from apps.essays.ocr import OCRUnavailable

    assert client(student).post("/api/v1/essays/ocr/", {}, format="multipart").status_code == 400
    page = SimpleUploadedFile("p1.jpg", b"x", content_type="image/jpeg")
    with patch("apps.essays.ocr.extract_text", side_effect=OCRUnavailable("no provider")):
        res = client(student).post("/api/v1/essays/ocr/", {"pages": [page]}, format="multipart")
    assert res.status_code == 503 and res.json()["code"] == "ocr_unavailable"
    assert client().post("/api/v1/essays/ocr/", {}, format="multipart").status_code in (401, 403)


@pytest.mark.django_db
def test_image_submit_charges_an_image_essay_once(pro_student, queued):
    res = client(pro_student).post("/api/v1/essays/image-submit/", {"text": ESSAY}, format="json")
    assert res.status_code == 202, res.content
    sub = EssaySubmission.objects.get(pk=res.json()["submission_id"])
    assert sub.topic is None and sub.source == "web" and sub.student == pro_student
    usage = SubscriptionUsage.objects.filter(user=pro_student)
    assert usage.count() == 1 and usage.first().kind == SubscriptionUsage.Kind.IMAGE_ESSAY
    queued.assert_called_once()


@pytest.mark.django_db
def test_free_plan_rules_apply_to_photo_essays(student, queued):
    # The existing tariff decides: here the FREE plan has no weekly photo essays.
    res = client(student).post("/api/v1/essays/image-submit/", {"text": ESSAY}, format="json")
    assert res.status_code == 403 and res.json()["detail"] == "LIMIT_EXCEEDED"
    assert EssaySubmission.objects.count() == 0
    queued.assert_not_called()


@pytest.mark.django_db
def test_english_photo_essay_needs_an_english_topic(pro_student, queued):
    student = pro_student
    res = client(student).post("/api/v1/essays/image-submit/", {"text": ESSAY, "subject": "english"}, format="json")
    assert res.status_code == 400 and res.json()["code"] == "topic_required"
    topic = EssayTopic.objects.create(
        title="IELTS Task 2", description="d", subject="english", category="ielts_task2", rubric_type="ielts_task2",
        word_limit_min=40, word_limit_max=400,
    )
    ok = client(student).post("/api/v1/essays/image-submit/", {"text": ESSAY, "topic_id": topic.id}, format="json")
    assert ok.status_code == 202, ok.content
    assert EssaySubmission.objects.get(pk=ok.json()["submission_id"]).topic == topic


@pytest.mark.django_db
def test_custom_topic_essay_keeps_title_and_charges_text_quota(student, queued):
    assert client(student).post("/api/v1/essays/custom/", {"title": "", "text": ESSAY}, format="json").status_code == 400
    res = client(student).post("/api/v1/essays/custom/", {"title": "  Kitob   va men ", "text": ESSAY}, format="json")
    assert res.status_code == 202, res.content
    sub = EssaySubmission.objects.get(pk=res.json()["submission_id"])
    assert sub.custom_title == "Kitob va men" and sub.topic is None
    assert SubscriptionUsage.objects.get(user=student).kind == SubscriptionUsage.Kind.TEXT_ESSAY


@pytest.mark.django_db
def test_too_short_and_duplicate_cost_nothing(student, queued):
    short = client(student).post("/api/v1/essays/custom/", {"title": "Qisqa", "text": "Bir necha so'z."}, format="json")
    assert short.status_code == 400 and short.json()["code"] == "too_short"
    first = client(student).post("/api/v1/essays/custom/", {"title": "Kitob", "text": ESSAY}, format="json")
    EssaySubmission.objects.filter(pk=first.json()["submission_id"]).update(status=EssaySubmission.Status.PENDING)
    again = client(student).post("/api/v1/essays/custom/", {"title": "Kitob", "text": ESSAY}, format="json")
    assert again.status_code == 200 and again.json()["status"] == "duplicate"
    assert SubscriptionUsage.objects.filter(user=student).count() == 1


@pytest.mark.django_db
def test_quota_denied_leaves_no_submission(student, queued):
    denied = QuotaDenied("limit_reached", "Limit tugadi")
    with patch("apps.webapi.views_essay_studio.enforce_essay_quota", side_effect=denied):
        res = client(student).post("/api/v1/essays/custom/", {"title": "Kitob", "text": ESSAY}, format="json")
    assert res.status_code == 403 and res.json()["detail"] == "LIMIT_EXCEEDED"
    assert EssaySubmission.objects.count() == 0
    queued.assert_not_called()


@pytest.mark.django_db
def test_failed_dispatch_releases_the_allowance(student):
    with patch("apps.essays.services.start_grading", return_value={"success": False, "error": "broker down"}):
        res = client(student).post("/api/v1/essays/custom/", {"title": "Kitob", "text": ESSAY}, format="json")
    assert res.status_code == 503
    usage = SubscriptionUsage.objects.get(user=student)
    assert usage.status == SubscriptionUsage.Status.RELEASED
