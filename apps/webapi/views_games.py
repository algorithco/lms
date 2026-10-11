"""Games JSON API — same rules as apps/games/views.py, JSON in/out.

Uses the shared XP engine (apps.games.engine) so balances,
combos and badges stay identical between the Django templates and React.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.games.models import Game, GameLevel, UserBadge, UserGameScore

from apps.games.engine import (
    award_xp,
    _get_leaderboard as _board,
    gazal_puzzle_order,
    get_game_content,
    get_user_stats as _totals,
    pick_level,
)

from .serializers import (
    GameLevelMetaSerializer,
    GameSerializer,
    UserGameScoreSerializer,
)


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
    level, levels = pick_level(game, request.GET.get("level"))
    if level is None:
        return Response({"detail": "No active levels for this game."}, status=404)

    data = level.question_data or {}
    try:
        content = get_game_content(game, level, data, request.user.pk)
    except ValueError:
        return Response({"detail": "This game level is currently unavailable."}, status=503)

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
    challenge_key = "level"
    if game.slug == "imlo_mina":
        try:
            word_index = int(request.data.get("word_index", -1))
        except (TypeError, ValueError):
            word_index = -1
        action = request.data.get("action", "")
        try:
            error_position = int(data.get("error_word_index", 0))
        except (TypeError, ValueError):
            return Response({"detail": "Invalid game level data."}, status=500)
        is_correct = action == "fix" and word_index == error_position
        answer = {"error_word_index": error_position} if action == "fix" else {}
        challenge_key = "imlo:error"
    elif game.slug == "gazal_puzzle":
        raw = str(request.data.get("order", ""))
        try:
            order = [int(x) for x in raw.split(",") if x.strip()]
        except ValueError:
            order = []
        try:
            _shuffled_lines, correct_order = gazal_puzzle_order(
                level, request.user.pk, data,
            )
        except ValueError:
            return Response({"detail": "This game level is currently unavailable."}, status=503)
        is_correct = len(order) == len(correct_order) and order == correct_order
        answer = {"correct_order": correct_order}
        challenge_key = "gazal"
    elif game.slug == "lugat_match":
        c1, c2 = str(request.data.get("card1_id", "")), str(request.data.get("card2_id", ""))
        is_match = False
        old_index = new_index = -1
        pair_count = len(data.get("pairs", []))
        for a, b in ((c1, c2), (c2, c1)):
            if a.startswith("old_") and b.startswith("new_"):
                try:
                    old_index = int(a[4:])
                    new_index = int(b[4:])
                    is_match = old_index == new_index and 0 <= old_index < pair_count
                except ValueError:
                    is_match = False
        is_correct = is_match
        answer = {"is_match": is_match}
        challenge_key = (
            f"lugat:{old_index}" if is_match else "lugat:invalid"
        )
    else:
        return Response({"detail": "Unknown game."}, status=404)

    result = award_xp(
        request.user,
        game,
        is_correct,
        level=level,
        challenge_key=challenge_key,
    )
    return Response({
        "is_correct": is_correct,
        "answer": answer,
        **result,
    })