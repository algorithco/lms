"""No AI result means "not graded": never an invented score, band, transcript or answer key.

Every provider failure mode is simulated with a mock: missing key, timeout,
broken (non-JSON) answer and out-of-range scores. After each, the allowance is
returned and the admin hears about repeated failures.
"""

from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core import ai_health
from apps.core.ai_health import AIUnavailable
from apps.essays.models import EssaySubmission
from apps.essays.services import apply_ai_result, grade_ielts_essay
from apps.payments.models import SubscriptionUsage

from django.contrib.auth import get_user_model

User = get_user_model()

IELTS_TEXT = (
    "Technology has changed how people study, and many schools now rely on online tools. "
    "However, some students lose focus when every lesson happens on a screen. "
) * 6


@pytest.fixture(autouse=True)
def _clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def student(db):
    return User.objects.create_user(email="hg_student@example.test", password="x-Pass-123!", role="student")


# --------------------------------------------------------------------------
# IELTS / CEFR essay grading
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "failure",
    [
        pytest.param({"side_effect": TimeoutError("timed out")}, id="timeout"),
        pytest.param({"side_effect": RuntimeError("401 invalid key")}, id="provider-error"),
    ],
)
def test_ielts_grading_provider_failure_is_not_graded(failure):
    with patch("apps.essays.services._is_mock_mode", return_value=False), \
         patch("apps.essays.pre_validation.pre_validate_essay"), \
         patch("apps.essays.services._get_llm_client"), \
         patch("apps.essays.services._chat_with_fallback", **failure):
        with pytest.raises(AIUnavailable):
            grade_ielts_essay(IELTS_TEXT, topic_title="Technology", task_type="ielts_task2", min_words=50)


def test_ielts_grading_broken_json_is_not_graded():
    class _Msg:
        content = "Sorry, I cannot do that {not json"

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    with patch("apps.essays.services._is_mock_mode", return_value=False), \
         patch("apps.essays.pre_validation.pre_validate_essay"), \
         patch("apps.essays.services._get_llm_client"), \
         patch("apps.essays.services._chat_with_fallback", return_value=(_Resp(), "m")):
        with pytest.raises(AIUnavailable):
            grade_ielts_essay(IELTS_TEXT, topic_title="Technology", task_type="ielts_task2", min_words=50)


def test_a_mock_grade_is_refused_when_the_platform_is_not_in_mock_mode(student):
    sub = EssaySubmission.objects.create(
        student=student, essay_text=IELTS_TEXT, status=EssaySubmission.Status.PENDING
    )
    fake = {"_mock_mode": True, "total_score": 9, "max_score": 9, "criteria": [], "summary": ""}
    with patch("apps.essays.services._is_mock_mode", return_value=False):
        with pytest.raises(AIUnavailable):
            apply_ai_result(sub, fake)
    sub.refresh_from_db()
    assert sub.status == EssaySubmission.Status.PENDING and sub.total_score in (None, 0)


# --------------------------------------------------------------------------
# Failed grading gives the allowance back and counts toward an admin alert
# --------------------------------------------------------------------------
def _committed_usage(student, sub):
    return SubscriptionUsage.objects.create(
        user=student,
        kind=SubscriptionUsage.Kind.TEXT_ESSAY,
        status=SubscriptionUsage.Status.COMMITTED,
        idempotency_key=f"essay:{sub.pk}",
        period_start=timezone.now() - timedelta(days=1),
        submission=sub,
    )


def test_failed_grading_marks_error_and_refunds_the_usage(student):
    from apps.essays.tasks import _mark_grading_failed

    sub = EssaySubmission.objects.create(student=student, essay_text=IELTS_TEXT, status=EssaySubmission.Status.PENDING)
    usage = _committed_usage(student, sub)
    _mark_grading_failed(sub.pk, RuntimeError("provider down"))
    sub.refresh_from_db()
    usage.refresh_from_db()
    assert sub.status == EssaySubmission.Status.ERROR
    assert usage.status == SubscriptionUsage.Status.RELEASED and usage.released_at is not None


def test_refund_is_idempotent_and_never_touches_a_graded_essays_usage(student):
    from apps.payments.entitlements import refund_usage_for_submission

    graded = EssaySubmission.objects.create(student=student, essay_text=IELTS_TEXT, status=EssaySubmission.Status.GRADED)
    other = EssaySubmission.objects.create(student=student, essay_text=IELTS_TEXT + " x", status=EssaySubmission.Status.PENDING)
    kept = _committed_usage(student, graded)
    gone = _committed_usage(student, other)
    assert refund_usage_for_submission(other.pk) == 1
    assert refund_usage_for_submission(other.pk) == 0
    kept.refresh_from_db()
    gone.refresh_from_db()
    assert kept.status == SubscriptionUsage.Status.COMMITTED
    assert gone.status == SubscriptionUsage.Status.RELEASED


def test_admin_is_told_after_three_failures_in_a_row_and_only_once(settings):
    settings.ADMIN_TELEGRAM_ID = 111
    with patch("apps.notifications.services.telegram_service.TelegramService.send_message") as send:
        ai_health.record_ai_failure("essay", "boom")
        ai_health.record_ai_failure("essay", "boom")
        assert send.call_count == 0
        ai_health.record_ai_failure("essay", "boom")
        assert send.call_count == 1
        ai_health.record_ai_failure("essay", "boom")
        assert send.call_count == 1  # cooldown: no spam
        assert send.call_args.kwargs["chat_id"] == 111
        assert "essay" in send.call_args.kwargs["text"]


def test_a_success_resets_the_failure_streak(settings):
    settings.ADMIN_TELEGRAM_ID = 111
    with patch("apps.notifications.services.telegram_service.TelegramService.send_message") as send:
        ai_health.record_ai_failure("ocr", "x")
        ai_health.record_ai_failure("ocr", "x")
        ai_health.record_ai_success("ocr")
        ai_health.record_ai_failure("ocr", "x")
        ai_health.record_ai_failure("ocr", "x")
        assert send.call_count == 0


# --------------------------------------------------------------------------
# The IELTS endpoint used to grade for anyone, without limit
# --------------------------------------------------------------------------
@pytest.fixture
def api(student):
    c = APIClient()
    c.force_authenticate(student)
    return c


def test_ielts_endpoint_failure_returns_503_and_gives_the_allowance_back(api, student):
    with patch("apps.essays.services.grade_ielts_essay", side_effect=AIUnavailable("down")):
        res = api.post("/api/v1/essays/ielts/grade/", {"essay_text": IELTS_TEXT, "task_type": "ielts_task2"}, format="json")
    assert res.status_code == 503 and res.json()["code"] == "not_graded"
    sub = EssaySubmission.objects.get(student=student)
    assert sub.status == EssaySubmission.Status.ERROR
    usage = SubscriptionUsage.objects.get(user=student)
    assert usage.status == SubscriptionUsage.Status.RELEASED


def test_ielts_endpoint_respects_the_text_essay_allowance(api, student):
    # FREE tier: one text essay in the window; the second is refused and leaves no trace.
    ok = {
        "overall_band": 6.0, "cefr_level": "B2", "word_count": 100, "min_words": 50, "criteria": [],
        "summary": "s", "strengths": [], "weaknesses": [], "teacher_recommendation": "", "improved_text": "",
        "total_score": 6, "max_score": 9,
    }
    with patch("apps.essays.services.grade_ielts_essay", return_value=ok), patch("apps.essays.services.apply_ai_result"):
        first = api.post("/api/v1/essays/ielts/grade/", {"essay_text": IELTS_TEXT}, format="json")
        second = api.post("/api/v1/essays/ielts/grade/", {"essay_text": IELTS_TEXT + " again"}, format="json")
    assert first.status_code == 200, first.content
    assert second.status_code == 403 and second.json()["detail"] == "LIMIT_EXCEEDED"
    assert EssaySubmission.objects.filter(student=student).count() == 1


# --------------------------------------------------------------------------
# Speaking: no transcript, no band, no XP when nothing real came back
# --------------------------------------------------------------------------
@pytest.fixture
def topic(db):
    from apps.speaking.models import SpeakingTopic

    return SpeakingTopic.objects.create(title="Hometown", part=SpeakingTopic.PartChoice.PART1, prompt="Tell me about your hometown.")


def _audio():
    return SimpleUploadedFile("a.wav", b"RIFF....WAVEfmt ...data...", content_type="audio/wav")


@pytest.mark.parametrize(
    "evaluation",
    [
        pytest.param(None, id="no-evaluation"),
        pytest.param({"overall_band": 7.0}, id="scores-missing"),
        pytest.param({"fluency_score": 12, "lexical_score": 6, "grammar_score": 6, "pronunciation_score": 6}, id="score-out-of-range"),
        pytest.param({"fluency_score": "n/a", "lexical_score": 6, "grammar_score": 6, "pronunciation_score": 6}, id="score-not-a-number"),
    ],
)
def test_speaking_bad_evaluation_is_not_graded(student, topic, evaluation):
    from apps.accounts.models import Profile
    from apps.speaking.models import SpeakingSubmission
    from apps.speaking.services import evaluate_speaking_submission

    xp_before = Profile.objects.get_or_create(user=student)[0].xp_points
    with patch("apps.speaking.services._process_audio_stream_fish_audio", return_value="I live in a small town."), \
         patch("apps.speaking.services._evaluate_speech_deepseek_r1", return_value=evaluation):
        with pytest.raises(AIUnavailable):
            evaluate_speaking_submission(_audio(), topic.pk, student, 30)
    assert not SpeakingSubmission.objects.filter(user=student).exists()
    assert Profile.objects.get(user=student).xp_points == xp_before


def test_speaking_endpoint_503_refunds_todays_call(api, student, topic):
    with patch("apps.speaking.views.evaluate_speaking_submission", side_effect=AIUnavailable("down")):
        res = api.post("/api/v1/speaking/submit/", {"audio": _audio(), "topic_id": topic.pk, "duration_seconds": "30"}, format="multipart")
    assert res.status_code == 503 and res.json()["code"] == "not_graded"
    # FREE gets 1 call a day; the failed one was returned, so a retry is allowed (not a 429).
    with patch("apps.speaking.views.evaluate_speaking_submission", side_effect=AIUnavailable("down")) as ev:
        again = api.post("/api/v1/speaking/submit/", {"audio": _audio(), "topic_id": topic.pk}, format="multipart")
    assert again.status_code == 503 and ev.call_count == 1


def test_speaking_endpoint_daily_cap_file_type_and_size(api, student, topic, settings):
    bad = SimpleUploadedFile("a.exe", b"MZ", content_type="application/x-msdownload")
    assert api.post("/api/v1/speaking/submit/", {"audio": bad, "topic_id": topic.pk}, format="multipart").status_code == 400
    with patch("apps.speaking.views.SpeakingSubmitView.MAX_AUDIO_BYTES", 5):
        assert api.post("/api/v1/speaking/submit/", {"audio": _audio(), "topic_id": topic.pk}, format="multipart").status_code == 413
    sub = type("Sub", (), {"id": 1})()
    with patch("apps.speaking.views.evaluate_speaking_submission", return_value=sub), \
         patch("apps.speaking.views._serialize_submission", return_value={"id": 1}):
        first = api.post("/api/v1/speaking/submit/", {"audio": _audio(), "topic_id": topic.pk}, format="multipart")
        second = api.post("/api/v1/speaking/submit/", {"audio": _audio(), "topic_id": topic.pk}, format="multipart")
    assert first.status_code == 201
    assert second.status_code == 429 and second.json()["code"] == "daily_limit"


# --------------------------------------------------------------------------
# Vocabulary generator and test converter
# --------------------------------------------------------------------------
def test_vocab_endpoint_without_ai_is_503_and_saves_nothing(db, settings):
    from apps.vocabulary.models import VocabularyPack

    settings.OPENROUTER_API_KEY = ""
    settings.DEEPSEEK_API_KEY = ""
    teacher = User.objects.create_user(email="hg_teacher@example.test", password="x-Pass-123!", role="teacher")
    c = APIClient()
    c.force_authenticate(teacher)
    res = c.post("/api/v1/vocabulary/generate/", {"raw_text": "resilient\npersistent", "save": True}, format="json")
    if res.status_code == 404:
        pytest.skip("vocabulary route not mounted under this path")
    assert res.status_code == 503 and res.json()["code"] == "ai_unavailable"
    assert VocabularyPack.objects.count() == 0


def test_students_cannot_use_the_vocab_generator(api):
    res = api.post("/api/v1/vocabulary/generate/", {"raw_text": "word"}, format="json")
    if res.status_code == 404:
        pytest.skip("vocabulary route not mounted under this path")
    assert res.status_code == 403


def test_converter_never_guesses_an_answer_or_invents_choices():
    from apps.tests.ai_converter import ConverterError, _parse_raw_text_regex, convert_document_to_test_data, save_converted_test

    parsed = _parse_raw_text_regex("1. Poytaxt qaysi?\nA) Toshkent\nB) Samarqand\n", "uzbek")
    q = parsed["questions"][0]
    assert q["_has_explicit_answer"] is False  # the parser's placeholder is not an answer

    with pytest.raises(ConverterError):
        _parse_raw_text_regex("", "uzbek")
    with patch("apps.tests.ai_converter._call_gemini_vision", return_value=""), \
         patch("apps.tests.ai_converter._call_openrouter_vision", return_value=""):
        with pytest.raises(ConverterError):
            convert_document_to_test_data(b"x", "scan.png", "image/png", "english")


@pytest.mark.django_db
def test_converter_refuses_to_save_questions_without_an_answer_or_choices():
    teacher = User.objects.create_user(email="hg_conv@example.test", password="x-Pass-123!", role="teacher")
    base = {"test_title": "T", "subject": "uzbek"}
    cases = [
        [{"text": "Q?", "choices": [{"code": "A", "text": "a"}, {"code": "B", "text": "b"}], "correct_answer": ""}],
        [{"text": "Q?", "choices": [{"code": "A", "text": "a"}], "correct_answer": "A"}],
        [{"text": "", "choices": [{"code": "A", "text": "a"}, {"code": "B", "text": "b"}], "correct_answer": "A"}],
        [{"text": "Q?", "choices": [{"code": "A", "text": "a"}, {"code": "B", "text": "b"}], "correct_answer": "D"}],
    ]
    from apps.tests.ai_converter import save_converted_test
    from apps.tests.models import Test

    for questions in cases:
        with pytest.raises(ValueError):
            save_converted_test(teacher, {**base, "questions": questions})
    assert Test.objects.count() == 0
    ok = save_converted_test(
        teacher,
        {**base, "questions": [{"text": "Q?", "choices": [{"code": "A", "text": "a"}, {"code": "B", "text": "b"}], "correct_answer": "B"}]},
    )
    assert ok["success"] and Test.objects.count() == 1


def test_tutor_without_ai_gives_only_the_answer_key_and_is_not_cached(db):
    from apps.courses.models import Course
    from apps.tests.ai_tutor import explain_question_mistake
    from apps.tests.models import Choice, Question, Test

    teacher = User.objects.create_user(email="hg_tutor_t@example.test", password="x-Pass-123!", role="teacher")
    course = Course.objects.create(teacher=teacher, title="C", slug="hg-c")
    test = Test.objects.create(title="T", course=course, status=Test.Status.PUBLISHED, is_active=True)
    q = Question.objects.create(test=test, text="Poytaxt qaysi?", position=1, points=1)
    right = Choice.objects.create(question=q, text="Toshkent", is_correct=True, position=1)
    wrong = Choice.objects.create(question=q, text="Samarqand", is_correct=False, position=2)
    with patch("apps.essays.services._is_mock_mode", return_value=False),          patch("apps.essays.services._get_llm_client", side_effect=RuntimeError("provider down")):
        out = explain_question_mistake(q.id, wrong.id)
    assert out["source"] == "answer_key" and out["ai_unavailable"] is True
    assert "Toshkent" in out["correct_rule"]
    assert out["why_wrong"] == "" and out["memory_tip"] == ""  # no reason for the mistake is made up
    assert cache.get(f"ai_explain_q{q.id}_c{wrong.id}") is None  # not cached: the next request can still get a real answer
    assert right.pk
