import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from types import SimpleNamespace
from asgiref.sync import async_to_sync
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.notifications.models import UserFeedback
from apps.notifications.bot.handlers import (
    admin_publish_feedback_callback,
    admin_reject_feedback_callback,
    callback_handler,
)

User = get_user_model()


@pytest.mark.django_db
class TestFeedbackApprovalFlow:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="student1@grandec.uz",
            password="testpassword123",
            first_name="Bekzod",
            last_name="Aliyev",
            role=User.Role.STUDENT,
        )

    @patch("apps.notifications.services.telegram_service.TelegramService.send_message_with_keyboard")
    def test_submit_feedback_creates_unpublished_record_and_notifies_admin(self, mock_tg):
        self.client.force_authenticate(user=self.user)
        payload = {
            "rating": 5,
            "category": "praise",
            "message": "Grandec platformasi orqali BMB imtihoniga ajoyib tayyorlandim!",
        }

        resp = self.client.post("/api/v1/feedback/", payload, format="json")
        assert resp.status_code == 201
        assert resp.data["success"] is True

        fb_id = resp.data["id"]
        fb = UserFeedback.objects.get(id=fb_id)
        assert fb.is_published is False
        assert fb.user == self.user
        assert fb.rating == 5
        assert fb.category == "praise"

        # Verify telegram notification was dispatched with inline buttons
        assert mock_tg.called
        call_kwargs = mock_tg.call_args.kwargs
        assert "publish_feedback_" in str(call_kwargs["buttons"])
        assert "reject_feedback_" in str(call_kwargs["buttons"])

    def test_public_endpoint_only_returns_approved_feedbacks(self):
        # Create one published and one unpublished feedback
        published = UserFeedback.objects.create(
            user=self.user,
            user_name="Bekzod Aliyev",
            rating=5,
            category=UserFeedback.Category.PRAISE,
            message="Tasdiqlangan ajoyib sharh!",
            is_published=True,
        )
        unpublished = UserFeedback.objects.create(
            user=self.user,
            user_name="Bekzod Aliyev",
            rating=3,
            category=UserFeedback.Category.BUG,
            message="Kutilayotgan sharh",
            is_published=False,
        )

        resp = self.client.get("/api/v1/feedback/public/")
        assert resp.status_code == 200
        data = resp.data
        assert data["count"] == 1
        results = data["results"]
        assert len(results) == 1
        assert results[0]["id"] == published.id
        assert results[0]["name"] == "Bekzod Aliyev"
        assert results[0]["role"] == "O'quvchi"
        assert results[0]["message"] == "Tasdiqlangan ajoyib sharh!"

    def test_admin_approves_feedback_via_bot(self):
        fb = UserFeedback.objects.create(
            user=self.user,
            user_name="Bekzod Aliyev",
            rating=5,
            category=UserFeedback.Category.FEEDBACK,
            message="Yangi sharh",
            is_published=False,
        )

        admin_id = 5582178765
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=admin_id, first_name="Admin", last_name=""),
            callback_query=SimpleNamespace(
                data=f"publish_feedback_{fb.id}",
                answer=AsyncMock(),
                edit_message_text=AsyncMock(),
                message=SimpleNamespace(text_html="Xabar matni"),
            ),
        )
        context = SimpleNamespace()

        async_to_sync(callback_handler)(update, context)

        fb.refresh_from_db()
        assert fb.is_published is True
        update.callback_query.answer.assert_called()

    def test_admin_rejects_feedback_via_bot(self):
        fb = UserFeedback.objects.create(
            user=self.user,
            user_name="Bekzod Aliyev",
            rating=2,
            category=UserFeedback.Category.BUG,
            message="Nosozlik bor",
            is_published=False,
        )

        admin_id = 5582178765
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=admin_id, first_name="Admin", last_name=""),
            callback_query=SimpleNamespace(
                data=f"reject_feedback_{fb.id}",
                answer=AsyncMock(),
                edit_message_text=AsyncMock(),
                message=SimpleNamespace(text_html="Xabar matni"),
            ),
        )
        context = SimpleNamespace()

        async_to_sync(callback_handler)(update, context)

        fb.refresh_from_db()
        assert fb.is_published is False
        update.callback_query.answer.assert_called()

    def test_unauthorized_user_cannot_approve_feedback(self):
        fb = UserFeedback.objects.create(
            user=self.user,
            user_name="Bekzod Aliyev",
            rating=5,
            category=UserFeedback.Category.FEEDBACK,
            message="Yangi sharh",
            is_published=False,
        )

        fake_user_id = 123456789  # Not admin
        update = SimpleNamespace(
            effective_user=SimpleNamespace(id=fake_user_id, first_name="Hacker", last_name=""),
            callback_query=SimpleNamespace(
                data=f"publish_feedback_{fb.id}",
                answer=AsyncMock(),
                edit_message_text=AsyncMock(),
                message=SimpleNamespace(text_html="Xabar matni"),
            ),
        )
        context = SimpleNamespace()

        async_to_sync(callback_handler)(update, context)

        fb.refresh_from_db()
        assert fb.is_published is False
        update.callback_query.answer.assert_called_with(
            "⛔️ Sizda ushbu amalni bajarish huquqi yo'q.", show_alert=True
        )
