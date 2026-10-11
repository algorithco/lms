"""Canonical exam scoring service — the ONE place totals are computed.

All grading paths (submit, finalize, result APIs, certificates) must consume
these helpers so section/aggregate totals can never diverge between files.

Conventions (safe and predictable):
- GAP_FILL: full points only when EVERY blank is correct, unless the
  question config sets partial_credit=true (then proportional per blank).
- MATCHING: full points only when EVERY prompt maps correctly, unless
  partial_credit=true (then proportional per prompt).
- Text comparison: whitespace-normalized, case-insensitive (follows the
  legacy TEXT behavior) unless config sets case_sensitive=true.
- WRITTEN is never objective: earned points come only from the canonical
  essay submission linked via ExamWrittenBridge, scaled to the question's
  points. Ungraded writing is pending, never zero.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


def normalize_text(value: Any, *, case_sensitive: bool = False) -> str:
    """Whitespace-normalized comparison form (TEXT parity by default)."""
    text = str(value or "").strip()
    text = " ".join(text.split())
    if not case_sensitive:
        text = text.lower()
    return text


def blank_is_correct(response_text: Any, accepted: list[str], *, case_sensitive: bool = False) -> bool:
    """True when the response matches ANY accepted answer for the blank."""
    given = normalize_text(response_text, case_sensitive=case_sensitive)
    if not given:
        return False
    return any(given == normalize_text(a, case_sensitive=case_sensitive) for a in accepted)


@dataclass(frozen=True)
class GapScore:
    earned: Decimal
    maximum: Decimal
    blanks_correct: int
    blanks_total: int
    fully_correct: bool


def grade_gap_fill(
    blanks_by_position: dict[int, list[str]],
    responses: dict[int, str],
    points: int,
    *,
    partial_credit: bool = False,
    case_sensitive: bool = False,
) -> GapScore:
    """Deterministic gap-fill scoring over relational blanks (no JSON blobs)."""
    total = len(blanks_by_position)
    maximum = Decimal(str(points))
    if total == 0:
        return GapScore(Decimal("0"), maximum, 0, 0, False)
    correct = sum(
        1
        for pos, accepted in blanks_by_position.items()
        if blank_is_correct(responses.get(pos, ""), accepted, case_sensitive=case_sensitive)
    )
    fully = correct == total
    if fully:
        earned = maximum
    elif partial_credit and correct:
        earned = (maximum * correct / total).quantize(Decimal("0.01"))
    else:
        earned = Decimal("0")
    return GapScore(earned, maximum, correct, total, fully)


@dataclass(frozen=True)
class MatchingScore:
    earned: Decimal
    maximum: Decimal
    pairs_correct: int
    pairs_total: int
    fully_correct: bool


def grade_matching(
    correct_map: dict[int, int],
    responses: dict[int, int | None],
    points: int,
    *,
    partial_credit: bool = False,
) -> MatchingScore:
    """Deterministic matching scoring. Shuffled display never affects grading:
    comparison is by stable prompt/option ids, never by display order."""
    total = len(correct_map)
    maximum = Decimal(str(points))
    if total == 0:
        return MatchingScore(Decimal("0"), maximum, 0, 0, False)
    correct = sum(
        1
        for prompt_id, option_id in correct_map.items()
        if responses.get(prompt_id) is not None and responses.get(prompt_id) == option_id
    )
    fully = correct == total
    if fully:
        earned = maximum
    elif partial_credit and correct:
        earned = (maximum * correct / total).quantize(Decimal("0.01"))
    else:
        earned = Decimal("0")
    return MatchingScore(earned, maximum, correct, total, fully)


def written_earned(
    points: int,
    effective_score: Decimal | float | None,
    rubric_max: int | float = 24,
) -> Decimal | None:
    """Scale a graded essay effective score onto the question's points.

    Raw rubric score and exam points stay separate concepts: this is the
    single deterministic conversion (linear scale, clamped to [0, points]).
    Returns None when the writing is not graded yet (pending — never zero).
    """
    if effective_score is None:
        return None
    try:
        ratio = Decimal(str(effective_score)) / Decimal(str(rubric_max))
    except Exception:
        return None
    if ratio < 0:
        ratio = Decimal("0")
    if ratio > 1:
        ratio = Decimal("1")
    return (Decimal(str(points)) * ratio).quantize(Decimal("0.01"))


@dataclass
class QuestionScore:
    question_id: int
    earned: Decimal = Decimal("0")
    maximum: Decimal = Decimal("0")
    is_correct: bool | None = None  # None = pending (written) or unanswered
    answered: bool = True
    section_code: str = ""
    section_id: int | None = None
    kind: str = "objective"  # objective | written


@dataclass
class SectionTotal:
    section_id: int | None
    section_code: str
    section_name: str
    earned: Decimal = Decimal("0")
    maximum: Decimal = Decimal("0")
    weight: Decimal = Decimal("1")


@dataclass
class AggregateScore:
    questions: list[QuestionScore] = field(default_factory=list)
    sections: list[SectionTotal] = field(default_factory=list)
    objective_earned: Decimal = Decimal("0")
    objective_max: Decimal = Decimal("0")
    writing_earned: Decimal = Decimal("0")
    writing_max: Decimal = Decimal("0")
    total_earned: Decimal = Decimal("0")
    total_max: Decimal = Decimal("0")
    weighted_percentage: Decimal = Decimal("0")
    has_pending_writing: bool = False

    @property
    def correct_count(self) -> int:
        return sum(1 for q in self.questions if q.is_correct is True)

    @property
    def wrong_count(self) -> int:
        return sum(1 for q in self.questions if q.answered and q.is_correct is False)

    @property
    def unanswered_count(self) -> int:
        return sum(1 for q in self.questions if not q.answered)


def aggregate(
    question_scores: list[QuestionScore],
    weights: dict[str, float] | None = None,
) -> AggregateScore:
    """Build section subtotals + aggregate from per-question scores.

    Weights are configuration data (profile.weights); missing codes weigh 1.
    Weighted percentage = Σ(earned×w) / Σ(max×w) × 100. Empty exam → 0.
    """
    weights = weights or {}
    agg = AggregateScore(questions=list(question_scores))
    by_section: dict[tuple[int | None, str], SectionTotal] = {}
    for q in question_scores:
        key = (q.section_id, q.section_code)
        sec = by_section.get(key)
        if sec is None:
            sec = by_section[key] = SectionTotal(
                section_id=q.section_id,
                section_code=q.section_code,
                section_name=q.section_code or "Umumiy",
            )
        sec.maximum += q.maximum
        if q.kind == "written":
            agg.writing_max += q.maximum
            if q.is_correct is not None:
                agg.writing_earned += q.earned
                sec.earned += q.earned
            else:
                agg.has_pending_writing = True
        else:
            agg.objective_max += q.maximum
            agg.objective_earned += q.earned
            sec.earned += q.earned
    agg.sections = list(by_section.values())
    agg.total_earned = agg.objective_earned + agg.writing_earned
    agg.total_max = agg.objective_max + agg.writing_max
    weighted_earned = Decimal("0")
    weighted_max = Decimal("0")
    for sec in agg.sections:
        try:
            w = Decimal(str(weights.get(sec.section_code, 1)))
        except Exception:
            w = Decimal("1")
        sec.weight = w
        weighted_earned += sec.earned * w
        weighted_max += sec.maximum * w
    if weighted_max > 0:
        agg.weighted_percentage = (weighted_earned / weighted_max * 100).quantize(Decimal("0.01"))
    return agg
