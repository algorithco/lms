from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.essays.models import (
    EssayGradingCache,
    EssayRewriteCache,
    EssaySubmission,
)
from apps.essays.services import (
    _load_cached_grading_result,
    _essay_grading_cache_identity,
    generate_improved_essay,
    grade_essay,
)

VALID_GRADE = {
    "criteria": [
        {"id": i, "name": f"Criterion {i}", "score": 1.5, "reason": "OK"}
        for i in range(1, 13)
    ],
    "total_score": 18,
    "max_score": 24,
    "summary": "Good essay.",
    "topic_match": True,
    "topic_match_reason": "Relevant.",
}


@override_settings(
    ESSAY_AI_PROVIDER="openrouter",
    OPENROUTER_API_KEY="sk-or-v1-testcachekey00000000000000000000000000",
    ESSAY_AI_MODEL="cache-test-model",
    OPENROUTER_AI_MODEL="cache-test-model",
    OPENROUTER_FALLBACK_MODELS=[],
)
class EssayGradeCacheTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch("apps.essays.services._grade_via_llm", return_value=(VALID_GRADE.copy(), "cache-test-model"))
    @patch("apps.essays.services._get_llm_client")
    def test_same_essay_and_topic_reuses_cached_grade(self, client_factory, grader):
        client_factory.return_value = MagicMock()
        first = grade_essay("Same essay body", "Topic A")
        second = grade_essay("Same   essay body", "Topic A")

        self.assertFalse(first["_from_cache"])
        self.assertTrue(second["_from_cache"])
        self.assertEqual(second["total_score"], 18)
        grader.assert_called_once()
        self.assertEqual(EssayGradingCache.objects.get().hit_count, 2)

    @patch("apps.essays.services._grade_via_llm", return_value=(VALID_GRADE.copy(), "cache-test-model"))
    @patch("apps.essays.services._get_llm_client")
    def test_cache_separates_topics_and_grading_context(self, client_factory, grader):
        client_factory.return_value = MagicMock()
        grade_essay("Same essay body", "Topic A")
        grade_essay("Same essay body", "Topic B")
        self.assertEqual(grader.call_count, 2)
        self.assertEqual(EssayGradingCache.objects.count(), 2)

        base_key = _essay_grading_cache_identity("Essay", "Topic")[0]
        with override_settings(ESSAY_GRADING_CACHE_VERSION="next"):
            changed_key = _essay_grading_cache_identity("Essay", "Topic")[0]
        self.assertNotEqual(base_key, changed_key)

    def test_cached_grade_is_revalidated(self):
        """A cached payload that no longer validates is discarded, not served."""
        text_hash = _essay_grading_cache_identity("Essay", "Topic")[0]
        EssayGradingCache.objects.create(
            text_hash=text_hash,
            essay_text="Essay",
            raw_result={"criteria": [], "total_score": 18, "max_score": 24},
            total_score=Decimal("18"), max_score=24,
        )
        self.assertIsNone(_load_cached_grading_result(text_hash))
        self.assertFalse(EssayGradingCache.objects.filter(text_hash=text_hash).exists())

    @patch("apps.essays.services._essay_rewrite_cache_hash", return_value="rewrite-hash-test")
    @patch("apps.essays.services._is_mock_mode", return_value=True)
    @patch("apps.essays.services._get_ai_model")
    def test_rewrite_cache_reused_across_submissions_with_same_grade_context(
        self, get_model, is_mock, rewrite_hash,
    ):
        get_model.return_value = "rewrite-cache-model"
        user = User.objects.create_user(email="rewrite-cache@example.test", password="StrongPass123!")
        first = EssaySubmission.objects.create(
            student=user, essay_text="A long essay body about literature.",
            status=EssaySubmission.Status.GRADED,
            total_score=Decimal("18"), max_score=24,
            raw_result=VALID_GRADE, summary="Improve the arguments.",
        )
        second = EssaySubmission.objects.create(
            student=user, essay_text=first.essay_text,
            status=EssaySubmission.Status.GRADED,
            total_score=Decimal("18"), max_score=24,
            raw_result=VALID_GRADE, summary="Improve the arguments.",
        )

        first_content = generate_improved_essay(first)
        second_content = generate_improved_essay(second)

        self.assertEqual(first_content, second_content)
        self.assertEqual(EssayRewriteCache.objects.count(), 1)
        cached = EssayRewriteCache.objects.get()
        self.assertEqual(cached.hit_count, 2)
        second.refresh_from_db()
        self.assertEqual(second.improved_content, first_content)

    def test_rewrite_cache_is_keyed_by_full_grading_context(self):
        """Different grade context (summary) must not share a rewrite."""
        user = User.objects.create_user(email="rewrite-key@example.test", password="StrongPass123!")
        first = EssaySubmission.objects.create(
            student=user, essay_text="A long essay body about literature.",
            status=EssaySubmission.Status.GRADED,
            total_score=Decimal("18"), max_score=24,
            raw_result=VALID_GRADE, summary="Improve the arguments.",
        )
        second = EssaySubmission.objects.create(
            student=user, essay_text=first.essay_text,
            status=EssaySubmission.Status.GRADED,
            total_score=Decimal("18"), max_score=24,
            raw_result=VALID_GRADE, summary="Butunlay boshqa xulosa.",
        )
        from apps.essays.services import _essay_rewrite_cache_hash

        with patch("apps.essays.services._is_mock_mode", return_value=True), patch(
            "apps.essays.services._get_ai_model", return_value="rewrite-cache-model",
        ):
            self.assertNotEqual(
                _essay_rewrite_cache_hash(first),
                _essay_rewrite_cache_hash(second),
            )
