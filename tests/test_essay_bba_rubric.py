"""
BBA 12-criterion rubric regression tests (offline, no LLM calls).

Guards the reported mis-scoring of the insurance essay (19.5/24 instead of
~22/24), whose biggest errors were:
  - Criterion 9 ("Qo'shimcha qo'llash") scored 0.5 because the grader read it
    as "did the student cite additional sources" instead of Uzbek
    suffix/affix usage errors.
  - Criterion 11 ("Leksik xilma-xillik") capped at 1 despite sufficient
    lexical variety.

The actual insurance essay text was not attached to the task, so these tests
guard the rubric *interpretation* (prompt wording + validation pipeline)
rather than a single golden score: any future prompt edit that reintroduces
the "sources" reading of criterion 9 or drops the criterion-11 full-2 rule
fails here before reaching production.
"""
from __future__ import annotations

from django.test import SimpleTestCase

from apps.essays.prompts import (
    ESSAY_GRADING_SYSTEM_PROMPT,
    ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE,
)
from apps.essays.services import _validate_result


def _valid_payload(scores: list[float]) -> dict:
    return {
        "criteria": [
            {"id": i + 1, "name": f"Mezon {i + 1}", "score": s, "reason": "izoh"}
            for i, s in enumerate(scores)
        ],
        "total_score": 0,
        "max_score": 24,
        "summary": "Xulosa.",
    }


# Expected insurance-essay distribution from the task (≈22/24).
INSURANCE_EXPECTED_SCORES = [2, 2, 2, 2, 1.5, 2, 2, 2, 2, 1.5, 2, 2]


class BbaPromptCriterion9Tests(SimpleTestCase):
    """Criterion 9 must mean suffix/affix errors — never sources/citations."""

    def test_full_prompt_defines_affix_errors(self):
        p = ESSAY_GRADING_SYSTEM_PROMPT
        self.assertIn("9 QO'SHIMCHA QO'LLASH", p)
        self.assertIn("suffiks/affiks", p.lower())
        self.assertIn("kelishik", p.lower())

    def test_full_prompt_forbids_source_reading(self):
        p = ESSAY_GRADING_SYSTEM_PROMPT
        self.assertIn("MANBA", p)
        self.assertIn("TAQIQLANADI", p)

    def test_simple_prompt_keeps_criterion9_guard(self):
        # The retry prompt is shorter but must not reintroduce the bug.
        p = ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE
        self.assertIn("9-QO'SHIMCHA", p)
        self.assertIn("suffiks/affiks", p.lower())
        self.assertIn("TAQIQLANADI", p)


class BbaPromptCriterion11Tests(SimpleTestCase):
    """Criterion 11 must allow full 2 points for satisfied requirements."""

    def test_full_prompt_allows_full_two(self):
        p = ESSAY_GRADING_SYSTEM_PROMPT
        self.assertIn("11 LUG'AT BOYLIGI", p)
        self.assertIn("to'liq 2 ball bering", p)
        self.assertIn("sun'iy murakkab", p.lower())

    def test_simple_prompt_keeps_criterion11_guard(self):
        p = ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE
        self.assertIn("11-LUG'AT", p)
        self.assertIn("to'liq 2 ball", p)


class BbaPromptStructureTests(SimpleTestCase):
    """All 12 criteria with 2/1.5/1/0.5/0 ladders + total=sum rule."""

    def test_all_twelve_criteria_present(self):
        for p in (ESSAY_GRADING_SYSTEM_PROMPT, ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE):
            for cid in range(1, 13):
                self.assertIn(str(cid), p)

    def test_error_count_ladders_present(self):
        p = ESSAY_GRADING_SYSTEM_PROMPT
        # Count-based criteria share the 0/1-2/3-4/5-6/7+ ladder.
        self.assertIn("1.5=1-2", p)
        self.assertIn("0=7+", p)

    def test_total_is_sum_rule_present(self):
        self.assertIn("yig'indisi", ESSAY_GRADING_SYSTEM_PROMPT)
        self.assertIn("yig'indi", ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE)

    def test_errors_array_in_json_format(self):
        for p in (ESSAY_GRADING_SYSTEM_PROMPT, ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE):
            self.assertIn('"errors":[]', p)


class BbaValidationTests(SimpleTestCase):
    """Validation normalizes evidence + forces per-criterion max 2."""

    def test_insurance_expected_distribution_sums_to_22(self):
        payload = _valid_payload(INSURANCE_EXPECTED_SCORES)
        _validate_result(payload)
        self.assertEqual(payload["total_score"], 22.0)
        self.assertEqual(payload["max_score"], 24)
        for c in payload["criteria"]:
            self.assertEqual(c["max_score"], 2)
            self.assertEqual(c["errors"], [])

    def test_errors_evidence_preserved_and_capped(self):
        payload = _valid_payload([2] * 12)
        payload["criteria"][8]["errors"] = ["  noto'g'ri qo'shimcha  ", 123, "", "x" * 500]
        _validate_result(payload)
        errors = payload["criteria"][8]["errors"]
        self.assertEqual(errors[0], "noto'g'ri qo'shimcha")
        self.assertIn("123", errors)
        self.assertTrue(all(len(e) <= 200 for e in errors))

    def test_errors_capped_at_six(self):
        payload = _valid_payload([1] * 12)
        payload["criteria"][0]["errors"] = [f"xato {i}" for i in range(20)]
        _validate_result(payload)
        self.assertEqual(len(payload["criteria"][0]["errors"]), 6)

    def test_non_list_errors_normalized(self):
        payload = _valid_payload([1.5] * 12)
        payload["criteria"][0]["errors"] = "not-a-list"
        _validate_result(payload)
        self.assertEqual(payload["criteria"][0]["errors"], [])

    def test_legacy_payload_without_errors_still_valid(self):
        # Old cached results have no "errors" key — must keep validating.
        payload = _valid_payload([1] * 12)
        _validate_result(payload)
        self.assertEqual(payload["total_score"], 12.0)
