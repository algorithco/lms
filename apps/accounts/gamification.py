"""
Gamification & Streak Engine (apps/accounts/gamification.py).

Duolingo-style daily habit loops:
- Streak flame (🔥 5 kun, 10 kun)
- Streak freeze protection
- XP rewards per educational action
- Weekly E-Sport Leagues (Bronze, Silver, Gold, Diamond)
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Dict

from django.utils import timezone

logger = logging.getLogger(__name__)


def record_user_activity(
    user,
    xp_amount: int = 20,
    activity_type: str = "general",
) -> Dict[str, Any]:
    """Record learning activity, update streak counter, and award XP."""
    if not user or not user.is_authenticated:
        return {"ok": False, "reason": "unauthenticated"}

    from apps.accounts.models import Profile

    profile, _ = Profile.objects.get_or_create(user=user)
    today = timezone.localdate()
    last_date = profile.last_activity_date

    streak_incremented = False
    streak_freeze_used = False

    if last_date == today:
        # Already active today — maintain streak, add XP
        pass
    elif last_date == today - timedelta(days=1):
        # Active yesterday — increment streak!
        profile.current_streak += 1
        if profile.current_streak > profile.longest_streak:
            profile.longest_streak = profile.current_streak
        profile.last_activity_date = today
        streak_incremented = True
    elif last_date is None:
        # First activity ever
        profile.current_streak = 1
        profile.longest_streak = max(profile.longest_streak, 1)
        profile.last_activity_date = today
        streak_incremented = True
    else:
        # Missed at least 1 day
        days_missed = (today - last_date).days
        if days_missed == 2 and profile.streak_freeze_count > 0:
            # Shield protected yesterday's miss!
            profile.streak_freeze_count -= 1
            streak_freeze_used = True
            profile.current_streak += 1
            if profile.current_streak > profile.longest_streak:
                profile.longest_streak = profile.current_streak
            profile.last_activity_date = today
        else:
            # Streak extinguished, restart
            profile.current_streak = 1
            profile.last_activity_date = today

    # Award XP
    profile.xp_points += xp_amount
    profile.weekly_xp += xp_amount

    # Dynamic promotion check based on weekly threshold
    if (
        profile.weekly_xp >= 800
        and profile.weekly_league != Profile.LeagueChoice.DIAMOND
    ):
        profile.weekly_league = Profile.LeagueChoice.DIAMOND
    elif profile.weekly_xp >= 400 and profile.weekly_league in (
        Profile.LeagueChoice.BRONZE,
        Profile.LeagueChoice.SILVER,
    ):
        profile.weekly_league = Profile.LeagueChoice.GOLD
    elif (
        profile.weekly_xp >= 150
        and profile.weekly_league == Profile.LeagueChoice.BRONZE
    ):
        profile.weekly_league = Profile.LeagueChoice.SILVER

    profile.save(
        update_fields=[
            "current_streak",
            "longest_streak",
            "last_activity_date",
            "streak_freeze_count",
            "xp_points",
            "weekly_xp",
            "weekly_league",
        ]
    )

    return {
        "ok": True,
        "current_streak": profile.current_streak,
        "longest_streak": profile.longest_streak,
        "streak_incremented": streak_incremented,
        "streak_freeze_used": streak_freeze_used,
        "xp_earned": xp_amount,
        "total_xp": profile.xp_points,
        "weekly_xp": profile.weekly_xp,
        "league": profile.weekly_league,
    }


def get_user_streak_info(user) -> Dict[str, Any]:
    """Return user's streak status, daily goal progress, and league info."""
    if not user or not user.is_authenticated:
        return {
            "current_streak": 0,
            "longest_streak": 0,
            "is_active_today": False,
            "streak_freeze_count": 0,
            "xp_points": 0,
            "weekly_xp": 0,
            "weekly_league": "bronze",
            "daily_goal_completed": False,
        }

    from apps.accounts.models import Profile

    profile, _ = Profile.objects.get_or_create(user=user)
    today = timezone.localdate()
    is_active_today = profile.last_activity_date == today

    # If user missed more than 1 day and has no freeze, preview 0
    effective_streak = profile.current_streak
    if profile.last_activity_date and (today - profile.last_activity_date).days > 1:
        if profile.streak_freeze_count == 0:
            effective_streak = 0

    return {
        "current_streak": effective_streak,
        "longest_streak": profile.longest_streak,
        "is_active_today": is_active_today,
        "streak_freeze_count": profile.streak_freeze_count,
        "xp_points": profile.xp_points,
        "weekly_xp": profile.weekly_xp,
        "weekly_league": profile.weekly_league,
        "daily_goal_completed": is_active_today,
    }


def get_weekly_league_leaderboard(user) -> Dict[str, Any]:
    """Return the weekly league leaderboard for the user's tier."""
    from apps.accounts.models import Profile

    profile, _ = (
        Profile.objects.get_or_create(user=user)
        if user and user.is_authenticated
        else (None, False)
    )
    target_league = profile.weekly_league if profile else Profile.LeagueChoice.BRONZE

    top_profiles = (
        Profile.objects.filter(weekly_league=target_league)
        .select_related("user")
        .order_by("-weekly_xp", "-xp_points")[:20]
    )

    participants = []
    user_rank = None
    for idx, p in enumerate(top_profiles, start=1):
        is_me = user and user.is_authenticated and p.user_id == user.id
        if is_me:
            user_rank = idx
        name = p.user.get_full_name() or p.user.email.split("@")[0]
        participants.append(
            {
                "rank": idx,
                "user_id": p.user_id,
                "name": name,
                "avatar_url": p.avatar.url if p.avatar else None,
                "weekly_xp": p.weekly_xp,
                "is_current_user": bool(is_me),
                "tier_badge": "🥇"
                if idx == 1
                else "🥈"
                if idx == 2
                else "🥉"
                if idx == 3
                else f"#{idx}",
            }
        )

    # Next Sunday 23:59 calculation
    now = timezone.now()
    days_until_sunday = (6 - now.weekday()) % 7
    sunday_end = (now + timedelta(days=days_until_sunday)).replace(
        hour=23, minute=59, second=59
    )

    return {
        "league": target_league,
        "league_title": dict(Profile.LeagueChoice.choices).get(
            target_league, target_league.title()
        ),
        "user_rank": user_rank
        or (len(participants) + 1 if user and user.is_authenticated else None),
        "participants": participants,
        "resets_in_hours": max(1, int((sunday_end - now).total_seconds() // 3600)),
    }
