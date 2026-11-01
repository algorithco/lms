"""
Tests for Phase 9.3.0:
1. Teacher Grade Override API (TeacherUpdateAttemptScoreView).
2. ReportLab Automated PDF Vedomost Generation (student & group).
3. Celery / Notification Group Broadcast with PDF Vedomost.
"""

import os
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.courses.models import Course, StudentGroup
from apps.results.models import Result, ResultSectionScore
from apps.results.pdf_generator import (
    generate_group_vedomost_pdf,
    generate_student_vedomost_pdf,
)
from apps.tests.models import Question, Test, TestAttempt

User = get_user_model()


@pytest.mark.django_db
class TestTeacherGradeOverrideAPI:
    """Test teacher grade override PATCH endpoint."""

    @pytest.fixture(autouse=True)
    def setup_fixtures(self):
        self.client = APIClient()

        # Teacher
        self.teacher = User.objects.create_user(
            email="teacher@grandec.uz",
            password="password123",
            first_name="Ustoz",
            last_name="Alisher",
            role="teacher",
        )

        # Student
        self.student = User.objects.create_user(
            email="student@grandec.uz",
            password="password123",
            first_name="Bobur",
            last_name="Mirzo",
            role="student",
        )

        # Course & Test
        self.course = Course.objects.create(
            title="IELTS Masterclass",
            slug="ielts-masterclass",
            teacher=self.teacher,
        )
        self.group = StudentGroup.objects.create(
            name="IELTS-01",
            teacher=self.teacher,
            invite_code="IELTS01",
            telegram_chat_id=-100123456789,
        )
        self.group.students.add(self.student)

        self.test_obj = Test.objects.create(
            title="IELTS Mock Exam #1",
            course=self.course,
            assigned_group=self.group,
            pass_percentage=60,
        )

        # Create 2 questions
        self.q1 = Question.objects.create(
            test=self.test_obj,
            text="Question 1 text",
            points=10,
            position=1,
        )
        self.q2 = Question.objects.create(
            test=self.test_obj,
            text="Question 2 text",
            points=10,
            position=2,
        )

        # Create Attempt
        self.attempt = TestAttempt.objects.create(
            test=self.test_obj,
            student=self.student,
            status=TestAttempt.Status.COMPLETED,
            score=Decimal("10.00"),
            percentage=Decimal("50.00"),
            is_passed=False,
            raw_score=1,
        )

        # Create Result
        self.result = Result.objects.create(
            attempt=self.attempt,
            student=self.student,
            test=self.test_obj,
            course=self.course,
            total_questions=2,
            correct_answers=1,
            wrong_answers=1,
            score=Decimal("10.00"),
            max_score=Decimal("20.00"),
            percentage=Decimal("50.00"),
            is_passed=False,
        )

        self.url = f"/api/v1/teacher/attempts/{self.attempt.id}/update-score/"

    def test_unauthenticated_forbidden(self):
        response = self.client.patch(self.url, {"score": 18})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_student_cannot_override_own_score(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.patch(self.url, {"score": 20})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_teacher_can_override_score_and_sync_result(self):
        self.client.force_authenticate(user=self.teacher)

        payload = {
            "score": 18,
            "raw_score": 2,
            "band_score": 7.5,
            "cefr_level": "C1",
            "teacher_comment": "Writing qismi tekshirildi, a'lo natija ko'rsatilgan.",
            "section_scores": {
                "LISTENING": {"earned": 9, "maximum": 10, "name": "Listening"},
                "READING": {"earned": 9, "maximum": 10, "name": "Reading"},
            },
        }

        response = self.client.patch(self.url, payload, format="json")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["success"] is True
        assert data["score"] == 18.0
        assert data["percentage"] == 90.0  # 18 / 20 * 100
        assert data["is_passed"] is True
        assert data["band_score"] == 7.5
        assert data["cefr_level"] == "C1"
        assert data["teacher_overridden"] is True
        assert "Writing qismi tekshirildi" in data["teacher_comment"]

        # Verify DB models
        self.attempt.refresh_from_db()
        assert self.attempt.score == Decimal("18.00")
        assert self.attempt.percentage == Decimal("90.00")
        assert self.attempt.is_passed is True
        assert self.attempt.teacher_overridden is True
        assert self.attempt.graded_by == self.teacher
        assert "LISTENING" in self.attempt.section_scores

        self.result.refresh_from_db()
        assert self.result.score == Decimal("18.00")
        assert self.result.percentage == Decimal("90.00")
        assert self.result.is_passed is True
        assert self.result.grading_status == "graded"

        # Check section score synchronization
        sec_scores = ResultSectionScore.objects.filter(result=self.result)
        assert sec_scores.count() == 2
        list_sec = sec_scores.filter(section_code="LISTENING").first()
        assert list_sec is not None
        assert list_sec.earned == Decimal("9.00")


@pytest.mark.django_db
class TestPDFVedomostGenerator:
    """Test ReportLab automated PDF scorecard and group vedomost generation."""

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.teacher = User.objects.create_user(
            email="teacher_pdf@grandec.uz",
            password="password123",
            first_name="Sherzod",
            last_name="Karimov",
            role="teacher",
        )
        self.student = User.objects.create_user(
            email="student_pdf@grandec.uz",
            password="password123",
            first_name="Zilola",
            last_name="Saidova",
            role="student",
        )
        self.course = Course.objects.create(
            title="General English B2",
            slug="general-english-b2",
            teacher=self.teacher,
        )
        self.group = StudentGroup.objects.create(
            name="GE-B2-04",
            teacher=self.teacher,
            subject="Ingliz tili",
            invite_code="GEB204",
            telegram_chat_id=-100987654321,
        )
        self.group.students.add(self.student)

        self.test_obj = Test.objects.create(
            title="CEFR Multi-Level Mock #4",
            course=self.course,
            assigned_group=self.group,
            pass_percentage=60,
        )

        self.q1 = Question.objects.create(
            test=self.test_obj,
            text="Listening question 1",
            points=25,
            position=1,
        )
        self.q2 = Question.objects.create(
            test=self.test_obj,
            text="Reading question 1",
            points=25,
            position=2,
        )

        self.attempt = TestAttempt.objects.create(
            test=self.test_obj,
            student=self.student,
            status=TestAttempt.Status.COMPLETED,
            score=Decimal("45.00"),
            percentage=Decimal("90.00"),
            is_passed=True,
            band_score=Decimal("7.0"),
            cefr_level="B2",
            teacher_comment="Listening va Reading bo'yicha a'lo ko'rsatkich.",
            section_scores={
                "LISTENING": {"earned": 25, "maximum": 25, "name": "Listening"},
                "READING": {"earned": 20, "maximum": 25, "name": "Reading"},
            },
        )

        self.result = Result.objects.create(
            attempt=self.attempt,
            student=self.student,
            test=self.test_obj,
            course=self.course,
            total_questions=2,
            correct_answers=2,
            wrong_answers=0,
            score=Decimal("45.00"),
            max_score=Decimal("50.00"),
            percentage=Decimal("90.00"),
            is_passed=True,
        )

    def test_student_vedomost_pdf_generation(self):
        pdf_path = generate_student_vedomost_pdf(self.attempt.id)
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 3000

        with open(pdf_path, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-"

    def test_group_vedomost_pdf_generation(self):
        pdf_path = generate_group_vedomost_pdf(self.group.id)
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 3000

        with open(pdf_path, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-"


@pytest.mark.django_db
class TestGroupBroadcastTask:
    """Test group result broadcasting with PDF vedomost attached."""

    @pytest.fixture(autouse=True)
    def setup_data(self):
        self.teacher = User.objects.create_user(
            email="teacher_bc@grandec.uz",
            password="password123",
            role="teacher",
        )
        self.student = User.objects.create_user(
            email="student_bc@grandec.uz",
            password="password123",
            first_name="Madina",
            last_name="Toshmatova",
            role="student",
        )
        self.course = Course.objects.create(
            title="CEFR Intensive",
            slug="cefr-intensive",
            teacher=self.teacher,
        )
        self.group = StudentGroup.objects.create(
            name="CEFR-INT-01",
            teacher=self.teacher,
            invite_code="CEFRINT",
            telegram_chat_id=-100555666777,
        )
        self.group.students.add(self.student)

        self.test_obj = Test.objects.create(
            title="Grammar Diagnostic Test",
            course=self.course,
            assigned_group=self.group,
            pass_percentage=60,
        )

        self.attempt = TestAttempt.objects.create(
            test=self.test_obj,
            student=self.student,
            status=TestAttempt.Status.COMPLETED,
            score=Decimal("80.00"),
            percentage=Decimal("80.00"),
            is_passed=True,
            band_score=Decimal("6.5"),
            cefr_level="B2",
        )

        self.result = Result.objects.create(
            attempt=self.attempt,
            student=self.student,
            test=self.test_obj,
            course=self.course,
            total_questions=10,
            correct_answers=8,
            wrong_answers=2,
            score=Decimal("80.00"),
            max_score=Decimal("100.00"),
            percentage=Decimal("80.00"),
            is_passed=True,
        )

    @patch("apps.notifications.services.telegram_service.TelegramService._send_document")
    @patch("apps.notifications.services.telegram_service.TelegramService.send_message")
    def test_send_group_result_and_vedomost(self, mock_send_msg, mock_send_doc):
        mock_send_doc.return_value = {"success": True, "message_id": 1234}

        from apps.notifications.tasks import _send_group_result_and_vedomost

        _send_group_result_and_vedomost(self.result)

        assert mock_send_doc.called
        call_args = mock_send_doc.call_args[1]
        assert call_args["chat_id"] == self.group.telegram_chat_id
        assert "YANGI IMTIHON NATIJASI" in call_args["caption"]
        assert "Madina Toshmatova" in call_args["caption"]
        assert "80" in call_args["caption"]
        assert os.path.exists(call_args["file_path"])
