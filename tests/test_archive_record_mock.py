"""Migration 0018: archive the old Record Mock (#12) without losing results."""

import importlib

import pytest
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model

from apps.courses.models import Course
from apps.results.models import Result
from apps.tests.models import Test, TestAttempt

migration = importlib.import_module("apps.tests.migrations.0018_archive_old_record_mock")
User = get_user_model()


@pytest.mark.django_db
def test_archive_hides_old_mock_and_keeps_results():
    teacher = User.objects.create_user(email="arch_t@example.com", password="x-Pass-123!", role="teacher")
    student = User.objects.create_user(email="arch_s@example.com", password="x-Pass-123!", role="student")
    course = Course.objects.create(teacher=teacher, title="C", slug="c-arch")
    old = Test.objects.create(
        title="Record Mock – Test 1 (Multi-Level CEFR & IELTS)", course=course, mock_code=migration.MOCK_CODE,
        description=migration.OLD_TEST_DESCRIPTION, status=Test.Status.PUBLISHED, is_active=True,
    )
    edited = Test.objects.create(title="Other", course=course, mock_code="OTHER", description="Hand-written")
    attempt = TestAttempt.objects.create(test=old, student=student, status=TestAttempt.Status.COMPLETED)
    Result.objects.create(
        attempt=attempt, student=student, test=old, course=course, score=10, max_score=70,
        total_questions=70, correct_answers=10, wrong_answers=60, unanswered=0, percentage=14.29, is_passed=False,
    )

    migration.forwards(django_apps, None)

    old.refresh_from_db()
    assert old.status == Test.Status.ARCHIVED and old.is_active is False
    assert "British Council" not in old.description
    assert Result.objects.filter(attempt=attempt).exists()
    edited.refresh_from_db()
    assert edited.description == "Hand-written" and edited.is_active is True

    # Hidden from students, still visible to admins.
    from rest_framework.test import APIClient

    c = APIClient()
    c.force_authenticate(student)
    ids = [t["id"] for t in c.get("/api/tests/?page_size=100").json()["results"]]
    assert old.id not in ids
    admin = User.objects.create_superuser(email="arch_a@example.com", password="x-Pass-123!")
    c.force_authenticate(admin)
    ids = [t["id"] for t in c.get("/api/tests/?page_size=100").json()["results"]]
    assert old.id in ids

    migration.backwards(django_apps, None)
    old.refresh_from_db()
    assert old.is_active is True
