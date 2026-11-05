"""When a finished test earns XP.

XP is a learning reward, so a result that shows no learning earns none:

* fewer than 30 % of the questions answered (a blank or near-blank paper);
* finished implausibly fast (under ``MIN_SECONDS_PER_QUESTION`` per question,
  and never less than ``MIN_SECONDS``): clicking through to farm XP;
* the same test already paid out its daily ceiling (``MAX_XP_PER_TEST_PER_DAY``),
  so retaking one test over and over cannot be farmed either.

``xp_for_result`` is a pure function (no database, no clock) so the rules are tested
directly; ``award_test_xp`` adds the per-day memory.
"""

from __future__ import annotations

from django.core.cache import cache
from django.utils import timezone

MIN_ANSWERED_RATIO = 0.30
MIN_SECONDS_PER_QUESTION = 3
MIN_SECONDS = 20
XP_PASSED = 25
XP_FINISHED = 15
#: One passed attempt plus one more finished attempt of the same test per day.
MAX_XP_PER_TEST_PER_DAY = XP_PASSED + XP_FINISHED


def xp_for_result(
    *,
    total_questions: int,
    answered: int,
    time_taken_seconds: int | None,
    passed: bool,
    xp_already_today: int = 0,
) -> int:
    """XP this result earns (0 when it does not qualify)."""
    if total_questions <= 0 or answered / total_questions < MIN_ANSWERED_RATIO:
        return 0
    if time_taken_seconds is not None and time_taken_seconds < max(MIN_SECONDS, MIN_SECONDS_PER_QUESTION * total_questions):
        return 0
    base = XP_PASSED if passed else XP_FINISHED
    return max(0, min(base, MAX_XP_PER_TEST_PER_DAY - max(0, xp_already_today)))


def _day_key(user_id: int, test_id: int) -> str:
    return f"test_xp:{user_id}:{test_id}:{timezone.localdate().isoformat()}"


def award_test_xp(user, result, attempt) -> int:
    """XP to give for this submitted attempt (and remember it for today's ceiling)."""
    key = _day_key(user.pk, attempt.test_id)
    already = int(cache.get(key, 0) or 0)
    answered = int(getattr(result, "correct_answers", 0) or 0) + int(getattr(result, "wrong_answers", 0) or 0)
    xp = xp_for_result(
        total_questions=int(getattr(result, "total_questions", 0) or 0),
        answered=answered,
        time_taken_seconds=getattr(result, "time_taken_seconds", None),
        passed=bool(getattr(result, "is_passed", False)),
        xp_already_today=already,
    )
    if xp:
        cache.set(key, already + xp, 60 * 60 * 36)
    return xp
