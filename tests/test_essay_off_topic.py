"""
Tests for strict Topic Relevance & Prompt Adherence (Mavzuga moslik) evaluation rules.

Covers:
1. Completely Off-topic (0 points, all criteria 0, required warning).
2. Partially Off-topic (Criterion 1 <= 1.0 / Band 3.0, total capped between 2 and 35 points).
3. Hard guardrails preventing LLM hallucinated scores from bypassing topic penalties.
4. Scaled score conversion in EssaySubmission.converted_score.
5. IELTS / Multi-level 4-criteria off-topic penalties.
6. Mock mode offline simulation.
"""

from decimal import Decimal
import pytest

from apps.essays.models import EssayCriterionScore, EssaySubmission
from apps.essays.services import (
    _mock_12_criteria_response,
    _mock_ielts_response,
    _validate_ielts_result,
    _validate_result,
)


@pytest.fixture
def base_bmb_criteria():
    """Return a baseline 12-criteria list (sum = 20.0)."""
    return [
        {
            "id": 1,
            "name": EssayCriterionScore.CRITERION_NAMES[1],
            "score": 2.0,
            "reason": "Zo'r",
            "errors": [],
        },
        {
            "id": 2,
            "name": EssayCriterionScore.CRITERION_NAMES[2],
            "score": 2.0,
            "reason": "Zo'r",
            "errors": [],
        },
        {
            "id": 3,
            "name": EssayCriterionScore.CRITERION_NAMES[3],
            "score": 2.0,
            "reason": "Zo'r",
            "errors": [],
        },
        {
            "id": 4,
            "name": EssayCriterionScore.CRITERION_NAMES[4],
            "score": 1.5,
            "reason": "Zo'r",
            "errors": [],
        },
        {
            "id": 5,
            "name": EssayCriterionScore.CRITERION_NAMES[5],
            "score": 1.5,
            "reason": "Zo'r",
            "errors": [],
        },
        {
            "id": 6,
            "name": EssayCriterionScore.CRITERION_NAMES[6],
            "score": 1.5,
            "reason": "Zo'r",
            "errors": [],
        },
        {
            "id": 7,
            "name": EssayCriterionScore.CRITERION_NAMES[7],
            "score": 2.0,
            "reason": "Zo'r",
            "errors": [],
        },
        {
            "id": 8,
            "name": EssayCriterionScore.CRITERION_NAMES[8],
            "score": 1.5,
            "reason": "Zo'r",
            "errors": [],
        },
        {
            "id": 9,
            "name": EssayCriterionScore.CRITERION_NAMES[9],
            "score": 1.5,
            "reason": "Zo'r",
            "errors": [],
        },
        {
            "id": 10,
            "name": EssayCriterionScore.CRITERION_NAMES[10],
            "score": 1.5,
            "reason": "Zo'r",
            "errors": [],
        },
        {
            "id": 11,
            "name": EssayCriterionScore.CRITERION_NAMES[11],
            "score": 1.5,
            "reason": "Zo'r",
            "errors": [],
        },
        {
            "id": 12,
            "name": EssayCriterionScore.CRITERION_NAMES[12],
            "score": 1.5,
            "reason": "Zo'r",
            "errors": [],
        },
    ]


@pytest.fixture
def base_ielts_criteria():
    """Return a baseline 4-criteria IELTS list with Band 7.5 scores."""
    return [
        {
            "id": 1,
            "name": EssayCriterionScore.IELTS_CRITERION_NAMES[1],
            "score": 7.5,
            "reason": "Well developed response",
            "errors": [],
        },
        {
            "id": 2,
            "name": EssayCriterionScore.IELTS_CRITERION_NAMES[2],
            "score": 7.5,
            "reason": "Clear progression",
            "errors": [],
        },
        {
            "id": 3,
            "name": EssayCriterionScore.IELTS_CRITERION_NAMES[3],
            "score": 7.5,
            "reason": "Rich vocabulary",
            "errors": [],
        },
        {
            "id": 4,
            "name": EssayCriterionScore.IELTS_CRITERION_NAMES[4],
            "score": 7.5,
            "reason": "Accurate grammar",
            "errors": [],
        },
    ]


# ---------------------------------------------------------------------------
# BMB Uzbek 12-Mezon Tests
# ---------------------------------------------------------------------------


def test_bmb_completely_off_topic_gives_zero(base_bmb_criteria):
    """A completely off-topic Uzbek essay must strictly receive 0 points."""
    raw_result = {
        "criteria": base_bmb_criteria,
        "total_score": 20.0,
        "max_score": 20,
        "summary": "Ona tili haqida fikr bildirilmagan.",
        "topic_status": "completely_off_topic",
        "is_completely_off_topic": True,
        "topic_match": False,
        "topic_match_reason": "Berilgan mavzu o'rniga sport haqida yozilgan.",
    }

    _validate_result(
        raw_result, essay_text="Futbolda 11 nafar o'yinchi to'p suradi. " * 30
    )

    assert raw_result["total_score"] == 0.0
    assert raw_result["is_completely_off_topic"] is True
    assert raw_result["is_off_topic"] is True
    assert raw_result["topic_match"] is False
    assert raw_result["topic_status"] == "completely_off_topic"

    for crit in raw_result["criteria"]:
        assert crit["score"] == 0.0

    assert "⛔ DIQQAT" in raw_result["summary"]
    assert "0 ball qo'yildi" in raw_result["summary"]


def test_bmb_partially_off_topic_caps_criterion_1_and_total(base_bmb_criteria):
    """A partially off-topic Uzbek essay must cap Criterion 1 <= 1.0 and total <= 7.0 (2-35 converted range)."""
    raw_result = {
        "criteria": base_bmb_criteria,
        "total_score": 20.0,
        "max_score": 20,
        "summary": "Mavzu qisman ochilgan, ammo asosiy savoldan chetga chiqilgan.",
        "topic_status": "partially_off_topic",
        "is_completely_off_topic": False,
        "topic_match": False,
        "topic_match_reason": "Mavzudan chetlanish mavjud.",
    }

    _validate_result(raw_result, essay_text="Mavzu bo'yicha qisman fikr. " * 30)

    assert raw_result["is_completely_off_topic"] is False
    assert raw_result["is_off_topic"] is True
    assert raw_result["topic_match"] is False
    assert raw_result["topic_status"] == "partially_off_topic"

    # Criterion 1 must not exceed 1.0
    crit1 = next(c for c in raw_result["criteria"] if c["id"] == 1)
    assert crit1["score"] <= 1.0

    # Total score must be capped at 7.0 (35% of 20.0)
    assert 2.0 <= raw_result["total_score"] <= 7.0
    assert "⚠️ OGOHLANTIRISH" in raw_result["summary"]
    assert "2 – 35 ball oralig'iga keskin tushirildi" in raw_result["summary"]


def test_bmb_on_topic_retains_normal_scoring(base_bmb_criteria):
    """An on-topic essay should retain its legitimate high scores without penalty."""
    raw_result = {
        "criteria": base_bmb_criteria,
        "total_score": 20.0,
        "max_score": 20,
        "summary": "Mavzu mukammal ochilgan.",
        "topic_status": "on_topic",
        "is_completely_off_topic": False,
        "topic_match": True,
        "topic_match_reason": "Mavzuga to'liq mos.",
    }

    _validate_result(
        raw_result, essay_text="Ona tilimizning buyuk merosi va tarovati. " * 30
    )

    assert raw_result["total_score"] == 20.0
    assert raw_result["is_completely_off_topic"] is False
    assert raw_result["is_off_topic"] is False
    assert raw_result["topic_match"] is True
    assert raw_result["topic_status"] == "on_topic"
    assert "⛔ DIQQAT" not in raw_result["summary"]
    assert "⚠️ OGOHLANTIRISH" not in raw_result["summary"]


# ---------------------------------------------------------------------------
# IELTS English 4-Criteria Tests
# ---------------------------------------------------------------------------


def test_ielts_completely_off_topic_gives_zero(base_ielts_criteria):
    """A completely off-topic IELTS essay must receive Band 0.0 across all criteria."""
    raw_result = {
        "criteria": base_ielts_criteria,
        "overall_band": 7.5,
        "summary": "Candidate wrote about cooking instead of environmental policy.",
        "topic_status": "completely_off_topic",
        "is_completely_off_topic": True,
        "topic_match": False,
        "topic_match_reason": "Completely off-topic response.",
    }

    result = _validate_ielts_result(
        raw_result, essay_text="Cooking delicious pasta requires flour. " * 40
    )

    assert result["overall_band"] == 0.0
    assert result["total_score"] == 0.0
    assert result["cefr_level"] == "Ungraded"
    assert result["is_completely_off_topic"] is True
    assert result["is_off_topic"] is True
    assert result["topic_match"] is False
    assert result["topic_status"] == "completely_off_topic"

    for crit in result["criteria"]:
        assert crit["score"] == 0.0

    assert "⛔ DIQQAT" in result["summary"]


def test_ielts_partially_off_topic_capped(base_ielts_criteria):
    """A partially off-topic IELTS essay must cap Task Response <= 3.0 and overall band <= 3.5."""
    raw_result = {
        "criteria": base_ielts_criteria,
        "overall_band": 7.5,
        "summary": "Candidate wrote a well-structured essay but deviated significantly from the prompt.",
        "topic_status": "partially_off_topic",
        "is_completely_off_topic": False,
        "topic_match": False,
        "topic_match_reason": "Partially addresses the topic with tangential arguments.",
    }

    result = _validate_ielts_result(
        raw_result,
        essay_text="While global warming is an issue, video games are fun. " * 30,
    )

    crit1 = next(c for c in result["criteria"] if c["id"] == 1)
    assert crit1["score"] <= 3.0
    assert result["overall_band"] <= 3.5
    assert result["is_completely_off_topic"] is False
    assert result["is_off_topic"] is True
    assert result["topic_match"] is False
    assert result["topic_status"] == "partially_off_topic"
    assert "⚠️ OGOHLANTIRISH" in result["summary"]


# ---------------------------------------------------------------------------
# EssaySubmission Converted Score Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_submission_converted_score_penalties():
    """Verify that EssaySubmission.converted_score adheres to strict off-topic range caps."""
    # 1. Completely off-topic -> 0
    sub_complete = EssaySubmission(
        total_score=Decimal("0.0"),
        max_score=20,
        is_completely_off_topic=True,
        is_off_topic=True,
        topic_status=EssaySubmission.TopicStatus.COMPLETELY_OFF_TOPIC,
    )
    assert sub_complete.converted_score == 0

    # 2. Partially off-topic with 6.0/20 raw score -> capped in [2, 35]
    # On 75 scale: 6.0 / 20 * 75 = 22.5 -> 22 or 23 points (within [2, 35])
    sub_partial = EssaySubmission(
        total_score=Decimal("6.0"),
        max_score=20,
        is_completely_off_topic=False,
        is_off_topic=True,
        topic_status=EssaySubmission.TopicStatus.PARTIALLY_OFF_TOPIC,
    )
    assert 2 <= sub_partial.converted_score <= 35

    # 3. Partially off-topic with higher score (e.g., 10.0/20 -> 37.5) -> must be strictly capped at 35
    sub_partial_high = EssaySubmission(
        total_score=Decimal("10.0"),
        max_score=20,
        is_completely_off_topic=False,
        is_off_topic=True,
        topic_status=EssaySubmission.TopicStatus.PARTIALLY_OFF_TOPIC,
    )
    assert sub_partial_high.converted_score == 35

    # 4. On-topic with 16.0/20 raw score -> 16 / 20 * 75 = 60 points
    sub_normal = EssaySubmission(
        total_score=Decimal("16.0"),
        max_score=20,
        is_completely_off_topic=False,
        is_off_topic=False,
        topic_status=EssaySubmission.TopicStatus.ON_TOPIC,
    )
    assert sub_normal.converted_score == 60


# ---------------------------------------------------------------------------
# Mock Mode Tests
# ---------------------------------------------------------------------------


def test_mock_mode_off_topic_simulation():
    """Verify mock grading handles completely and partially off-topic cues."""
    # Completely off-topic BMB mock
    res_bmb_zero = _mock_12_criteria_response(
        "Bu matn butunlay boshqa mavzu haqida yozilgan esse.", topic_title="Tabiat"
    )
    assert res_bmb_zero["total_score"] == 0.0
    assert res_bmb_zero["is_completely_off_topic"] is True
    assert "⛔ DIQQAT" in res_bmb_zero["summary"]

    # Partially off-topic BMB mock
    res_bmb_partial = _mock_12_criteria_response(
        "Bu matnda qisman chetlashish mavjud bo'lgan esse matni.", topic_title="Tabiat"
    )
    assert 2.0 <= res_bmb_partial["total_score"] <= 7.0
    assert res_bmb_partial["criteria"][0]["score"] <= 1.0
    assert "⚠️ OGOHLANTIRISH" in res_bmb_partial["summary"]

    # Completely off-topic IELTS mock
    res_ielts_zero = _mock_ielts_response(
        "This essay is completely off-topic response.", topic_title="Climate Change"
    )
    assert res_ielts_zero["overall_band"] == 0.0
    assert res_ielts_zero["is_completely_off_topic"] is True

    # Partially off-topic IELTS mock
    res_ielts_partial = _mock_ielts_response(
        "This response is partially off-topic with tangential arguments.",
        topic_title="Climate Change",
    )
    assert res_ielts_partial["overall_band"] <= 3.5
    assert res_ielts_partial["criteria"][0]["score"] <= 3.0
