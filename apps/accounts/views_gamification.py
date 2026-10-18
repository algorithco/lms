"""
Gamification API Views (apps/accounts/views_gamification.py).

GET /api/v1/gamification/streak/  — Current streak, fire icon status, daily goal
GET /api/v1/gamification/league/  — Weekly league standings, rank, reset timer
"""
from __future__ import annotations

from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .gamification import get_user_streak_info, get_weekly_league_leaderboard


class UserStreakView(APIView):
    """GET /api/v1/gamification/streak/"""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        data = get_user_streak_info(request.user)
        return Response(data, status=status.HTTP_200_OK)


class WeeklyLeagueView(APIView):
    """GET /api/v1/gamification/league/"""

    permission_classes = [permissions.AllowAny]

    def get(self, request: Request) -> Response:
        data = get_weekly_league_leaderboard(request.user)
        return Response(data, status=status.HTTP_200_OK)
