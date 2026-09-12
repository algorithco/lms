"""
Asinxron esse baholash testlari — Cloudflare 502 regression suite.

502 Bad Gateway ildiz sababi: submit request'i sinxron grade_essay()
(30–90s LLM chaqiruvi)ni kutardi. Bu fayl quyidagi kontraktlarni tekshiradi:

    1. Submit view DARHOL qaytadi — request path'da LLM chaqiruvi YO'Q.
    2. Broker (Celery/Redis) tushsa ham request bloklanmaydi — background
       thread fallback ishlaydi.
    3. Thread retry'lari tugagach submission PENDING'da qotib qolmaydi
       (ERROR bo'ladi).
    4. Baholash tugagach o'quvchiga Telegram xabari yuboriladi.
    5. Polling status endpoint'i to'g'ri shartnomani qaytaradi.
    6. TMA submit API 202 "processing" qaytaradi.

MUHIM: thread fallback testlari TransactionTestCase'da bo'lishi SHART —
thread alohida DB ulanishida ishlaydi va TestCase'nin atomic tranzaksiyasi
ichida yozilgan qatorlarni ko'ra olmaydi (yoki sqlite lock'ga tushadi).
"""
from __future__ import annotations

import threading
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.essays.models import EssaySubmission, EssayTopic
from apps.notifications.models import NotificationLog

MOCK_GRADE = {
    "criteria": [
        {"id": i, "name": f"Criterion {i}", "score": 1.5, "reason": "OK"}
        for i in range(1, 13)
    ],
    "total_score": 18.0,
    "max_score": 24,
    "summary": "Yaxshi esse.",
    "topic_match": True,
    "topic_match_reason": "",
}

# Thread fallback retry backoff — testlarda tez bo'lishi uchun.
FAST_BACKOFF = (0.01, 0.01, 0.01)


class AsyncGradingFixtureMixin:
    """Student + faol mavzu fixture'asi (TestCase va TransactionTestCase uchun umumiy)."""

    def setUp(self) -> None:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.student = User.objects.create_user(
            email="student@test.com",
            password="testpass123",
            first_name="Test",
            last_name="Student",
            role="student",
        )
        self.topic = EssayTopic.objects.create(
            title="Test mavzu",
            description="Test tavsif",
            word_limit_min=20,
            word_limit_max=500,
            time_limit_minutes=60,
        )
        self.submission = EssaySubmission.objects.create(
            student=self.student,
            topic=self.topic,
            status=EssaySubmission.Status.DRAFT,
            essay_text="Bu test uchun yozilgan yetarlicha uzun esse matni " * 5,
            word_count=50,
        )
        self.submit_url = reverse(
            "essays:submit", kwargs={"submission_id": self.submission.id},
        )

    def _join_grading_thread(self, timeout: float = 20.0):
        """start_thread_grading ochgan thread'ni kutib olish (determinizm)."""
        for t in threading.enumerate():
            if t.name == f"essay-grade-{self.submission.id}":
                t.join(timeout=timeout)
                return t
        return None


class AsyncGradingBaseTestCase(AsyncGradingFixtureMixin, TestCase):
    """Thread ishlatmaydigan testlar uchun oddiy baza."""


class SubmitImmediateResponseTests(AsyncGradingBaseTestCase):
    """Broker ishlab turganda: submit darhol qaytadi, task queue qilinadi."""

    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.student)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("apps.essays.tasks.grade_submission_task")
    def test_submit_returns_immediately_with_pending_status(
        self, mock_task: MagicMock,
    ) -> None:
        """Broker ishlab tursa: task queue qilinadi, view darhol qaytadi."""
        mock_task.delay.return_value = MagicMock()

        resp = self.client.post(self.submit_url)

        self.assertEqual(resp.status_code, 200)
        mock_task.delay.assert_called_once_with(
            self.submission.id, fail_status=EssaySubmission.Status.ERROR,
        )
        mock_task.apply.assert_not_called()  # thread fallback ishga tushmagan

        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, EssaySubmission.Status.PENDING)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("apps.essays.tasks.grade_submission_task")
    def test_submit_never_calls_grade_essay_in_request_path(
        self, mock_task: MagicMock,
    ) -> None:
        """Request path'da sinxron grade_essay() chaqiruvi bo'lishi MUMKIN EMAS."""
        with patch("apps.essays.services.grade_essay") as mock_grade:
            self.client.post(self.submit_url)
            mock_grade.assert_not_called()


class ThreadFallbackTests(AsyncGradingFixtureMixin, TransactionTestCase):
    """Redis tushgan holat: background thread fallback.

    TransactionTestCase: thread alohida DB ulanishida yozadi — TestCase
    atomic bloki ichidan bu ko'rinmas edi (sqlite "table is locked").
    """

    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.student)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("apps.essays.tasks.grade_submission_task")
    def test_submit_thread_fallback_when_broker_down(
        self, mock_task: MagicMock,
    ) -> None:
        """Redis tushgan: delay xato beradi → background thread fallback."""
        mock_task.delay.side_effect = Exception("broker down")
        mock_task.apply.return_value = MagicMock()  # thread'da muvaffaqiyatli

        resp = self.client.post(self.submit_url)

        self.assertEqual(resp.status_code, 200)
        mock_task.delay.assert_called_once()
        self._join_grading_thread()

        mock_task.apply.assert_called_once_with(
            args=[self.submission.id],
            kwargs={"fail_status": EssaySubmission.Status.ERROR},
        )

    @override_settings(ESSAY_THREAD_RETRY_BACKOFF=FAST_BACKOFF, CELERY_TASK_ALWAYS_EAGER=False)
    @patch("apps.essays.tasks.grade_submission_task")
    def test_thread_fallback_marks_error_after_exhausted_retries(
        self, mock_task: MagicMock,
    ) -> None:
        """Retry'lar tugagach submission PENDING'da qotmasligi kerak.

        _mark_grading_failed MOCK qilinmaydi — haqiqiy funksiya thread'da
        ishlab statusni ERROR ga o'tkazishini tekshiramiz.
        """
        mock_task.delay.side_effect = Exception("broker down")
        mock_task.apply.side_effect = Exception("LLM ishlamadi")

        resp = self.client.post(self.submit_url)
        self.assertEqual(resp.status_code, 200)

        thread = self._join_grading_thread()
        self.assertIsNotNone(thread, "Background thread ishga tushmagan")

        self.assertEqual(mock_task.apply.call_count, 3)  # 3 urinish

        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, EssaySubmission.Status.ERROR)
        self.assertIn("LLM ishlamadi", self.submission.error_message)


class GradeTaskNotificationTests(AsyncGradingBaseTestCase):
    """Baholash tugagach Telegram bildirishnomasi."""

    def test_grade_task_notifies_student_on_graded(self) -> None:
        """Task GRADED qilganda NotificationLog (telegram) yoziladi."""
        from apps.essays.tasks import grade_submission_task

        class FakeHTTPResponse:
            status_code = 200

            def json(self) -> dict:
                return {"ok": True, "result": {"message_id": 42}}

        class FakeClient:
            def __init__(self, *args, **kwargs) -> None:
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args) -> None:
                return None

            def post(self, *args, **kwargs) -> FakeHTTPResponse:
                return FakeHTTPResponse()

        with (
            patch("apps.essays.services.grade_essay", return_value=MOCK_GRADE),
            patch(
                "apps.notifications.services.telegram_service.httpx.Client",
                FakeClient,
            ),
            override_settings(TELEGRAM_BOT_TOKEN="123456:TEST-TOKEN"),
        ):
            self.student.telegram_chat_id = 123456789
            self.student.telegram_identity_verified_at = timezone.now()
            self.student.save(update_fields=[
                "telegram_chat_id", "telegram_identity_verified_at",
            ])

            grade_submission_task.apply(
                args=[self.submission.id],
                kwargs={"fail_status": EssaySubmission.Status.ERROR},
            )

        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, EssaySubmission.Status.GRADED)
        self.assertEqual(self.submission.total_score, Decimal("18.0"))

        log = NotificationLog.objects.filter(
            notification_type="essay_graded",
            recipient=self.student,
            channel=NotificationLog.Channel.TELEGRAM,
        ).first()
        self.assertIsNotNone(log, "Telegram bildirishnomasi yozilmagan")
        self.assertEqual(log.status, NotificationLog.Status.SENT)

    def test_notification_skipped_without_telegram(self) -> None:
        """telegram_chat_id yo'q bo'lsa — xato emas, shunchaki o'tkazib yuboriladi."""
        from apps.essays.tasks import grade_submission_task

        with (
            patch("apps.essays.services.grade_essay", return_value=MOCK_GRADE),
        ):
            grade_submission_task.apply(
                args=[self.submission.id],
                kwargs={"fail_status": EssaySubmission.Status.ERROR},
            )

        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, EssaySubmission.Status.GRADED)
        self.assertFalse(
            NotificationLog.objects.filter(
                notification_type="essay_graded", recipient=self.student,
            ).exists(),
        )


class StatusEndpointTests(AsyncGradingBaseTestCase):
    """GET /essays/api/<id>/status/ polling shartnomasi."""

    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.student)
        self.status_url = reverse(
            "essays:grading-status", kwargs={"submission_id": self.submission.id},
        )

    def test_pending_returns_poll_after(self) -> None:
        self.submission.status = EssaySubmission.Status.PENDING
        self.submission.save(update_fields=["status"])

        resp = self.client.get(self.status_url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["poll_after"], 3)

    def test_graded_returns_result_url(self) -> None:
        self.submission.status = EssaySubmission.Status.GRADED
        self.submission.total_score = Decimal("18.0")
        self.submission.max_score = 24
        self.submission.save(update_fields=["status", "total_score", "max_score"])

        data = self.client.get(self.status_url).json()
        self.assertEqual(data["status"], "graded")
        self.assertIn("result_url", data)
        self.assertEqual(data["total_score"], 18.0)

    def test_error_returns_message(self) -> None:
        self.submission.status = EssaySubmission.Status.ERROR
        self.submission.error_message = "LLM xatosi"
        self.submission.save(update_fields=["status", "error_message"])

        data = self.client.get(self.status_url).json()
        self.assertEqual(data["status"], "error")
        self.assertIn("LLM xatosi", data["error"])

    def test_requires_authentication(self) -> None:
        self.client.logout()
        resp = self.client.get(self.status_url)
        self.assertEqual(resp.status_code, 302)  # login sahifasiga redirect


class TMASubmitAsyncTests(AsyncGradingBaseTestCase):
    """TMA (Telegram Mini App) submit API — 202 processing shartnomasi."""

    def setUp(self) -> None:
        super().setUp()
        from rest_framework.test import APIClient

        self.api = APIClient()
        self.api.force_authenticate(user=self.student)
        self.tma_url = reverse(
            "telegram_app:essay-submit", kwargs={"submission_id": self.submission.id},
        )

    @patch("apps.essays.services.start_grading")
    def test_tma_submit_returns_processing(self, mock_start: MagicMock) -> None:
        mock_start.return_value = {"success": True, "async": True, "mode": "celery"}

        resp = self.api.post(
            self.tma_url, {"essay_text": "Yetarlicha uzun test esse matni " * 5},
        )

        self.assertEqual(resp.status_code, 202)
        data = resp.json()
        self.assertEqual(data["status"], "processing")
        self.assertEqual(data["poll_after"], 3)
        self.assertIn("result_url", data)

        mock_start.assert_called_once()

    @patch("apps.essays.services.start_grading")
    def test_tma_submit_rejects_double_submit_while_pending(
        self, mock_start: MagicMock,
    ) -> None:
        self.submission.status = EssaySubmission.Status.PENDING
        self.submission.save(update_fields=["status"])

        resp = self.api.post(
            self.tma_url, {"essay_text": "Ikkinchi marta yuborish urinishi " * 5},
        )
        self.assertEqual(resp.status_code, 202)
        mock_start.assert_not_called()  # ikkinchi task queue qilinmadi

    def test_tma_result_includes_poll_hint_while_pending(self) -> None:
        self.submission.status = EssaySubmission.Status.PENDING
        self.submission.save(update_fields=["status"])

        result_url = reverse(
            "telegram_app:essay-result", kwargs={"submission_id": self.submission.id},
        )
        data = self.api.get(result_url).json()
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["poll_after"], 3)

    @patch("apps.essays.services.start_grading")
    def test_tma_resubmit_after_error_requeues_grading(
        self, mock_start: MagicMock,
    ) -> None:
        """ERROR holatda (AI timeout) TMA qayta yuborishda queue qilinadi.

        Status ERROR'ni PENDING'ga o'tkazish real start_async_grading'da
        (ResubmitTests'da tekshirilgan); view kontrakti — ERROR esseni ham
        start_grading'ga uzatib, 202 processing qaytarish.
        """
        mock_start.return_value = {"success": True, "async": True, "mode": "celery"}
        self.submission.status = EssaySubmission.Status.ERROR
        self.submission.error_message = "API timeout"
        self.submission.save(update_fields=["status", "error_message"])

        resp = self.api.post(
            self.tma_url, {"essay_text": "Yetarlicha uzun test esse matni " * 5},
        )
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.json()["status"], "processing")
        mock_start.assert_called_once()
        submitted_essay = mock_start.call_args.args[0]
        self.assertEqual(submitted_essay.status, EssaySubmission.Status.ERROR)
        self.assertEqual(
            submitted_essay.essay_text.strip(),
            ("Yetarlicha uzun test esse matni " * 5).strip(),
        )


class StartGradingModeTests(AsyncGradingFixtureMixin, TransactionTestCase):
    """start_grading() dispatch qatlami.

    TransactionTestCase: thread fallback DB'ga alohida ulanish orqali yozadi,
    TestCase'nin atomic tranzaksiya izolyatsiyasi thread ichidan ko'rinmaydi.
    """

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("apps.essays.tasks.grade_submission_task")
    def test_mode_celery_when_broker_up(self, mock_task: MagicMock) -> None:
        from apps.essays.services import start_grading

        mock_task.delay.return_value = MagicMock()
        result = start_grading(self.submission)
        self.assertEqual(result["mode"], "celery")
        self.assertTrue(result["async"])

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("apps.essays.tasks.grade_submission_task")
    def test_mode_thread_when_broker_down(self, mock_task: MagicMock) -> None:
        from apps.essays.services import start_grading

        mock_task.delay.side_effect = Exception("broker down")
        mock_task.apply.return_value = MagicMock()

        result = start_grading(self.submission)
        self.assertEqual(result["mode"], "thread")
        self._join_grading_thread()

    def test_mode_inline_when_under_min_words(self) -> None:
        """Min-word'dan kam → teacher fallback inline (LLM umuman chaqirilmaydi)."""
        from apps.essays.services import start_grading

        self.submission.essay_text = "Juda qisqa"
        self.submission.save(update_fields=["essay_text"])

        with patch("apps.essays.tasks.grade_submission_task") as mock_task:
            result = start_grading(self.submission)
            mock_task.delay.assert_not_called()

        self.assertEqual(result["mode"], "inline")
        self.assertTrue(result["fallback"])
        self.submission.refresh_from_db()
        self.assertEqual(
            self.submission.status, EssaySubmission.Status.PENDING_TEACHER,
        )


class ResubmitTests(AsyncGradingFixtureMixin, TransactionTestCase):
    """Qayta yuborish (resubmit) kontrakti — AI timeout/ERROR'dan keyin.

    User talabi: esse ERROR/pending_teacher holatida bo'lsa-yu, lekin bazada
    AI natijasi (score/izoh) YO'Q bo'lsa — xatolik qaytarmay, qayta baholash
    kerak. Faqat natija bazaga yozilgandan keyin bloklash lozim.
    """

    def setUp(self) -> None:
        super().setUp()
        self.client.force_login(self.student)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_error_essay_can_be_resubmitted(self) -> None:
        """ERROR holat, natija yo'q → qayta yuborish ruxsat, PENDING bo'ladi."""
        self.submission.status = EssaySubmission.Status.ERROR
        self.submission.error_message = "API timeout: 429"
        self.submission.save(update_fields=["status", "error_message"])

        with patch("apps.essays.tasks.grade_submission_task") as mock_task:
            mock_task.delay.return_value = MagicMock()
            resp = self.client.post(self.submit_url)

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("allaqachon", resp.content.decode("utf-8", errors="ignore").lower())
        mock_task.delay.assert_called_once()

        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, EssaySubmission.Status.PENDING)
        self.assertEqual(self.submission.error_message, "")  # eski xato tozalandi

    def test_graded_essay_is_blocked(self) -> None:
        """To'liq baholangan (GRADED + score) → bloklanadi."""
        self.submission.status = EssaySubmission.Status.GRADED
        self.submission.total_score = Decimal("18.0")
        self.submission.raw_result = MOCK_GRADE
        self.submission.save(update_fields=["status", "total_score", "raw_result"])

        with patch("apps.essays.tasks.grade_submission_task") as mock_task:
            resp = self.client.post(self.submit_url)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "allaqachon baholangan", resp.content.decode("utf-8", errors="ignore").lower(),
        )
        mock_task.delay.assert_not_called()  # qayta baholash yuborilmadi

    def test_pending_essay_returns_processing_not_error(self) -> None:
        """PENDING (hali ishlanmoqda) → xato emas, processing javob."""
        self.submission.status = EssaySubmission.Status.PENDING
        self.submission.save(update_fields=["status"])

        resp = self.client.post(self.submit_url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(
            "data-async-redirect", resp.content.decode("utf-8", errors="ignore"),
        )

    def test_teacher_reviewed_essay_is_blocked(self) -> None:
        """Ustoz bahosi bor (final_score) → bloklanadi."""
        self.submission.status = EssaySubmission.Status.TEACHER_REVIEWED
        self.submission.final_score = Decimal("20.0")
        self.submission.save(update_fields=["status", "final_score"])

        resp = self.client.post(self.submit_url)
        self.assertIn(
            "allaqachon baholangan", resp.content.decode("utf-8", errors="ignore").lower(),
        )

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_pending_teacher_without_result_is_resubmittable(self) -> None:
        """PENDING_TEACHER, AI natijasi yo'q → qayta baholashga ruxsat."""
        self.submission.status = EssaySubmission.Status.PENDING_TEACHER
        self.submission.save(update_fields=["status"])

        with patch("apps.essays.tasks.grade_submission_task") as mock_task:
            mock_task.delay.return_value = MagicMock()
            resp = self.client.post(self.submit_url)

        self.assertEqual(resp.status_code, 200)
        mock_task.delay.assert_called_once()
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, EssaySubmission.Status.PENDING)

    def test_essay_has_grade_result_helper(self) -> None:
        """essay_has_grade_result() to'g'ri ishlashi."""
        from apps.essays.services import essay_has_grade_result

        self.submission.status = EssaySubmission.Status.DRAFT
        self.submission.save(update_fields=["status"])
        self.assertFalse(essay_has_grade_result(self.submission))

        self.submission.status = EssaySubmission.Status.ERROR
        self.submission.save(update_fields=["status"])
        self.assertFalse(essay_has_grade_result(self.submission))

        self.submission.status = EssaySubmission.Status.GRADED
        self.submission.total_score = Decimal("18.0")
        self.submission.raw_result = MOCK_GRADE
        self.submission.save(update_fields=["status", "total_score", "raw_result"])
        self.assertTrue(essay_has_grade_result(self.submission))

        self.submission.status = EssaySubmission.Status.TEACHER_REVIEWED
        self.submission.final_score = Decimal("20.0")
        self.submission.save(update_fields=["status", "final_score"])
        self.assertTrue(essay_has_grade_result(self.submission))

    def test_ai_evaluation_row_counts_as_result(self) -> None:
        """Legacy AIEvaluation yozuvi bor, raw_result bo'sh → natija DEB hisoblanadi
        (eski tizimda baholangan esse qayta baholanmaydi)."""
        from apps.essays.models import AIEvaluation
        from apps.essays.services import essay_has_grade_result

        AIEvaluation.objects.create(submission=self.submission)
        self.submission.status = EssaySubmission.Status.AI_EVALUATED
        self.submission.raw_result = {}
        self.submission.save(update_fields=["status", "raw_result"])

        # hasattr yo'li — RelatedObjectDoesNotExist ko'tarilmasligi kerak.
        self.assertTrue(essay_has_grade_result(self.submission))

    def test_no_ai_evaluation_row_is_safe(self) -> None:
        """AIEvaluation yozuvi YO'Q bo'lsa ham exception ko'tarilmasligi kerak —
        hasattr False qaytaradi va raw_result'ga qaraydi."""
        from apps.essays.services import essay_has_grade_result

        self.submission.status = EssaySubmission.Status.AI_EVALUATED
        self.submission.raw_result = {"criteria": [{"id": 1, "score": 2}]}
        self.submission.save(update_fields=["status", "raw_result"])

        self.assertFalse(hasattr(self.submission, "ai_evaluation"))
        self.assertTrue(essay_has_grade_result(self.submission))

        # raw_result tozalangach — natija yo'q, qayta baholash mumkin.
        self.submission.raw_result = {}
        self.submission.save(update_fields=["raw_result"])
        self.assertFalse(essay_has_grade_result(self.submission))


class LLMClientTimeoutTests(AsyncGradingBaseTestCase):
    """ESSAY_AI_REQUEST_TIMEOUT sozlamasi OpenAI client'ga yetib boradi.

    Test mock mode'da ishlaydi (API kalitsiz): _get_llm_client mock-mode
    bo'lsa ham haqiqiy OpenAI client ob'ektini quradi (network yo'q),
    shuning uchun timeout qiymatini tekshirish mumkin.
    """

    @override_settings(
        ESSAY_AI_MOCK_MODE=True,
        OPENROUTER_API_KEY="",
        GROQ_API_KEY="",
        ESSAY_AI_REQUEST_TIMEOUT=120,
    )
    def test_timeout_setting_used_by_client(self) -> None:
        from apps.essays.services import _get_llm_client

        with patch("openai.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            client = _get_llm_client()

        self.assertIsNotNone(client)
        call_kwargs = mock_openai.call_args.kwargs
        self.assertEqual(call_kwargs["base_url"], "https://openrouter.ai/api/v1")
        self.assertEqual(call_kwargs["timeout"].read, 120)
        self.assertEqual(call_kwargs["timeout"].connect, 10)

    @override_settings(
        ESSAY_AI_MOCK_MODE=True,
        OPENROUTER_API_KEY="",
        GROQ_API_KEY="",
        ESSAY_AI_REQUEST_TIMEOUT=30,
    )
    def test_explicit_timeout_overrides_setting(self) -> None:
        from apps.essays.services import _get_llm_client

        with patch("openai.OpenAI") as mock_openai:
            mock_openai.return_value = MagicMock()
            _get_llm_client(timeout=45.0)

        self.assertEqual(mock_openai.call_args.kwargs["timeout"].read, 45)
