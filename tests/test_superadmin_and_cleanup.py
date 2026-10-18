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
