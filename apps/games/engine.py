"""
Games engine — shared XP, combo, and badge logic.

Used by both the legacy Django views (HTMX) and the React SPA JSON API
(apps.webapi.views_games) to ensure identical behavior.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Max, Sum
from django.utils import timezone

from .models import Badge, Game, GameLevel, UserBadge, UserGameCompletion, UserGameScore

# XP bonus constants
COMBO_BONUS_XP = 5  # extra XP per combo level
STREAK_MILESTONES = {3: "🔥 3x COMBO!", 5: "⚡ 5x SUPER COMBO!", 10: "🌟 10x LEGENDARY!"}


# ---------------------------------------------------------------------------
# Helper: XP & Badge engine
# ---------------------------------------------------------------------------

@transaction.atomic
def award_xp(
    user,
    game: Game,
    is_correct: bool,
    time_seconds: int = 0,
    level: GameLevel | None = None,
    challenge_key: str = "level",
) -> dict[str, Any]:
    """
    Award XP/coins and check for badge unlocks.

    Returns dict with XP earned, coins earned, and any new badges.
    """
    score, _ = UserGameScore.objects.get_or_create(user=user, game=game)
    # Serialize each game's reward writes. The unique completion constraint
    # also prevents concurrent duplicate credits for the same item.
    score = UserGameScore.objects.select_for_update().get(user=user, game=game)
    completion_created = False
    if is_correct and level is not None:
        _, completion_created = UserGameCompletion.objects.get_or_create(
            score=score,
            level=level,
            challenge_key=challenge_key,
        )
    already_completed = is_correct and level is not None and not completion_created
    credited_correct = is_correct and not already_completed
    combo = (
        score.current_streak
        if already_completed
        else score.current_streak + 1 if credited_correct else 0
    )
    if credited_correct:
        multiplier = float(game.combo_multiplier) ** min(max(combo - 1, 0), 5)
        xp_earned = int(game.xp_per_correct * multiplier)
        coins_earned = int(game.coins_per_correct * multiplier)
    else:
        xp_earned = 0
        coins_earned = 0

    score.current_streak = combo
    score.total_xp = F("total_xp") + xp_earned
    score.total_coins = F("total_coins") + coins_earned
    score.last_played_at = timezone.now()
    update_fields = ["current_streak", "total_xp", "total_coins", "last_played_at"]
    if credited_correct:
        score.games_played = F("games_played") + 1
        update_fields.append("games_played")
    if credited_correct:
        score.correct_answers = F("correct_answers") + 1
        update_fields.append("correct_answers")
        if combo > score.best_streak:
            score.best_streak = combo
            update_fields.append("best_streak")
    elif not is_correct:
        score.wrong_answers = F("wrong_answers") + 1
        update_fields.append("wrong_answers")

    if time_seconds > 0 and (score.best_time_seconds == 0 or time_seconds < score.best_time_seconds):
        score.best_time_seconds = time_seconds
        update_fields.append("best_time_seconds")

    score.save(update_fields=update_fields)
    score.refresh_from_db()

    # Badge XP is credited once to this game-score row, not multiplied by the
    # number of games the user has played.
    new_badges = _check_badges(user, score)
    score.refresh_from_db()
    if score.total_xp > score.high_score:
        score.high_score = score.total_xp
        score.save(update_fields=["high_score"])

    return {
        "xp_earned": xp_earned,
        "coins_earned": coins_earned,
        "total_xp": score.total_xp,
        "total_coins": score.total_coins,
        "combo": combo,
        "streak": combo,
        "new_badges": [{"name": b.badge.name, "emoji": b.badge.icon_emoji} for b in new_badges],
        "already_completed": already_completed,
    }


def _check_badges(user, reward_score: UserGameScore) -> list:
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
            ub, created = UserBadge.objects.get_or_create(user=user, badge=badge)
            if created:
                UserGameScore.objects.filter(pk=reward_score.pk).update(
                    total_xp=F("total_xp") + badge.xp_bonus
                )
                newly_earned.append(ub)

    return newly_earned


def get_user_stats(user) -> dict:
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


def _get_leaderboard(limit: int = 10) -> list:
    """Get top players by total XP across all games."""
    return (
        UserGameScore.objects
        .values("user__id", "user__first_name", "user__last_name")
        .annotate(
            total_xp=Sum("total_xp"),
            total_coins=Sum("total_coins"),
            games_played=Sum("games_played"),
            total_correct=Sum("correct_answers"),
        )
        .order_by("-total_xp")[:limit]
    )


def get_leaderboard_full() -> list:
    """Full leaderboard with level info."""
    from .models import LEVEL_THRESHOLDS, get_player_level

    raw_board = _get_leaderboard(50)

    level_names = {
        1: "Boshlang'ich", 5: "O'quvchi", 10: "Tajribali",
        15: "Mutaxassis", 20: "Usta", 25: "Katta Usta",
        30: "Ekspert", 35: "Master", 40: "Grand Master",
        45: "Legend", 50: "Titan",
    }

    leaderboard = []
    for entry in raw_board:
        lvl_info = get_player_level(entry["total_xp"] or 0)
        level_name = "Boshlang'ich"
        for lvl in sorted(level_names.keys(), reverse=True):
            if lvl_info["level"] >= lvl:
                level_name = level_names[lvl]
                break

        leaderboard.append({
            "id": entry["user__id"],
            "name": f"{entry['user__first_name']} {entry['user__last_name']}",
            "total_xp": entry["total_xp"] or 0,
            "total_coins": entry["total_coins"] or 0,
            "games_played": entry["games_played"] or 0,
            "level": lvl_info["level"],
            "level_name": level_name,
        })
    return leaderboard


def get_games_hub_etag(request, *args, **kwargs) -> str:
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


def pick_level(game, level_id=None):
    """Pick a random level or get specific one."""
    levels = GameLevel.objects.filter(game=game, is_active=True).order_by("sort_order")
    if level_id:
        from django.shortcuts import get_object_or_404
        return get_object_or_404(GameLevel, id=level_id, game=game, is_active=True), levels
    level = levels.filter(difficulty__lte=3).order_by("?").first() or levels.first()
    return level, levels


def gazal_puzzle_order(level, user_id: int, data: dict) -> tuple[list[str], list[int]]:
    """Return a stable, user-specific scramble and the expected display order."""
    lines = data.get("bayt_lines") if isinstance(data, dict) else None
    if (
        not isinstance(lines, list)
        or len(lines) < 2
        or any(not isinstance(line, str) or not line.strip() for line in lines)
    ):
        raise ValueError("Gazal level must contain at least two non-empty lines.")

    correct_order = data.get("correct_order", list(range(len(lines))))
    if (
        not isinstance(correct_order, list)
        or any(type(position) is not int for position in correct_order)
        or sorted(correct_order) != list(range(len(lines)))
    ):
        raise ValueError("Gazal level has an invalid correct order.")

    seed = hashlib.sha256(
        f"{settings.SECRET_KEY}:gazal:{user_id}:{level.pk}".encode()
    ).digest()
    shuffled_indexes = list(range(len(lines)))
    random.Random(int.from_bytes(seed, "big")).shuffle(shuffled_indexes)
    # Avoid serving a solved puzzle on first load when the shuffle matches the
    # configured canonical order exactly.
    if len(shuffled_indexes) > 1 and shuffled_indexes == correct_order:
        shuffled_indexes = shuffled_indexes[1:] + shuffled_indexes[:1]

    expected_order = [shuffled_indexes.index(source_index) for source_index in correct_order]
    return [lines[index] for index in shuffled_indexes], expected_order


def get_game_content(game, level, data, user_id: int):
    """Generate game-specific content from level data."""
    content: dict = {}
    if game.slug == "imlo_mina":
        text = str(data.get("text", ""))
        content = {"text": text, "words": text.split()}
    elif game.slug == "gazal_puzzle":
        shuffled, _expected_order = gazal_puzzle_order(level, user_id, data)
        content = {"shuffled_lines": shuffled, "line_count": len(shuffled)}
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
    return content