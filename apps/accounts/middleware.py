"""
Accounts Middleware — Banned User enforcement.
"""

from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin


class BannedUserMiddleware(MiddlewareMixin):
    """
    Blocks banned users from accessing protected endpoints.
    Returns 403 Forbidden with explicit reason and support contacts.
    """

    def process_request(self, request):
        user = getattr(request, "user", None)
        if (
            user
            and getattr(user, "is_authenticated", False)
            and getattr(user, "is_banned", False)
        ):
            # Exempt logout if necessary, else block all actions
            if request.path.endswith("/logout/"):
                return None

            ban_reason = (
                getattr(user, "ban_reason", "")
                or "Qalbaki to'lov cheki yuklash orqali firibgarlik"
            )
            detail = (
                "Hisobingiz bloklandi! Siz tomonidan qalbaki to'lov kvitansiyasi aniqlandi. "
                "Tizimdan foydalanish huquqingiz cheklandi. Savollar bo'yicha: @grandec_admin"
            )
            return JsonResponse(
                {
                    "detail": detail,
                    "is_banned": True,
                    "ban_reason": ban_reason,
                },
                status=403,
            )
        return None
