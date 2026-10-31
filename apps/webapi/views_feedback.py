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

        # Notify administrator via Telegram
        try:
            admin_id = getattr(settings, "ADMIN_TELEGRAM_ID", 5582178765)
            stars = "⭐" * rating
            author_display = name or "Anonim"
            phone_display = phone or "-"
            role_display = f" ({user.role})" if user and hasattr(user, "role") else ""
            cat_display = dict(UserFeedback.Category.choices).get(category, category)

            telegram_text = (
                f"💬 <b>Yangi fikr/taklif kelib tushdi!</b>\n\n"
                f"👤 <b>Foydalanuvchi:</b> {author_display}{role_display}\n"
                f"📞 <b>Telefon:</b> {phone_display}\n"
                f"⭐ <b>Baho:</b> {stars} ({rating}/5)\n"
                f"📂 <b>Kategoriya:</b> {cat_display}\n"
                f"📝 <b>Xabar:</b>\n{message}\n\n"
                f"📅 <b>Vaqt:</b> {timezone.now().strftime('%Y-%m-%d %H:%M')}"
            )
            TelegramService.send_message(admin_id, telegram_text)
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
