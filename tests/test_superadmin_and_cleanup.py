"""Tests for promote_superadmin command, cleanup_mock_tests command, and Telegram ID 5582178765 superadmin auto-promotion."""
from io import StringIO
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.accounts.models import Profile
from apps.accounts.services.telegram_identity import get_or_create_telegram_user
from apps.courses.models import Course
from apps.tests.models import Test

User = get_user_model()


@pytest.mark.django_db
def test_promote_superadmin_command_creates_and_promotes():
    out = StringIO()
    call_command("promote_superadmin", "--telegram-id", "5582178765", stdout=out)
    output = out.getvalue()
    assert "Superadmin" in output

    user = User.objects.get(telegram_chat_id=5582178765)
    assert user.is_superuser is True
    assert user.is_staff is True
    assert user.role == User.Role.ADMIN
    assert user.profile.plan == "pro"
    assert user.telegram_identity_verified_at is not None


@pytest.mark.django_db
def test_promote_superadmin_command_existing_user():
    user = User.objects.create_user(
        email="test_admin_tg@grandec.uz",
        password="PassWord123!",
        role="student",
        telegram_chat_id=5582178765,
    )
    user.profile.plan = "free"
    user.profile.save(update_fields=["plan"])

    out = StringIO()
    call_command("promote_superadmin", "--telegram-id", "5582178765", stdout=out)
    output = out.getvalue()
    assert "Successfully promoted" in output

    user.refresh_from_db()
    assert user.is_superuser is True
    assert user.is_staff is True
    assert user.role == User.Role.ADMIN
    assert user.profile.plan == "pro"


@pytest.mark.django_db
def test_get_or_create_telegram_user_auto_promotes_superadmin():
    tg_payload = {
        "id": 5582178765,
        "first_name": "Komiljon",
        "last_name": "Roziyev",
        "username": "kruziyev",
    }
    user, created = get_or_create_telegram_user(tg_payload)
    assert user.is_superuser is True
    assert user.is_staff is True
    assert user.role == User.Role.ADMIN
    assert user.telegram_chat_id == 5582178765
    assert user.profile.plan == "pro"


@pytest.mark.django_db
def test_cleanup_mock_tests_command(teacher_user=None):
    user = User.objects.create_user(
        email="teacher_cleanup_test@example.com",
        password="Password123!",
        role="teacher",
    )
    course = Course.objects.create(teacher=user, title="Test Course", slug="test-course-cleanup")

    # Seed mock tests
    t1 = Test.objects.create(
        course=course,
        title="Shukurov Mock",
        mock_code="#MOCK-SHUKUROV",
    )
    t2 = Test.objects.create(
        course=course,
        title="BMB Day 4 Mock",
        mock_code="#MOCK-BMB04",
    )
    # Teacher custom test (should NOT be deleted)
    t3 = Test.objects.create(
        course=course,
        title="Ustoz Testi",
        mock_code="#MOCK-TEACHER99",
    )

    out = StringIO()
    call_command("cleanup_mock_tests", stdout=out)
    output = out.getvalue()
    assert "Successfully deleted 2 test(s)" in output

    assert not Test.objects.filter(id=t1.id).exists()
    assert not Test.objects.filter(id=t2.id).exists()
    assert Test.objects.filter(id=t3.id).exists()


@pytest.mark.django_db
def test_cleanup_mock_essays_command():
    from apps.essays.models import EssayTopic

    e1 = EssayTopic.objects.create(
        title="The Impact of Remote Work on Modern Productivity",
        category="ielts_task2",
        subject="english",
        rubric_type="ielts_task2",
    )
    e2 = EssayTopic.objects.create(
        title="Investment in Renewable Energy as a Sustainable Future Solution",
        category="ielts_task2",
        subject="english",
        rubric_type="ielts_task2",
    )
    e3 = EssayTopic.objects.create(
        title="The Role of Artificial Intelligence in Contemporary Education",
        category="multilevel",
        subject="english",
        rubric_type="ielts_task2",
    )
    e_uz = EssayTopic.objects.create(
        title="Ona tilimiz — millatimiz faxri va g'ururi",
        category="ona_tili",
        subject="uzbek",
        rubric_type="bmb_12",
    )

    out = StringIO()
    call_command("cleanup_mock_tests", stdout=out)
    output = out.getvalue()
    assert "Cleaned up mock essays" in output

    assert not EssayTopic.objects.filter(id=e1.id).exists()
    assert not EssayTopic.objects.filter(id=e2.id).exists()
    assert not EssayTopic.objects.filter(id=e3.id).exists()
    assert EssayTopic.objects.filter(id=e_uz.id).exists()


@pytest.mark.django_db
def test_strict_subject_segregation_essay_topics_api(client):
    from apps.essays.models import EssayTopic
    from rest_framework_simplejwt.tokens import RefreshToken

    user = User.objects.create_user(
        email="student_segregation_test@example.com",
        password="Password123!",
        role="student",
    )
    token = str(RefreshToken.for_user(user).access_token)

    # Uzbek topic
    uz_topic = EssayTopic.objects.create(
        title="O'zbek adabiyoti durdonalari",
        category="ona_tili",
        subject="uzbek",
        rubric_type="bmb_12",
    )
    # English IELTS topic
    ielts_topic = EssayTopic.objects.create(
        title="IELTS Writing Task 2: Academic Education",
        category="ielts_task2",
        subject="english",
        rubric_type="ielts_task2",
    )
    # English Multi-level topic
    ml_topic = EssayTopic.objects.create(
        title="CEFR Multi-level Writing: City Infrastructure",
        category="multilevel",
        subject="english",
        rubric_type="ielts_task2",
    )

    # 1. Uzbek mode
    res_uz = client.get(
        "/tma/api/essays/topics/?subject=uzbek",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert res_uz.status_code == 200
    topics_uz = res_uz.json().get("topics", [])
    uz_ids = [t["id"] for t in topics_uz]
    assert uz_topic.id in uz_ids
    assert ielts_topic.id not in uz_ids
    assert ml_topic.id not in uz_ids

    # 2. English IELTS mode
    res_ielts = client.get(
        "/tma/api/essays/topics/?subject=english&category=ielts",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert res_ielts.status_code == 200
    topics_ielts = res_ielts.json().get("topics", [])
    ielts_ids = [t["id"] for t in topics_ielts]
    assert ielts_topic.id in ielts_ids
    assert uz_topic.id not in ielts_ids
    assert ml_topic.id not in ielts_ids

    # 3. English Multi-level mode
    res_ml = client.get(
        "/tma/api/essays/topics/?subject=english&category=multilevel",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert res_ml.status_code == 200
    topics_ml = res_ml.json().get("topics", [])
    ml_ids = [t["id"] for t in topics_ml]
    assert ml_topic.id in ml_ids
    assert uz_topic.id not in ml_ids
    assert ielts_topic.id not in ml_ids

