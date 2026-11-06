from __future__ import annotations

from decimal import Decimal
import os
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework import status

from apps.courses.models import Course, StudentGroup
from apps.organizations.models import CenterBranch
from apps.results.models import Result
from apps.tests.models import (
    Choice,
    ExamSection,
    Question,
    StudentAnswer,
    Test,
    TestAttempt,
)
from apps.notifications.tasks import _send_group_result_and_vedomost

User = get_user_model()


@pytest.fixture
def auth_users(db):
    teacher = User.objects.create_user(
        email="bio_teacher@grandec.uz",
        password="Password123!",
        first_name="Alisher",
        last_name="Navoiy",
        role="teacher",
    )
    student1 = User.objects.create_user(
        email="student_sam1@grandec.uz",
        password="Password123!",
        first_name="Zilola",
        last_name="Karimova",
        role="student",
        referral_code="ZILOLA26",
    )
    student2 = User.objects.create_user(
        email="student_sam2@grandec.uz",
        password="Password123!",
        first_name="Bekzod",
        last_name="Shodiyev",
        role="student",
        referral_code="BEKZOD26",
    )
    return teacher, student1, student2


@pytest.fixture
def setup_branch_and_test(db, auth_users):
    teacher, student1, student2 = auth_users

    branch = CenterBranch.objects.create(
        name="Grand Education — Samarqand Markaziy Filiali",
        branch_code="SAM-01",
        region="Samarqand viloyati",
        director=teacher,
        subjects_offered=["biology", "chemistry", "law"],
    )
    student1.branch = branch
    student1.save(update_fields=["branch"])

    group = StudentGroup.objects.create(
        name="Biologiya Milliy-101",
        teacher=teacher,
        branch=branch,
        subject="biology",
        invite_code="BIO-888",
        telegram_chat_id="-1009988776655",
    )
    group.students.add(student1, student2)

    course = Course.objects.create(
        title="Biologiya Milliy Sertifikat",
        slug="biologiya-milliy-sertifikat-test",
        teacher=teacher,
        subject="biology",
    )

    test = Test.objects.create(
        title="Biologiya Diagnostika Mock #1",
        course=course,
        subject="biology",
        assigned_group=group,
        time_limit_minutes=60,
        show_results_immediately=True,
    )

    # 1. Closed questions (1-32)
    q1 = Question.objects.create(
        test=test,
        position=1,
        text="Sitologiya nimani o'rganadi?",
        question_type=Question.QuestionType.SINGLE_CHOICE,
        points=Decimal("1.90"),
    )
    Choice.objects.create(question=q1, text="Hujayrani", is_correct=True)
    Choice.objects.create(question=q1, text="To'qimani", is_correct=False)

    # 2. Matching matrix (33-35)
    q33 = Question.objects.create(
        test=test,
        position=33,
        text="Organoidlar va ularning funksiyalarini moslashtiring.",
        question_type=Question.QuestionType.MATCHING_MATRIX,
        correct_text="1-A, 2-B, 3-C",
        points=Decimal("2.80"),
    )

    # 3. Dual open calculation (36-45)
    q36 = Question.objects.create(
        test=test,
        position=36,
        text="DNK fragmentidagi nukleotidlarni hisoblang: a) A soni; b) G soni.",
        question_type=Question.QuestionType.DUAL_OPEN_CALC,
        correct_text="120 | 180",
        points=Decimal("2.80"),
    )

    # Student 1 Attempt & Result
    att1 = TestAttempt.objects.create(
        test=test,
        student=student1,
        status=TestAttempt.Status.COMPLETED,
        score=Decimal("7.50"),
        percentage=Decimal("100.00"),
        is_passed=True,
    )
    StudentAnswer.objects.create(attempt=att1, question=q1, is_correct=True)
    StudentAnswer.objects.create(attempt=att1, question=q33, text_answer="1-A, 2-B, 3-C", is_correct=True)
    StudentAnswer.objects.create(attempt=att1, question=q36, text_answer="120 | 180", is_correct=True)

    res1 = Result.objects.create(
        student=student1,
        test=test,
        course=course,
        attempt=att1,
        score=Decimal("7.50"),
        max_score=Decimal("7.50"),
        percentage=Decimal("100.00"),
        is_passed=True,
        time_taken_seconds=1800,
        total_questions=3,
        correct_answers=3,
        wrong_answers=0,
        unanswered=0,
    )

    # Student 2 Attempt & Result (lower score)
    att2 = TestAttempt.objects.create(
        test=test,
        student=student2,
        status=TestAttempt.Status.COMPLETED,
        score=Decimal("4.70"),
        percentage=Decimal("62.67"),
        is_passed=True,
    )
    StudentAnswer.objects.create(attempt=att2, question=q1, is_correct=True)
    StudentAnswer.objects.create(attempt=att2, question=q33, text_answer="1-A, 2-B, 3-C", is_correct=True)
    StudentAnswer.objects.create(attempt=att2, question=q36, text_answer="100 | 150", is_correct=False)

    res2 = Result.objects.create(
        student=student2,
        test=test,
        course=course,
        attempt=att2,
        score=Decimal("4.70"),
        max_score=Decimal("7.50"),
        percentage=Decimal("62.67"),
        is_passed=True,
        time_taken_seconds=2100,
        total_questions=3,
        correct_answers=2,
        wrong_answers=1,
        unanswered=0,
    )

    return branch, group, test, res1, res2, student1, student2


@pytest.mark.django_db
def test_result_detail_returns_subject_analysis_and_share_data(setup_branch_and_test):
    branch, group, test, res1, res2, student1, student2 = setup_branch_and_test

    client = Client()
    client.force_login(student1)

    url = f"/api/results/{res1.id}/detail/"
    resp = client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    # 1. Subject analysis
    assert "subject_analysis" in data
    analysis = data["subject_analysis"]
    assert analysis["kind"] == "science_bmb"
    assert analysis["subject"] == "biology"
    assert analysis["bmb_grade"] == "A+"
    assert analysis["closed_questions"]["correct_count"] == 1
    assert analysis["matching_questions"]["correct_count"] == 1
    assert analysis["open_calc_questions"]["correct_count"] == 1

    # 2. Branch info
    assert "branch_info" in data
    branch_info = data["branch_info"]
    assert branch_info["branch_name"] == "Grand Education — Samarqand Markaziy Filiali"
    assert branch_info["branch_code"] == "SAM-01"
    assert branch_info["region"] == "Samarqand viloyati"

    # 3. Share data
    assert "share_data" in data
    share_data = data["share_data"]
    assert "Grand Education" in share_data["share_text"]
    assert "Biologiya" in share_data["share_text"]
    assert "ZILOLA26" in share_data["referral_url"]
    assert "https://t.me/share/url" in share_data["telegram_share_url"]
    assert share_data["pdf_download_url"] == f"/api/results/{res1.id}/pdf/"

    # 4. Question details earned_points
    q_details = data["question_details"]
    assert len(q_details) == 3
    for q in q_details:
        assert "earned_points" in q
        assert q["earned_points"] > 0


@pytest.mark.django_db
def test_law_subject_analysis_and_mistakes(db, auth_users):
    teacher, student1, _ = auth_users
    course = Course.objects.create(
        title="Huquqshunoslik",
        slug="huquqshunoslik-test",
        teacher=teacher,
        subject="law",
    )
    test = Test.objects.create(
        title="Huquqshunoslik Mock #1",
        course=course,
        subject="law",
        show_results_immediately=True,
    )
    q_theory = Question.objects.create(
        test=test,
        position=1,
        text="O'zbekiston Respublikasi Konstitutsiyasining 1-moddasi mazmuni?",
        question_type=Question.QuestionType.SINGLE_CHOICE,
        points=Decimal("2.00"),
    )
    q_case = Question.objects.create(
        test=test,
        position=36,
        text="Fuqaro A ish beruvchi bilan mehnat shartnomasini bekor qilganda qanday kafolatlarga ega?",
        question_type=Question.QuestionType.LEGAL_CASE_STUDY,
        points=Decimal("3.00"),
    )

    att = TestAttempt.objects.create(
        test=test,
        student=student1,
        status=TestAttempt.Status.COMPLETED,
        score=Decimal("2.00"),
        percentage=Decimal("40.00"),
    )
    StudentAnswer.objects.create(attempt=att, question=q_theory, is_correct=True)
    StudentAnswer.objects.create(attempt=att, question=q_case, is_correct=False)

    res = Result.objects.create(
        student=student1,
        test=test,
        course=course,
        attempt=att,
        score=Decimal("2.00"),
        max_score=Decimal("5.00"),
        percentage=Decimal("40.00"),
        is_passed=False,
        time_taken_seconds=900,
        total_questions=2,
        correct_answers=1,
        wrong_answers=1,
        unanswered=0,
    )

    client = Client()
    client.force_login(student1)
    resp = client.get(f"/api/results/{res.id}/detail/")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    law_analysis = data["subject_analysis"]
    assert law_analysis["kind"] == "law_jurisprudence"
    assert law_analysis["theory_questions"]["correct_count"] == 1
    assert law_analysis["case_study_questions"]["correct_count"] == 0
    assert len(law_analysis["mistake_topics"]) > 0


@pytest.mark.django_db
def test_result_vedomost_pdf_download_endpoint(setup_branch_and_test):
    branch, group, test, res1, res2, student1, student2 = setup_branch_and_test

    client = Client()
    client.force_login(student1)

    url = f"/api/results/{res1.id}/pdf/"
    resp = client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    assert resp["Content-Type"] == "application/pdf"
    assert "attachment" in resp["Content-Disposition"]
    assert f"grandec_natija_{res1.id}.pdf" in resp["Content-Disposition"]

    # Other student cannot access without permission
    client2 = Client()
    client2.force_login(student2)
    resp_unauth = client2.get(url)
    assert resp_unauth.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_send_group_result_telegram_broadcast_with_rank_and_branch(setup_branch_and_test):
    branch, group, test, res1, res2, student1, student2 = setup_branch_and_test

    with patch("apps.notifications.services.telegram_service.TelegramService.send_document") as mock_send_doc, \
         patch("apps.notifications.services.telegram_service.TelegramService._call_api"):

        mock_send_doc.return_value = {"success": True, "message_id": 12345}

        # Broadcast for Student 1 (Highest score -> 1-o'rin)
        _send_group_result_and_vedomost(res1)

        assert mock_send_doc.called
        call_args = mock_send_doc.call_args[1]
        caption = call_args["caption"]

        assert "Biologiya" in caption
        assert "🧬" in caption
        assert "Samarqand Markaziy Filiali" in caption
        assert "Guruhda 1-o'rin!" in caption
        assert "Zilola Karimova" in caption
        assert f"results/{res1.id}" in caption

        # Broadcast for Student 2 (Lower score -> 2-o'rin)
        mock_send_doc.reset_mock()
        _send_group_result_and_vedomost(res2)

        assert mock_send_doc.called
        call_args2 = mock_send_doc.call_args[1]
        caption2 = call_args2["caption"]

        assert "Guruhda 2-o'rin" in caption2
        assert "Bekzod Shodiyev" in caption2
