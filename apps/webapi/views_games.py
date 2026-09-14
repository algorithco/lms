"""Games JSON API — same rules as apps/games/views.py, JSON in/out.

Uses the shared XP engine (apps.games.views._award_xp) so balances,
combos and badges stay identical between the Django templates and React.
"""
from __future__ import annotations

import random

from django.db.models import Sum
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.games.models import Game, GameLevel, UserBadge, UserGameScore
from apps.games.views import _award_xp

from .serializers import (
    GameLevelMetaSerializer,
    GameSerializer,
    UserGameScoreSerializer,
)


def _totals(user):
    agg = UserGameScore.objects.filter(user=user).aggregate(
        xp=Sum("total_xp"), coins=Sum("total_coins")
    )
    return {"total_xp": agg["xp"] or 0, "total_coins": agg["coins"] or 0}


def _board(limit=10):
    return list(
        UserGameScore.objects.filter(game__isnull=False)
        .values("user__id", "user__first_name", "user__last_name")
        .annotate(
            total_xp=Sum("total_xp"),
            total_coins=Sum("total_coins"),
            games_played=Sum("games_played"),
        )
        .order_by("-total_xp")[:limit]
    )


def _pick_level(game, level_id=None):
    levels = GameLevel.objects.filter(game=game, is_active=True).order_by("sort_order")
    if level_id:
        return get_object_or_404(GameLevel, id=level_id, game=game, is_active=True), levels
    level = levels.filter(difficulty__lte=3).order_by("?").first() or levels.first()
    return level, levels


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def hub_view(request):
    """Game hub — mirrors games_index context as JSON."""
    games = Game.objects.filter(is_active=True).order_by("sort_order")
    scores = UserGameScore.objects.filter(user=request.user).select_related("game")
    badges = (
        UserBadge.objects.filter(user=request.user)
        .select_related("badge")
        .order_by("-earned_at")[:5]
    )
    return Response({
        "games": GameSerializer(games, many=True).data,
        "scores": UserGameScoreSerializer(scores, many=True).data,
        "stats": _totals(request.user),
        "recent_badges": [
            {"name": b.badge.name, "emoji": b.badge.icon_emoji} for b in badges
        ],
        "leaderboard": _board(10),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def leaderboard_view(request):
    board = _board(10)
    mine = _totals(request.user)
    return Response({"leaderboard": board, "my_stats": mine})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def play_view(request, slug: str):
    """Random (or ?level=) level content. Answers are never leaked."""
    game = get_object_or_404(Game, slug=slug, is_active=True)
    level, levels = _pick_level(game, request.GET.get("level"))
    if level is None:
        return Response({"detail": "No active levels for this game."}, status=404)

    data = level.question_data or {}
    content: dict = {}
    if game.slug == "imlo_mina":
        text = str(data.get("text", ""))
        content = {"text": text, "words": text.split()}
    elif game.slug == "gazal_puzzle":
        lines = list(data.get("bayt_lines", []))
        shuffled = lines.copy()
        random.shuffle(shuffled)
        content = {"shuffled_lines": shuffled, "line_count": len(lines)}
    elif game.slug == "lugat_match":
        pairs = data.get("pairs", [])
        cards = []
        for i, pair in enumerate(pairs):
            cards.append({"id": f"old_{i}", "pair_id": i, "text": pair.get("old", ""), "type": "old"})
            cards.append({"id": f"new_{i}", "pair_id": i, "text": pair.get("new", ""), "type": "new"})
        random.shuffle(cards)
        content = {"cards": cards, "pairs_count": len(pairs)}
    else:
        content = {"data": data}

    score = UserGameScore.objects.filter(user=request.user, game=game).first()
    return Response({
        "game": GameSerializer(game).data,
        "level": {
            "id": level.id,
            "title": level.title,
            "difficulty": level.difficulty,
            "hint": level.hint,
            "time_limit_seconds": level.time_limit_seconds,
        },
        "levels": GameLevelMetaSerializer(levels, many=True).data,
        "content": content,
        "my_score": UserGameScoreSerializer(score).data if score else None,
    })


def _combo(request, correct: bool) -> int:
    try:
        combo = int(request.data.get("combo", 0))
    except (TypeError, ValueError):
        combo = 0
    return combo + 1 if correct else 0


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def check_view(request, slug: str):
    """Validate a move — identical rules to the HTMX check views."""
    game = get_object_or_404(Game, slug=slug, is_active=True)
    level = get_object_or_404(
        GameLevel, id=request.data.get("level_id"), game=game
    )
    data = level.question_data or {}

    answer: dict = {}
    if game.slug == "imlo_mina":
        try:
            word_index = int(request.data.get("word_index", -1))
        except (TypeError, ValueError):
            word_index = -1
        action = request.data.get("action", "")
        error_position = int(data.get("error_word_index", 0))
        is_correct = (action == "fix" and word_index == error_position) or action == "skip"
        answer = {"error_word_index": error_position}
    elif game.slug == "gazal_puzzle":
        raw = str(request.data.get("order", ""))
        try:
            order = [int(x) for x in raw.split(",") if x.strip()]
        except ValueError:
            order = []
        lines = data.get("bayt_lines", [])
        is_correct = order == list(range(len(lines)))
        answer = {"correct_order": list(range(len(lines)))}
    elif game.slug == "lugat_match":
        c1, c2 = str(request.data.get("card1_id", "")), str(request.data.get("card2_id", ""))
        is_match = False
        for a, b in ((c1, c2), (c2, c1)):
            if a.startswith("old_") and b.startswith("new_"):
                try:
                    is_match = int(a[4:]) == int(b[4:])
                except ValueError:
                    is_match = False
        is_correct = is_match
        answer = {"is_match": is_match}
    else:
        return Response({"detail": "Unknown game."}, status=404)

    combo = _combo(request, is_correct)
    result = _award_xp(request.user, game, is_correct, combo=combo)
    return Response({
        "is_correct": is_correct,
        "combo": combo,
        "answer": answer,
        **result,
    })
