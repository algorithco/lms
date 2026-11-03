"""CEFR Multi-level (BMB) estimated scoring.

The official exam scores every section on a 0–75 scale with a Rasch model we
cannot reproduce, so this is an *estimate*:

- Listening / Reading: raw correct answers (0–35) → 0–75 through the
  piecewise-linear anchor table in ``scales/cefr_multilevel.json``.
- Writing / Speaking: the AI/teacher grade (earned / maximum) scaled to 0–75.
- Overall level = mean of the four section scores; it is only reported when
  every required section has a score.

The scale lives in JSON (not code) so it can be swapped for the official
table without touching this module. IELTS bands are deliberately absent:
IELTS is a separate exam type with its own 40-question tables.
"""

from __future__ import annotations

import json
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

SCALE_PATH = Path(__file__).resolve().parent / "scales" / "cefr_multilevel.json"

SCORED = "scored"
PENDING = "pending"  # submitted, waiting for writing/speaking grading
MISSING = "missing"  # section absent from the test or left completely blank

# Sections scored from right/wrong answers; the rest are rated (W/S).
OBJECTIVE_SECTIONS = ("LISTENING", "READING")


@lru_cache(maxsize=1)
def load_scale() -> dict[str, Any]:
    with SCALE_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def _round1(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def raw_to_scaled(raw: int | float | Decimal, questions: int | None = None) -> Decimal:
    """Raw L/R correct count → 0–75 by linear interpolation between anchors.

    A section with a non-standard question count is first normalised to the
    configured count (35) so the anchor table still applies.
    """
    scale = load_scale()
    anchors = [(Decimal(str(r)), Decimal(str(s))) for r, s in scale["raw_to_scaled"]]
    top_raw = anchors[-1][0]
    value = Decimal(str(raw))
    if questions and Decimal(questions) != top_raw:
        value = value * top_raw / Decimal(questions)
    value = max(anchors[0][0], min(top_raw, value))
    for (r0, s0), (r1, s1) in zip(anchors, anchors[1:]):
        if value <= r1:
            return _round1(s0 + (value - r0) * (s1 - s0) / (r1 - r0))
    return _round1(anchors[-1][1])


def rated_to_scaled(earned: Decimal | float, maximum: Decimal | float) -> Decimal:
    """Writing/Speaking grade (earned of maximum) → 0–75."""
    maximum = Decimal(str(maximum))
    if maximum <= 0:
        return Decimal("0")
    ratio = min(Decimal("1"), max(Decimal("0"), Decimal(str(earned)) / maximum))
    return _round1(ratio * Decimal(str(load_scale()["scale_max"])))


def level_for(score: Decimal | float) -> str:
    """0–75 score → C1 / B2 / B1 / BELOW_B1 (thresholds from the scale file)."""
    scale = load_scale()
    value = Decimal(str(score))
    for band in sorted(scale["levels"], key=lambda b: b["min"], reverse=True):
        if value >= Decimal(str(band["min"])):
            return band["level"]
    return scale["below_level"]


def pass_rule() -> dict[str, Any]:
    """Lowest certificate level and its threshold, for "B1: ≥ 38/75" labels."""
    scale = load_scale()
    lowest = min(
        (b for b in scale["levels"] if b["level"] in scale["certificate_levels"]),
        key=lambda b: b["min"],
    )
    return {"scale_max": scale["scale_max"], "level": lowest["level"], "min": lowest["min"]}


def score_sections(
    question_scores: Iterable[Any], section_names: dict[str, str] | None = None
) -> dict[str, dict[str, Any]]:
    """Per-section estimate from per-question scores.

    ``question_scores`` are ``apps.tests.scoring.QuestionScore``-like objects
    (section_code, is_correct, answered, earned, maximum). The returned map
    keeps the ``{code: {name, earned, maximum}}`` shape that
    ``TestAttempt.section_scores`` readers (PDF vedomost) already expect,
    plus ``status`` / ``score`` / ``level``. Sections not in the test are
    omitted; a section left completely blank is ``missing``.
    """
    scale = load_scale()
    section_names = section_names or {}
    by_code: dict[str, list[Any]] = {}
    for q in question_scores:
        by_code.setdefault((q.section_code or "").upper(), []).append(q)

    result: dict[str, dict[str, Any]] = {}
    for code, cfg in scale["sections"].items():
        items = by_code.get(code)
        if not items:
            continue
        entry: dict[str, Any] = {
            "name": section_names.get(code) or code.capitalize(),
            "status": MISSING,
            "score": None,
            "level": None,
        }
        if cfg["kind"] == "objective":
            raw = sum(1 for q in items if q.is_correct is True)
            entry.update(earned=raw, maximum=len(items))
            if any(q.answered for q in items):
                entry.update(status=SCORED, score=raw_to_scaled(raw, len(items)))
        else:
            earned = sum((Decimal(str(q.earned)) for q in items), Decimal("0"))
            maximum = sum((Decimal(str(q.maximum)) for q in items), Decimal("0"))
            entry.update(earned=earned, maximum=maximum)
            if any(q.answered and q.is_correct is None for q in items):
                entry["status"] = PENDING
            elif any(q.answered for q in items):
                entry.update(status=SCORED, score=rated_to_scaled(earned, maximum))
        if entry["score"] is not None:
            entry["level"] = level_for(entry["score"])
        result[code] = entry
    return result


def summarize(section_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Overall estimate from a ``score_sections`` map (fresh or stored JSON)."""
    scale = load_scale()
    sections = []
    for code in scale["sections"]:
        entry = dict(section_map.get(code) or {"name": code.capitalize(), "status": MISSING})
        entry["code"] = code
        entry.setdefault("score", None)
        entry.setdefault("level", None)
        sections.append(entry)

    scored = {
        s["code"]: Decimal(str(s["score"]))
        for s in sections
        if s.get("status") == SCORED and s.get("score") is not None
    }
    required = scale["required_sections"]
    missing = [c for c in required if c not in scored]
    overall = None
    if not missing:
        mean = _round1(sum(scored[c] for c in required) / len(required))
        overall = {"score": mean, "level": level_for(mean)}

    return {
        "scale": "cefr_multilevel",
        "scale_max": scale["scale_max"],
        "is_estimate": True,
        "sections": sections,
        "overall": overall,
        "missing_sections": missing,
        "has_certificate": bool(overall and overall["level"] in scale["certificate_levels"]),
    }


def compute(question_scores: Iterable[Any], section_names: dict[str, str] | None = None) -> dict[str, Any]:
    return summarize(score_sections(question_scores, section_names))


def to_json(result: dict[str, Any]) -> dict[str, Any]:
    """Decimal → float copy, safe for JSONField storage and API responses."""

    def conv(v: Any) -> Any:
        if isinstance(v, Decimal):
            return float(v)
        if isinstance(v, dict):
            return {k: conv(x) for k, x in v.items()}
        if isinstance(v, list):
            return [conv(x) for x in v]
        return v

    return conv(result)
