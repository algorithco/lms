"""
Tests for Telegram Mini App Auth, Offline-First Batch Save, DeepSeek Socratic AI Tutor, and Interactive Streak.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.gamification import get_user_streak_info, record_user_activity
from apps.courses.models import Category, Course
from apps.tests.ai_tutor import generate_socratic_explanation
from apps.tests.models import Choice, Question, Test, TestAttempt

User = get_user_model()


def _make_tma_init_data(user_dict: dict, bot_token: str = "test-bot-token-12345", start_param: str = "") -> str:
    """Generate valid Telegram initData with HMAC-SHA256 signature."""
    auth_date = int(time.time())
    data = {
        "auth_date": str(auth_date),
        "user": json.dumps(user_dict, separators=(",", ":")),
    }
    if start_param:
        data["start_param"] = start_param

    sorted_pairs = sorted(data.items())
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_pairs)

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    data_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    data["hash"] = data_hash
    return urlencode(data)


@pytest.mark.django_db
class TestTelegramMiniAppAuth:
    """Tests for zero-friction TMA Telegram WebApp authentication."""

    def test_tma_auth_new_user_and_tokens(self):
        client = APIClient()
        tg_id = 9988776655
        init_data = _make_tma_init_data(
            {"id": tg_id, "first_name": "Sardor", "last_name": "Karimov", "username": "sardor_k"},
            start_param="test_456",
        )

        with override_settings(TELEGRAM_BOT_TOKEN="test-bot-token-12345"):
            resp = client.post(
                "/api/v1/auth/telegram-webapp/",
                {"init_data": init_data},
                format="json",
            )

        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "tokens" in data
        assert "access" in data["tokens"]
        assert "refresh" in data["tokens"]
        assert data["user"]["first_name"] == "Sardor"
        assert data["start_param"] == "test_456"

        # Verify User record was created in database
        u = User.objects.filter(telegram_chat_id=tg_id).first()
        assert u is not None
        assert u.first_name == "Sardor"
        assert u.role == User.Role.STUDENT

    def test_tma_auth_invalid_hash_rejected(self):
        client = APIClient()
        with override_settings(TELEGRAM_BOT_TOKEN="test-bot-token-12345"):
            resp = client.post(
                "/api/v1/auth/telegram-webapp/",
                {"init_data": "auth_date=123&user={}&hash=fake_invalid_hash"},
                format="json",
            )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestOfflineBatchSave:
    """Tests for offline-first batch answer saving."""

    def test_save_batch_answers_atomic(self):
        teacher = User.objects.create_user(
            email="bio_teacher@grandec.uz",
            password="Password123!",
            role=User.Role.TEACHER,
        )
        cat = Category.objects.create(name="Biologiya", slug="biology-cat")
        course = Course.objects.create(
            title="Biologiya Kursi",
            slug="bio-course-batch",
            teacher=teacher,
            category=cat,
            subject="biology",
        )
        user = User.objects.create_user(
            email="batch_student@grandec.uz",
            password="Password123!",
            role=User.Role.STUDENT,
        )
        test = Test.objects.create(
            course=course,
            title="Biologiya Offline Mock",
            subject="biology",
            time_limit_minutes=45,
            is_active=True,
        )
        q1 = Question.objects.create(test=test, text="Hujayraning energetik stansiyasi?", question_type="single", points=2)
        c1 = Choice.objects.create(question=q1, text="Mitoxondriya", is_correct=True)
        Choice.objects.create(question=q1, text="Ribosoma", is_correct=False)

        q2 = Question.objects.create(test=test, text="Xloroplast qanday pigmentga ega?", question_type="single", points=2)
        c3 = Choice.objects.create(question=q2, text="Xlorofill", is_correct=True)

        attempt = TestAttempt.objects.create(
            student=user,
            test=test,
            status=TestAttempt.Status.IN_PROGRESS,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        payload = {
            "attempt_id": attempt.id,
            "answers": [
                {"question_id": q1.id, "choice_ids": [c1.id]},
                {"question_id": q2.id, "choice_ids": [c3.id]},
            ],
        }

        resp = client.post(
            f"/api/tests/attempts/{attempt.id}/save-batch/",
            payload,
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert data["saved_count"] == 2
        assert data["synced"] is True

        # Verify in database
        from apps.tests.models import StudentAnswer

        sa1 = StudentAnswer.objects.filter(attempt=attempt, question=q1).first()
        assert sa1 is not None
        assert c1 in sa1.selected_choices.all()


@pytest.mark.django_db
class TestDeepSeekSocraticTutor:
    """Tests for Socratic AI Tutor explanations and Redis 7-day caching."""

    def test_socratic_explanation_generation_and_caching(self):
        cache.clear()
        res = generate_socratic_explanation(
            question_text="Mitoz jarayonining anafaza bosqichida nima sodir bo'ladi?",
            correct_answer="Xromatidlar qutblarga ajraladi",
            user_answer="Yadro qobig'i hosil bo'ladi",
            subject="biology",
            question_id=9991,
        )
        assert res["success"] is True
        assert isinstance(res["explanation"], str)
        assert len(res["explanation"]) > 20
        assert res["cached"] is False

        # Second call must hit the 7-day cache
        res2 = generate_socratic_explanation(
            question_text="Mitoz jarayonining anafaza bosqichida nima sodir bo'ladi?",
            correct_answer="Xromatidlar qutblarga ajraladi",
            user_answer="Yadro qobig'i hosil bo'ladi",
            subject="biology",
            question_id=9991,
        )
        assert res2["success"] is True
        assert res2["cached"] is True
        assert res2["explanation"] == res["explanation"]

    def test_socratic_tutor_api_endpoint(self):
        teacher = User.objects.create_user(
            email="law_teacher_soc@grandec.uz",
            password="Password123!",
            role=User.Role.TEACHER,
        )
        cat = Category.objects.create(name="Huquq", slug="law-cat-soc")
        course = Course.objects.create(
            title="Huquqshunoslik",
            slug="law-course-soc",
            teacher=teacher,
            category=cat,
            subject="law",
        )
        user = User.objects.create_user(
            email="socratic_user@grandec.uz",
            password="Password123!",
            role=User.Role.STUDENT,
        )
        if hasattr(user, "profile"):
            user.profile.plan = "pro"
            user.profile.save()

        test = Test.objects.create(
            course=course,
            title="Huquq Mock",
            subject="law",
            is_active=True,
        )
        q = Question.objects.create(test=test, text="O'zbekiston Respublikasi Konstitutsiyasining 1-moddasi?", question_type="single")
        Choice.objects.create(question=q, text="O'zbekiston — suveren, demokratik, huquqiy, ijtimoiy va dunyoviy davlat", is_correct=True)
        wrong = Choice.objects.create(question=q, text="O'zbekiston — monarxiya davlati", is_correct=False)

        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(
            "/api/tests/socratic-tutor/",
            {
                "question_id": q.id,
                "selected_choice_id": wrong.id,
                "user_answer": wrong.text,
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["success"] is True
        assert "explanation" in data
        assert data["subject"] == "law"


@pytest.mark.django_db
class TestInteractiveStreak:
    """Tests for streak tracking, week-days status, and milestones."""

    def test_streak_calculation_and_milestones(self):
        user = User.objects.create_user(
            email="streak_hero@grandec.uz",
            password="Password123!",
            role=User.Role.STUDENT,
        )
        if hasattr(user, "profile"):
            user.profile.current_streak = 5
            user.profile.longest_streak = 10
            user.profile.save()

        info = get_user_streak_info(user)
        assert "week_days" in info
        assert len(info["week_days"]) == 7
        assert "milestones" in info
        assert len(info["milestones"]) == 2
        assert info["milestones"][0]["target"] == 7

        # Test activity recording increments streak
        res = record_user_activity(user, xp_amount=25, activity_type="test")
        assert res["ok"] is True
        assert res["current_streak"] >= 1
        assert res["total_xp"] >= 25

    def test_streak_api_endpoint(self):
        user = User.objects.create_user(
            email="streak_api@grandec.uz",
            password="Password123!",
            role=User.Role.STUDENT,
        )

        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.get("/api/v1/gamification/streak/")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "current_streak" in data
        assert "week_days" in data
        assert "milestones" in data
