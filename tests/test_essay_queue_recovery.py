"""
Essa baholash navbati (queue) routing regression testlari — 2026-09-16 outage.

Ildiz sabab: CELERY_TASK_ROUTES essa task'larini "essay_grading" queue'ga
yo'naltirdi, prod worker esa faqat default "celery" queue'ni consume qilardi.
Har bir esse PENDING'da qotib qoldi ("AI baholamoqda"), teacher queue bo'sh.

Ushbu suite quyidagi kontraktlarni himoya qiladi:

  1. Essay task'lari HAQIQATAN "essay_grading" queue'ga route qilinadi.
  2. compose worker komandasi -Q orqali shu queue'ni consume qiladi
     (docker-compose.yml va docker-compose.prod.yml).
  3. deploy/preflight.sh bu kontrakt tekshiruvini o'z ichiga oladi.
  4. recover_stale_essays buyrug'i stale PENDING'larni xavfsiz tiklaydi:
     atomic claim + dedup oynasi + double grading yo'q.
"""
from __future__ import annotations

import io
from contextlib import redirect_stdout
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.essays.models import EssaySubmission, EssayTopic

class FullEssayReachesGraderTests(TestCase):
    """Phase 3 kontrakt: AI HECH QACHON kesilmagan/predview matnni baholamaydi —
    bazadagi TO'LIQ essay_text graderning o'ziga yetib boradi."""

    def setUp(self) -> None:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.student = User.objects.create_user(
            email="fulltext@test.com", password="x", role="student",
        )
        self.topic = EssayTopic.objects.create(
            title="To'liq matn mavzusi", description="",
            word_limit_min=20, word_limit_max=2000, time_limit_minutes=60,
        )

    def test_complete_submitted_text_passed_to_llm(self) -> None:
        # ~30 000 belgi — MAX_ESSAY_LENGTH (50_000) ostida, lekin har qanday
        # "birinchi paragraf/predview" kesishdan ancha katta.
        full_text = ("Bu paragraf o'quvchining haqiqiy esse matnidan olingan. " * 500).strip()
        sub = EssaySubmission.objects.create(
            student=self.student, topic=self.topic,
            status=EssaySubmission.Status.PENDING,
            essay_text=full_text, word_count=5_000,
        )
        from apps.essays.tasks import grade_submission_task

        with patch(
            "apps.essays.services.grade_essay", return_value=dict(MOCK_GRADE),
        ) as mock_grade:
            grade_submission_task.apply(
                args=[sub.pk], kwargs={"fail_status": EssaySubmission.Status.ERROR},
            )
        mock_grade.assert_called_once()
        graded_text = mock_grade.call_args.args[0]
        self.assertEqual(graded_text, full_text)
        self.assertGreater(len(graded_text), 20_000)

    def test_oversized_essay_rejected_before_grading(self) -> None:
        """MAX_ESSAY_LENGTH'dan katta matn saqlanmasdan, foydalanuvchiga
        tushunarli 400 bilan rad etiladi (gradingga umuman yuborilmaydi)."""
        from apps.essays.views import MAX_ESSAY_LENGTH

        oversized = "a" * (MAX_ESSAY_LENGTH + 1)
        self.client.force_login(self.student)
        response = self.client.post(
            "/essays/api/autosave/",
            {"submission_id": "", "essay_text": oversized},
        )
        # Autosave endpoint requires a valid submission id; a bare oversized
        # text must hit the length guard BEFORE any DB lookup matters.
        self.assertEqual(response.status_code, 400)
        self.assertIn("juda uzun", response.json().get("error", ""))
        # Contract: nothing oversized ever reached the grading queue.
        self.assertFalse(
            EssaySubmission.objects.filter(
                essay_text=oversized, status=EssaySubmission.Status.PENDING,
            ).exists(),
        )


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


class QueueRoutingConfigTests(TestCase):
    """Routed task'lar worker tomonidan consume qilinishi kerak."""

    def test_essay_tasks_routed_to_essay_grading_queue(self) -> None:
        from django.conf import settings

        routes = settings.CELERY_TASK_ROUTES
        for task_name in (
            "essays.grade_submission",
            "essays.auto_submit_expired",
            "essays.reap_stale_pending",
        ):
            self.assertIn(task_name, routes, f"{task_name} not routed")
            self.assertEqual(
                routes[task_name].get("queue"), "essay_grading",
                f"{task_name} must route to essay_grading",
            )

    def test_dev_compose_worker_consumes_routed_queue(self) -> None:
        with open("docker-compose.yml", encoding="utf-8") as fh:
            compose = fh.read()
        self.assertRegex(
            compose,
            r"command:\s*celery\s+-A config worker\s+-l info\s+-Q\s+celery,essay_grading",
            "docker-compose.yml worker must consume essay_grading via -Q",
        )

    def test_prod_compose_worker_consumes_routed_queue(self) -> None:
        with open("docker-compose.prod.yml", encoding="utf-8") as fh:
            compose = fh.read()
        self.assertRegex(
            compose,
            r"command:\s*celery\s+-A config worker\s+-l info\s+-Q\s+celery,essay_grading",
            "docker-compose.prod.yml worker must consume essay_grading via -Q",
        )

    def test_preflight_checks_worker_queue_flag(self) -> None:
        with open("deploy/preflight.sh", encoding="utf-8") as fh:
            preflight = fh.read()
        self.assertIn("essay_grading", preflight)
        self.assertIn("-Q", preflight)


class RecoverStaleEssaysTests(TestCase):
    """recover_stale_essays: atomic claim, dedup, double-grading himoyasi."""

    def setUp(self) -> None:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.student = User.objects.create_user(
            email="recover@test.com",
            password="testpass123",
            first_name="Recover",
            last_name="Test",
            role="student",
        )
        self.topic = EssayTopic.objects.create(
            title="Tiklash mavzusi",
            description="Tavsif",
            word_limit_min=20,
            word_limit_max=500,
            time_limit_minutes=60,
        )

    def _make_pending(self, stale_minutes: int) -> EssaySubmission:
        sub = EssaySubmission.objects.create(
            student=self.student,
            topic=self.topic,
            status=EssaySubmission.Status.PENDING,
            essay_text="Bu yetarli uzunlikdagi test esse matni " * 5,
            word_count=30,
        )
        # updated_at ni orqaga surish (auto_now ni bypass qilib).
        qs = EssaySubmission.objects.filter(pk=sub.pk)
        old = timezone.now() - timedelta(minutes=stale_minutes)
        qs.update(updated_at=old)
        sub.refresh_from_db()
        return sub

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_requeues_only_stale_pending(self) -> None:
        stale = self._make_pending(stale_minutes=30)
        fresh = self._make_pending(stale_minutes=1)

        with patch(
            "apps.essays.tasks.grade_submission_task.delay",
        ) as mock_delay:
            mock_delay.return_value = MagicMock()
            out = io.StringIO()
            with redirect_stdout(out):
                call_command("recover_stale_essays", minutes=10)

        mock_delay.assert_called_once()
        called_id = mock_delay.call_args.args[0]
        self.assertEqual(called_id, stale.pk)
        fresh.refresh_from_db()
        self.assertEqual(fresh.status, EssaySubmission.Status.PENDING)

    @override_settings(ESSAY_GRADING_PENDING_TIMEOUT_SECONDS=60)
    def test_reaper_terminalizes_overdue_pending_without_queueing_again(self) -> None:
        """An unavailable worker must produce a terminal error, not requeue forever."""
        stale = self._make_pending(stale_minutes=30)
        EssaySubmission.objects.filter(pk=stale.pk).update(
            grading_started_at=timezone.now() - timedelta(minutes=2),
        )

        from apps.essays.tasks import grade_submission_task, reap_stale_pending_essays

        with patch.object(grade_submission_task, "delay") as mock_delay:
            result = reap_stale_pending_essays.apply().result

        self.assertEqual(result["expired"], 1)
        mock_delay.assert_not_called()
        stale.refresh_from_db()
        self.assertEqual(stale.status, EssaySubmission.Status.ERROR)
        self.assertIn("belgilangan vaqt", stale.error_message)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_dry_run_changes_nothing(self) -> None:
        stale = self._make_pending(stale_minutes=30)

        with patch(
            "apps.essays.tasks.grade_submission_task.delay",
        ) as mock_delay:
            out = io.StringIO()
            with redirect_stdout(out):
                call_command("recover_stale_essays", minutes=10, dry_run=True)

        mock_delay.assert_not_called()
        stale.refresh_from_db()
        self.assertEqual(stale.status, EssaySubmission.Status.PENDING)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_no_double_grading_after_recovery(self) -> None:
        """Tiklangan qator task'da GRADED bo'lgach, ikkinchi task natijani yo'q qilmasligi kerak."""
        stale = self._make_pending(stale_minutes=30)

        with patch(
            "apps.essays.services.grade_essay",
            return_value=dict(MOCK_GRADE),
        ) as mock_grade, patch(
            "apps.essays.tasks.grade_submission_task.delay",
        ) as mock_delay:
            mock_delay.return_value = MagicMock()
            out = io.StringIO()
            with redirect_stdout(out):
                call_command("recover_stale_essays", minutes=10)
            mock_delay.assert_called_once()
            # Endi task'ni 2 marta bajaramiz (retry/duplicate delivery) —
            # FSM + status guard tufayli ikkinchisi no-op bo'lishi shart.
            from apps.essays.tasks import grade_submission_task

            r1 = grade_submission_task.apply(
                args=[stale.pk], kwargs={"fail_status": EssaySubmission.Status.ERROR},
            )
            r2 = grade_submission_task.apply(
                args=[stale.pk], kwargs={"fail_status": EssaySubmission.Status.ERROR},
            )

        self.assertEqual(r1.result.get("status"), "ok")
        self.assertIn(r2.result.get("status"), {"not_gradeable"})
        stale.refresh_from_db()
        self.assertEqual(stale.status, EssaySubmission.Status.GRADED)
        mock_grade.assert_called_once()  # LLM faqat BIR marta chaqirildi

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    def test_inline_mode_grades_locally(self) -> None:
        stale = self._make_pending(stale_minutes=30)

        with patch(
            "apps.essays.services.grade_essay",
            return_value=dict(MOCK_GRADE),
        ):
            out = io.StringIO()
            with redirect_stdout(out):
                call_command("recover_stale_essays", minutes=10, inline=True)

        stale.refresh_from_db()
        self.assertEqual(stale.status, EssaySubmission.Status.GRADED)
