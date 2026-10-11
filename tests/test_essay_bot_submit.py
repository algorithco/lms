from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from asgiref.sync import async_to_sync
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.essays.models import EssaySubmission
from apps.notifications.bot.handlers import (
    _handle_bot_essay_text,
    essay_submit_handler,
)

class TelegramEssaySubmissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="essay-bot@example.test",
            password=None,
            first_name="Essay",
            telegram_chat_id=77123456,
            telegram_identity_verified_at=__import__("django.utils.timezone", fromlist=["now"]).now(),
        )
        self.message = SimpleNamespace(text="A sufficiently long direct essay body.", reply_text=AsyncMock())
        self.update = SimpleNamespace(
            effective_user=SimpleNamespace(id=self.user.telegram_chat_id, first_name="Essay", last_name=""),
            message=self.message,
            callback_query=None,
        )
        self.context = SimpleNamespace(args=[], user_data={})

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("apps.essays.tasks.grade_submission_task")
    def test_start_then_text_enqueues_canonical_grader(self, mock_task):
        mock_task.delay.return_value = object()
        async_to_sync(essay_submit_handler)(self.update, self.context)
        self.assertEqual(self.context.user_data["bot_essay_state"], "awaiting_text")

        async_to_sync(_handle_bot_essay_text)(self.update, self.context)

        submission = EssaySubmission.objects.get(student=self.user)
        self.assertIsNone(submission.topic_id)
        self.assertEqual(submission.status, EssaySubmission.Status.PENDING)
        mock_task.delay.assert_called_once_with(
            submission.id,
            fail_status=EssaySubmission.Status.ERROR,
        )
        self.assertNotIn("bot_essay_state", self.context.user_data)
        # Wording mandated by the commercial essay spec for an accepted essay.
        reply = self.message.reply_text.await_args.args[0]
        self.assertIn("Esse qabul qilindi", reply)
        self.assertIn("Baholash boshlandi", reply)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("apps.essays.tasks.grade_submission_task")
    def test_identical_pending_submission_does_not_enqueue_again(self, mock_task):
        mock_task.delay.return_value = object()
        text = self.message.text
        first_context = SimpleNamespace(args=[text], user_data={})
        async_to_sync(essay_submit_handler)(self.update, first_context)
        mock_task.delay.reset_mock()

        second_context = SimpleNamespace(args=[text], user_data={})
        async_to_sync(essay_submit_handler)(self.update, second_context)

        self.assertEqual(EssaySubmission.objects.filter(student=self.user).count(), 1)
        mock_task.delay.assert_not_called()
        self.assertIn("allaqachon qabul qilingan", self.message.reply_text.await_args.args[0])

    @override_settings(CELERY_TASK_ALWAYS_EAGER=False)
    @patch("apps.essays.tasks.grade_submission_task")
    def test_identical_graded_submission_returns_existing_grade(self, mock_task):
        existing = EssaySubmission.objects.create(
            student=self.user,
            topic=None,
            essay_text=self.message.text,
            status=EssaySubmission.Status.GRADED,
            total_score=19,
            max_score=24,
        )

        async_to_sync(essay_submit_handler)(self.update, SimpleNamespace(
            args=[self.message.text], user_data={}
        ))

        self.assertEqual(EssaySubmission.objects.filter(student=self.user).count(), 1)
        mock_task.delay.assert_not_called()
        reply = self.message.reply_text.await_args.args[0]
        self.assertIn("allaqachon baholangan", reply)
        self.assertIn("19.0/24", reply)
        self.assertIn(str(existing.id), reply)
