"""Referral API views for viral growth system."""

from __future__ import annotations

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.models import ReferralHistory
from apps.accounts.services.referral import apply_referral_reward


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_referral_code_view(request):
    """
    Returns the authenticated user's referral code, links, and invite statistics.
    """
    user = request.user
    if not user.referral_code:
        import secrets

        user.referral_code = f"ref_{secrets.token_hex(4)}"
        user.save(update_fields=["referral_code"])

    total_invited = ReferralHistory.objects.filter(referrer=user).count()

    return Response(
        {
            "referral_code": user.referral_code,
            "referral_link": f"https://grandec.uz/r/{user.referral_code}",
            "telegram_bot_link": f"https://t.me/uz_essaygrader_bot?start=ref_{user.referral_code}",
            "total_invited": total_invited,
            "bonus_tests": getattr(user, "bonus_tests", 0),
            "bonus_essays": getattr(user, "bonus_essays", 0),
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def apply_referral_view(request):
    """
    Applies a referral code for the authenticated user to claim welcome bonus.
    """
    code = (
        request.data.get("code")
        or request.data.get("referral_code")
        or ""
    ).strip()

    if not code:
        return Response({"error": "Referal kodi kiritilmadi."}, status=400)

    success, message = apply_referral_reward(request.user, code)
    if not success:
        return Response({"error": message, "status": "FAILED"}, status=400)

    return Response(
        {
            "status": "SUCCESS",
            "message": message,
            "bonus_tests": request.user.bonus_tests,
            "bonus_essays": request.user.bonus_essays,
        },
        status=200,
    )
