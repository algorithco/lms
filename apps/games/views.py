"""
Games views — gamification hub, game logic, leaderboard, XP system.

Endpoints:
    GET  /games/                         — Game hub (all games)
    GET  /games/imlo-mina/               — Imlo Minalari game page
    POST /games/api/imlo-mina/check/     — Check imlo answer (HTMX)
    GET  /games/gazal-puzzle/            — Navoiy vs Dunyo puzzle page
    POST /games/api/gazal-puzzle/check/  — Check gazal order (HTMX)
    GET  /games/lugat-match/             — Eski So'zlar Dueli page
    POST /games/api/lugat-match/check/   — Check match pair (HTMX)
    GET  /games/leaderboard/             — Live leaderboard
    GET  /games/api/leaderboard/         — Leaderboard data (HTMX)
"""
from __future__ import annotations

import json
import logging
import random
from typing import Any

import hashlib

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, F, Max, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import condition
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Badge, Game, GameLevel, UserBadge, UserGameScore

logger = logging.getLogger(__name__)

# XP bonus constants
COMBO_BONUS_XP = 5           # extra XP per combo level
STREAK_MILESTONES = {3: "🔥 3x COMBO!", 5: "⚡ 5x SUPER COMBO!", 10: "🌟 10x LEGENDARY!"}


# ---------------------------------------------------------------------------
# Helper: XP & Badge engine
# ---------------------------------------------------------------------------

def _award_xp(user, game: Game, is_correct: bool, combo: int = 0, time_seconds: int = 0) -> dict[str, Any]:
    """
    Award XP/coins and check for badge unlocks.

    Returns dict with XP earned, coins earned, and any new badges.
    """
    score, _ = UserGameScore.objects.get_or_create(user=user, game=game)

    xp_earned = 0
    coins_earned = 0
    new_badges = []

    if is_correct:
        base_xp = game.xp_per_correct
        base_coins = game.coins_per_correct

        # Combo multiplier
        if combo >= 2:
            multiplier = float(game.combo_multiplier) ** min(combo - 1, 5)
            xp_earned = int(base_xp * multiplier)
            coins_earned = int(base_coins * multiplier)
        else:
            xp_earned = base_xp
            coins_earned = base_coins

        score.correct_answers = F("correct_answers") + 1
    else:
        score.wrong_answers = F("wrong_answers") + 1

    score.total_xp = F("total_xp") + xp_earned
    score.total_coins = F("total_coins") + coins_earned
    score.games_played = F("games_played") + 1
    score.last_played_at = timezone.now()

    update_fields = [
        "total_xp", "total_coins", "games_played",
        "last_played_at",
    ]

    if is_correct:
        update_fields.append("correct_answers")
    else:
        update_fields.append("wrong_answers")

    if time_seconds > 0 and (score.best_time_seconds == 0 or time_seconds < score.best_time_seconds):
        score.best_time_seconds = time_seconds
        update_fields.append("best_time_seconds")

    score.save(update_fields=update_fields)

    # Refresh to get updated values
    score.refresh_from_db()

    # Update best streak (after refresh so we can compare)
    if is_correct and combo > score.best_streak:
        score.best_streak = combo
        score.save(update_fields=["best_streak"])

    # Update high score
    if score.total_xp > score.high_score:
        score.high_score = score.total_xp
        score.save(update_fields=["high_score"])

    # Check badge conditions
    new_badges = _check_badges(user)

    return {
        "xp_earned": xp_earned,
        "coins_earned": coins_earned,
        "total_xp": score.total_xp,
        "total_coins": score.total_coins,
        "streak": combo,
        "new_badges": [{"name": b.badge.name, "emoji": b.badge.icon_emoji} for b in new_badges],
    }


def _check_badges(user) -> list:
    """Check and award any newly unlocked badges."""
    newly_earned = []

    # Get all badge conditions
    all_badges = Badge.objects.all()
    earned_ids = set(
        UserBadge.objects.filter(user=user).values_list("badge_id", flat=True)
    )

    # Get user's total stats across all games
    total_stats = UserGameScore.objects.filter(user=user).aggregate(
        total_correct=Sum("correct_answers"),
        total_xp=Sum("total_xp"),
        total_coins=Sum("total_coins"),
        total_games=Sum("games_played"),
        max_streak=Max("best_streak"),
    )

    for badge in all_badges:
        if badge.id in earned_ids:
            continue

        earned = False

        if badge.badge_type == Badge.BadgeType.IMLO_MASTER:
            imlo_score = UserGameScore.objects.filter(
                user=user, game__slug=Game.GameType.IMLO_MINA
            ).first()
            earned = imlo_score and imlo_score.correct_answers >= badge.required_value

        elif badge.badge_type == Badge.BadgeType.GAZAL_SCHOLAR:
            gazal_score = UserGameScore.objects.filter(
                user=user, game__slug=Game.GameType.GAZAL_PUZZLE
            ).first()
            earned = gazal_score and gazal_score.correct_answers >= badge.required_value

        elif badge.badge_type == Badge.BadgeType.LUGAT_ACADEMIC:
            lugat_score = UserGameScore.objects.filter(
                user=user, game__slug=Game.GameType.LUGAT_MATCH
            ).first()
            earned = lugat_score and lugat_score.correct_answers >= badge.required_value

        elif badge.badge_type == Badge.BadgeType.COMBO_KING:
            earned = (total_stats["max_streak"] or 0) >= badge.required_value

        elif badge.badge_type == Badge.BadgeType.XP_HUNTER:
            earned = (total_stats["total_xp"] or 0) >= badge.required_value

        elif badge.badge_type == Badge.BadgeType.COIN_COLLECTOR:
            earned = (total_stats["total_coins"] or 0) >= badge.required_value

        elif badge.badge_type == Badge.BadgeType.DAILY_PLAYER:
            earned = (total_stats["total_games"] or 0) >= badge.required_value

        if earned:
            ub = UserBadge.objects.create(user=user, badge=badge)
            # Award bonus XP
            UserGameScore.objects.filter(user=user).update(
                total_xp=F("total_xp") + badge.xp_bonus
            )
            newly_earned.append(ub)
            logger.info("Badge earned: user=%d, badge=%s", user.id, badge.name)

    return newly_earned


def _get_user_stats(user) -> dict:
    """Get aggregated user game stats for sidebar/header."""
    stats = UserGameScore.objects.filter(user=user).aggregate(
        total_xp=Sum("total_xp"),
        total_coins=Sum("total_coins"),
        badges_count=Count("user__badges"),
    )
    return {
        "total_xp": stats["total_xp"] or 0,
        "total_coins": stats["total_coins"] or 0,
        "badges_count": stats["badges_count"] or 0,
    }


# ---------------------------------------------------------------------------
# Game Hub
# ---------------------------------------------------------------------------

def _games_hub_etag(request, *args, **kwargs) -> str:
    """ETAG for games hub — changes when game count or user XP changes."""
    from django.core.cache import cache as dj_cache
    user_id = request.user.id
    cache_key = f"games_hub_etag_{user_id}"
    etag = dj_cache.get(cache_key)
    if etag:
        return etag

    game_count = Game.objects.filter(is_active=True).count()
    user_xp = UserGameScore.objects.filter(user=request.user).aggregate(
        total=Sum("total_xp")
    )["total"] or 0
    raw = f"{game_count}:{user_xp}:{user_id}"
    etag = hashlib.md5(raw.encode()).hexdigest()
    dj_cache.set(cache_key, etag, 60)
    return etag


@condition(etag_func=_games_hub_etag)
@login_required
def games_index_view(request: HttpRequest) -> HttpResponse:
    """Games hub — all available games with user stats."""
    games = Game.objects.filter(is_active=True).order_by("sort_order")
    user_stats = _get_user_stats(request.user)

    # Per-game user scores
    user_scores = {}
    for score in UserGameScore.objects.filter(user=request.user):
        user_scores[score.game_id] = score

    # Recent badges
    recent_badges = (
        UserBadge.objects.filter(user=request.user)
        .select_related("badge")
        .order_by("-earned_at")[:5]
    )

    # Leaderboard (top 10)
    leaderboard = (
        UserGameScore.objects.filter(game__isnull=False)
        .values("user__id", "user__first_name", "user__last_name")
        .annotate(total_xp=Sum("total_xp"))
        .order_by("-total_xp")[:10]
    )

    return render(request, "web/games_index.html", {
        "games": games,
        "user_scores": user_scores,
        "user_stats": user_stats,
        "recent_badges": recent_badges,
        "leaderboard": leaderboard,
    })


# ---------------------------------------------------------------------------
# Game 1: Imlo Minalari
# ---------------------------------------------------------------------------

@login_required
def imlo_mines_view(request: HttpRequest) -> HttpResponse:
    """Imlo Minalari — find spelling errors in text."""
    game = get_object_or_404(Game, slug=Game.GameType.IMLO_MINA, is_active=True)
    levels = GameLevel.objects.filter(game=game, is_active=True).order_by("sort_order")

    user_stats = _get_user_stats(request.user)
    imlo_score = UserGameScore.objects.filter(user=request.user, game=game).first()

    # Pick a random level or get specific one
    level_id = request.GET.get("level")
    if level_id:
        level = get_object_or_404(GameLevel, id=level_id, game=game, is_active=True)
    else:
        level = levels.filter(difficulty__lte=3).order_by("?").first()
        if not level:
            level = levels.first()

    if level is None:
        logger.warning("No active levels found for game: %s", game.slug)
        messages.error(request, "Hozircha bu o'yin uchun mavjud darajalar yo'q.")
        return redirect("/games/")

    return render(request, "web/imlo_mines.html", {
        "game": game,
        "level": level,
        "levels": levels,
        "user_stats": user_stats,
        "imlo_score": imlo_score,
    })


@login_required
@require_POST
def imlo_check_view(request: HttpRequest) -> HttpResponse:
    """Check imlo answer via HTMX — returns partial HTML."""
    game = get_object_or_404(Game, slug=Game.GameType.IMLO_MINA, is_active=True)
    level_id = request.POST.get("level_id")
    word_index = request.POST.get("word_index", type=int)
    action = request.POST.get("action")  # "fix" or "flag"

    level = get_object_or_404(GameLevel, id=level_id, game=game)
    data = level.question_data

    # word_index refers to the position in the text words array
    error_position = data.get("error_word_index", 0)
    is_correct_fix = (action == "fix" and word_index == error_position)
    is_correct = is_correct_fix or (action == "skip")

    combo = int(request.POST.get("combo", 0))
    if is_correct:
        combo += 1
    else:
        combo = 0

    result = _award_xp(
        request.user, game, is_correct,
        combo=combo,
    )

    return render(request, "web/imlo_result_partial.html", {
        "is_correct": is_correct,
        "result": result,
        "combo": combo,
        "level": level,
        "data": data,
        "word_index": word_index,
        "action": action,
    })


# ---------------------------------------------------------------------------
# Game 2: Navoiy vs Dunyo (G'azal Puzzle)
# ---------------------------------------------------------------------------

@login_required
def gazal_puzzle_view(request: HttpRequest) -> HttpResponse:
    """G'azal Puzzle — arrange poem lines in correct order."""
    game = get_object_or_404(Game, slug=Game.GameType.GAZAL_PUZZLE, is_active=True)
    levels = GameLevel.objects.filter(game=game, is_active=True).order_by("sort_order")

    user_stats = _get_user_stats(request.user)
    gazal_score = UserGameScore.objects.filter(user=request.user, game=game).first()

    level_id = request.GET.get("level")
    if level_id:
        level = get_object_or_404(GameLevel, id=level_id, game=game, is_active=True)
    else:
        level = levels.filter(difficulty__lte=3).order_by("?").first()
        if not level:
            level = levels.first()

    if level is None:
        logger.warning("No active levels found for game: %s", game.slug)
        messages.error(request, "Hozircha bu o'yin uchun mavjud darajalar yo'q.")
        return redirect("/games/")

    # Shuffle lines for display
    data = level.question_data
    lines = list(data.get("bayt_lines", []))
    shuffled = lines.copy()
    random.shuffle(shuffled)

    return render(request, "web/gazal_puzzle.html", {
        "game": game,
        "level": level,
        "levels": levels,
        "user_stats": user_stats,
        "gazal_score": gazal_score,
        "shuffled_lines": shuffled,
        "original_lines": lines,
    })


@login_required
@require_POST
def gazal_check_view(request: HttpRequest) -> HttpResponse:
    """Check gazal order via HTMX."""
    game = get_object_or_404(Game, slug=Game.GameType.GAZAL_PUZZLE, is_active=True)
    level_id = request.POST.get("level_id")
    order_str = request.POST.get("order", "")  # comma-separated indices

    level = get_object_or_404(GameLevel, id=level_id, game=game)
    data = level.question_data
    bayt_lines = data.get("bayt_lines", [])

    try:
        submitted_order = [int(x) for x in order_str.split(",") if x.strip()]
    except (ValueError, AttributeError):
        submitted_order = []

    is_correct = submitted_order == list(range(len(bayt_lines)))

    combo = int(request.POST.get("combo", 0))
    if is_correct:
        combo += 1
    else:
        combo = 0

    result = _award_xp(request.user, game, is_correct, combo=combo)

    return render(request, "web/gazal_result_partial.html", {
        "is_correct": is_correct,
        "result": result,
        "combo": combo,
        "level": level,
        "data": data,
        "bayt_lines": bayt_lines,
        "submitted_order": submitted_order,
    })


# ---------------------------------------------------------------------------
# Game 3: Eski So'zlar Dueli (Lug'at Match)
# ---------------------------------------------------------------------------

@login_required
def lugat_match_view(request: HttpRequest) -> HttpResponse:
    """Memory card match game for old-new word pairs."""
    game = get_object_or_404(Game, slug=Game.GameType.LUGAT_MATCH, is_active=True)
    levels = GameLevel.objects.filter(game=game, is_active=True).order_by("sort_order")

    user_stats = _get_user_stats(request.user)
    lugat_score = UserGameScore.objects.filter(user=request.user, game=game).first()

    level_id = request.GET.get("level")
    if level_id:
        level = get_object_or_404(GameLevel, id=level_id, game=game, is_active=True)
    else:
        level = levels.filter(difficulty__lte=3).order_by("?").first()
        if not level:
            level = levels.first()

    if level is None:
        logger.warning("No active levels found for game: %s", game.slug)
        messages.error(request, "Hozircha bu o'yin uchun mavjud darajalar yo'q.")
        return redirect("/games/")

    data = level.question_data
    pairs = data.get("pairs", [])

    # Create cards: each pair becomes 2 cards (old + new)
    cards = []
    for i, pair in enumerate(pairs):
        cards.append({"id": f"old_{i}", "pair_id": i, "text": pair.get("old", ""), "type": "old"})
        cards.append({"id": f"new_{i}", "pair_id": i, "text": pair.get("new", ""), "type": "new"})
    random.shuffle(cards)

    return render(request, "web/lugat_match.html", {
        "game": game,
        "level": level,
        "levels": levels,
        "user_stats": user_stats,
        "lugat_score": lugat_score,
        "cards": cards,
        "pairs": pairs,
    })


@login_required
@require_POST
def lugat_check_view(request: HttpRequest) -> HttpResponse:
    """Check match pair via HTMX."""
    game = get_object_or_404(Game, slug=Game.GameType.LUGAT_MATCH, is_active=True)
    card1_id = request.POST.get("card1_id", "")
    card2_id = request.POST.get("card2_id", "")

    # Parse pair indices
    is_match = False
    if card1_id.startswith("old_") and card2_id.startswith("new_"):
        idx1 = int(card1_id.replace("old_", ""))
        idx2 = int(card2_id.replace("new_", ""))
        is_match = idx1 == idx2
    elif card1_id.startswith("new_") and card2_id.startswith("old_"):
        idx1 = int(card1_id.replace("new_", ""))
        idx2 = int(card2_id.replace("old_", ""))
        is_match = idx1 == idx2

    combo = int(request.POST.get("combo", 0))
    if is_match:
        combo += 1
    else:
        combo = 0

    result = _award_xp(request.user, game, is_match, combo=combo)

    return render(request, "web/lugat_result_partial.html", {
        "is_correct": is_match,
        "result": result,
        "combo": combo,
        "card1_id": card1_id,
        "card2_id": card2_id,
    })


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

@login_required
def leaderboard_view(request: HttpRequest) -> HttpResponse:
    """Full leaderboard page."""
    user_stats = _get_user_stats(request.user)
    board = _get_leaderboard()

    return render(request, "web/leaderboard.html", {
        "leaderboard": board,
        "user_stats": user_stats,
    })


@login_required
def leaderboard_partial_view(request: HttpRequest) -> HttpResponse:
    """Leaderboard HTMX partial for live updates."""
    board = _get_leaderboard()
    return render(request, "web/leaderboard_partial.html", {
        "leaderboard": board,
    })


def _get_leaderboard() -> list:
    """Get top 10 players by total XP across all games."""
    return (
        UserGameScore.objects
        .values("user__id", "user__first_name", "user__last_name")
        .annotate(
            total_xp=Sum("total_xp"),
            total_coins=Sum("total_coins"),
            games_played=Sum("games_played"),
            total_correct=Sum("correct_answers"),
        )
        .order_by("-total_xp")[:10]
    )


# ---------------------------------------------------------------------------
# Full Leaderboard Page
# ---------------------------------------------------------------------------

@login_required
def leaderboard_full_view(request: HttpRequest) -> HttpResponse:
    """To'liq leaderboard sahifasi — level tizimi, haftalik challenge, streak."""
    from apps.games.models import (
        DailyStreak, UserGameScore, WeeklyChallenge, UserChallenge,
        get_player_level,
    )
    from apps.games.models import LEVEL_THRESHOLDS

    user = request.user

    # User's total XP
    user_xp = (
        UserGameScore.objects.filter(user=user)
        .aggregate(total=Sum("total_xp"))["total"] or 0
    )
    my_level_info = get_player_level(user_xp)

    # Level name mapping
    level_names = {
        1: "Boshlang'ich", 5: "O'quvchi", 10: "Tajribali",
        15: "Mutaxassis", 20: "Usta", 25: "Katta Usta",
        30: "Ekspert", 35: "Master", 40: "Grand Master",
        45: "Legend", 50: "Titan",
    }
    level_name = "Boshlang'ich"
    for lvl in sorted(level_names.keys(), reverse=True):
        if my_level_info["level"] >= lvl:
            level_name = level_names[lvl]
            break

    my_stats = {
        **my_level_info,
        "total_xp": user_xp,
        "level_name": level_name,
    }

    # Full leaderboard (top 50)
    raw_board = (
        UserGameScore.objects
        .values("user__id", "user__first_name", "user__last_name")
        .annotate(
            total_xp=Sum("total_xp"),
            total_coins=Sum("total_coins"),
            games_played=Sum("games_played"),
        )
        .order_by("-total_xp")[:50]
    )

    leaderboard = []
    for entry in raw_board:
        lvl_info = get_player_level(entry["total_xp"] or 0)
        leaderboard.append({
            "id": entry["user__id"],
            "name": f"{entry['user__first_name']} {entry['user__last_name']}",
            "total_xp": entry["total_xp"] or 0,
            "total_coins": entry["total_coins"] or 0,
            "games_played": entry["games_played"] or 0,
            "level": lvl_info["level"],
            "is_me": entry["user__id"] == user.id,
        })

    # Current weekly challenge
    now = timezone.now()
    current_challenge = WeeklyChallenge.objects.filter(
        starts_at__lte=now, ends_at__gte=now, is_active=True,
    ).first()

    my_challenge_progress = 0
    my_challenge_current = 0
    if current_challenge:
        uc = UserChallenge.objects.filter(
            user=user, challenge=current_challenge,
        ).first()
        if uc:
            my_challenge_progress = uc.progress_pct
            my_challenge_current = uc.current_value

    # Streak
    streak_obj, _ = DailyStreak.objects.get_or_create(user=user)

    # Streak rewards: (days, (xp, coins))
    streak_rewards = [
        (3, (30, 15)),
        (7, (75, 35)),
        (14, (150, 75)),
        (30, (500, 250)),
    ]

    ctx = {
        "my_stats": my_stats,
        "leaderboard": leaderboard,
        "current_challenge": current_challenge,
        "my_challenge_progress": my_challenge_progress,
        "my_challenge_current": my_challenge_current,
        "my_streak": streak_obj.current_streak,
        "streak_rewards": streak_rewards,
    }

    return render(request, "web/leaderboard.html", ctx)
