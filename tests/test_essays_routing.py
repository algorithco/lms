"""
Essays App — URL Routing Integration Tests

Tests that:
    1. All URL names resolve to the correct paths (no duplicate names)
    2. 12-mezon flow routes to the unified result view
    3. Legacy BMB flow routes to the same unified result view
    4. Unified result view renders the correct template per grading system
    5. Auth guards redirect anonymous users to login
    6. converted_score property works correctly
    7. submit-create redirects to essays:result after grading
"""
from __future__ import annotations

import json
import threading
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import TestCase, RequestFactory, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.essays.models import (
    AIEvaluation,
    EssayCriterionScore,
    EssaySubmission,
    EssayTopic,
)
from apps.essays.views import essay_improve_view, essay_result_view

User = get_user_model()


class ImprovedEssayEndpointTests(TestCase):
    """
    POST /essays/result/<id>/improve/ — AI yaxshilangan versiya endpointi.

    Covers: URL resolution, ownership, ungraded guard, caching (no
    re-generation), generation via mocked LLM, and error handling.
    """

    GRADED_RAW_RESULT = {
        "criteria": [
            {"id": i, "name": f"Criterion {i}", "score": 1.5, "reason": "ok"}
            for i in range(1, 13)
        ],
        "total_score": 18.0,
        "max_score": 24,
        "summary": "Yaxshi, lekin dalillar kuchsiz.",
    }

    def setUp(self) -> None:
        self.student = User.objects.create_user(
            email="improve@test.com",
            password="testpass123",
            first_name="Im",
            last_name="Prove",
            role="student",
        )
        self.other = User.objects.create_user(
            email="other@test.com",
            password="testpass123",
            first_name="Other",
            last_name="User",
            role="student",
        )
        self.sub = EssaySubmission.objects.create(
            student=self.student,
            essay_text="Kitob o'qish foydali. Men kitob yaxshi ko'raman.",
            status=EssaySubmission.Status.GRADED,
            total_score=Decimal("18.0"),
            max_score=24,
            raw_result=self.GRADED_RAW_RESULT,
            summary="Yaxshi, lekin dalillar kuchsiz.",
        )
        self.url = reverse("essays:improve", kwargs={"submission_id": self.sub.id})

    def _post(self, user=None) -> object:
        request = RequestFactory().post(self.url)
        request.user = user or self.student
        return essay_improve_view(request, submission_id=self.sub.id)

    def test_url_resolves(self) -> None:
        self.assertEqual(self.url, f"/essays/result/{self.sub.id}/improve/")

    def test_get_not_allowed(self) -> None:
        request = RequestFactory().get(self.url)
        request.user = self.student
        resp = essay_improve_view(request, submission_id=self.sub.id)
        self.assertEqual(resp.status_code, 405)

    def test_other_user_gets_404(self) -> None:
        with self.assertRaises(Http404):
            self._post(user=self.other)

    def test_ungraded_submission_rejected(self) -> None:
        self.sub.status = EssaySubmission.Status.DRAFT
        self.sub.save()
        resp = self._post()
        self.assertEqual(resp.status_code, 400)
        data = json.loads(resp.content)
        self.assertFalse(data["ok"])

    @patch("apps.essays.services.generate_improved_essay")
    def test_success_returns_content(self, mock_gen: MagicMock) -> None:
        mock_gen.return_value = "Yaxshilangan esse matni bu yerda turadi."
        resp = self._post()
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["ok"])
        self.assertEqual(data["content"], "Yaxshilangan esse matni bu yerda turadi.")

    def test_cached_second_call_skips_regeneration(self) -> None:
        """When improved_content exists, the LLM chain must not be called."""
        self.sub.improved_content = "Allaqachon yaratilgan versiya."
        self.sub.improved_at = timezone.now()
        self.sub.save()

        with patch("apps.essays.services._chat_with_fallback") as mock_chat:
            resp = self._post()

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data["ok"])
        self.assertFalse(data["improved"])  # cache hit, not freshly generated
        self.assertEqual(data["content"], "Allaqachon yaratilgan versiya.")
        mock_chat.assert_not_called()  # no LLM call — served from DB

    @patch("apps.essays.services.generate_improved_essay")
    def test_generation_error_maps_to_502(self, mock_gen: MagicMock) -> None:
        mock_gen.side_effect = ValueError("API xatolik: 429")
        resp = self._post()
        self.assertEqual(resp.status_code, 502)
        data = json.loads(resp.content)
        self.assertFalse(data["ok"])

    def test_service_generates_and_persists(self) -> None:
        """generate_improved_essay() calls the LLM and saves improved_content."""
        from apps.essays.services import generate_improved_essay

        fake_response = MagicMock()
        fake_response.choices[0].message.content = (
            "Kitob o'qish inson tafakkurini yuksaltiradi va dunyoqarashini boyitadi. "
            "Bu esa o'smirning shaxsiy kamolotiga bevosita xizmat qiladi. "
            "Xulosa qilib aytganda, kitob — eng sadoqatli usto va do'stdir."
        )

        with patch(
            "apps.essays.services._get_llm_client"
        ) as mock_client, patch(
            "apps.essays.services._chat_with_fallback"
        ) as mock_chat:
            mock_client.return_value = MagicMock()
            mock_chat.return_value = (fake_response, "test-model:free")

            content = generate_improved_essay(
                EssaySubmission.objects.get(pk=self.sub.pk)
            )

        self.assertIn("tafakkurini", content)
        sub = EssaySubmission.objects.get(pk=self.sub.pk)
        self.assertEqual(sub.improved_content, content)
        self.assertIsNotNone(sub.improved_at)

    def test_service_idempotent_when_cached(self) -> None:
        from apps.essays.services import generate_improved_essay

        self.sub.improved_content = "Saqlangan versiya."
        self.sub.save()
        content = generate_improved_essay(EssaySubmission.objects.get(pk=self.sub.pk))
        self.assertEqual(content, "Saqlangan versiya.")


class URLReverseResolutionTests(TestCase):
    """Verify that every essays URL name resolves to the expected path."""

    def test_result_url(self) -> None:
        url = reverse("essays:result", kwargs={"submission_id": 42})
        self.assertEqual(url, "/essays/result/42/")

    def test_submit_new_url(self) -> None:
        url = reverse("essays:submit-new")
        self.assertEqual(url, "/essays/submit/")

    def test_topics_url(self) -> None:
        url = reverse("essays:topics")
        self.assertEqual(url, "/essays/")

    def test_write_url(self) -> None:
        url = reverse("essays:write", kwargs={"submission_id": 7})
        self.assertEqual(url, "/essays/write/7/")

    def test_password_gate_url(self) -> None:
        url = reverse("essays:password-gate", kwargs={"topic_id": 7})
        self.assertEqual(url, "/essays/7/start/")

    def test_autosave_url(self) -> None:
        url = reverse("essays:autosave")
        self.assertEqual(url, "/essays/api/autosave/")

    def test_legacy_submit_url(self) -> None:
        url = reverse("essays:submit", kwargs={"submission_id": 10})
        self.assertEqual(url, "/essays/10/submit/")

    def test_request_review_url(self) -> None:
        url = reverse("essays:request-review", kwargs={"submission_id": 10})
        self.assertEqual(url, "/essays/10/request-review/")

    def test_teacher_queue_url(self) -> None:
        url = reverse("essays:teacher-queue")
        self.assertEqual(url, "/essays/teacher/queue/")

    def test_teacher_review_url(self) -> None:
        url = reverse("essays:teacher-review", kwargs={"submission_id": 5})
        self.assertEqual(url, "/essays/teacher/5/review/")

    def test_teacher_submit_review_url(self) -> None:
        url = reverse("essays:teacher-submit-review", kwargs={"submission_id": 5})
        self.assertEqual(url, "/essays/teacher/5/submit-review/")

    def test_no_duplicate_result_names(self) -> None:
        """There must be exactly ONE URL named 'result' — no shadowing."""
        from apps.essays.urls import urlpatterns

        result_routes = [p for p in urlpatterns if p.name == "result"]
        self.assertEqual(
            len(result_routes), 1,
            f"Expected 1 'result' URL, found {len(result_routes)}: {result_routes}",
        )

    def test_no_duplicate_submit_names(self) -> None:
        """'submit' (legacy) and 'submit-new' must be distinct names."""
        from apps.essays.urls import urlpatterns

        names = [p.name for p in urlpatterns]
        self.assertIn("submit", names)
        self.assertIn("submit-new", names)
        # They must resolve to different paths
        self.assertNotEqual(
            reverse("essays:submit", kwargs={"submission_id": 1}),
            reverse("essays:submit-new"),
        )


class AuthGuardTests(TestCase):
    """Unauthenticated users must be redirected to LOGIN_URL."""

    def setUp(self) -> None:
        self.login_url = reverse("web:login")

    def test_result_redirects_anonymous(self) -> None:
        url = reverse("essays:result", kwargs={"submission_id": 1})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_submit_new_redirects_anonymous(self) -> None:
        url = reverse("essays:submit-new")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_topics_redirects_anonymous(self) -> None:
        url = reverse("essays:topics")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_write_redirects_anonymous(self) -> None:
        url = reverse("essays:write", kwargs={"submission_id": 1})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_teacher_queue_redirects_anonymous(self) -> None:
        url = reverse("essays:teacher-queue")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)


class ConvertedScorePropertyTests(TestCase):
    """Verify the converted_score property on EssaySubmission."""

    def test_full_score(self) -> None:
        sub = EssaySubmission(total_score=Decimal("24.0"), max_score=24)
        self.assertEqual(sub.converted_score, 75)

    def test_zero_score(self) -> None:
        sub = EssaySubmission(total_score=Decimal("0.0"), max_score=24)
        self.assertEqual(sub.converted_score, 0)

    def test_partial_score(self) -> None:
        sub = EssaySubmission(total_score=Decimal("19.0"), max_score=24)
        # 19/24 * 75 = 59.375 → 59
        self.assertEqual(sub.converted_score, 59)

    def test_none_total_score(self) -> None:
        sub = EssaySubmission(total_score=None, max_score=24)
        self.assertIsNone(sub.converted_score)

    def test_zero_max_score(self) -> None:
        sub = EssaySubmission(total_score=Decimal("10.0"), max_score=0)
        self.assertIsNone(sub.converted_score)

    @override_settings(ESSAY_TARGET_SCALE=100)
    def test_custom_target_scale(self) -> None:
        sub = EssaySubmission(total_score=Decimal("18.0"), max_score=24)
        # 18/24 * 100 = 75
        self.assertEqual(sub.converted_score, 75)

    def test_score_percentage(self) -> None:
        sub = EssaySubmission(total_score=Decimal("19.0"), max_score=24)
        self.assertEqual(sub.score_percentage, 79.2)

    def test_is_passed(self) -> None:
        sub = EssaySubmission(total_score=Decimal("15.0"), max_score=24)
        # 15/24 = 62.5% >= 60 → True
        self.assertTrue(sub.is_passed)

    def test_is_not_passed(self) -> None:
        sub = EssaySubmission(total_score=Decimal("13.0"), max_score=24)
        # 13/24 = 54.2% < 60 → False
        self.assertFalse(sub.is_passed)


class UnifiedResultViewTests(TestCase):
    """
    The unified essay_result_view must:
    - Render 'result.html' for 12-mezon submissions (with criteria)
    - Render 'essay_result.html' for legacy BMB submissions (with AIEvaluation)
    """

    def setUp(self) -> None:
        self.student = User.objects.create_user(
            email="student@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Student",
            role="student",
        )
        self.factory = RequestFactory()

    def _make_request(self, submission_id: int) -> MagicMock:
        """Create a fake GET request as self.student."""
        request = self.factory.get(f"/essays/result/{submission_id}/")
        request.user = self.student
        return request

    @patch("apps.essays.views.render")
    def test_new_12mezon_uses_result_template(self, mock_render: MagicMock) -> None:
        """Submission with EssayCriterionScore → 'result.html' template."""
        sub = EssaySubmission.objects.create(
            student=self.student,
            essay_text="Test essay text.",
            status=EssaySubmission.Status.GRADED,
            total_score=Decimal("19.0"),
            max_score=24,
        )
        # Create 12 criteria
        for i in range(1, 13):
            EssayCriterionScore.objects.create(
                submission=sub,
                criterion_id=i,
                name=f"Criterion {i}",
                score=Decimal("1.5"),
            )

        request = self._make_request(sub.id)
        essay_result_view(request, submission_id=sub.id)

        mock_render.assert_called_once()
        args = mock_render.call_args
        template = args[0][1] if len(args[0]) > 1 else args[1][0]
        context = args[0][2] if len(args[0]) > 2 else args[1][1]

        self.assertEqual(template, "essays/result.html")
        self.assertIn("criteria", context)
        self.assertEqual(len(context["criteria"]), 12)
        self.assertEqual(context["submission"].id, sub.id)

    @patch("apps.essays.views.render")
    def test_new_12mezon_max_score_24_uses_result_template(
        self, mock_render: MagicMock
    ) -> None:
        """Even without criteria, max_score=24 → 'result.html' (new system)."""
        sub = EssaySubmission.objects.create(
            student=self.student,
            essay_text="Test essay text.",
            status=EssaySubmission.Status.GRADED,
            total_score=Decimal("15.0"),
            max_score=24,
            # No EssayCriterionScore created
        )

        request = self._make_request(sub.id)
        essay_result_view(request, submission_id=sub.id)

        mock_render.assert_called_once()
        template = mock_render.call_args[0][1]
        self.assertEqual(template, "essays/result.html")

    @patch("apps.essays.views.render")
    def test_legacy_bmb_uses_essay_result_template(self, mock_render: MagicMock) -> None:
        """Legacy submission (no criteria, max_score != 24) → 'essay_result.html'."""
        sub = EssaySubmission.objects.create(
            student=self.student,
            essay_text="Legacy essay text.",
            status=EssaySubmission.Status.AI_EVALUATED,
            total_score=Decimal("22.0"),
            max_score=30,  # Legacy 30-point BMB
        )
        # Create legacy AIEvaluation
        AIEvaluation.objects.create(
            submission=sub,
            criteria_scores={
                "topic_coverage": 8,
                "argumentation": 6,
                "grammar_spelling": 5,
                "style_vocabulary": 3,
            },
            total_score=Decimal("22.00"),
            feedback_text="Yaxshi esse!",
        )

        request = self._make_request(sub.id)
        essay_result_view(request, submission_id=sub.id)

        mock_render.assert_called_once()
        template = mock_render.call_args[0][1]
        self.assertEqual(template, "essays/essay_result.html")

    @patch("apps.essays.views.render")
    def test_result_view_shows_converted_score(self, mock_render: MagicMock) -> None:
        """12-mezon result view includes converted_score context."""
        sub = EssaySubmission.objects.create(
            student=self.student,
            essay_text="Test essay.",
            status=EssaySubmission.Status.GRADED,
            total_score=Decimal("19.0"),
            max_score=24,
        )
        for i in range(1, 13):
            EssayCriterionScore.objects.create(
                submission=sub,
                criterion_id=i,
                name=f"Criterion {i}",
                score=Decimal("1.5"),
            )

        request = self._make_request(sub.id)
        essay_result_view(request, submission_id=sub.id)

        context = mock_render.call_args[0][2]
        self.assertEqual(context["submission"].converted_score, 59)

    def test_result_view_404_for_other_student(self) -> None:
        """Student A cannot view Student B's submission."""
        other_student = User.objects.create_user(
            email="other@test.com",
            password="testpass123",
            role="student",
        )
        sub = EssaySubmission.objects.create(
            student=other_student,
            essay_text="Other student essay.",
            status=EssaySubmission.Status.GRADED,
            total_score=Decimal("10.0"),
            max_score=24,
        )

        self.client.login(email="student@test.com", password="testpass123")
        url = reverse("essays:result", kwargs={"submission_id": sub.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    def test_result_view_404_for_nonexistent(self) -> None:
        """Non-existent submission returns 404."""
        self.client.login(email="student@test.com", password="testpass123")
        url = reverse("essays:result", kwargs={"submission_id": 99999})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)


class LegacyFlowRoutingTests(TestCase):
    """
    Verify the legacy topic-based flow:
    topics → write → submit → (result page via unified view)
    """

    def setUp(self) -> None:
        self.student = User.objects.create_user(
            email="student@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Student",
            role="student",
        )
        self.teacher = User.objects.create_user(
            email="teacher@test.com",
            password="testpass123",
            first_name="Teacher",
            last_name="User",
            role="teacher",
        )
        self.topic = EssayTopic.objects.create(
            title="Ona tili mavzusi",
            description="Esse yozing",
            word_limit_min=50,
            word_limit_max=500,
            created_by=self.teacher,
        )

    def test_password_gate_creates_draft_submission(self) -> None:
        """Password gate creates a DRAFT submission and redirects to write page."""
        self.client.login(email="student@test.com", password="testpass123")
        url = reverse("essays:password-gate", kwargs={"topic_id": self.topic.id})
        resp = self.client.get(url, follow=True)
        self.assertEqual(resp.status_code, 200)

        sub = EssaySubmission.objects.get(student=self.student, topic=self.topic)
        self.assertEqual(sub.status, EssaySubmission.Status.DRAFT)

    def test_legacy_submit_requires_post(self) -> None:
        """GET on submit endpoint should return 405 (Method Not Allowed)."""
        sub = EssaySubmission.objects.create(
            student=self.student,
            topic=self.topic,
            essay_text="Some text.",
            status=EssaySubmission.Status.DRAFT,
        )
        self.client.login(email="student@test.com", password="testpass123")
        url = reverse("essays:submit", kwargs={"submission_id": sub.id})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 405)


class NewFlowRoutingTests(TransactionTestCase):
    """
    Verify the new 12-mezon flow:
    submit-new (GET → form, POST → grade) → redirect to result

    TransactionTestCase: start_grading() baholashni background thread'da
    ishga tushiradi — thread o'z DB ulanishida yozadi, TestCase atomic
    izolyatsiyasi ichidan bu ko'rinmasdi (va sqlite lock berardi).
    """

    def setUp(self) -> None:
        self.student = User.objects.create_user(
            email="student@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Student",
            role="student",
        )

    def _join_grading_threads(self, timeout: float = 20.0) -> None:
        """start_grading() ochgan background thread'larni kutib olish."""
        for t in threading.enumerate():
            if t.name and t.name.startswith("essay-grade-"):
                t.join(timeout=timeout)

    def test_submit_new_get_returns_form(self) -> None:
        """GET on submit-new shows the essay form."""
        self.client.login(email="student@test.com", password="testpass123")
        url = reverse("essays:submit-new")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    @patch("apps.essays.services.grade_essay")
    def test_submit_new_post_redirects_to_result(self, mock_grade: MagicMock) -> None:
        """POST on submit-new grades and redirects to essays:result."""
        mock_grade.return_value = {
            "criteria": [
                {"id": i, "name": f"Criterion {i}", "score": 1.5, "reason": "OK"}
                for i in range(1, 13)
            ],
            "total_score": 18.0,
            "max_score": 24,
            "summary": "Yaxshi!",
        }

        self.client.login(email="student@test.com", password="testpass123")
        url = reverse("essays:submit-new")
        resp = self.client.post(url, {"essay_text": "Bu test esse matni." * 10})
        self._join_grading_threads()

        self.assertEqual(resp.status_code, 302)
        self.assertIn("/essays/result/", resp.url)

        # Verify the redirect URL is essays:result
        sub = EssaySubmission.objects.filter(student=self.student).latest("id")
        expected = reverse("essays:result", kwargs={"submission_id": sub.id})
        self.assertEqual(resp.url, expected)

    @patch("apps.essays.services.grade_essay")
    def test_submit_new_creates_12_criteria(self, mock_grade: MagicMock) -> None:
        """After grading, 12 EssayCriterionScore records must exist."""
        mock_grade.return_value = {
            "criteria": [
                {"id": i, "name": f"Criterion {i}", "score": 2.0, "reason": "Perfect"}
                for i in range(1, 13)
            ],
            "total_score": 24.0,
            "max_score": 24,
            "summary": "A'lo!",
        }

        self.client.login(email="student@test.com", password="testpass123")
        url = reverse("essays:submit-new")
        self.client.post(url, {"essay_text": "To'liq esse matni " * 20})
        self._join_grading_threads()

        sub = EssaySubmission.objects.filter(student=self.student).latest("id")
        criteria = sub.criteria.all()
        self.assertEqual(criteria.count(), 12)
        self.assertEqual(sub.total_score, Decimal("24.0"))
        self.assertEqual(sub.max_score, 24)
        self.assertEqual(sub.status, EssaySubmission.Status.GRADED)

    @patch("apps.essays.services.grade_essay")
    def test_submit_new_regrading_clears_old_criteria(
        self, mock_grade: MagicMock
    ) -> None:
        """Re-grading an essay must delete old criteria before creating new ones."""
        mock_grade.return_value = {
            "criteria": [
                {"id": i, "name": f"Criterion {i}", "score": 1.0, "reason": "OK"}
                for i in range(1, 13)
            ],
            "total_score": 12.0,
            "max_score": 24,
            "summary": "O'rtacha",
        }

        self.client.login(email="student@test.com", password="testpass123")
        url = reverse("essays:submit-new")

        # First submission
        self.client.post(url, {"essay_text": "Birinchi marta " * 20})
        self._join_grading_threads()
        sub = EssaySubmission.objects.filter(student=self.student).latest("id")
        self.assertEqual(sub.criteria.count(), 12)

        # Second submission (re-grading the same essay_text creates new submission)
        mock_grade.return_value["total_score"] = 16.0
        mock_grade.return_value["summary"] = "Yaxshiroq"
        self.client.post(url, {"essay_text": "Ikkinchi marta " * 20})
        self._join_grading_threads()
        sub2 = EssaySubmission.objects.filter(student=self.student).latest("id")
        self.assertEqual(sub2.criteria.count(), 12)
        # Must be a different submission (new one, not overwriting)
        self.assertNotEqual(sub.id, sub2.id)


class TemplateContainsScoreTests(TestCase):
    """
    Verify that templates render converted_score and 12-criteria correctly.
    These are end-to-end tests using the Django test client.
    """

    def setUp(self) -> None:
        self.student = User.objects.create_user(
            email="student@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Student",
            role="student",
        )
        self.client.login(email="student@test.com", password="testpass123")

    def test_result_page_shows_12_criteria(self) -> None:
        """The result.html page must show all 12 criteria rows."""
        sub = EssaySubmission.objects.create(
            student=self.student,
            essay_text="Test essay.",
            status=EssaySubmission.Status.GRADED,
            total_score=Decimal("19.0"),
            max_score=24,
            summary="Yaxshi natija.",
        )
        names = [
            "Uslub", "Ikkala qarash va shaxsiy fikr",
            "Dalillar bilan asoslanganlik", "Kirish/asosiy qism/xulosa",
            "Mantiqiy-qurilish", "Mantiqiy-mazmuniy izchillik",
            "Imlo xatolari", "Punktuatsiya xatolari",
            "Qo'shimcha qo'llash xatolari", "So'z qo'llash uslubiy xatolari",
            "Leksik xilma-xillik", "Sheva/vulgarizm/parazit so'zlar",
        ]
        for i, name in enumerate(names, 1):
            EssayCriterionScore.objects.create(
                submission=sub,
                criterion_id=i,
                name=name,
                score=Decimal("1.5"),
            )

        url = reverse("essays:result", kwargs={"submission_id": sub.id})
        resp = self.client.get(url)
        content = resp.content.decode()

        # Check all 12 criterion names appear in the page
        # Django auto-escapes ' to &#x27; in HTML, so we search with both forms
        import html as html_module
        for name in names:
            escaped_name = html_module.escape(name)
            self.assertTrue(
                name in content or escaped_name in content,
                f"Criterion '{name}' not found in result page",
            )

        # Check total score display
        self.assertIn("19.0", content)
        self.assertIn("24", content)

        # Check converted score display
        self.assertIn("59", content)  # 19/24*75 ≈ 59

    def test_result_page_shows_score_percentage(self) -> None:
        """Score percentage bar should be present."""
        sub = EssaySubmission.objects.create(
            student=self.student,
            essay_text="Test essay.",
            status=EssaySubmission.Status.GRADED,
            total_score=Decimal("18.0"),
            max_score=24,
        )
        url = reverse("essays:result", kwargs={"submission_id": sub.id})
        resp = self.client.get(url)
        content = resp.content.decode()
        # 18/24*100 = 75.0%
        self.assertIn("75.0", content)

    def test_result_page_error_status_shows_error(self) -> None:
        """Error status submissions should show error message."""
        sub = EssaySubmission.objects.create(
            student=self.student,
            essay_text="Test essay.",
            status=EssaySubmission.Status.ERROR,
            error_message="Baholashda xatolik",
        )
        url = reverse("essays:result", kwargs={"submission_id": sub.id})
        resp = self.client.get(url)
        content = resp.content.decode()
        self.assertIn("Baholashda xatolik", content)
