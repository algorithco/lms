"""
Tests for Parent Retention CRM, Telegram Smart Alerts, and Branch Churn Warning Engine.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import ParentStudentRelation
from apps.accounts.services.parent_link import (
    generate_parent_deep_link_token,
    get_parent_deep_link,
    link_parent_to_student,
    verify_parent_deep_link_token,
)
from apps.courses.models import Category, Course
from apps.notifications.tasks_parent import (
    send_monday_branch_digest_task,
    send_parent_test_alert_task,
    send_parent_weekly_digest_task,
)
from apps.organizations.models import CenterBranch
from apps.results.models import Result
from apps.tests.models import Choice, Question, StudentAnswer, Test, TestAttempt

User = get_user_model()


@pytest.mark.django_db
class TestParentLinkAndDeepLinkSecurity:
    """Test HMAC deep-link generation, verification, and database linking."""

    def test_deep_link_token_generation_and_verification(self):
        student_id = 42
        token = generate_parent_deep_link_token(student_id)
        assert len(token) == 12
        assert verify_parent_deep_link_token(student_id, token) is True
        assert verify_parent_deep_link_token(student_id, "invalid_tok") is False
        assert verify_parent_deep_link_token(999, token) is False

        url = get_parent_deep_link(student_id)
        assert f"start=parent_{student_id}_{token}" in url

    def test_link_parent_to_student_service(self):
        student = User.objects.create_user(
            email="ali_student@grandec.uz",
            password="Password123!",
            role=User.Role.STUDENT,
        )
        tg_id = 7766554433
        rel, created = link_parent_to_student(
            student=student,
            telegram_id=tg_id,
            parent_name="Karim aka",
            parent_phone="+998901112233",
        )
        assert created is True
        assert rel.is_verified is True
        assert rel.notifications_enabled is True
        assert rel.parent_telegram_id == tg_id
        assert rel.parent_name == "Karim aka"

        # Calling again should update existing
        rel2, created2 = link_parent_to_student(
            student=student,
            telegram_id=tg_id,
            parent_name="Karim Karimov",
            parent_phone="+998901112233",
        )
        assert created2 is False
        assert rel2.id == rel.id
        assert rel2.parent_name == "Karim Karimov"


@pytest.mark.django_db
class TestParentWebAPIEndpoints:
    """Test parent relations web API viewsets."""

    def test_parent_relations_get_and_post(self):
        student = User.objects.create_user(
            email="web_parent_student@grandec.uz",
            password="Password123!",
            role=User.Role.STUDENT,
        )
        client = APIClient()
        client.force_authenticate(user=student)

        # GET: initially empty, deep_link provided
        res = client.get("/api/v1/parents/relation/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert "relations" in data
        assert "deep_link" in data
        assert f"start=parent_{student.id}_" in data["deep_link"]
        assert data["has_connected_parent"] is False

        # POST: add phone
        post_res = client.post(
            "/api/v1/parents/relation/",
            {"parent_phone": "+998 90 987 65 43", "parent_name": "Ona Qizim"},
            format="json",
        )
        assert post_res.status_code == status.HTTP_201_CREATED
        post_data = post_res.json()
        assert post_data["parent_phone"] == "+998909876543"
        assert post_data["parent_name"] == "Ona Qizim"
        assert len(post_data["verification_code"]) == 6

        # PATCH: toggle notifications
        rel_id = post_data["id"]
        patch_res = client.patch(
            f"/api/v1/parents/relation/{rel_id}/",
            {"notifications_enabled": False},
            format="json",
        )
        assert patch_res.status_code == status.HTTP_200_OK
        assert patch_res.json()["notifications_enabled"] is False


@pytest.mark.django_db
class TestParentAutomatedAlertsAndDigests:
    """Test instant exam alert and weekly/Monday digests."""

    @patch("apps.notifications.services.telegram_service.TelegramService.send_message")
    def test_instant_exam_alert_with_rich_card(self, mock_send):
        teacher = User.objects.create_user(
            email="bio_teach@grandec.uz",
            password="Password123!",
            role=User.Role.TEACHER,
        )
        student = User.objects.create_user(
            email="exam_student@grandec.uz",
            password="Password123!",
            first_name="Madina",
            last_name="Valiyeva",
            role=User.Role.STUDENT,
        )
        # Link parent
        ParentStudentRelation.objects.create(
            student=student,
            parent_telegram_id=987654321,
            parent_name="Vali aka",
            is_verified=True,
            notifications_enabled=True,
            instant_alerts_enabled=True,
        )

        cat = Category.objects.create(name="Biologiya", slug="bio-crm")
        course = Course.objects.create(
            title="Biologiya Kursi",
            slug="bio-course-crm",
            teacher=teacher,
            category=cat,
            subject="biology",
        )
        test = Test.objects.create(
            course=course,
            title="Biologiya Milliy Mock #1",
            subject="biology",
            time_limit_minutes=45,
            is_active=True,
        )
        q1 = Question.objects.create(test=test, text="Hujayra bo'linishi va mitoz?")
        attempt = TestAttempt.objects.create(
            student=student,
            test=test,
            status=TestAttempt.Status.COMPLETED,
        )
        # Record a wrong answer for weak topic
        StudentAnswer.objects.create(attempt=attempt, question=q1, is_correct=False)

        result = Result.objects.create(
            attempt=attempt,
            student=student,
            test=test,
            course=course,
            score=76.0,
            max_score=100.0,
            percentage=76.0,
            total_questions=30,
            correct_answers=23,
            wrong_answers=7,
            is_passed=True,
        )

        # Execute task
        out = send_parent_test_alert_task(result.id)
        assert out["status"] == "sent"
        assert out["count"] == 1
        assert mock_send.called

        # Verify message content contains subject icon, grade, and weak topics
        call_args = mock_send.call_args[1]
        msg_text = call_args["text"]
        assert "Farzandingiz yangi test topshirdi" in msg_text
        assert "Madina Valiyeva" in msg_text
        assert "Biologiya" in msg_text
        assert "BMB darajasi" in msg_text
        assert "Hujayra bo'linishi" in msg_text

    @patch("apps.notifications.services.telegram_service.TelegramService.send_message")
    def test_weekly_parent_digest_task(self, mock_send):
        student = User.objects.create_user(
            email="weekly_student@grandec.uz",
            password="Password123!",
            first_name="Javohir",
            role=User.Role.STUDENT,
        )
        ParentStudentRelation.objects.create(
            student=student,
            parent_telegram_id=1122334455,
            is_verified=True,
            weekly_report_enabled=True,
        )
        out = send_parent_weekly_digest_task()
        assert out["status"] == "completed"
        assert out["dispatched"] >= 1
        assert mock_send.called

    @patch("apps.notifications.services.telegram_service.TelegramService.send_message")
    def test_monday_branch_director_digest(self, mock_send):
        director = User.objects.create_user(
            email="director_sam@grandec.uz",
            password="Password123!",
            role=User.Role.ADMIN,
            telegram_chat_id=5544332211,
        )
        branch = CenterBranch.objects.create(
            name="Samarqand Markazi",
            branch_code="SAM-DIR-01",
            director=director,
            is_active=True,
        )
        User.objects.create_user(
            email="student_sam@grandec.uz",
            password="Password123!",
            role=User.Role.STUDENT,
            branch=branch,
        )
        out = send_monday_branch_digest_task()
        assert out["status"] == "completed"
        assert out["dispatched"] >= 1
        assert mock_send.called
        msg = mock_send.call_args[1]["text"]
        assert "Samarqand Markazi haftalik tahlili" in msg
        assert "Faol o'quvchilar" in msg


@pytest.mark.django_db
class TestBranchRetentionRiskEngine:
    """Test branch churn risk classification and reminder dispatch."""

    def test_retention_risk_api_three_tiers(self):
        admin = User.objects.create_user(
            email="branch_super@grandec.uz",
            password="Password123!",
            role=User.Role.ADMIN,
            is_superuser=True,
        )
        branch = CenterBranch.objects.create(
            name="Toshkent Chilonzor Filiali",
            branch_code="TAS-CHIL-01",
            is_active=True,
        )

        # 1. Active student (green)
        s_green = User.objects.create_user(
            email="active_student@grandec.uz",
            password="Password123!",
            first_name="Anvar",
            role=User.Role.STUDENT,
            branch=branch,
        )
        # Active attempt yesterday
        cat_risk = Category.objects.create(name="Umumiy Fanlar", slug="umumiy-risk")
        course_risk = Course.objects.create(
            title="Kurs 1",
            slug="course-risk-1",
            teacher=admin,
            category=cat_risk,
            subject="biology",
        )
        t1 = Test.objects.create(course=course_risk, title="Test 1", subject="biology")
        TestAttempt.objects.create(
            student=s_green,
            test=t1,
            status=TestAttempt.Status.COMPLETED,
        )

        # 2. Inactive student > 5 days (red)
        s_red = User.objects.create_user(
            email="risk_student@grandec.uz",
            password="Password123!",
            first_name="Rustam",
            role=User.Role.STUDENT,
            branch=branch,
        )
        s_red.date_joined = timezone.now() - timedelta(days=10)
        s_red.save()

        # Connect parent to s_red
        ParentStudentRelation.objects.create(
            student=s_red,
            parent_name="Rustam Otasi",
            parent_phone="+998905556677",
            parent_telegram_id=888999111,
            is_verified=True,
        )

        client = APIClient()
        client.force_authenticate(user=admin)

        res = client.get(f"/api/v1/panel/branches/{branch.id}/retention-risk/")
        assert res.status_code == status.HTTP_200_OK
        data = res.json()

        assert "summary" in data
        assert "students" in data
        assert data["summary"]["total_students"] >= 2
        assert data["summary"]["active_count"] >= 1
        assert data["summary"]["risk_count"] >= 1

        # Check student payload
        red_item = next(st for st in data["students"] if st["id"] == s_red.id)
        assert red_item["tier"] == "red"
        assert red_item["has_parent_telegram"] is True
        assert red_item["parent_name"] == "Rustam Otasi"

    @patch("apps.notifications.services.telegram_service.TelegramService.send_message")
    def test_send_reminder_api(self, mock_send):
        admin = User.objects.create_user(
            email="reminder_admin@grandec.uz",
            password="Password123!",
            role=User.Role.ADMIN,
            is_superuser=True,
        )
        branch = CenterBranch.objects.create(
            name="Buxoro Registon",
            branch_code="BUX-REM-01",
            is_active=True,
        )
        student = User.objects.create_user(
            email="rem_student@grandec.uz",
            password="Password123!",
            first_name="Shahzod",
            role=User.Role.STUDENT,
            branch=branch,
            telegram_chat_id=12345678,
        )
        ParentStudentRelation.objects.create(
            student=student,
            parent_name="Shahzod Onasi",
            parent_telegram_id=87654321,
            is_verified=True,
        )

        client = APIClient()
        client.force_authenticate(user=admin)

        res = client.post(
            f"/api/v1/panel/branches/{branch.id}/send-reminder/",
            {"student_id": student.id, "reminder_type": "both"},
            format="json",
        )
        assert res.status_code == status.HTTP_200_OK
        data = res.json()
        assert data["success"] is True
        assert data["sent_to_student"] is True
        assert data["sent_to_parent"] is True
        assert mock_send.call_count == 2
