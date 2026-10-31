"""
User Feedback API endpoint.
Collects user ratings, feedback, bug reports, and suggestions,
and dispatches Telegram alerts to platform administrators.
"""

import logging
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.models import UserFeedback
from apps.notifications.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)


class FeedbackView(APIView):
    """
    POST /api/v1/feedback/
    Foydalanuvchi fikri, taklifi yoki xatolik xabarini qabul qilish.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request, *args, **kwargs) -> Response:
        data = request.data or {}
        message = str(data.get("message", "")).strip()

        if not message or len(message) < 3:
            return Response(
                {"error": "Fikr yoki xabaringiz matnini kiritishingiz shart (kamida 3 ta belgi)."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rating = int(data.get("rating", 5))
            rating = max(1, min(5, rating))
        except (ValueError, TypeError):
            rating = 5

        category = str(data.get("category", UserFeedback.Category.FEEDBACK)).strip().lower()
        if category not in [c.value for c in UserFeedback.Category]:
            category = UserFeedback.Category.FEEDBACK

        user = request.user if request.user and request.user.is_authenticated else None
        
        name = str(data.get("name", "")).strip()
        if not name and user:
            name = user.get_full_name() or user.username or ""

        phone = str(data.get("phone", "")).strip()
        if not phone and user:
            phone = getattr(user, "phone_number", "") or ""

        # Create record in DB
        feedback = UserFeedback.objects.create(
            user=user,
            user_name=name,
            user_phone=phone,
            rating=rating,
            category=category,
            message=message,
        )

        # Notify administrator via Telegram with approval buttons
        try:
            admin_id = int(getattr(settings, "ADMIN_TELEGRAM_ID", 5582178765))
            stars = "⭐" * rating
            author_display = name or "Anonim"
            user_handle = ""
            if user:
                user_handle = f" (@{user.username})" if getattr(user, "username", "") else f" (ID: {user.pk})"
            phone_display = phone or "-"
            role_display = f" [{user.role}]" if user and hasattr(user, "role") else ""
            cat_display = dict(UserFeedback.Category.choices).get(category, category)

            telegram_text = (
                f"📬 <b>Yangi Fikr / Taklif / Xatolik!</b>\n\n"
                f"👤 <b>Yuboruvchi:</b> {author_display}{user_handle}{role_display}\n"
                f"📞 <b>Telefon:</b> {phone_display}\n"
                f"⭐️ <b>Baho:</b> {stars} ({rating}/5)\n"
                f"🏷 <b>Turi:</b> {cat_display}\n"
                f"📅 <b>Sana:</b> {timezone.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                f"📝 <b>Xabar matni:</b>\n"
                f"<i>\"{message}\"</i>\n\n"
                f"Ushbu sharhni bosh sahifada (grandec.uz) chiqarishni xohlaysizmi?"
            )
            buttons = [
                [
                    {
                        "text": "✅ Saytda chiqarish",
                        "callback_data": f"publish_feedback_{feedback.pk}",
                    },
                    {
                        "text": "❌ Rad etish",
                        "callback_data": f"reject_feedback_{feedback.pk}",
                    },
                ]
            ]
            TelegramService.send_message_with_keyboard(
                chat_id=admin_id,
                text=telegram_text,
                buttons=buttons,
                parse_mode="HTML",
            )
        except Exception as exc:
            logger.warning("Failed to send Telegram notification for feedback #%d: %s", feedback.pk, exc)

        return Response(
            {
                "success": True,
                "message": "Fikringiz uchun tashakkur! Taklifingiz muvaffaqiyatli qabul qilindi.",
                "id": feedback.pk,
            },
            status=status.HTTP_201_CREATED,
        )


class PublicFeedbackListView(APIView):
    """
    GET /api/v1/feedback/public/
    Admin tomonidan tasdiqlangan (is_published=True) haqiqiy foydalanuvchilar sharhlari.
    """

    permission_classes = [AllowAny]

    def get(self, request: Request, *args, **kwargs) -> Response:
        feedbacks = (
            UserFeedback.objects.filter(is_published=True)
            .select_related("user")
            .order_by("-created_at")[:30]
        )

        results = []
        for fb in feedbacks:
            role_label = ""
            if fb.user:
                role_val = getattr(fb.user, "role", "")
                if role_val == "student":
                    role_label = "O'quvchi"
                elif role_val == "teacher":
                    role_label = "O'qituvchi"
                elif role_val == "admin":
                    role_label = "Administrator"
                else:
                    role_label = "Foydalanuvchi"
            else:
                role_label = "Foydalanuvchi"

            results.append(
                {
                    "id": fb.pk,
                    "name": fb.name,
                    "role": role_label,
                    "rating": fb.rating,
                    "category": fb.category,
                    "category_display": dict(UserFeedback.Category.choices).get(fb.category, fb.category),
                    "message": fb.message,
                    "created_at": fb.created_at.strftime("%Y-%m-%d"),
                }
            )

        return Response({"results": results, "count": len(results)})
