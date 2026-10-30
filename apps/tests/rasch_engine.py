"""
apps/tests/services/rasch_engine.py

Continuous 1PL Rasch IRT (Item Response Theory) Scoring Engine.

Calculates:
1. Laplace-smoothed correct probability:
   P_i = (C_i + 0.5) / (N + 1)
   where C_i = correct attempts, N = total attempts.
   Guarantees 0 < P_i < 1 without division by zero.

2. Item Difficulty Logit (beta_i):
   beta_i = ln((1 - P_i) / P_i)
   Positive when hard (few students correct), negative when easy (most students correct).

3. Continuous Dynamic Weight (W_i):
   W_i = clamp(B * exp(k * beta_i), min_weight, max_weight)
   where B = baseline points (default 2.0), k = sensitivity coefficient (default 0.40).
   Hard questions scale up to 3.0 - 10.0 points.
   Easy questions scale down to 0.5 - 1.0 points.

4. Dual Scoring:
   - raw_score: Count of correctly answered questions (e.g. 12 / 15).
   - rasch_score: Sum of W_i for all correctly answered questions.
   - max_rasch_score: Sum of W_i for all questions in the test.
   - rasch_percentage: (rasch_score / max_rasch_score) * 100.
   - rasch_grade: Official BMB grade (A+, A, B+, B, C+, C, Fail).
   - rasch_explanation: Personalized feedback explaining which questions earned high dynamic weights.
"""

from __future__ import annotations

import logging
import math
from decimal import Decimal
from typing import Any, Sequence

from django.db import transaction
from django.db.models import Count, Q

logger = logging.getLogger(__name__)


class RaschEngine:
    """Continuous 1PL Rasch IRT Scoring & Dynamic Calibration Engine."""

    DEFAULT_BASELINE: float = 2.0
    DEFAULT_K: float = 0.40
    MIN_WEIGHT: float = 0.5
    MAX_WEIGHT: float = 10.0

    @classmethod
    def calculate_probability(cls, correct_attempts: int, total_attempts: int) -> float:
        """
        Calculate probability with Laplace smoothing:
        P_i = (C_i + 0.5) / (N + 1)
        """
        c = max(0, int(correct_attempts))
        n = max(0, int(total_attempts))
        # Ensure c <= n for sanity if manual counters diverge
        c = min(c, n) if n > 0 else c
        return (c + 0.5) / (n + 1.0)

    @classmethod
    def calculate_logit(cls, p_i: float) -> float:
        """
        Calculate difficulty logit:
        beta_i = ln((1 - P_i) / P_i)
        """
        # Clamp p_i to prevent numerical extreme bounds
        p = max(1e-6, min(1.0 - 1e-6, float(p_i)))
        odds_ratio = (1.0 - p) / p
        return math.log(odds_ratio)

    @classmethod
    def calculate_dynamic_weight(
        cls,
        beta_i: float,
        baseline: float = DEFAULT_BASELINE,
        k: float = DEFAULT_K,
        min_weight: float = MIN_WEIGHT,
        max_weight: float = MAX_WEIGHT,
    ) -> float:
        """
        Calculate dynamic weight:
        W_i = clamp(B * exp(k * beta_i), min_weight, max_weight)
        """
        b = float(baseline) if baseline > 0 else cls.DEFAULT_BASELINE
        raw_weight = b * math.exp(float(k) * float(beta_i))
        clamped = max(float(min_weight), min(float(max_weight), raw_weight))
        return round(clamped, 2)

    @classmethod
    def grade_from_percentage(cls, percentage: float | Decimal) -> str:
        """
        Map Rasch percentage to official BMB Grade:
        86%+ -> A+
        75%-85.99% -> A
        68%-74.99% -> B+
        60%-67.99% -> B
        53%-59.99% -> C+
        46%-52.99% -> C
        <46% -> Fail
        """
        pct = float(percentage)
        if pct >= 86.0:
            return "A+"
        if pct >= 75.0:
            return "A"
        if pct >= 68.0:
            return "B+"
        if pct >= 60.0:
            return "B"
        if pct >= 53.0:
            return "C+"
        if pct >= 46.0:
            return "C"
        return "Fail"

    @classmethod
    def generate_explanation(
        cls,
        correct_questions_with_weights: list[tuple[int, float, float]],
        total_questions: int,
        student_rasch_score: float,
    ) -> str:
        """
        Generate pedagogical explanation string:
        correct_questions_with_weights: list of (position, weight, logit)
        """
        # Filter questions that were significantly difficult (beta > 0 and weight >= 2.5)
        hard_correct = [
            (pos, w, logit)
            for pos, w, logit in correct_questions_with_weights
            if logit > 0.0 and w >= 2.5
        ]
        hard_correct.sort(key=lambda x: x[1], reverse=True)

        if hard_correct:
            top_hard = hard_correct[:3]
            details = [f"{pos}-savol ({round(w, 1)} ball)" for pos, w, _ in top_hard]
            if len(details) == 1:
                items_str = details[0]
            elif len(details) == 2:
                items_str = f"{details[0]} va {details[1]}"
            else:
                items_str = f"{details[0]}, {details[1]} va {details[2]}"

            return (
                f"Siz to'g'ri topgan {items_str} boshqa o'quvchilar uchun eng qiyin "
                f"bo'lgani sababli, ularga yuqori dinamik ball berildi."
            )

        return (
            "Savollar qiyinlik darajasi barcha o'quvchilarning umumiy natijalari asosida "
            "uzluksiz tahlil qilinib, shaxsiy dinamik ballingiz hisoblandi."
        )

    @classmethod
    @transaction.atomic
    def update_test_question_stats(cls, test_id: int) -> dict[str, Any]:
        """
        Recount and update all Question Rasch parameters for a given Test
        based on all completed StudentAnswers.
        """
        from apps.tests.models import Question, StudentAnswer, TestAttempt

        questions = list(
            Question.objects.filter(test_id=test_id).order_by("position", "id")
        )
        if not questions:
            return {"questions_updated": 0}

        q_ids = [q.id for q in questions]

        # Aggregate attempts per question from completed attempts
        agg_rows = (
            StudentAnswer.objects.filter(
                question_id__in=q_ids,
                attempt__status__in=[
                    TestAttempt.Status.COMPLETED,
                    TestAttempt.Status.TIMEOUT,
                ],
            )
            .values("question_id")
            .annotate(
                total=Count("id"),
                correct=Count("id", filter=Q(is_correct=True)),
            )
        )
        stats_by_qid = {r["question_id"]: (r["total"], r["correct"]) for r in agg_rows}

        for q in questions:
            total_n, correct_c = stats_by_qid.get(q.id, (0, 0))
            p_i = cls.calculate_probability(correct_c, total_n)
            logit_i = cls.calculate_logit(p_i)
            # Use Question points as baseline if set, otherwise default
            baseline = float(q.points) if q.points and q.points > 0 else cls.DEFAULT_BASELINE
            weight_i = cls.calculate_dynamic_weight(logit_i, baseline=baseline)

            q.total_attempts = total_n
            q.correct_attempts = correct_c
            q.difficulty_logit = round(logit_i, 4)
            q.current_rasch_weight = weight_i

        Question.objects.bulk_update(
            questions,
            [
                "total_attempts",
                "correct_attempts",
                "difficulty_logit",
                "current_rasch_weight",
            ],
        )

        return {
            "questions_updated": len(questions),
            "questions": [
                {
                    "id": q.id,
                    "position": q.position,
                    "total_attempts": q.total_attempts,
                    "correct_attempts": q.correct_attempts,
                    "difficulty_logit": q.difficulty_logit,
                    "current_rasch_weight": q.current_rasch_weight,
                }
                for q in questions
            ],
        }

    @classmethod
    @transaction.atomic
    def recalculate_test_rasch(cls, test_id: int) -> dict[str, Any]:
        """
        Full recalculation for a test:
        1. Recalculates question logits & weights from all student responses.
        2. Re-scores all completed attempts and results with updated weights.
        """
        from apps.results.models import Result
        from apps.tests.models import Question, StudentAnswer, Test, TestAttempt

        test = Test.objects.get(id=test_id)
        stats_result = cls.update_test_question_stats(test_id)

        # Refresh questions from DB with updated weights
        questions = list(
            Question.objects.filter(test_id=test_id).order_by("position", "id")
        )
        weights_by_qid = {q.id: q.current_rasch_weight for q in questions}
        logits_by_qid = {q.id: q.difficulty_logit for q in questions}
        positions_by_qid = {q.id: q.position for q in questions}

        max_rasch_score = round(sum(weights_by_qid.values()), 2)

        # Re-score attempts
        attempts = list(
            TestAttempt.objects.filter(
                test_id=test_id,
                status__in=[
                    TestAttempt.Status.COMPLETED,
                    TestAttempt.Status.TIMEOUT,
                ],
            ).prefetch_related("answers")
        )

        updated_attempts: list[TestAttempt] = []
        updated_results: list[Result] = []

        for attempt in attempts:
            earned_rasch = 0.0
            correct_questions: list[tuple[int, float, float]] = []

            for ans in attempt.answers.all():
                if ans.is_correct:
                    qid = ans.question_id
                    w = weights_by_qid.get(qid, cls.DEFAULT_BASELINE)
                    earned_rasch += w
                    correct_questions.append(
                        (
                            positions_by_qid.get(qid, 0),
                            w,
                            logits_by_qid.get(qid, 0.0),
                        )
                    )

            earned_rasch = round(earned_rasch, 2)
            pct = (
                round((earned_rasch / max_rasch_score) * 100.0, 2)
                if max_rasch_score > 0
                else 0.0
            )
            grade = cls.grade_from_percentage(pct)
            explanation = cls.generate_explanation(
                correct_questions, len(questions), earned_rasch
            )

            attempt.rasch_score = Decimal(str(earned_rasch))
            attempt.rasch_grade = grade
            updated_attempts.append(attempt)

            # Update associated Result if exists
            res = Result.objects.filter(attempt_id=attempt.id).first()
            if res:
                res.rasch_score = Decimal(str(earned_rasch))
                res.max_rasch_score = Decimal(str(max_rasch_score))
                res.rasch_grade = grade
                res.rasch_explanation = explanation
                updated_results.append(res)

        if updated_attempts:
            TestAttempt.objects.bulk_update(
                updated_attempts, ["rasch_score", "rasch_grade"]
            )
        if updated_results:
            Result.objects.bulk_update(
                updated_results,
                [
                    "rasch_score",
                    "max_rasch_score",
                    "rasch_grade",
                    "rasch_explanation",
                ],
            )

        return {
            "status": "success",
            "test_id": test_id,
            "test_title": test.title,
            "questions_updated": stats_result["questions_updated"],
            "attempts_updated": len(updated_attempts),
            "results_updated": len(updated_results),
            "max_rasch_score": max_rasch_score,
            "questions": stats_result.get("questions", []),
        }

    @classmethod
    def evaluate_attempt_rasch(
        cls,
        attempt: Any,
        all_questions: Sequence[Any],
        answers_by_qid: dict[int, Any],
    ) -> tuple[Decimal, Decimal, str, str]:
        """
        Evaluate Rasch metrics for an attempt currently being graded.
        Returns: (rasch_score, max_rasch_score, rasch_grade, rasch_explanation)
        """
        # Step 1: Update per-question counters incrementally for this attempt
        questions_to_update: list[Any] = []
        correct_questions: list[tuple[int, float, float]] = []
        earned_rasch = 0.0
        max_rasch = 0.0

        for q in all_questions:
            student_ans = answers_by_qid.get(q.id)
            is_correct = bool(student_ans and student_ans.is_correct)

            # Increment in-memory / DB counters
            new_total = (q.total_attempts or 0) + 1
            new_correct = (q.correct_attempts or 0) + (1 if is_correct else 0)

            p_i = cls.calculate_probability(new_correct, new_total)
            logit_i = cls.calculate_logit(p_i)
            baseline = float(q.points) if q.points and q.points > 0 else cls.DEFAULT_BASELINE
            weight_i = cls.calculate_dynamic_weight(logit_i, baseline=baseline)

            q.total_attempts = new_total
            q.correct_attempts = new_correct
            q.difficulty_logit = round(logit_i, 4)
            q.current_rasch_weight = weight_i
            questions_to_update.append(q)

            max_rasch += weight_i
            if is_correct:
                earned_rasch += weight_i
                correct_questions.append((q.position, weight_i, logit_i))

        # Bulk update questions with new weights
        from apps.tests.models import Question

        Question.objects.bulk_update(
            questions_to_update,
            [
                "total_attempts",
                "correct_attempts",
                "difficulty_logit",
                "current_rasch_weight",
            ],
        )

        earned_rasch = round(earned_rasch, 2)
        max_rasch = round(max_rasch, 2)
        pct = (
            round((earned_rasch / max_rasch) * 100.0, 2)
            if max_rasch > 0
            else 0.0
        )
        grade = cls.grade_from_percentage(pct)
        explanation = cls.generate_explanation(
            correct_questions, len(all_questions), earned_rasch
        )

        return (
            Decimal(str(earned_rasch)),
            Decimal(str(max_rasch)),
            grade,
            explanation,
        )
