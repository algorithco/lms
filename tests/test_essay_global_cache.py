"""Shared (cross-account) AI essay grading cache — acceptance tests.

Proves the Phase O matrix: cross-account reuse with exactly one provider call,
context isolation (topic / rubric / prompt / model / scoring / scope), cache
normalization, leader/follower coordination, safe failure + recovery, zero
scores, invalidation, privacy and serialization, and Milliy Sertifikat
isolation.

No test ever reaches a real AI provider: ``_grade_via_llm`` is patched and its
call count is the assertion that matters.
"""
from __future__ import annotations

import copy
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.essays import metrics
from apps.essays.models import EssayGradingCache, EssaySubmission, EssayTopic, TeacherReview
from apps.essays.services import (
    _claim_grading_cache_entry,
    _complete_cache_entry,
    _load_cached_grading_result,
    apply_cached_grade_to_submission,
    build_grading_context,
    distribute_cached_grade,
    essay_has_grade_result,
    grade_essay,
    grading_cache_identity,
    grading_cache_key_for_submission,
    invalidate_cache_entry,
    normalize_essay_text,
    purge_obsolete_cache_entries,
    recover_stale_grading_cache_entries,
    stamp_grading_cache_key,
    ESSAY_RUBRIC_VERSION,
)

ESSAY = "Inson hayotida kitob o'qishning o'rni beqiyosdir. " * 6
EDITED_ESSAY = ESSAY + "Bundan tashqari, mustaqil fikrlash ham muhim."

MODEL = "grandec-test-model"


def _grade(total_per_criterion: float | None = None) -> dict:
    """A complete, valid 12-criterion grade payload."""
    max_scores = {1: 2.0, 2: 2.0, 3: 2.0, 4: 1.5, 5: 1.5, 6: 1.5, 7: 2.0, 8: 1.5, 9: 1.5, 10: 1.5, 11: 1.5, 12: 1.5}
    if total_per_criterion is not None:
        criteria = [
            {"id": i, "name": f"Criterion {i}", "score": min(total_per_criterion, max_scores[i]), "reason": "Izoh."}
            for i in range(1, 13)
        ]
    else:
        criteria = [
            {"id": i, "name": f"Criterion {i}", "score": max_scores[i], "reason": "Izoh."}
            for i in range(1, 13)
        ]
    total = sum(c["score"] for c in criteria)
    return {
        "criteria": criteria,
        "total_score": total,
        "max_score": 20,
        "summary": "Yaxshi esse.",
        "topic_match": True,
        "topic_match_reason": "Mavzuga mos.",
    }


ZERO_GRADE = _grade(0.0)
FULL_GRADE = _grade(2.0)


@override_settings(
    ESSAY_AI_PROVIDER="openrouter",
    OPENROUTER_API_KEY="sk-or-v1-sharedcache000000000000000000000000",
    ESSAY_AI_MODEL=MODEL,
    OPENROUTER_AI_MODEL=MODEL,
    OPENROUTER_FALLBACK_MODELS=[],
    ESSAY_CACHE_WAIT_SECONDS=2,
)
class SharedEssayCacheTestCase(TestCase):
    """Base: deterministic grading stub + call counting."""

    def setUp(self) -> None:
        cache.clear()
        metrics.reset()
        self.user_a = User.objects.create_user(email="cache-a@example.test", password="StrongPass123!")
        self.user_b = User.objects.create_user(email="cache-b@example.test", password="StrongPass123!")
        self.topic = EssayTopic.objects.create(
            title="Kitob va inson", category="essay", word_limit_min=10, word_limit_max=500,
        )
        self.llm = MagicMock()
        patcher_client = patch("apps.essays.services._get_llm_client", return_value=self.llm)
        patcher_client.start()
        self.addCleanup(patcher_client.stop)

    def patch_grader(self, grade: dict | None = None, side_effect=None):
        """Patch the model chain; returns the mock (``.call_count`` == AI requests)."""
        grader = MagicMock()
        if side_effect is not None:
            grader.side_effect = side_effect
        else:
            payload = copy.deepcopy(grade or FULL_GRADE)

            def _respond(*_args, **_kwargs):
                return copy.deepcopy(payload), MODEL

            grader.side_effect = _respond
        patcher = patch("apps.essays.services._grade_via_llm", grader)
        patcher.start()
        self.addCleanup(patcher.stop)
        return grader

    def submission(self, student, *, text: str = ESSAY, topic=None, scope=None, status=None):
        return EssaySubmission.objects.create(
            student=student,
            topic=self.topic if topic is None else topic,
            essay_text=text,
            word_count=len(text.split()),
            status=status or EssaySubmission.Status.PENDING,
            **({"cache_scope": scope} if scope else {}),
        )

    def run_task(self, submission):
        """Run the canonical grading task synchronously."""
        from apps.essays.tasks import grade_submission_task

        return grade_submission_task.apply(
            args=[submission.pk], kwargs={"fail_status": EssaySubmission.Status.ERROR},
        ).get()


class CrossAccountReuseTests(SharedEssayCacheTestCase):
    """Phase 4/8: Student A → AI, Student B → same canonical evaluation."""

    def test_second_account_reuses_one_ai_evaluation(self):
        grader = self.patch_grader()
        sub_a = self.submission(self.user_a)
        sub_b = self.submission(self.user_b)

        result_a = self.run_task(sub_a)
        sub_a.refresh_from_db()
        self.assertIn(result_a["status"], ("graded", "ok"))
        self.assertEqual(grader.call_count, 1)
        self.assertEqual(sub_a.grading_source, EssaySubmission.GradingSource.AI)
        self.assertEqual(sub_a.total_score, Decimal("20.0"))

        result_b = self.run_task(sub_b)
        sub_b.refresh_from_db()

        # Exactly one canonical AI evaluation for two accounts.
        self.assertEqual(grader.call_count, 1)
        self.assertIn(result_b["status"], ("graded", "ok"))
        self.assertEqual(sub_b.total_score, sub_a.total_score)
        self.assertEqual(sub_b.grading_source, EssaySubmission.GradingSource.CACHE)
        self.assertIsNotNone(sub_b.grading_cache_id)
        self.assertIsNone(sub_a.grading_cache_id)

        # Independent submissions and independent rubric rows.
        self.assertNotEqual(sub_a.pk, sub_b.pk)
        self.assertEqual(sub_a.criteria.count(), 12)
        self.assertEqual(sub_b.criteria.count(), 12)
        self.assertEqual(sub_a.student_id, self.user_a.pk)
        self.assertEqual(sub_b.student_id, self.user_b.pk)

        entry = EssayGradingCache.objects.get()
        self.assertEqual(entry.status, EssayGradingCache.Status.COMPLETED)
        self.assertEqual(entry.cache_schema_version, EssayGradingCache.CACHE_SCHEMA_VERSION)
        self.assertTrue(entry.is_reusable())
        self.assertEqual(entry.hit_count, 2)
        self.assertEqual(entry.reuse_count, 1)
        self.assertIsNotNone(entry.completed_at)
        self.assertEqual(entry.rubric_version, ESSAY_RUBRIC_VERSION)

    def test_distribution_completes_waiting_submission_without_second_ai_call(self):
        grader = self.patch_grader()
        sub_a = self.submission(self.user_a)
        self.run_task(sub_a)
        self.assertEqual(grader.call_count, 1)

        sub_b = self.submission(self.user_b)
        key = stamp_grading_cache_key(sub_b)
        self.assertEqual(sub_b.grading_cache_key, key)

        applied = distribute_cached_grade(key, exclude_submission_id=sub_a.pk)
        sub_b.refresh_from_db()

        self.assertEqual(applied, 1)
        self.assertEqual(sub_b.status, EssaySubmission.Status.GRADED)
        self.assertEqual(sub_b.grading_source, EssaySubmission.GradingSource.CACHE)
        self.assertEqual(grader.call_count, 1)
        self.assertEqual(sub_b.criteria.count(), 12)

        # Idempotent: a second sweep must not re-grade or duplicate rows.
        self.assertEqual(distribute_cached_grade(key), 0)
        self.assertEqual(sub_b.criteria.count(), 12)

    def test_apply_cached_grade_to_submission_is_idempotent(self):
        self.patch_grader()
        sub_a = self.submission(self.user_a)
        self.run_task(sub_a)
        key = grading_cache_key_for_submission(sub_a)

        sub_b = self.submission(self.user_b)
        sub_b.grading_cache_key = key
        sub_b.save(update_fields=["grading_cache_key"])

        self.assertTrue(apply_cached_grade_to_submission(sub_b, key))
        self.assertFalse(apply_cached_grade_to_submission(sub_b, key))


class ContextIsolationTests(SharedEssayCacheTestCase):
    """Phase 6: reuse only under an identical grading context."""

    def test_different_essay_is_a_cache_miss(self):
        grader = self.patch_grader()
        grade_essay(ESSAY, "Kitob va inson")
        grade_essay(EDITED_ESSAY, "Kitob va inson")
        self.assertEqual(grader.call_count, 2)
        self.assertEqual(EssayGradingCache.objects.count(), 2)

    def test_normalization_shares_a_working_copy_variant(self):
        grader = self.patch_grader()
        first = grade_essay("Kitob o'qish foydali.   Inson uchun\n\nmuhim.", "Topic")
        second = grade_essay("Kitob o'qish foydali. Inson uchun muhim.", "Topic")
        self.assertFalse(first["_from_cache"])
        self.assertTrue(second["_from_cache"])
        self.assertEqual(grader.call_count, 1)

    def test_crlf_and_tab_variants_share_one_fingerprint(self):
        grader = self.patch_grader()
        grade_essay("Kitob o'qish foydali.\r\nInson uchun muhim.", "Topic")
        result = grade_essay("Kitob o'qish foydali.\tInson uchun muhim.", "Topic")
        self.assertTrue(result["_from_cache"])
        self.assertEqual(grader.call_count, 1)

    def test_normalizer_preserves_meaning(self):
        self.assertEqual(normalize_essay_text("A  b\r\n\r\nc  "), "A b c")
        self.assertNotEqual(
            normalize_essay_text("Men kitob o'qiyman."),
            normalize_essay_text("Men kitob o'qimayman."),
        )
        # Punctuation is meaningful and must not be stripped.
        self.assertNotEqual(normalize_essay_text("Yaxshi."), normalize_essay_text("Yaxshi"))

    def test_different_topic_is_a_cache_miss(self):
        grader = self.patch_grader()
        grade_essay(ESSAY, "Kitob va inson")
        grade_essay(ESSAY, "Vatan va til")
        self.assertEqual(grader.call_count, 2)

    def test_topic_identity_and_instructions_participate_in_the_key(self):
        topic_a = EssayTopic.objects.create(
            title="Bir xil sarlavha", description="Birinchi qo'llanma", category="essay", word_limit_min=10,
        )
        topic_b = EssayTopic.objects.create(
            title="Bir xil sarlavha", description="Butunlay boshqa qo'llanma", category="essay", word_limit_min=10,
        )
        ctx_a = build_grading_context(topic=topic_a, scope="practice")
        ctx_b = build_grading_context(topic=topic_b, scope="practice")
        # Same title, different topic record and different instructions.
        self.assertNotEqual(ctx_a["topic_id"], ctx_b["topic_id"])
        self.assertNotEqual(ctx_a["topic_digest"], ctx_b["topic_digest"])
        self.assertNotEqual(
            grading_cache_identity(ESSAY, topic_a.title, context=ctx_a)["cache_key"],
            grading_cache_identity(ESSAY, topic_b.title, context=ctx_b)["cache_key"],
        )

        # Identical topic content and instructions → identical identity.
        twin = EssayTopic.objects.create(
            title="Bir xil sarlavha", description="Birinchi qo'llanma", category="essay", word_limit_min=10,
        )
        ctx_twin = build_grading_context(topic=twin, scope="practice")
        self.assertEqual(ctx_twin["topic_digest"], ctx_a["topic_digest"])

    def test_changed_topic_instructions_are_a_cache_miss(self):
        grader = self.patch_grader()
        topic = EssayTopic.objects.create(title="Qo'llanma testi", category="essay", word_limit_min=10)
        ctx = build_grading_context(topic=topic, scope="practice")
        grade_essay(ESSAY, topic.title, cache_context=ctx)

        topic.description = "Yangi qo'llanma matni"
        topic.save(update_fields=["description"])
        ctx_changed = build_grading_context(topic=topic, scope="practice")
        result = grade_essay(ESSAY, topic.title, cache_context=ctx_changed)
        self.assertFalse(result["_from_cache"])
        self.assertEqual(grader.call_count, 2)

    def test_changed_prompt_version_is_a_cache_miss(self):
        grader = self.patch_grader()
        grade_essay(ESSAY, "Topic")
        with override_settings(ESSAY_GRADING_CACHE_VERSION="v4"):
            result = grade_essay(ESSAY, "Topic")
        self.assertFalse(result["_from_cache"])
        self.assertEqual(grader.call_count, 2)

    def test_changed_rubric_version_is_a_cache_miss(self):
        grader = self.patch_grader()
        grade_essay(ESSAY, "Topic")
        with patch("apps.essays.services.ESSAY_RUBRIC_VERSION", "grandec-essay-12x2-v2"):
            result = grade_essay(ESSAY, "Topic")
        self.assertFalse(result["_from_cache"])
        self.assertEqual(grader.call_count, 2)

    def test_changed_model_is_a_cache_miss(self):
        grader = self.patch_grader()
        grade_essay(ESSAY, "Topic")
        with override_settings(ESSAY_AI_MODEL="other-model", OPENROUTER_AI_MODEL="other-model"):
            result = grade_essay(ESSAY, "Topic")
        self.assertFalse(result["_from_cache"])
        self.assertEqual(grader.call_count, 2)

    def test_changed_scoring_version_is_a_cache_miss(self):
        grader = self.patch_grader()
        grade_essay(ESSAY, "Topic")
        with override_settings(ESSAY_SCORING_VERSION="v2"):
            result = grade_essay(ESSAY, "Topic")
        self.assertFalse(result["_from_cache"])
        self.assertEqual(grader.call_count, 2)

    def test_changed_language_is_a_cache_miss(self):
        p = patch("apps.essays.services.grading_cache_identity", wraps=grading_cache_identity)
        p.start()
        self.addCleanup(p.stop)
        grader = self.patch_grader()
        grade_essay(ESSAY, "Topic")
        with override_settings(LANGUAGE_CODE="ru"):
            result = grade_essay(ESSAY, "Topic")
        self.assertFalse(result["_from_cache"])
        self.assertEqual(grader.call_count, 2)


class HighStakesIsolationTests(SharedEssayCacheTestCase):
    """Phase H/K: restricted assessments never share a grade across accounts."""

    def test_high_stakes_scope_never_reuses_across_accounts(self):
        grader = self.patch_grader()
        identity = grading_cache_identity(
            ESSAY, "", context=build_grading_context(topic_title="", scope="high_stakes"),
        )
        self.assertFalse(identity["cacheable"])

        first = grade_essay(
            ESSAY, "", cache_context=build_grading_context(topic_title="", scope="high_stakes"),
        )
        second = grade_essay(
            ESSAY, "", cache_context=build_grading_context(topic_title="", scope="high_stakes"),
        )
        self.assertFalse(first["_from_cache"])
        self.assertFalse(second["_from_cache"])
        self.assertEqual(grader.call_count, 2)
        self.assertEqual(EssayGradingCache.objects.count(), 0)

    def test_practice_entry_is_not_matched_by_a_high_stakes_run(self):
        grader = self.patch_grader()
        practice = grade_essay(ESSAY, "Kitob va inson")
        self.assertFalse(practice["_from_cache"])

        shared = grade_essay(ESSAY, "Kitob va inson")
        self.assertTrue(shared["_from_cache"])

        highs = grade_essay(
            ESSAY, "Kitob va inson",
            cache_context=build_grading_context(
                topic_title="Kitob va inson", scope="high_stakes",
            ),
        )
        self.assertFalse(highs["_from_cache"])
        self.assertEqual(grader.call_count, 2)

    def test_exam_bridge_submissions_are_high_stakes(self):
        from apps.tests.models import ExamWrittenBridge, StudentAnswer
        from apps.tests.services import (
            ExamBridgeService,
            SaveAnswerService,
            StartAttemptService,
            SubmitAttemptService,
        )
        from tests.test_official_rules_readiness import build_milliy_exam, make_user, no_dispatch

        teacher = make_user("cache-exam-t@e.com", "teacher")
        student = make_user("cache-exam-s@e.com")
        exam = build_milliy_exam(teacher, title="Cache exam")
        attempt = StartAttemptService.execute(test_id=exam["test"].id, student=student)
        SaveAnswerService.execute(
            attempt.id, exam["q_w"].id, [], student, written_text="Matn. " * 30,
        )
        with no_dispatch():
            SubmitAttemptService.execute(attempt.id, student)
        answer = StudentAnswer.objects.get(attempt=attempt, question=exam["q_w"])
        bridge = ExamWrittenBridge.objects.get(answer=answer)

        self.assertIsNotNone(bridge.essay_submission_id)
        self.assertEqual(
            bridge.essay_submission.cache_scope, EssaySubmission.CacheScope.HIGH_STAKES,
        )
        self.assertEqual(bridge.rubric_version, ESSAY_RUBRIC_VERSION)
        # The bridge kept working: the submission exists and is queued/pending,
        # never silently marked graded by a shared evaluation.
        self.assertIn(
            bridge.essay_submission.status,
            (EssaySubmission.Status.PENDING, EssaySubmission.Status.DRAFT),
        )
        self.assertEqual(ExamBridgeService._rubric_version(), ESSAY_RUBRIC_VERSION)


class ConcurrencyAndRecoveryTests(SharedEssayCacheTestCase):
    """Phase F/E: one leader per key, waiting followers, safe recovery."""

    def test_follower_waits_without_calling_the_provider(self):
        grader = self.patch_grader()
        identity = grading_cache_identity(ESSAY, "Kitob va inson")
        self.assertTrue(identity["cacheable"])

        claim = _claim_grading_cache_entry(identity, ESSAY)
        self.assertTrue(claim.is_leader)

        with self.assertRaises(TimeoutError):
            grade_essay(ESSAY, "Kitob va inson")

        self.assertEqual(grader.call_count, 0)
        entry = EssayGradingCache.objects.get()
        self.assertEqual(entry.status, EssayGradingCache.Status.PROCESSING)
        self.assertGreaterEqual(entry.waiting_count, 1)
        self.assertTrue(entry.lease_is_active())

        # The leader completes; the next caller reuses it without any AI call.
        _complete_cache_entry(claim, FULL_GRADE)
        result = grade_essay(ESSAY, "Kitob va inson")
        self.assertTrue(result["_from_cache"])
        self.assertEqual(result["total_score"], 20.0)
        self.assertEqual(grader.call_count, 0)

    @override_settings(ESSAY_CACHE_WAIT_SECONDS=1)
    def test_second_account_does_not_start_a_second_ai_request_while_leased(self):
        from celery.exceptions import Retry

        from apps.essays.services import grading_context_for_submission

        grader = self.patch_grader()
        sub_a = self.submission(self.user_a)
        sub_b = self.submission(self.user_b)

        # Reserve the key exactly as the submission's own context would.
        identity = grading_cache_identity(
            ESSAY, self.topic.title, context=grading_context_for_submission(sub_a),
        )
        self.assertEqual(identity["cache_key"], grading_cache_key_for_submission(sub_b))
        claim = _claim_grading_cache_entry(identity, ESSAY)
        self.assertTrue(claim.is_leader)

        # Service contract: a waiter gives up (the caller retries) instead of
        # paying for a second AI request.
        with self.assertRaises(TimeoutError):
            grade_essay(
                ESSAY, self.topic.title, cache_context=grading_context_for_submission(sub_b),
            )
        # Through the canonical task the same thing surfaces as a Celery retry.
        with self.assertRaises((TimeoutError, Retry)):
            self.run_task(sub_b)

        sub_b.refresh_from_db()
        self.assertEqual(grader.call_count, 0)
        self.assertEqual(sub_b.status, EssaySubmission.Status.PENDING)
        self.assertFalse(essay_has_grade_result(sub_b))

        _complete_cache_entry(claim, FULL_GRADE)
        self.run_task(sub_b)
        sub_b.refresh_from_db()
        self.assertEqual(sub_b.status, EssaySubmission.Status.GRADED)
        self.assertEqual(sub_b.grading_source, EssaySubmission.GradingSource.CACHE)
        self.assertEqual(grader.call_count, 0)
        self.assertEqual(sub_a.status, EssaySubmission.Status.PENDING)

    def test_provider_failure_leaves_no_artifact_and_retry_completes(self):
        failing = self.patch_grader(side_effect=ValueError("LLM bo'sh javob qaytardi"))
        with self.assertRaises(ValueError):
            grade_essay(ESSAY, "Kitob va inson")
        self.assertEqual(EssayGradingCache.objects.count(), 0)
        self.assertEqual(failing.call_count, 1)

        succeeding = self.patch_grader()
        result = grade_essay(ESSAY, "Kitob va inson")
        self.assertFalse(result["_from_cache"])
        entry = EssayGradingCache.objects.get()
        self.assertEqual(entry.status, EssayGradingCache.Status.COMPLETED)
        self.assertEqual(entry.failure_count, 0)
        self.assertEqual(succeeding.call_count, 1)

    def test_failed_leader_with_waiters_keeps_a_bounded_retry_window(self):
        from apps.essays.services import _fail_cache_entry

        identity = grading_cache_identity(ESSAY, "Kitob va inson")
        claim = _claim_grading_cache_entry(identity, ESSAY)
        EssayGradingCache.objects.filter(pk=claim.entry.pk).update(waiting_count=1)

        _fail_cache_entry(claim, RuntimeError("provider down"))

        entry = EssayGradingCache.objects.get()
        self.assertEqual(entry.status, EssayGradingCache.Status.FAILED)
        self.assertEqual(entry.failure_count, 1)
        self.assertIn("RuntimeError", entry.error_summary)
        self.assertEqual(entry.raw_result, {})
        self.assertIsNotNone(entry.lease_expires_at)

    def test_stale_lease_is_recovered_and_the_key_can_be_graded_again(self):
        grader = self.patch_grader()
        identity = grading_cache_identity(ESSAY, "Kitob va inson")
        claim = _claim_grading_cache_entry(identity, ESSAY)
        self.assertTrue(claim.is_leader)

        EssayGradingCache.objects.filter(pk=claim.entry.pk).update(
            lease_expires_at=timezone.now() - timedelta(seconds=10),
        )
        self.assertEqual(recover_stale_grading_cache_entries(), 1)

        entry = EssayGradingCache.objects.get()
        self.assertEqual(entry.status, EssayGradingCache.Status.FAILED)
        self.assertEqual(entry.lease_owner, "")
        self.assertEqual(entry.error_summary, "stale lease recovered")

        result = grade_essay(ESSAY, "Kitob va inson")
        self.assertFalse(result["_from_cache"])
        self.assertEqual(grader.call_count, 1)
        self.assertEqual(EssayGradingCache.objects.get().status, EssayGradingCache.Status.COMPLETED)

    def test_expired_lease_does_not_overwrite_a_newer_valid_result(self):
        first = self.patch_grader()
        identity = grading_cache_identity(ESSAY, "Kitob va inson")
        stale_claim = _claim_grading_cache_entry(identity, ESSAY)

        # The first leader stalls; its lease expires and a newer leader finishes.
        EssayGradingCache.objects.filter(pk=stale_claim.entry.pk).update(
            lease_expires_at=timezone.now() - timedelta(seconds=5),
        )
        fresh = grade_essay(ESSAY, "Kitob va inson")
        self.assertFalse(fresh["_from_cache"])
        entry = EssayGradingCache.objects.get()
        self.assertEqual(entry.status, EssayGradingCache.Status.COMPLETED)
        self.assertEqual(entry.total_score, Decimal("20.0"))

        # The stalled worker must not clobber the newer result.
        _complete_cache_entry(stale_claim, _grade(1.0))
        entry.refresh_from_db()
        self.assertEqual(entry.total_score, Decimal("20.0"))
        self.assertEqual(entry.status, EssayGradingCache.Status.COMPLETED)
        self.assertEqual(first.call_count, 1)
        self.assertTrue(entry.is_reusable())


@override_settings(
    ESSAY_AI_PROVIDER="openrouter",
    OPENROUTER_API_KEY="sk-or-v1-sharedcache000000000000000000000000",
    ESSAY_AI_MODEL=MODEL,
    OPENROUTER_AI_MODEL=MODEL,
    OPENROUTER_FALLBACK_MODELS=[],
    ESSAY_CACHE_WAIT_SECONDS=30,
)
class SimultaneousSubmissionTests(TransactionTestCase):
    """Phase F: two accounts submitting the same essay at the same moment.

    The leader is held inside the (stubbed) provider call until the second
    submission is provably waiting on the same cache key, so the test exercises
    real concurrent workers rather than a simulated ordering.

    NOTE: this test runs on the project's configured database. SQLite proves
    the coordination logic (conditional UPDATE + lease) but is NOT proof of
    PostgreSQL race safety; run it against PostgreSQL for that claim.
    """

    def setUp(self) -> None:
        cache.clear()
        metrics.reset()
        self.user_a = User.objects.create_user(email="race-a@example.test", password="StrongPass123!")
        self.user_b = User.objects.create_user(email="race-b@example.test", password="StrongPass123!")
        self.topic = EssayTopic.objects.create(
            title="Bir vaqtda topshirish", category="essay", word_limit_min=10,
        )
        self.sub_a = EssaySubmission.objects.create(
            student=self.user_a, topic=self.topic, essay_text=ESSAY,
            word_count=12, status=EssaySubmission.Status.PENDING,
        )
        self.sub_b = EssaySubmission.objects.create(
            student=self.user_b, topic=self.topic, essay_text=ESSAY,
            word_count=12, status=EssaySubmission.Status.PENDING,
        )

    def test_two_simultaneous_identical_submissions_make_one_ai_request(self):
        import threading
        import time as _time

        from django.db import connection

        from apps.essays.tasks import grade_submission_task

        leader_running = threading.Event()
        release_leader = threading.Event()
        provider_calls: list[int] = []

        def stub_grader(*_args, **_kwargs):
            provider_calls.append(1)
            leader_running.set()
            release_leader.wait(timeout=20)
            return copy.deepcopy(FULL_GRADE), MODEL

        outcomes: dict[str, object] = {}

        def run(name: str, submission_id: int) -> None:
            try:
                outcomes[name] = grade_submission_task.apply(
                    args=[submission_id], kwargs={"fail_status": EssaySubmission.Status.ERROR},
                ).get()
            except Exception as exc:  # noqa: BLE001 - recorded and asserted below
                outcomes[name] = exc
            finally:
                connection.close()

        with patch("apps.essays.services._grade_via_llm", side_effect=stub_grader), patch(
            "apps.essays.services._get_llm_client", return_value=MagicMock(),
        ):
            first = threading.Thread(target=run, args=("a", self.sub_a.pk), daemon=True)
            first.start()
            self.assertTrue(
                leader_running.wait(timeout=20),
                f"leader never reached the provider: outcomes={outcomes}",
            )

            second = threading.Thread(target=run, args=("b", self.sub_b.pk), daemon=True)
            second.start()

            # Wait until the second submission is registered as a waiter on the
            # leader's cache key (i.e. it did NOT start its own provider call).
            deadline = _time.monotonic() + 20
            waiting = False
            while _time.monotonic() < deadline:
                if EssayGradingCache.objects.filter(waiting_count__gte=1).exists():
                    waiting = True
                    break
                if not second.is_alive():
                    break
                _time.sleep(0.05)

            release_leader.set()
            first.join(timeout=40)
            second.join(timeout=40)

        self.assertTrue(waiting, "the second submission never registered as a waiter")
        self.assertEqual(len(provider_calls), 1, f"expected exactly one AI request, got {provider_calls}")

        self.sub_a.refresh_from_db()
        self.sub_b.refresh_from_db()
        self.assertEqual(self.sub_a.status, EssaySubmission.Status.GRADED)
        self.assertEqual(self.sub_b.status, EssaySubmission.Status.GRADED)
        self.assertEqual(self.sub_a.total_score, self.sub_b.total_score)
        sources = {self.sub_a.grading_source, self.sub_b.grading_source}
        self.assertIn(EssaySubmission.GradingSource.CACHE, sources)
        self.assertEqual(EssayGradingCache.objects.count(), 1)
        entry = EssayGradingCache.objects.get()
        self.assertEqual(entry.status, EssayGradingCache.Status.COMPLETED)
        # hit_count counts cache reads: the original evaluation (1) plus the
        # follower's reuse. A concurrent follower may legitimately read the
        # entry twice (once while waiting, once when applying it), so the exact
        # number of reads is not asserted — the sequential reuse test does that.
        self.assertGreaterEqual(entry.hit_count, 2)
        self.assertGreaterEqual(entry.reuse_count, 1)


class ZeroScoreTests(SharedEssayCacheTestCase):
    def test_zero_score_is_cached_and_reused_as_zero(self):
        grader = self.patch_grader(ZERO_GRADE)
        first = grade_essay(ESSAY, "Kitob va inson")
        second = grade_essay(ESSAY, "Kitob va inson")

        self.assertEqual(first["total_score"], 0.0)
        self.assertFalse(first["_from_cache"])
        self.assertTrue(second["_from_cache"])
        self.assertEqual(second["total_score"], 0.0)
        self.assertEqual(grader.call_count, 1)

        entry = EssayGradingCache.objects.get()
        self.assertEqual(entry.total_score, Decimal("0.0"))
        self.assertTrue(entry.is_reusable())

    def test_zero_score_reaches_the_second_account_as_a_real_grade(self):
        grader = self.patch_grader(ZERO_GRADE)
        sub_a = self.submission(self.user_a)
        sub_b = self.submission(self.user_b)
        self.run_task(sub_a)
        self.run_task(sub_b)

        sub_b.refresh_from_db()
        self.assertEqual(grader.call_count, 1)
        self.assertEqual(sub_b.status, EssaySubmission.Status.GRADED)
        self.assertEqual(sub_b.total_score, Decimal("0.0"))
        self.assertTrue(essay_has_grade_result(sub_b))
        self.assertEqual(sub_b.criteria.count(), 12)


class ValidationAndInvalidationTests(SharedEssayCacheTestCase):
    def test_corrupt_cached_payload_is_never_served(self):
        grader = self.patch_grader()
        key = grading_cache_identity(ESSAY, "Kitob va inson")["cache_key"]
        EssayGradingCache.objects.create(
            text_hash=key,
            essay_text=ESSAY,
            raw_result={"criteria": [], "total_score": 20, "max_score": 20},
            total_score=Decimal("20.0"),
            max_score=20,
            status=EssayGradingCache.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        self.assertIsNone(_load_cached_grading_result(key))
        self.assertFalse(EssayGradingCache.objects.filter(text_hash=key).exists())

        result = grade_essay(ESSAY, "Kitob va inson")
        self.assertFalse(result["_from_cache"])
        self.assertEqual(grader.call_count, 1)
        self.assertTrue(EssayGradingCache.objects.get().is_reusable())

    def test_incompatible_schema_version_is_regraded(self):
        grader = self.patch_grader()
        first = grade_essay(ESSAY, "Kitob va inson")
        self.assertFalse(first["_from_cache"])

        EssayGradingCache.objects.update(cache_schema_version=1)
        second = grade_essay(ESSAY, "Kitob va inson")
        self.assertFalse(second["_from_cache"])
        self.assertEqual(grader.call_count, 2)
        self.assertEqual(
            EssayGradingCache.objects.get().cache_schema_version,
            EssayGradingCache.CACHE_SCHEMA_VERSION,
        )

    def test_invalidated_entry_is_regraded(self):
        grader = self.patch_grader()
        grade_essay(ESSAY, "Kitob va inson")
        entry = EssayGradingCache.objects.get()
        invalidate_cache_entry(entry, reason="admin test")

        entry.refresh_from_db()
        self.assertIsNotNone(entry.invalidated_at)
        self.assertFalse(entry.is_reusable())

        result = grade_essay(ESSAY, "Kitob va inson")
        self.assertFalse(result["_from_cache"])
        self.assertEqual(grader.call_count, 2)

    def test_purge_keeps_valid_entries_and_removes_obsolete_ones(self):
        self.patch_grader()
        grade_essay(ESSAY, "Kitob va inson")
        keep = EssayGradingCache.objects.get()

        obsolete = EssayGradingCache.objects.create(
            text_hash="0" * 64,
            essay_text="eski",
            raw_result={"criteria": [], "total_score": 1, "max_score": 20},
            total_score=Decimal("1.0"),
            max_score=20,
            status=EssayGradingCache.Status.COMPLETED,
            cache_schema_version=1,
        )
        invalidated = EssayGradingCache.objects.create(
            text_hash="1" * 64,
            essay_text="bekor qilingan",
            raw_result={"criteria": [], "total_score": 1, "max_score": 20},
            total_score=Decimal("1.0"),
            max_score=20,
            status=EssayGradingCache.Status.COMPLETED,
            invalidated_at=timezone.now(),
        )
        deleted = purge_obsolete_cache_entries()
        self.assertGreaterEqual(deleted, 2)
        self.assertTrue(EssayGradingCache.objects.filter(pk=keep.pk).exists())
        self.assertFalse(EssayGradingCache.objects.filter(pk=obsolete.pk).exists())
        self.assertFalse(EssayGradingCache.objects.filter(pk=invalidated.pk).exists())

    def test_purge_never_deletes_a_live_lease(self):
        identity = grading_cache_identity(ESSAY, "Kitob va inson")
        claim = _claim_grading_cache_entry(identity, ESSAY)
        purge_obsolete_cache_entries(keep_days=1)
        self.assertTrue(EssayGradingCache.objects.filter(pk=claim.entry.pk).exists())


class ProvenanceAndPrivacyTests(SharedEssayCacheTestCase):
    """Phase K: the student is told a saved evaluation was applied — nothing else."""

    def setUp(self) -> None:
        super().setUp()
        self.patch_grader()
        self.sub_a = self.submission(self.user_a)
        self.sub_b = self.submission(self.user_b)
        self.run_task(self.sub_a)
        self.run_task(self.sub_b)
        self.sub_b.refresh_from_db()

    def test_provenance_is_recorded_on_the_second_submission(self):
        self.assertEqual(self.sub_b.grading_source, EssaySubmission.GradingSource.CACHE)
        self.assertIsNotNone(self.sub_b.grading_cache_id)
        self.assertEqual(self.sub_a.grading_source, EssaySubmission.GradingSource.AI)

    def test_status_endpoint_exposes_only_own_provenance(self):
        from django.urls import reverse

        self.client.force_login(self.user_b)
        response = self.client.get(
            reverse("essays:grading-status", args=[self.sub_b.pk]),
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["cached"])
        self.assertEqual(payload["grading_source"], "cache")

        serialized = json.dumps(payload)
        for leaked in (
            "text_hash", "grading_context", "grading_cache_key", "lease_owner",
            self.user_a.email, str(self.sub_a.pk), "fingerprint",
        ):
            self.assertNotIn(leaked, serialized)

    def test_other_student_cannot_read_the_submission(self):
        from django.urls import reverse

        self.client.force_login(self.user_a)
        response = self.client.get(reverse("essays:grading-status", args=[self.sub_b.pk]))
        self.assertEqual(response.status_code, 404)

    def test_cache_payload_has_no_user_identity_or_teacher_data(self):
        entry = EssayGradingCache.objects.get()
        payload = json.dumps(entry.grading_context)
        for leaked in (self.user_a.email, self.user_b.email):
            self.assertNotIn(leaked, payload)
        for identity_key in ("email", "student", "user", "account"):
            self.assertNotIn(identity_key, payload.lower().replace("topic_title", ""))
        self.assertEqual(sorted(entry.raw_result.keys()), sorted(
            ["criteria", "total_score", "max_score", "summary", "topic_match", "topic_match_reason"],
        ))

    def test_teacher_override_stays_local_to_one_submission(self):
        TeacherReview.objects.create(
            submission=self.sub_a,
            teacher=self.user_a,
            final_score=Decimal("7.0"),
            teacher_comments="Faqat shu o'quvchi uchun.",
        )
        self.sub_a.final_score = Decimal("7.0")
        self.sub_a.save(update_fields=["final_score"])

        self.sub_b.refresh_from_db()
        entry = EssayGradingCache.objects.get()

        self.assertIsNone(self.sub_b.final_score)
        self.assertEqual(self.sub_b.total_score, Decimal("20.0"))
        self.assertNotIn("Faqat shu o'quvchi uchun.", json.dumps(entry.raw_result))
        self.assertFalse(
            TeacherReview.objects.filter(submission=self.sub_b).exists(),
        )


class AdminAndOperationsTests(SharedEssayCacheTestCase):
    """Phase N/ops: privileged, auditable administration of the shared cache."""

    def setUp(self) -> None:
        super().setUp()
        self.admin = User.objects.create_superuser(
            email="cache-admin@example.test", password="StrongPass123!",
        )
        self.client.force_login(self.admin)

    def _changelist_url(self) -> str:
        from django.urls import reverse

        return reverse("admin:essays_essaygradingcache_changelist")

    def test_changelist_renders_with_operational_columns(self):
        self.patch_grader()
        grade_essay(ESSAY, "Kitob va inson")
        response = self.client.get(self._changelist_url())
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn(EssayGradingCache.Status.COMPLETED, body)

    def test_admin_can_invalidate_an_entry(self):
        self.patch_grader()
        grade_essay(ESSAY, "Kitob va inson")
        entry = EssayGradingCache.objects.get()

        response = self.client.post(
            self._changelist_url(),
            {"action": "invalidate_selected", "_selected_action": [entry.pk]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        entry.refresh_from_db()
        self.assertIsNotNone(entry.invalidated_at)
        self.assertFalse(entry.is_reusable())

    def test_admin_retry_action_keeps_a_live_lease(self):
        identity = grading_cache_identity(ESSAY, "Kitob va inson")
        claim = _claim_grading_cache_entry(identity, ESSAY)
        self.assertTrue(claim.is_leader)

        self.client.post(
            self._changelist_url(),
            {"action": "retry_failed_entries", "_selected_action": [claim.entry.pk]},
            follow=True,
        )
        entry = EssayGradingCache.objects.get(pk=claim.entry.pk)
        # A live leader must never be overtaken by an admin action.
        self.assertEqual(entry.status, EssayGradingCache.Status.PROCESSING)
        self.assertTrue(entry.lease_is_active())

    def test_recovery_command_runs_and_recovers_a_stale_lease(self):
        from io import StringIO

        from django.core.management import call_command

        identity = grading_cache_identity(ESSAY, "Kitob va inson")
        claim = _claim_grading_cache_entry(identity, ESSAY)
        EssayGradingCache.objects.filter(pk=claim.entry.pk).update(
            lease_expires_at=timezone.now() - timedelta(seconds=5),
        )

        out = StringIO()
        call_command("recover_essay_caches", stdout=out)
        self.assertIn("recovered=1", out.getvalue())
        self.assertEqual(
            EssayGradingCache.objects.get(pk=claim.entry.pk).status,
            EssayGradingCache.Status.FAILED,
        )


class LookupCostTests(SharedEssayCacheTestCase):
    """Phase P: a cache hit is an indexed, bounded-query operation."""

    def test_cache_hit_uses_a_bounded_number_of_queries_and_no_ai_call(self):
        grader = self.patch_grader()
        grade_essay(ESSAY, "Kitob va inson")
        self.assertEqual(grader.call_count, 1)

        # Measured: one indexed SELECT on the unique cache key + one UPDATE
        # accounting for the reuse. No scan, no provider call.
        with self.assertNumQueries(2):
            result = grade_essay(ESSAY, "Kitob va inson")
        self.assertTrue(result["_from_cache"])
        self.assertEqual(grader.call_count, 1)

    def test_cache_hit_is_indexed_on_the_unique_key(self):
        field = EssayGradingCache._meta.get_field("text_hash")
        self.assertTrue(field.unique)
        self.assertTrue(field.db_index)
        self.assertEqual(field.max_length, 64)


class EssayEditAndCompatibilityTests(SharedEssayCacheTestCase):
    def test_edited_essay_never_receives_the_stale_grade(self):
        grader = self.patch_grader()
        sub_a = self.submission(self.user_a)
        self.run_task(sub_a)

        sub_b = self.submission(self.user_b, text=EDITED_ESSAY)
        self.run_task(sub_b)
        sub_b.refresh_from_db()

        self.assertEqual(grader.call_count, 2)
        self.assertEqual(sub_b.grading_source, EssaySubmission.GradingSource.AI)
        self.assertEqual(EssayGradingCache.objects.count(), 2)

    def test_previously_graded_submission_keeps_working(self):
        legacy = EssaySubmission.objects.create(
            student=self.user_a,
            topic=self.topic,
            essay_text=ESSAY,
            word_count=len(ESSAY.split()),
            status=EssaySubmission.Status.GRADED,
            raw_result=FULL_GRADE,
            total_score=Decimal("20.0"),
            max_score=20,
            grading_source=EssaySubmission.GradingSource.AI,
        )
        self.assertTrue(essay_has_grade_result(legacy))
        self.assertEqual(legacy.grading_source, EssaySubmission.GradingSource.AI)
        self.assertIsNone(legacy.grading_cache_id)

    def test_task_passes_the_full_context_and_stamps_the_key(self):
        self.patch_grader()
        submission = self.submission(self.user_a)
        result = self.run_task(submission)
        submission.refresh_from_db()

        self.assertIn(result["status"], ("graded", "ok"))
        self.assertTrue(submission.grading_cache_key)
        self.assertEqual(
            submission.grading_cache_key, grading_cache_key_for_submission(submission),
        )

    def test_metrics_record_hits_reuses_and_avoided_requests(self):
        self.patch_grader()
        sub_a = self.submission(self.user_a)
        sub_b = self.submission(self.user_b)
        self.run_task(sub_a)
        self.run_task(sub_b)

        snapshot = metrics.snapshot()
        self.assertEqual(snapshot.get("essay_cache_hit"), 1)
        self.assertEqual(snapshot.get("essay_cache_ai_request"), 1)
        self.assertGreaterEqual(snapshot.get("essay_cache_leader_claimed", 0), 1)
        self.assertGreater(metrics.cache_hit_rate(), 0.0)
