"""
BMB 12-criterion rubric regression tests (offline, no LLM calls).

Official BMB 12-criterion rubric with total 20.0 max score:
  - Criteria 1, 2, 3, 7: max 2.0 points
  - Criteria 4, 5, 6, 8, 9, 10, 11, 12: max 1.5 points
  - Total: 2.0*4 + 1.5*8 = 20.0 points
"""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.essays.models import EssayCriterionScore
from apps.essays.prompts import (
    ESSAY_GRADING_SYSTEM_PROMPT,
    ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE,
)
from apps.essays.services import _validate_result, ESSAY_RUBRIC_MAX_SCORE


def _valid_payload(scores: list[float] | None = None) -> dict:
    if scores is None:
        # Valid maximum scores per criterion (total 20.0)
        scores = [2.0, 2.0, 2.0, 1.5, 1.5, 1.5, 2.0, 1.5, 1.5, 1.5, 1.5, 1.5]
    return {
        "criteria": [
            {"id": i + 1, "name": f"Mezon {i + 1}", "score": s, "reason": "izoh"}
            for i, s in enumerate(scores)
        ],
        "total_score": 0,
        "max_score": 20,
        "summary": "Xulosa.",
    }


# Representative valid distribution (16.5 / 20.0)
BMB_SAMPLE_SCORES = [2.0, 1.5, 2.0, 1.0, 1.5, 1.0, 2.0, 1.0, 1.5, 1.0, 1.0, 1.0]


class BbaPromptGrammarTests(SimpleTestCase):
    """Grammar / affix criterion must mean suffix/affix errors — never sources/citations."""

    def test_full_prompt_defines_affix_errors(self):
        p = ESSAY_GRADING_SYSTEM_PROMPT
        self.assertIn("6 GRAMMATIK QOIDALARGA RIOYA ETILGANI", p)
        self.assertIn("suffiks/affiks", p.lower())
        self.assertIn("kelishik", p.lower())

    def test_full_prompt_forbids_source_reading(self):
        p = ESSAY_GRADING_SYSTEM_PROMPT
        self.assertIn("MANBA", p)
        self.assertIn("TAQIQLANADI", p)

    def test_simple_prompt_keeps_grammar_guard(self):
        p = ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE
        self.assertIn("6-mezon", p)
        self.assertIn("suffiks/affiks", p.lower())
        self.assertIn("TAQIQLANADI", p)


class BbaPromptVocabularyTests(SimpleTestCase):
    """Vocabulary criterion must reward precise and rich vocabulary."""

    def test_full_prompt_has_vocabulary_criterion(self):
        p = ESSAY_GRADING_SYSTEM_PROMPT
        self.assertIn("5 SO'Z QO'LLASH ANIQLIGI VA BOY LUG'AT ZAXIRASI", p)

    def test_simple_prompt_has_vocabulary_criterion(self):
        p = ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE
        self.assertIn("5 So'z qo'llash va lug'at boyligi", p)


class BbaPromptStructureTests(SimpleTestCase):
    """All 12 criteria with 20.0 max points + total=sum rule."""

    def test_all_twelve_criteria_present(self):
        for p in (ESSAY_GRADING_SYSTEM_PROMPT, ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE):
            for cid in range(1, 13):
                self.assertIn(str(cid), p)

    def test_total_is_sum_rule_present(self):
        self.assertIn("yig'indisi", ESSAY_GRADING_SYSTEM_PROMPT)
        self.assertIn("yig'indi", ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE)

    def test_max_score_20_in_prompts(self):
        for p in (ESSAY_GRADING_SYSTEM_PROMPT, ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE):
            self.assertIn("20", p)

    def test_errors_array_in_json_format(self):
        for p in (ESSAY_GRADING_SYSTEM_PROMPT, ESSAY_GRADING_SYSTEM_PROMPT_SIMPLE):
            self.assertIn('"errors":[]', p)


class BbaValidationTests(SimpleTestCase):
    """Validation normalizes evidence + forces 20 max score and individual criterion maxes."""

    def test_sample_distribution_sums_correctly(self):
        payload = _valid_payload(BMB_SAMPLE_SCORES)
        _validate_result(payload)
        expected_sum = float(sum(BMB_SAMPLE_SCORES))
        self.assertEqual(payload["total_score"], expected_sum)
        self.assertEqual(payload["max_score"], 20)
        # Check individual max_scores
        for c in payload["criteria"]:
            crit_max = float(EssayCriterionScore.CRITERION_MAX_SCORES[c["id"]])
            self.assertEqual(c["max_score"], crit_max)

    def test_errors_evidence_preserved_and_capped(self):
        payload = _valid_payload()
        payload["criteria"][6]["errors"] = ["  imlo xatosi  ", 123, "", "x" * 500]
        _validate_result(payload)
        errors = payload["criteria"][6]["errors"]
        self.assertEqual(errors[0], "imlo xatosi")
        self.assertIn("123", errors)
        self.assertTrue(all(len(e) <= 200 for e in errors))

    def test_errors_capped_at_six(self):
        payload = _valid_payload()
        payload["criteria"][0]["errors"] = [f"xato {i}" for i in range(20)]
        _validate_result(payload)
        self.assertEqual(len(payload["criteria"][0]["errors"]), 6)

    def test_non_list_errors_normalized(self):
        payload = _valid_payload()
        payload["criteria"][0]["errors"] = "not-a-list"
        _validate_result(payload)
        self.assertEqual(payload["criteria"][0]["errors"], [])

    def test_spelling_errors_and_recommendations_normalized(self):
        payload = _valid_payload()
        payload["spelling_errors"] = [
            {"word": "muxrdor", "correction": "muhrdor", "explanation": "H va X farqi"}
        ]
        payload["strengths"] = ["Kuchli tezis"]
        payload["weaknesses"] = ["Lug'at oddiy"]
        payload["teacher_recommendation"] = "Ko'proq o'qing"
        payload["improved_text"] = "Tahrirlangan matn"
        _validate_result(payload)
        self.assertEqual(len(payload["spelling_errors"]), 1)
        self.assertEqual(payload["spelling_errors"][0]["word"], "muxrdor")
        self.assertEqual(payload["strengths"], ["Kuchli tezis"])
        self.assertEqual(payload["improved_text"], "Tahrirlangan matn")

    def test_criterion_score_cannot_exceed_its_max(self):
        # Criterion 4 has max 1.5, trying 2.0 must raise ValueError
        payload = _valid_payload()
        payload["criteria"][3]["score"] = 2.0  # id 4 max is 1.5
        with self.assertRaises(ValueError):
            _validate_result(payload)

    def test_verbose_model_label_uses_database_safe_rubric_name(self):
        payload = _valid_payload()
        payload["criteria"][0]["name"] = "Uslub va boshqa izohlar " * 10

        _validate_result(payload)

        for criterion in payload["criteria"]:
            self.assertEqual(
                criterion["name"],
                EssayCriterionScore.CRITERION_NAMES[criterion["id"]],
            )
            self.assertLessEqual(len(criterion["name"]), 100)
