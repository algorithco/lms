"""
Comprehensive Master QA Test Suite for GRAND EDUCATION v2 (`grandec.uz` / `algorithco/lms`).

Covers:
1. 6-Step Duolingo-style Onboarding (`POST /api/v1/users/onboarding/` & `/api/auth/onboarding/`),
   Step 3 "other" with `sub_subject`, `GET /api/v1/dashboard/` integration, and
   `send_daily_onboarding_reminders` Celery task.
2. Telegram Group Binding (`StudentGroup` <-> `telegram_chat_id` & `telegram_chat_title`) via
   1-click deep-link (`/start link_<invite_code>`), manual `/ulash` & `/link` commands, and
   `GET /api/v1/school/groups/` serializer fields (`group_code`, `telegram_chat_id`, `telegram_chat_title`).
3. Student Joining Group by Code (`POST /api/v1/school/groups/join/`) and by Invite Token
   (`GET` & `POST /api/v1/groups/join/<invite_token>/`).
4. Real-Time Auto-Broadcast of Results + PDF Vedomost to Linked Telegram Groups:
   - 4a. Test Attempt Completion (`process_test_result_task` & `_send_group_result_and_vedomost`)
   - 4b. AI Essay Grading Completion (`notify_student_essay_graded` & `broadcast_essay_result_to_groups`)
   - 4c. AI Speaking Evaluation Completion (`broadcast_speaking_result_to_groups`)
   - 4d. Web Trigger for Group Leaderboard & Vedomost Broadcast (`POST /api/v1/school/groups/{id}/broadcast-vedomost/`)
5. Content Seeder Verification (`call_command("seed_content")`).
"""

from __future__ import annotations

import os
import re
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.courses.models import Course, StudentGroup
from apps.essays.models import EssayCriterionScore, EssaySubmission, EssayTopic
from apps.essays.services import notify_student_essay_graded
from apps.notifications.bot.group_assistant import cmd_link_group
from apps.notifications.bot.handlers import start_handler
from apps.notifications.services.telegram_service import TelegramService
from apps.notifications.tasks import (
    _ensure_telegram_service_helpers,
    _send_group_result_and_vedomost,
    broadcast_speaking_result_to_groups,
    process_test_result_task,
    send_daily_onboarding_reminders,
)
from apps.results.models import Result, ResultSectionScore
from apps.speaking.models import SpeakingSubmission, SpeakingTopic
from apps.tests.models import Question, Test, TestAttempt

User = get_user_model()

# Ensure TelegramService class helpers (send_document, _call_api) are attached before patching
_ensure_telegram_service_helpers()


# ===========================================================================
# TEST 1: 6-Step Duolingo-style Onboarding & Daily Reminder Celery Task
# ===========================================================================


@pytest.mark.django_db
class TestDuolingoOnboardingAndDailyReminders:
    """Verify 6-step onboarding endpoints, dashboard daily goal sync, and reminder task."""

    def setup_method(self):
        self.client = APIClient()
        self.student = User.objects.create_user(
            email="onboard_v2_student@grandec.uz",
            password="Password123!",
            first_name="Jasurbek",
            last_name="Ergashev",
            role="student",
            telegram_chat_id=778899001,
        )
        Profile.objects.get_or_create(user=self.student)
        self.client.force_authenticate(user=self.student)

    def test_six_step_onboarding_submission_and_auth_alias(self):
        payload = {
            "referral_source": "Telegram kanal yoki guruhdan",
            "main_goal": "Davlat va xalqaro sertifikat olish (BMB / IELTS / CEFR)",
            "active_subject": "uzbek",
            "target_exam": "milliy_sertifikat",
            "sub_subject": "",
            "level": "beginner",
            "daily_goal_minutes": 30,
            "reminder_slot": "evening",
        }

        resp = self.client.post("/api/v1/users/onboarding/", payload, format="json")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["onboarding_completed"] is True
        assert data["daily_plan_summary"]

        profile = Profile.objects.get(user=self.student)
        assert profile.onboarding_completed is True
        assert profile.referral_source == "Telegram kanal yoki guruhdan"
        assert profile.main_goal == "Davlat va xalqaro sertifikat olish (BMB / IELTS / CEFR)"
        assert profile.active_subject == "uzbek"
        assert profile.target_exam == "milliy_sertifikat"
        assert profile.level == "beginner"
        assert profile.daily_goal_minutes == 30
        assert profile.reminder_slot == "evening"
        assert len(profile.daily_plan_summary) > 10

        # Also verify /api/auth/onboarding/ alias works identically
        resp_alias = self.client.post("/api/auth/onboarding/", payload, format="json")
        assert resp_alias.status_code == status.HTTP_200_OK
        assert resp_alias.json()["onboarding_completed"] is True

    def test_step3_other_with_sub_subject_and_dashboard_sync(self):
        payload = {
            "referral_source": "Do'stim yoki ustozim tavsiya qildi",
            "main_goal": "Oliy ta'lim (OTM) kirish imtihonlariga tayyorlanish",
            "active_subject": "uzbek",
            "target_exam": "other",
            "sub_subject": "Matematika",
            "level": "intermediate",
            "daily_goal_minutes": 30,
            "reminder_slot": "evening",
        }

        resp = self.client.post("/api/v1/users/onboarding/", payload, format="json")
        assert resp.status_code == status.HTTP_200_OK

        profile = Profile.objects.get(user=self.student)
        assert profile.onboarding_completed is True
        assert profile.sub_subject == "Matematika"
        assert "Matematika" in profile.daily_plan_summary
        assert profile.daily_goal_minutes == 30
        self.student.profile = profile

        # Verify GET /api/v1/dashboard/ reflects daily_goal and recommended_practice
        dash_resp = self.client.get("/api/v1/dashboard/")
        assert dash_resp.status_code == status.HTTP_200_OK
        dash_data = dash_resp.json()
        assert dash_data["daily_goal"]["goal_minutes"] == 30
        assert dash_data["daily_goal"]["reminder_slot"] == "evening"
        assert len(dash_data["recommended_practice"]) >= 3

    def test_send_daily_onboarding_reminders_celery_task(self):
        profile = Profile.objects.get(user=self.student)
        profile.onboarding_completed = True
        profile.daily_goal_minutes = 30
        profile.reminder_slot = "evening"
        profile.target_grade = "A+"
        profile.current_streak = 5
        profile.save()

        # Another student with morning slot should not be messaged during evening run
        morning_student = User.objects.create_user(
            email="morning_student@grandec.uz",
            password="Password123!",
            first_name="Aziza",
            last_name="Karimova",
            role="student",
            telegram_chat_id=778899002,
        )
        m_profile, _ = Profile.objects.get_or_create(user=morning_student)
        m_profile.onboarding_completed = True
        m_profile.reminder_slot = "morning"
        m_profile.save()

        with patch.object(TelegramService, "_call_api", return_value={"ok": True, "success": True}) as mock_api:
            res = send_daily_onboarding_reminders(slot="evening")

        assert res["status"] == "ok"
        assert res["slot"] == "evening"
        assert res["sent_count"] >= 1
        assert mock_api.called

        sent_payloads = [c.args[1] if len(c.args) > 1 else c.kwargs.get("payload", {}) for c in mock_api.call_args_list]
        chat_ids = [p.get("chat_id") for p in sent_payloads]
        assert self.student.telegram_chat_id in chat_ids
        assert morning_student.telegram_chat_id not in chat_ids

        student_msg = next(p["text"] for p in sent_payloads if p.get("chat_id") == self.student.telegram_chat_id)
        assert "30 daqiqa" in student_msg
        assert "Jasurbek Ergashev" in student_msg


# ===========================================================================
# TEST 2: Telegram Group Binding (1-Click Deep-Link, /ulash, /link & API)
# ===========================================================================


@pytest.mark.django_db
class TestTelegramGroupBinding:
    """Verify StudentGroup <-> telegram_chat_id & telegram_chat_title binding."""

    def setup_method(self):
        self.client = APIClient()
        self.teacher = User.objects.create_user(
            email="teacher_grp_v2@grandec.uz",
            password="Password123!",
            first_name="Otabek",
            last_name="Nurmatov",
            role="teacher",
            telegram_chat_id=900100200,
        )
        self.group = StudentGroup.objects.create(
            teacher=self.teacher,
            name="Milliy Sertifikat Pro",
            subject="uzbek",
        )

    def test_auto_generated_invite_code_and_group_code_property(self):
        assert self.group.invite_code is not None
        assert re.match(r"^[A-Z]+-[A-Z0-9]+$", self.group.invite_code)
        assert self.group.group_code == self.group.invite_code
        assert self.group.invite_token is not None

    def test_one_click_deep_link_in_supergroup(self):
        update = MagicMock()
        update.effective_chat.id = -10099887766
        update.effective_chat.type = "supergroup"
        update.effective_chat.title = "Milliy Sertifikat Guruh A"
        update.effective_user.id = self.teacher.telegram_chat_id
        update.effective_user.username = "otabek_ustoz"
        update.message.text = f"/start link_{self.group.invite_code}"
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.args = [f"link_{self.group.invite_code}"]

        async_to_sync(start_handler)(update, context)

        self.group.refresh_from_db()
        assert self.group.telegram_chat_id == -10099887766
        assert self.group.telegram_chat_title == "Milliy Sertifikat Guruh A"

        assert update.message.reply_text.called
        reply_text = update.message.reply_text.call_args[0][0]
        assert "✅ Ushbu Telegram guruh Grand Education platformasidagi" in reply_text
        assert self.group.name in reply_text

    def test_manual_ulash_and_link_commands_in_group_chat(self):
        # 1. Test /ulash <invite_code>
        update_ulash = MagicMock()
        update_ulash.effective_chat.id = -10055443322
        update_ulash.effective_chat.type = "supergroup"
        update_ulash.effective_chat.title = "BMB Ona Tili Guruh 1"
        update_ulash.effective_user.id = self.teacher.telegram_chat_id
        update_ulash.effective_user.username = "otabek_ustoz"
        update_ulash.message.text = f"/ulash {self.group.invite_code}"
        update_ulash.message.reply_text = AsyncMock()

        context_ulash = MagicMock()
        context_ulash.args = [self.group.invite_code]

        async_to_sync(cmd_link_group)(update_ulash, context_ulash)

        self.group.refresh_from_db()
        assert self.group.telegram_chat_id == -10055443322
        assert self.group.telegram_chat_title == "BMB Ona Tili Guruh 1"
        reply_ulash = update_ulash.message.reply_text.call_args[0][0]
        assert "✅ Ushbu Telegram guruh Grand Education platformasidagi" in reply_ulash

        # 2. Test /link <invite_code> in another group chat
        update_link = MagicMock()
        update_link.effective_chat.id = -10066778899
        update_link.effective_chat.type = "group"
        update_link.effective_chat.title = "BMB Ona Tili Guruh 2"
        update_link.effective_user.id = self.teacher.telegram_chat_id
        update_link.effective_user.username = "otabek_ustoz"
        update_link.message.text = f"/link {self.group.invite_code}"
        update_link.message.reply_text = AsyncMock()

        context_link = MagicMock()
        context_link.args = [self.group.invite_code]

        async_to_sync(cmd_link_group)(update_link, context_link)

        self.group.refresh_from_db()
        assert self.group.telegram_chat_id == -10066778899
        assert self.group.telegram_chat_title == "BMB Ona Tili Guruh 2"
        reply_link = update_link.message.reply_text.call_args[0][0]
        assert "✅ Ushbu Telegram guruh Grand Education platformasidagi" in reply_link

    def test_school_groups_api_returns_group_code_and_telegram_metadata(self):
        self.group.telegram_chat_id = -10099887766
        self.group.telegram_chat_title = "Milliy Sertifikat Guruh A"
        self.group.save()

        self.client.force_authenticate(user=self.teacher)
        resp = self.client.get("/api/v1/school/groups/")
        assert resp.status_code == status.HTTP_200_OK
        items = resp.json()
        assert len(items) >= 1

        grp_data = next(g for g in items if g["id"] == self.group.id)
        assert grp_data["group_code"] == self.group.invite_code
        assert grp_data["invite_code"] == self.group.invite_code
        assert grp_data["telegram_chat_id"] == -10099887766
        assert grp_data["telegram_chat_title"] == "Milliy Sertifikat Guruh A"


# ===========================================================================
# TEST 3: Student Joining Group by Code / Link
# ===========================================================================


@pytest.mark.django_db
class TestStudentGroupJoinFlows:
    """Verify student joining StudentGroup via code and invite_token."""

    def setup_method(self):
        self.client = APIClient()
        self.teacher = User.objects.create_user(
            email="teacher_join_v2@grandec.uz",
            password="Password123!",
            first_name="Malika",
            last_name="Sultanova",
            role="teacher",
        )
        self.group = StudentGroup.objects.create(
            teacher=self.teacher,
            name="IELTS Intensive 7.5+",
            subject="english",
        )
        self.student1 = User.objects.create_user(
            email="student1_join_v2@grandec.uz",
            password="Password123!",
            first_name="Bekzod",
            last_name="Tursunov",
            role="student",
        )
        self.student2 = User.objects.create_user(
            email="student2_join_v2@grandec.uz",
            password="Password123!",
            first_name="Sevara",
            last_name="Aliyeva",
            role="student",
        )

    def test_student_join_by_code_endpoint(self):
        self.client.force_authenticate(user=self.student1)
        resp = self.client.post(
            "/api/v1/school/groups/join/",
            {"code": self.group.invite_code},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert self.group.students.filter(id=self.student1.id).exists()

    def test_student_join_by_invite_token_endpoint(self):
        # Public GET preview
        preview_resp = self.client.get(f"/api/v1/groups/join/{self.group.invite_token}/")
        assert preview_resp.status_code == status.HTTP_200_OK
        preview_data = preview_resp.json()
        assert preview_data["id"] == self.group.id
        assert preview_data["name"] == self.group.name
        assert preview_data["invite_code"] == self.group.invite_code

        # Authenticated POST join
        self.client.force_authenticate(user=self.student2)
        join_resp = self.client.post(f"/api/v1/groups/join/{self.group.invite_token}/")
        assert join_resp.status_code == status.HTTP_200_OK
        join_data = join_resp.json()
        assert join_data["status"] == "SUCCESS"
        assert self.group.students.filter(id=self.student2.id).exists()


# ===========================================================================
# TEST 4: Real-Time Auto-Broadcast of Results + PDF Vedomost to Linked Groups
# ===========================================================================


@pytest.mark.django_db
class TestRealTimeGroupAutoBroadcastAndVedomost:
    """Verify automatic scorecard + PDF vedomost delivery to linked Telegram groups."""

    def setup_method(self):
        self.client = APIClient()
        self.teacher = User.objects.create_user(
            email="teacher_bc_v2@grandec.uz",
            password="Password123!",
            first_name="Sardor",
            last_name="Rahimov",
            role="teacher",
        )
        # Note: student intentionally has NO personal telegram_chat_id to prove
        # group broadcast works independently of personal Telegram linking!
        self.student = User.objects.create_user(
            email="student_bc_v2@grandec.uz",
            password="Password123!",
            first_name="Dilnoza",
            last_name="Qodirova",
            role="student",
            telegram_chat_id=None,
        )
        self.course = Course.objects.create(
            teacher=self.teacher,
            title="IELTS & BMB Pro Course",
            slug="ielts-bmb-pro-course",
            subject="english",
            status=Course.Status.PUBLISHED,
        )
        self.group = StudentGroup.objects.create(
            teacher=self.teacher,
            name="IELTS & BMB Pro Group",
            subject="english",
            telegram_chat_id=-100123456789,
            telegram_chat_title="IELTS & BMB Pro Group",
        )
        self.group.students.add(self.student)

    def test_4a_test_attempt_completion_broadcasts_pdf_vedomost(self):
        test_obj = Test.objects.create(
            title="CEFR Multi-Level Diagnostic Mock #1",
            course=self.course,
            subject="english",
            status=Test.Status.PUBLISHED,
            pass_percentage=Decimal("60.00"),
        )
        Question.objects.create(
            test=test_obj,
            text="Sample question 1",
            points=50,
            position=1,
        )
        Question.objects.create(
            test=test_obj,
            text="Sample question 2",
            points=50,
            position=2,
        )

        attempt = TestAttempt.objects.create(
            test=test_obj,
            student=self.student,
            status=TestAttempt.Status.COMPLETED,
            score=Decimal("86.00"),
            percentage=Decimal("86.00"),
            is_passed=True,
            band_score=Decimal("7.5"),
            cefr_level="C1",
            section_scores={
                "LISTENING": {"earned": 44, "maximum": 50, "name": "Listening"},
                "READING": {"earned": 42, "maximum": 50, "name": "Reading"},
            },
        )
        result = Result.objects.create(
            attempt=attempt,
            student=self.student,
            test=test_obj,
            course=self.course,
            total_questions=2,
            correct_answers=2,
            wrong_answers=0,
            score=Decimal("86.00"),
            max_score=Decimal("100.00"),
            percentage=Decimal("86.00"),
            is_passed=True,
        )
        ResultSectionScore.objects.create(
            result=result,
            section_code="LISTENING",
            section_name="Listening",
            earned=Decimal("44.00"),
            maximum=Decimal("50.00"),
        )
        ResultSectionScore.objects.create(
            result=result,
            section_code="READING",
            section_name="Reading",
            earned=Decimal("42.00"),
            maximum=Decimal("50.00"),
        )

        with (
            patch.object(TelegramService, "send_document", return_value={"ok": True, "success": True}) as mock_doc,
            patch.object(TelegramService, "_call_api", return_value={"ok": True, "success": True}),
            patch("apps.notifications.tasks._generate_certificate", return_value=False),
            patch("apps.notifications.tasks._send_email_result"),
        ):
            task_out = process_test_result_task(result.id)

        assert task_out["status"] == "completed"
        assert mock_doc.called
        call_kwargs = mock_doc.call_args.kwargs
        assert call_kwargs["chat_id"] == -100123456789
        assert os.path.exists(call_kwargs["file_path"])
        assert call_kwargs["file_path"].endswith(".pdf")

        caption = call_kwargs["caption"]
        assert "Dilnoza Qodirova" in caption
        assert "IELTS &amp; BMB Pro Group" in caption  # Telegram HTML-escaped
        assert "CEFR Multi-Level Diagnostic Mock #1" in caption
        assert "Listening: 44/50" in caption
        assert "Reading: 42/50" in caption
        assert f"https://grandec.uz/results/{result.id}" in caption

    def test_4b_ai_essay_grading_completion_broadcasts_pdf_scorecard(self):
        topic = EssayTopic.objects.create(
            title="Artificial Intelligence in Modern Education",
            description="Discuss both views and give your opinion.",
            subject="english",
            category="ielts_task2",
            rubric_type="ielts_task2",
        )
        submission = EssaySubmission.objects.create(
            student=self.student,
            topic=topic,
            essay_text="Artificial intelligence is transforming education around the world...",
            word_count=265,
            status=EssaySubmission.Status.GRADED,
            total_score=Decimal("7.5"),
            max_score=9,
            summary="Strong academic essay with clear progression.",
            raw_result={
                "overall_band": 7.5,
                "cefr_level": "C1",
                "weaknesses": ["Complex conditional clauses", "Academic collocations"],
            },
        )
        EssayCriterionScore.objects.create(
            submission=submission,
            criterion_id=1,
            name="Task Response",
            score=Decimal("7.5"),
            reason="Well developed arguments.",
        )

        with (
            patch.object(TelegramService, "send_document", return_value={"ok": True, "success": True}) as mock_doc,
            patch.object(TelegramService, "_call_api", return_value={"ok": True, "success": True}),
        ):
            notify_student_essay_graded(submission)

        assert mock_doc.called
        call_kwargs = mock_doc.call_args.kwargs
        assert call_kwargs["chat_id"] == -100123456789
        assert os.path.exists(call_kwargs["file_path"])
        assert call_kwargs["file_path"].endswith(".pdf")

        caption = call_kwargs["caption"]
        assert "YANGI AI ESSE NATIJASI" in caption
        assert "Dilnoza Qodirova" in caption
        assert "IELTS &amp; BMB Pro Group" in caption or "IELTS & BMB Pro Group" in caption
        assert "Artificial Intelligence in Modern Education" in caption
        assert f"https://grandec.uz/essays/result/{submission.id}" in caption

    def test_4c_ai_speaking_evaluation_completion_broadcasts_pdf_scorecard(self):
        sp_topic = SpeakingTopic.objects.create(
            title="Describe a memorable journey you have taken",
            subject="english",
            part=SpeakingTopic.PartChoice.PART2,
            prompt="Describe a memorable journey you have taken recently.",
            bullet_points=["Where you went", "Who you went with", "Why it was memorable"],
        )
        speaking_sub = SpeakingSubmission.objects.create(
            user=self.student,
            topic=sp_topic,
            duration_seconds=115,
            transcript="Last summer I travelled to Samarkand by high-speed train...",
            fluency_score=Decimal("7.5"),
            lexical_score=Decimal("7.0"),
            grammar_score=Decimal("6.5"),
            pronunciation_score=Decimal("7.0"),
            overall_band=Decimal("7.0"),
            feedback={
                "summary": "Fluent delivery with good topic vocabulary.",
                "fluency_feedback": "Well-organized long turn.",
                "lexical_feedback": "Good idiomatic expressions.",
                "grammar_feedback": "Minor tense slips.",
                "pronunciation_feedback": "Clear intonation.",
            },
            status=SpeakingSubmission.Status.COMPLETED,
        )

        with (
            patch.object(TelegramService, "send_document", return_value={"ok": True, "success": True}) as mock_doc,
            patch.object(TelegramService, "_call_api", return_value={"ok": True, "success": True}),
        ):
            res = broadcast_speaking_result_to_groups(speaking_sub)

        assert res["status"] == "sent"
        assert res["sent_groups"] == 1
        assert mock_doc.called
        call_kwargs = mock_doc.call_args.kwargs
        assert call_kwargs["chat_id"] == -100123456789
        assert os.path.exists(call_kwargs["file_path"])
        assert call_kwargs["file_path"].endswith(".pdf")

        caption = call_kwargs["caption"]
        assert "YANGI AI SPEAKING NATIJASI" in caption
        assert "Dilnoza Qodirova" in caption
        assert "Describe a memorable journey you have taken" in caption
        assert "Band 7.0" in caption

    def test_4d_web_trigger_group_leaderboard_and_vedomost_broadcast(self):
        self.client.force_authenticate(user=self.teacher)
        url = f"/api/v1/school/groups/{self.group.id}/broadcast-vedomost/"

        with (
            patch.object(TelegramService, "send_document", return_value={"ok": True, "success": True}) as mock_doc,
            patch.object(TelegramService, "_call_api", return_value={"ok": True, "success": True}) as mock_api,
        ):
            resp = self.client.post(url, {}, format="json")

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["status"] == "ok"

        assert mock_api.called
        msg_payload = mock_api.call_args.args[1]
        assert msg_payload["chat_id"] == -100123456789
        assert "GURUH REYTINGI VA VEDOMOST" in msg_payload["text"]
        assert self.group.name in msg_payload["text"]

        assert mock_doc.called
        doc_kwargs = mock_doc.call_args.kwargs
        assert doc_kwargs["chat_id"] == -100123456789
        assert os.path.exists(doc_kwargs["file_path"])
        assert doc_kwargs["file_path"].endswith(".pdf")


# ===========================================================================
# TEST 5: Content Seeder Verification (`seed_content`)
# ===========================================================================


@pytest.mark.django_db
class TestSeedContentCommand:
    """Verify `python manage.py seed_content` populates all required tests and topics."""

    def test_seed_content_populates_tests_essay_topics_and_speaking_topics(self):
        call_command("seed_content")

        # 1. >= 2 published uzbek Milliy Sertifikat tests and >= 2 Attestatsiya tests
        uzbek_published = Test.objects.filter(
            subject="uzbek",
            status=Test.Status.PUBLISHED,
            is_active=True,
        )
        milliy_tests = uzbek_published.filter(exam_type="milliy_sertifikat")
        attest_tests = uzbek_published.filter(exam_type="attestatsiya")
        assert milliy_tests.count() >= 2
        assert attest_tests.count() >= 2

        # 2. >= 6 active EssayTopics for each of ielts_task1, ielts_task2, ona_tili
        for category_code in ("ielts_task1", "ielts_task2", "ona_tili"):
            cnt = EssayTopic.objects.filter(category=category_code, is_active=True).count()
            assert cnt >= 6, f"Expected >= 6 EssayTopics for {category_code}, got {cnt}"

        # 3. >= 6 active SpeakingTopics for each of part1, part2, part3, multilevel
        for part_code in ("part1", "part2", "part3", "multilevel"):
            cnt = SpeakingTopic.objects.filter(part=part_code, is_active=True).count()
            assert cnt >= 6, f"Expected >= 6 SpeakingTopics for {part_code}, got {cnt}"
