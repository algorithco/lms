"""Payment card, plan display with a manual limit, data-fix commands and the backup scripts."""

from __future__ import annotations

import shutil
import subprocess
from decimal import Decimal
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import Profile
from apps.payments.models import SubscriptionOverride, SubscriptionPlan
from apps.payments.subscriptions import grant_subscription

User = get_user_model()
ROOT = Path(__file__).resolve().parent.parent


def _working_bash() -> str | None:
    """A real bash (on Windows ``bash`` may be the WSL stub, which cannot run scripts)."""
    for candidate in (shutil.which("bash"), "C:/Program Files/Git/bin/bash.exe"):
        if not candidate or not Path(candidate).exists():
            continue
        try:
            probe = subprocess.run([candidate, "-c", "echo ok"], capture_output=True, text=True, timeout=20)
        except Exception:
            continue
        if probe.returncode == 0 and probe.stdout.strip() == "ok":
            return candidate
    return None


BASH = _working_bash()


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


def _user(email, role="student"):
    u = User.objects.create_user(email=email, password="x-Pass-123!", role=role)
    Profile.objects.get_or_create(user=u)
    return u


def _api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


# --------------------------------------------------------------------------
# Payment card
# --------------------------------------------------------------------------
CARD_URLS = ("/api/v1/payments/card-info/", "/api/v1/billing/card-details/")


@pytest.mark.django_db
@pytest.mark.parametrize("url", CARD_URLS)
def test_no_card_configured_says_unavailable_and_tells_the_admin_once(url, settings):
    settings.PAYMENT_CARD_NUMBER = ""
    settings.PAYMENT_CARD_HOLDER = ""
    settings.ADMIN_TELEGRAM_ID = 4242
    user = _user("card_a@example.test")
    with patch("apps.notifications.services.telegram_service.TelegramService.send_message") as send:
        first = _api(user).get(url)
        second = _api(user).get(url)
    for res in (first, second):
        assert res.status_code == 503
        body = res.json()
        assert body["code"] == "payment_unavailable"
        assert body["detail"] == "To'lov ma'lumoti hozircha mavjud emas."
        assert "card_number" not in body
    assert send.call_count == 1 and send.call_args.kwargs["chat_id"] == 4242


@pytest.mark.django_db
def test_card_is_served_only_from_settings_and_only_when_complete(settings):
    user = _user("card_b@example.test")
    settings.PAYMENT_CARD_NUMBER = "0000 1111 2222 3333"
    settings.PAYMENT_CARD_HOLDER = ""
    with patch("apps.notifications.services.telegram_service.TelegramService.send_message"):
        assert _api(user).get(CARD_URLS[0]).status_code == 503  # a number without a holder is not enough
    settings.PAYMENT_CARD_HOLDER = "Test Holder"
    res = _api(user).get(CARD_URLS[0])
    assert res.status_code == 200
    assert res.json()["card_number"] == "0000 1111 2222 3333" and res.json()["card_holder"] == "Test Holder"
    assert APIClient().get(CARD_URLS[0]).status_code in (401, 403)  # guests never see it


def test_no_card_number_is_written_in_the_source_or_example_env():
    leaked = []
    for path in list((ROOT / "apps").rglob("*.py")) + list((ROOT / "config").rglob("*.py")) + [ROOT / ".env.example", ROOT / ".env.prod.example"]:
        if "4916" in path.read_text(encoding="utf-8", errors="ignore"):
            leaked.append(str(path.relative_to(ROOT)))
    assert leaked == []


# --------------------------------------------------------------------------
# Plan display with a manual limit override
# --------------------------------------------------------------------------
def _pro(user):
    plan, _ = SubscriptionPlan.objects.get_or_create(
        plan_type="pro", defaults={"name": "Pro", "price_monthly": Decimal("15000"), "test_limit": 30, "text_essay_weekly_limit": 15}
    )
    admin = User.objects.create_superuser(email=f"adm_{user.email}", password="x-Pass-123!")
    grant_subscription(user, plan, kind="admin", actor=admin, days=30, reason="test")


@pytest.mark.django_db
def test_pro_student_with_a_manual_limit_stays_pro_and_is_marked_custom():
    user = _user("tier_pro@example.test")
    _pro(user)
    SubscriptionOverride.objects.create(user=user, is_active=True, text_essay_weekly_limit=2, reason="special case")
    me = _api(user).get("/api/auth/me/").json()
    assert me["plan"] == "PRO" and me["is_paid"] is True and me["has_custom_limit"] is True
    ent = _api(user).get("/api/v1/billing/entitlement/").json()
    plan_name = SubscriptionPlan.objects.get(plan_type="pro").name
    assert ent["plan_name"] == plan_name and ent["plan_type"] == "pro" and ent["custom_limit"] is True
    assert ent["is_paid"] is True
    # the limits still come from the override: only the label changed
    assert ent["source"] == "override" and ent["text_essay"]["limit"] == 2


@pytest.mark.django_db
def test_student_with_only_an_override_is_free_with_the_custom_mark():
    user = _user("tier_free@example.test")
    SubscriptionOverride.objects.create(user=user, is_active=True, text_essay_weekly_limit=5, reason="gift")
    me = _api(user).get("/api/auth/me/").json()
    assert me["plan"] == "FREE" and me["has_custom_limit"] is True
    ent = _api(user).get("/api/v1/billing/entitlement/").json()
    assert ent["plan_type"] is None and ent["custom_limit"] is True and ent["text_essay"]["limit"] == 5


@pytest.mark.django_db
def test_ordinary_students_have_no_custom_mark_and_quotas_use_the_same_tier_function():
    from apps.payments.ai_quota import get_display_tier, get_user_plan_tier

    user = _user("tier_plain@example.test")
    assert get_display_tier(user) == ("free", False)
    _pro(user)
    assert get_display_tier(user) == ("pro", False)
    assert get_user_plan_tier(user) == "pro"
    assert _api(user).get("/api/v1/billing/entitlement/").json()["custom_limit"] is False
    assert _api(user).get("/api/auth/me/").json()["has_custom_limit"] is False


# --------------------------------------------------------------------------
# publish_cefr_writing_topics
# --------------------------------------------------------------------------
@pytest.fixture
def cefr_mock(db):
    from apps.courses.models import Course
    from apps.tests.models import Question, Test

    teacher = _user("cefr_t@example.test", "teacher")
    course = Course.objects.create(teacher=teacher, title="CEFR", slug="cefr-x")
    test = Test.objects.create(
        title="Record Mock", course=course, exam_type=Test.ExamType.CEFR_MULTILEVEL,
        status=Test.Status.PUBLISHED, is_active=True, subject="english",
    )
    texts = [
        "TASK 1.1 · INFORMAL — Write about 50 words.\nWrite a short email to a friend.",
        "TASK 1.2 · FORMAL — Write 120–150 words.\nWrite an email to the manager.",
        "PART 2 · BLOG POST — Write 180–200 words.\nYou are taking part in a blog.",
        "A written prompt without any word range.",
    ]
    for i, text in enumerate(texts, start=1):
        Question.objects.create(test=test, text=text, question_type="written", position=2000 + i, points=1)
    return test


@pytest.mark.django_db
def test_cefr_topics_command_is_a_dry_run_by_default_then_idempotent(cefr_mock):
    from apps.essays.models import EssayTopic

    out = StringIO()
    call_command("publish_cefr_writing_topics", stdout=out)
    assert EssayTopic.objects.count() == 0
    assert "dry run" in out.getvalue() and "would create 3" in out.getvalue()

    call_command("publish_cefr_writing_topics", "--apply", stdout=StringIO())
    topics = list(EssayTopic.objects.order_by("id"))
    assert len(topics) == 3
    assert all(t.category == "multilevel" and t.subject == "english" and t.is_active for t in topics)
    assert [(t.word_limit_min, t.word_limit_max) for t in topics] == [(40, 75), (120, 150), (180, 200)]
    assert [t.rubric_type for t in topics] == ["ielts_task1", "ielts_task1", "ielts_task2"]
    assert topics[1].description.startswith("TASK 1.2")  # the exam's own text, not written here

    call_command("publish_cefr_writing_topics", "--apply", stdout=StringIO())
    assert EssayTopic.objects.count() == 3  # nothing duplicated


@pytest.mark.django_db
def test_published_cefr_topics_appear_in_the_english_studio_list(cefr_mock):
    call_command("publish_cefr_writing_topics", "--apply", stdout=StringIO())
    res = _api(_user("cefr_student@example.test")).get("/tma/api/essays/topics/?subject=english&category=multilevel")
    assert res.status_code == 200
    titles = [t["title"] for t in res.json()["topics"]]
    assert len(titles) == 3 and any("TASK 1.1" in t for t in titles)


# --------------------------------------------------------------------------
# fix_official_claims
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_official_claims_command_dry_run_changes_nothing_apply_softens_only_the_safe_cases():
    from apps.essays.models import EssayTopic

    topic = EssayTopic.objects.create(
        title="Rasmiy namuna: Vatan", description="Natijaga kafolat beramiz. Cambridge uslubida.", category="ona_tili"
    )
    out = StringIO()
    call_command("fix_official_claims", stdout=out)
    topic.refresh_from_db()
    assert topic.title == "Rasmiy namuna: Vatan"
    assert "needs a person" in out.getvalue() and "dry run" in out.getvalue()

    call_command("fix_official_claims", "--apply", stdout=StringIO())
    topic.refresh_from_db()
    assert topic.title == "Namuna: Vatan"
    assert "kafolat" in topic.description and "Cambridge" in topic.description  # left for a person
    again = StringIO()
    call_command("fix_official_claims", "--apply", stdout=again)
    assert "Automatic fixes: 0 rows" in again.getvalue()


# --------------------------------------------------------------------------
# Backup scripts
# --------------------------------------------------------------------------
@pytest.mark.skipif(BASH is None, reason="bash not available")
@pytest.mark.parametrize("script", ["backup_db.sh", "backup_offsite.sh", "restore_test.sh"])
def test_backup_scripts_are_valid_bash(script):
    result = subprocess.run([BASH, "-n", str(ROOT / "deploy" / "scripts" / script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(BASH is None, reason="bash not available")
def test_offsite_script_sends_nothing_without_a_target_and_restore_refuses_remote_hosts(tmp_path):
    env = {"PATH": __import__("os").environ["PATH"]}
    off = subprocess.run([BASH, str(ROOT / "deploy/scripts/backup_offsite.sh"), str(tmp_path)], capture_output=True, text=True, env=env)
    assert off.returncode == 2 and "Nothing was copied" in off.stderr
    fake = tmp_path / "x.sql.gz"
    fake.write_bytes(b"")
    res = subprocess.run(
        [BASH, str(ROOT / "deploy/scripts/restore_test.sh"), str(fake)],
        capture_output=True, text=True, env={**env, "PGHOST": "db.example.com"},
    )
    assert res.returncode == 1 and "non-local host" in res.stderr


def test_no_cron_or_service_was_added_for_backups():
    text = (ROOT / "docs" / "BACKUP.md").read_text(encoding="utf-8")
    assert "Nothing here is switched on yet" in text
    assert not list((ROOT / "deploy").glob("*backup*.service")) and not list((ROOT / "deploy").glob("*backup*.timer"))
