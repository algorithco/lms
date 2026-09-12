"""
Arena services — matchmaking, ELO rating, duel scoring, rewards, achievements.

Pure service layer used by the WebSocket consumer, HTTP views, the Telegram
bot and the Mini App. Keeps all business rules (ELO math, combo/time bonuses,
XP/coin rewards, badge conditions) in one testable place.

Scoring model (per correct answer):
    points = base_points + combo_bonus + time_bonus

        base_points  = question.points (default 10)
        combo_bonus  = min(streak - 1, 5) * 2        (consecutive correct answers)
        time_bonus   = base * tier                    (speed tiers below)

ELO model:
    K = 32, expected = 1 / (1 + 10 ** ((r_opp - r_me) / 400)),
    new = max(100, round(r + K * (outcome - expected)))
    outcome: win=1.0, draw=0.5, loss=0.0
"""
from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

if TYPE_CHECKING:  # quoted annotations only (local imports avoid cycles)
    from .models import ArenaProfile, ArenaRoom

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ELO_INITIAL = 1000
ELO_K = 32
ELO_FLOOR = 100

# Speed tiers: (max_seconds, bonus fraction of base points)
TIME_BONUS_TIERS = [
    (3, 0.5),   # ≤3s  → +50%
    (5, 0.3),   # ≤5s  → +30%
    (8, 0.15),  # ≤8s  → +15%
]

COMBO_BONUS_PER_STEP = 2
COMBO_BONUS_MAX_STEPS = 5

# Duel rewards (XP / coins) by outcome
REWARD_WIN = (25, 10)
REWARD_LOSS = (10, 4)
REWARD_DRAW = (15, 6)
PERFORMANCE_BONUS = (5, 2)  # extra XP/coins when best_streak >= 5

ARENA_GAME_SLUG = "arena_duel"
BOT_EMAIL = "arena.bot@lms.local"
BOT_DISPLAY_NAME = "Arena Bot"
BOT_ACCURACY = 0.7  # probability a bot answers correctly

# Elo windows used when searching for an opponent
MATCH_WINDOWS = [150, 400, 100_000]


def _bot_fallback_seconds() -> float:
    return float(getattr(settings, "ARENA_BOT_FALLBACK_SECONDS", 15))


def _countdown_seconds() -> float:
    return float(getattr(settings, "ARENA_COUNTDOWN_SECONDS", 3))


# ---------------------------------------------------------------------------
# ELO
# ---------------------------------------------------------------------------

def expected_score(rating_a: int, rating_b: int) -> float:
    """Expected score of player A against player B (0..1)."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))


def compute_elo(rating: int, opponent_rating: int, outcome: float) -> int:
    """New rating after one game. outcome: 1.0 win / 0.5 draw / 0.0 loss."""
    exp = expected_score(rating, opponent_rating)
    new_rating = rating + round(ELO_K * (outcome - exp))
    return max(ELO_FLOOR, new_rating)


# ---------------------------------------------------------------------------
# Profile / game-row helpers
# ---------------------------------------------------------------------------

def get_or_create_profile(user) -> "ArenaProfile":
    """Get or create the ArenaProfile row for a user (bot-safe)."""
    from .models import ArenaProfile
    profile, _ = ArenaProfile.objects.get_or_create(
        user=user,
        defaults={"rating": ELO_INITIAL},
    )
    return profile


def get_arena_game():
    """Get (or create) the Game row that tracks Arena XP/coins."""
    from apps.games.models import Game
    game = Game.objects.filter(slug=ARENA_GAME_SLUG).first()
    if game is None:
        game = Game.objects.create(
            name="Quiz Arena Dueli",
            slug=ARENA_GAME_SLUG,
            description="1v1 real-time quiz duel — ELO reyting, kombo va tezlik bonuslari.",
            icon_emoji="⚔️",
            xp_per_correct=10,
            coins_per_correct=5,
            is_active=False,  # hidden from the web games hub; tracked via /arena/
        )
    return game


def get_bot_user():
    """Get (or create) the shared bot account used as an AI opponent."""
    import secrets

    from django.contrib.auth import get_user_model
    User = get_user_model()
    bot = User.objects.filter(email=BOT_EMAIL).first()
    if bot is None:
        bot = User.objects.create_user(
            email=BOT_EMAIL,
            password=secrets.token_urlsafe(16),
            first_name=BOT_DISPLAY_NAME,
            last_name="",
            role="student",
            is_bot=True,
        )
    if not bot.is_bot:
        User.objects.filter(pk=bot.pk).update(is_bot=True)
        bot.is_bot = True
    return bot


# ---------------------------------------------------------------------------
# Question generation
# ---------------------------------------------------------------------------

def generate_questions_for_room(room) -> int:
    """Fill the room with questions: DB test questions first, built-in fallback pool."""
    from .models import ArenaQuestion
    from apps.tests.models import Question

    db_questions = list(
        Question.objects.filter(
            question_type__in=[
                Question.QuestionType.SINGLE_CHOICE,
                Question.QuestionType.MULTIPLE_CHOICE,
            ]
        )
        .order_by("?")[: room.total_questions]
    )

    created = 0
    for i, q in enumerate(db_questions):
        if created >= room.total_questions:
            break
        choices = list(q.choices.all())
        if len(choices) < 4:
            continue
        correct_letter = None
        for ci, c in enumerate(choices[:4]):
            if c.is_correct:
                correct_letter = chr(97 + ci)
                break
        if correct_letter is None:
            continue

        ArenaQuestion.objects.create(
            room=room,
            question_text=q.text,
            option_a=choices[0].text,
            option_b=choices[1].text,
            option_c=choices[2].text,
            option_d=choices[3].text,
            correct_answer=correct_letter,
            position=created,
            points=10,
        )
        created += 1

    if created < room.total_questions:
        fallback_questions = [
            {"text": "Ona tili so'zining to'g'ri yozilishi?", "a": "Ona tili", "b": "Ona-tili", "c": "Onatili", "d": "Ana tili", "correct": "a"},
            {"text": "Qaysi jumlada vergul to'g'ri ishlatilgan?", "a": "U keldi va ketdi", "b": "U keldi, va ketdi", "c": "U keldi, ketdi", "d": "U, keldi ketdi", "correct": "c"},
            {"text": "Alisher Navoiy nechinchi asrda yashagan?", "a": "XIV asr", "b": "XV asr", "c": "XVI asr", "d": "XIII asr", "correct": "b"},
            {"text": "'She'r' so'zining to'g'ri plural shakli?", "a": "She'rlar", "b": "She'rlari", "c": "She'rim", "d": "She'rdan", "correct": "a"},
            {"text": "Qaysi so'z ot chiqarish shaklida?", "a": "Kitob", "b": "Kitobdan", "c": "Kitobga", "d": "Kitobda", "correct": "b"},
            {"text": "'Gullar' so'zida nechta unli harf bor?", "a": "2", "b": "3", "c": "4", "d": "1", "correct": "b"},
            {"text": "Navoiyning mashhur asari?", "a": "Boburnoma", "b": "Xamsa", "c": "Muqaddima", "d": "Muhokama", "correct": "b"},
            {"text": "Gap tuzilishida faol fe'l qaysi?", "a": "Kitob", "b": "Katta", "c": "O'qidi", "d": "Bugun", "correct": "c"},
            {"text": "'Yurak' so'zining sinonimi?", "a": "Bosh", "b": "Qalb", "c": "Ko'z", "d": "Qo'l", "correct": "b"},
            {"text": "Qaysi jumlada maf'ul to'g'ri aniqlangan?", "a": "O'quvchi kitobni o'qidi", "b": "O'quvchi kitob o'qidi", "c": "Kitob o'qidi o'quvchi", "d": "O'qidi o'quvchi kitob", "correct": "a"},
            {"text": "'O'zbekiston' so'zida nechta unli harf bor?", "a": "3", "b": "4", "c": "5", "d": "2", "correct": "b"},
            {"text": "Qaysi so'z sifat?", "a": "Ko'cha", "b": "Chiroyli", "c": "O'qish", "d": "Deraza", "correct": "b"},
            {"text": "'Kitob' so'zining kelishik shakli?", "a": "Kitoblar", "b": "Kitobim", "c": "Kitobga", "d": "Kitobchi", "correct": "c"},
            {"text": "O'zbek alifbosida nechta harf bor?", "a": "26", "b": "28", "c": "29", "d": "30", "correct": "c"},
            {"text": "'Mehr' so'zining ma'nosi?", "a": "Nafrat", "b": "Muhabbat", "c": "G'azab", "d": "Qayg'u", "correct": "b"},
        ]
        random.shuffle(fallback_questions)
        for q in fallback_questions[: room.total_questions - created]:
            ArenaQuestion.objects.create(
                room=room,
                question_text=q["text"],
                option_a=q["a"],
                option_b=q["b"],
                option_c=q["c"],
                option_d=q["d"],
                correct_answer=q["correct"],
                position=created,
                points=10,
            )
            created += 1

    return created


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _time_bonus_fraction(time_seconds: float) -> float:
    """Bonus fraction of base points for a response time (0 if too slow)."""
    for max_seconds, fraction in TIME_BONUS_TIERS:
        if time_seconds <= max_seconds:
            return fraction
    return 0.0


def score_answer(
    base_points: int,
    streak_before: int,
    time_seconds: float,
    is_correct: bool,
) -> dict[str, int]:
    """
    Compute points for one answer: base + combo + time bonus.

    Returns {"base_points", "combo_bonus", "time_bonus", "points", "streak"}.
    """
    if not is_correct:
        return {
            "base_points": 0,
            "combo_bonus": 0,
            "time_bonus": 0,
            "points": 0,
            "streak": 0,
        }

    streak = streak_before + 1
    combo_steps = min(max(streak - 1, 0), COMBO_BONUS_MAX_STEPS)
    combo_bonus = combo_steps * COMBO_BONUS_PER_STEP
    time_bonus = int(round(base_points * _time_bonus_fraction(time_seconds)))
    points = base_points + combo_bonus + time_bonus

    return {
        "base_points": base_points,
        "combo_bonus": combo_bonus,
        "time_bonus": time_bonus,
        "points": points,
        "streak": streak,
    }


# ---------------------------------------------------------------------------
# Answer submission (used by consumer + tests)
# ---------------------------------------------------------------------------

def submit_answer(
    room,
    user_id: int,
    answer: str,
    question_index: int,
    time_seconds: float | None = None,
) -> dict[str, Any] | None:
    """
    Grade a single answer for a player in a duel room.

    - Idempotent: a player can only answer each question once.
    - Updates ArenaPlayer (score/streak/time), writes an ArenaAnswerLog.

    Returns the scoring breakdown or None (invalid room/index/repeat answer).
    """
    from .models import ArenaAnswerLog, ArenaPlayer, ArenaQuestion, ArenaRoom

    answer = (answer or "").strip().lower()
    if answer not in ("a", "b", "c", "d"):
        return None

    try:
        room = ArenaRoom.objects.get(pk=room.pk)
        if room.status != ArenaRoom.Status.STARTED:
            return None
        question = ArenaQuestion.objects.get(room=room, position=question_index)
        player = ArenaPlayer.objects.get(room=room, player_id=user_id)

        # No double answering
        if ArenaAnswerLog.objects.filter(player=player, position=question_index).exists():
            return None
    except (ArenaRoom.DoesNotExist, ArenaQuestion.DoesNotExist, ArenaPlayer.DoesNotExist):
        return None

    if time_seconds is None:
        time_seconds = 0.0
    time_seconds = max(0.0, min(float(time_seconds), room.time_per_question))

    is_correct = answer == question.correct_answer
    breakdown = score_answer(question.points, player.streak, time_seconds, is_correct)

    with transaction.atomic():
        player.score += breakdown["points"]
        player.answered_questions += 1
        player.total_time_seconds += int(time_seconds)
        if is_correct:
            player.correct_answers += 1
            player.streak = breakdown["streak"]
            if player.streak > player.best_streak:
                player.best_streak = player.streak
        else:
            player.streak = 0
        player.save()

        ArenaAnswerLog.objects.create(
            room=room,
            player=player,
            position=question_index,
            answer=answer,
            is_correct=is_correct,
            time_taken_seconds=round(time_seconds, 2),
            points=breakdown["points"],
            base_points=breakdown["base_points"],
            combo_bonus=breakdown["combo_bonus"],
            time_bonus=breakdown["time_bonus"],
            streak=player.streak,
        )

    return {
        "is_correct": is_correct,
        "points": breakdown["points"],
        "base_points": breakdown["base_points"],
        "combo_bonus": breakdown["combo_bonus"],
        "time_bonus": breakdown["time_bonus"],
        "correct_answer": question.correct_answer,
        "streak": player.streak,
        "time_taken_seconds": round(time_seconds, 2),
    }


def bot_decide_answer(room, question_index: int, bot_user_id: int) -> dict[str, Any]:
    """Pick the bot's answer + a human-like response delay (seconds)."""
    from .models import ArenaQuestion

    try:
        question = ArenaQuestion.objects.get(room=room, position=question_index)
    except ArenaQuestion.DoesNotExist:
        return {"answer": "a", "delay": 1.0}

    if random.random() < BOT_ACCURACY:
        answer = question.correct_answer
    else:
        answer = random.choice([c for c in ("a", "b", "c", "d") if c != question.correct_answer])

    delay = random.uniform(*getattr(settings, "ARENA_BOT_ANSWER_DELAY_RANGE", (3.0, 8.0)))
    return {"answer": answer, "delay": delay}


# ---------------------------------------------------------------------------
# Room lifecycle
# ---------------------------------------------------------------------------

def _create_room_and_players(
    player1,
    player2=None,
    mode: str = "queue",
    status: str | None = None,
) -> "ArenaRoom":
    """Create a room + player rows + questions (transactional)."""
    from .models import ArenaPlayer, ArenaRoom

    with transaction.atomic():
        room = ArenaRoom.objects.create(
            player1=player1,
            player2=player2,
            mode=mode,
            status=status or ArenaRoom.Status.WAITING,
            total_questions=getattr(settings, "ARENA_QUESTIONS_PER_DUEL", 10),
            time_per_question=getattr(settings, "ARENA_TIME_PER_QUESTION", 15),
        )
        ArenaPlayer.objects.create(room=room, player=player1, is_bot=player1.is_bot)
        if player2 is not None:
            ArenaPlayer.objects.create(room=room, player=player2, is_bot=player2.is_bot)
        if room.status == ArenaRoom.Status.STARTED:
            room.started_at = timezone.now()
            room.save(update_fields=["started_at"])
            generate_questions_for_room(room)
    return room


def join_matchmaking_queue(user, channel_name: str = "") -> tuple[Any, "ArenaRoom | None"]:
    """
    Add the user to the queue and try to match them with a waiting opponent.

    Returns (queue_entry, room_or_None). When room is not None the duel can
    start immediately; otherwise the consumer schedules the bot fallback.
    """
    from .models import ArenaQueueEntry, ArenaRoom

    with transaction.atomic():
        # Invalidate any previous waiting entries for this user
        ArenaQueueEntry.objects.filter(user=user, status=ArenaQueueEntry.Status.WAITING).update(
            status=ArenaQueueEntry.Status.EXPIRED,
        )

        entry = ArenaQueueEntry.objects.create(
            user=user,
            rating=get_or_create_profile(user).rating,
            status=ArenaQueueEntry.Status.WAITING,
            channel_name=channel_name,
        )

        opponent_entry = _find_opponent(entry)

        if opponent_entry is None:
            return entry, None

        # Both entries are locked — build the duel
        from django.contrib.auth import get_user_model
        User = get_user_model()
        player1 = User.objects.get(pk=entry.user_id)
        player2 = User.objects.get(pk=opponent_entry.user_id)

        room = _create_room_and_players(player1, player2, mode=ArenaRoom.Mode.QUEUE,
                                        status=ArenaRoom.Status.STARTED)
        ArenaQueueEntry.objects.filter(pk__in=[entry.pk, opponent_entry.pk]).update(
            status=ArenaQueueEntry.Status.MATCHED,
            matched_at=timezone.now(),
            room=room,
        )
        entry.room = room
        opponent_entry.room = room
        return entry, room


def _find_opponent(entry):
    """Find a matching WAITING opponent under lock. Returns the entry or None."""
    from .models import ArenaQueueEntry

    candidates = list(
        ArenaQueueEntry.objects.select_for_update()
        .filter(status=ArenaQueueEntry.Status.WAITING)
        .exclude(pk=entry.pk)
        .order_by("created_at")
    )
    if not candidates:
        return None

    my_rating = entry.rating
    for window in MATCH_WINDOWS:
        for cand in candidates:
            if cand.status != ArenaQueueEntry.Status.WAITING:
                continue
            if abs(cand.rating - my_rating) <= window:
                return cand
    return None


def create_custom_room(user) -> "ArenaRoom":
    """Create a WAITING custom room with an invite code for a friend."""
    from .models import ArenaRoom
    room = _create_room_and_players(user, mode=ArenaRoom.Mode.CUSTOM,
                                    status=ArenaRoom.Status.WAITING)
    return room


def join_custom_room(room_code: str, user) -> tuple["ArenaRoom | None", str | None]:
    """
    Join a custom room by invite code. Returns (room, error_message).

    Player1's own consumer gets the `match_found` broadcast from the joining
    side, so both clients start the duel together.
    """
    from .models import ArenaPlayer, ArenaRoom

    code = (room_code or "").strip().upper()
    if not code:
        return None, "Xona kodi ko'rsatilmagan."

    with transaction.atomic():
        try:
            room = ArenaRoom.objects.select_for_update().get(
                room_code=code,
                mode=ArenaRoom.Mode.CUSTOM,
                status=ArenaRoom.Status.WAITING,
                player2__isnull=True,
            )
        except ArenaRoom.DoesNotExist:
            return None, f"'{code}' xonasi topilmadi yoki allaqachon boshlangan."
        if room.player1_id == user.id:
            return None, "Bu xonani o'zingiz yaratgansiz. Raqibni kutmoqdasiz."
        room.player2 = user
        room.status = ArenaRoom.Status.STARTED
        room.started_at = timezone.now()
        room.save()
        ArenaPlayer.objects.create(room=room, player=user)
        generate_questions_for_room(room)

    return room, None


def create_bot_room(user) -> "ArenaRoom":
    """Create a duel against the simulated AI opponent (mode=BOT)."""
    from .models import ArenaRoom
    bot = get_bot_user()
    room = _create_room_and_players(user, player2=bot, mode=ArenaRoom.Mode.BOT,
                                    status=ArenaRoom.Status.STARTED)
    room.bot_user = bot
    room.save(update_fields=["bot_user"])
    return room


def assign_bot_opponent(entry_or_id) -> "ArenaRoom | None":
    """
    Bot fallback: called ~15s after queueing when no human opponent appeared.

    Under lock, re-checks for a human opponent first, then creates a bot duel.
    Returns the created room, or None if the entry was already matched/expired.
    """
    from .models import ArenaQueueEntry, ArenaRoom

    if not isinstance(entry_or_id, ArenaQueueEntry):
        try:
            entry = ArenaQueueEntry.objects.get(pk=entry_or_id)
        except ArenaQueueEntry.DoesNotExist:
            return None
    else:
        entry = entry_or_id

    with transaction.atomic():
        entry = ArenaQueueEntry.objects.select_for_update().get(pk=entry.pk)
        if entry.status != ArenaQueueEntry.Status.WAITING:
            return None

        # Last chance for a human opponent
        opponent = _find_opponent(entry)
        if opponent is not None:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            player1 = User.objects.get(pk=entry.user_id)
            player2 = User.objects.get(pk=opponent.user_id)
            room = _create_room_and_players(player1, player2, mode=ArenaRoom.Mode.QUEUE,
                                            status=ArenaRoom.Status.STARTED)
            ArenaQueueEntry.objects.filter(pk__in=[entry.pk, opponent.pk]).update(
                status=ArenaQueueEntry.Status.MATCHED,
                matched_at=timezone.now(),
                room=room,
            )
            return room

        from django.contrib.auth import get_user_model
        user = get_user_model().objects.get(pk=entry.user_id)
        room = create_bot_room(user)
        entry.status = ArenaQueueEntry.Status.MATCHED
        entry.matched_at = timezone.now()
        entry.room = room
        entry.save(update_fields=["status", "matched_at", "room"])
        return room


def mark_question_sent(room_code: str, question_index: int) -> None:
    """
    Record the moment a question was actually broadcast to the clients.

    Speed bonuses are measured from this timestamp in the consumer, so it
    must reflect question DISPLAY time — not the match countdown start.
    Without this, the first question's clock includes the pre-game countdown
    and fast answers lose their time bonus. Only updates when the index is
    still the room's current question (no stale reconnects resetting it).
    """
    from .models import ArenaRoom

    try:
        room = ArenaRoom.objects.get(room_code=room_code)
    except ArenaRoom.DoesNotExist:
        return
    if room.status != ArenaRoom.Status.STARTED:
        return
    if room.current_question_index != question_index:
        return
    # Re-sending the current question after reconnect must not extend time.
    if room.question_started_at is None:
        room.question_started_at = timezone.now()
        room.save(update_fields=["question_started_at"])


def mark_question_started(room_code: str) -> bool:
    """
    Atomically mark the first question as started.

    Returns True only for the consumer that actually flipped the flag — used to
    make exactly one consumer responsible for the countdown + first question.
    """
    from .models import ArenaRoom

    with transaction.atomic():
        try:
            room = ArenaRoom.objects.select_for_update().get(room_code=room_code)
        except ArenaRoom.DoesNotExist:
            return False
        if room.status != ArenaRoom.Status.STARTED or room.question_started_at is not None:
            return False
        room.question_started_at = timezone.now()
        room.save(update_fields=["question_started_at"])
        return True


def queue_position(user) -> int:
    """Number of people ahead of the user in the queue (for display)."""
    from .models import ArenaQueueEntry
    entry = (
        ArenaQueueEntry.objects.filter(user=user, status=ArenaQueueEntry.Status.WAITING)
        .order_by("created_at")
        .first()
    )
    if entry is None:
        return 0
    return (
        ArenaQueueEntry.objects.filter(
            status=ArenaQueueEntry.Status.WAITING,
            created_at__lt=entry.created_at,
        ).count()
        + 1
    )


# ---------------------------------------------------------------------------
# Game flow control (locking helpers for the consumer)
# ---------------------------------------------------------------------------

def advance_question(
    room_code: str,
    expected_index: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Atomically move the room to the next question (or signal the end).

    Returns {"finished": bool, "index": int, "total": int, "advanced": bool}.

    Guards (all under the room row lock) so concurrent consumers can't
    double-advance or prematurely finish a duel:
    - ``expected_index``: the question the caller thinks is current. If the
      room has already moved on, the call is a stale no-op.
    - ``force=False`` (both-answered path): only advances when every player
      has answered the CURRENT question; otherwise the caller raced ahead of
      the game state and must not advance or finish anything.
    - ``force=True`` (per-question timeout path): advances the expected
      question even if nobody answered.
    Only the caller that actually advanced ("advanced": True) broadcasts the
    next question; a genuinely finished duel is signalled exactly once per
    caller and `finish_duel` is idempotent.
    """
    from .models import ArenaAnswerLog, ArenaPlayer, ArenaRoom

    with transaction.atomic():
        try:
            room = ArenaRoom.objects.select_for_update().get(room_code=room_code)
        except ArenaRoom.DoesNotExist:
            return {"finished": True, "index": 0, "total": 0, "advanced": False}

        if room.status != ArenaRoom.Status.STARTED:
            return {"finished": True, "index": room.current_question_index, "total": room.total_questions, "advanced": False}

        # Stale call — the room already moved past the question the caller saw.
        if expected_index is not None and room.current_question_index != expected_index:
            return {"finished": False, "index": room.current_question_index, "total": room.total_questions, "advanced": False}

        if not force:
            # Both-answered path: never advance past an open question.
            player_count = ArenaPlayer.objects.filter(room=room).count()
            answered = (
                ArenaAnswerLog.objects.filter(room=room, position=room.current_question_index)
                .values("player_id")
                .distinct()
                .count()
            )
            if player_count == 0 or answered < player_count:
                return {"finished": False, "index": room.current_question_index, "total": room.total_questions, "advanced": False}

        if room.current_question_index >= room.total_questions - 1:
            return {"finished": True, "index": room.current_question_index, "total": room.total_questions, "advanced": False}

        room.current_question_index += 1
        room.question_started_at = timezone.now()
        room.save(update_fields=["current_question_index", "question_started_at"])
        return {"finished": False, "index": room.current_question_index, "total": room.total_questions, "advanced": True}


def both_answered(room_code: str) -> bool:
    """True when every player in the room has answered the current question."""
    from .models import ArenaAnswerLog, ArenaPlayer, ArenaRoom

    try:
        room = ArenaRoom.objects.get(room_code=room_code)
    except ArenaRoom.DoesNotExist:
        return False
    player_count = ArenaPlayer.objects.filter(room=room).count()
    if player_count == 0:
        return False
    answered = (
        ArenaAnswerLog.objects.filter(room=room, position=room.current_question_index)
        .values("player_id")
        .distinct()
        .count()
    )
    return answered >= player_count


def get_scores(room_code: str) -> list[dict[str, Any]]:
    """Current scores for every player in the room."""
    from .models import ArenaPlayer, ArenaRoom

    try:
        room = ArenaRoom.objects.get(room_code=room_code)
    except ArenaRoom.DoesNotExist:
        return []

    players = ArenaPlayer.objects.filter(room=room).select_related("player").order_by("id")
    return [
        {
            "user_id": p.player_id,
            "name": p.player.get_full_name() or p.player.email,
            "score": p.score,
            "correct": p.correct_answers,
            "answered": p.answered_questions,
            "streak": p.streak,
            "is_bot": p.is_bot,
        }
        for p in players
    ]


# ---------------------------------------------------------------------------
# Duel completion & rewards
# ---------------------------------------------------------------------------

def finish_duel(room_code: str) -> dict[str, Any] | None:
    """
    Finish the duel: determine winner, apply ELO, award XP/coins, check badges.

    Idempotent — returns the same summary on repeat calls.
    """
    from .models import ArenaPlayer, ArenaRoom

    try:
        room = ArenaRoom.objects.get(room_code=room_code)
    except ArenaRoom.DoesNotExist:
        return None

    if room.status == ArenaRoom.Status.FINISHED:
        return _duel_summary(room)

    with transaction.atomic():
        room = ArenaRoom.objects.select_for_update().get(pk=room.pk)
        if room.status == ArenaRoom.Status.FINISHED:
            return _duel_summary(room)

        players = list(
            ArenaPlayer.objects.filter(room=room)
            .select_related("player")
            .order_by("id")
        )
        if len(players) < 1:
            room.status = ArenaRoom.Status.FINISHED
            room.finished_at = timezone.now()
            room.save(update_fields=["status", "finished_at"])
            return None

        # --- Winner -----------------------------------------------------
        if len(players) == 2:
            if players[0].score > players[1].score:
                winner = players[0]
            elif players[1].score > players[0].score:
                winner = players[1]
            else:
                winner = None
            if winner is None and players[0].correct_answers > players[1].correct_answers:
                winner = players[0]
            elif winner is None and players[1].correct_answers > players[0].correct_answers:
                winner = players[1]
        else:
            winner = players[0]

        room.winner = winner.player if winner else None
        room.status = ArenaRoom.Status.FINISHED
        room.finished_at = timezone.now()

        # --- Rewards & ELO per player ----------------------------------
        for p in players:
            profile = get_or_create_profile(p.player)
            p.rating_before = profile.rating

            if winner is None:
                outcome, xp, coins = 0.5, REWARD_DRAW[0], REWARD_DRAW[1]
            elif winner.pk == p.pk:
                outcome, xp, coins = 1.0, REWARD_WIN[0], REWARD_WIN[1]
            else:
                outcome, xp, coins = 0.0, REWARD_LOSS[0], REWARD_LOSS[1]

            # Performance bonus for long combos
            if p.best_streak >= 5:
                xp += PERFORMANCE_BONUS[0]
                coins += PERFORMANCE_BONUS[1]

            opponent = players[0] if p.pk != players[0].pk else (players[1] if len(players) > 1 else None)
            opp_rating = get_or_create_profile(opponent.player).rating if opponent else profile.rating
            new_rating = compute_elo(profile.rating, opp_rating, outcome)
            p.rating_change = new_rating - profile.rating
            p.xp_earned = xp
            p.coins_earned = coins
            p.save(update_fields=[
                "rating_before", "rating_change", "xp_earned", "coins_earned",
            ])

            # --- ArenaProfile ------------------------------------------
            profile.duels_played += 1
            profile.total_correct += p.correct_answers
            profile.total_answers += p.answered_questions
            profile.total_time_seconds += p.total_time_seconds
            if outcome == 1.0:
                profile.wins += 1
                profile.current_win_streak += 1
                profile.best_win_streak = max(profile.best_win_streak, profile.current_win_streak)
            elif outcome == 0.0:
                profile.losses += 1
                profile.current_win_streak = 0
            else:
                profile.draws += 1
            profile.rating = new_rating
            profile.save()

            # --- UserGameScore (XP/coins through the games economy) -----
            if not p.player.is_bot:
                _award_game_score(p.player, xp, coins, p.correct_answers,
                                  p.answered_questions - p.correct_answers,
                                  p.best_streak)

        room.p1_rating_before = players[0].rating_before if players else None
        room.p2_rating_before = players[1].rating_before if len(players) > 1 else None
        room.p1_rating_change = players[0].rating_change if players else 0
        room.p2_rating_change = players[1].rating_change if len(players) > 1 else 0
        room.save(update_fields=[
            "winner", "status", "finished_at",
            "p1_rating_before", "p2_rating_before",
            "p1_rating_change", "p2_rating_change",
        ])

        # --- Badges (real users only) -----------------------------------
        for p in players:
            if not p.player.is_bot:
                try:
                    award_badges(p.player)
                except Exception:
                    logger.exception("Badge award failed: user=%s", p.player_id)

    return _duel_summary(room)


def _duel_summary(room) -> dict[str, Any]:
    """Serializable summary of a finished duel."""
    from .models import ArenaPlayer

    players = list(
        ArenaPlayer.objects.filter(room=room)
        .select_related("player")
        .order_by("id")
    )
    return {
        "room_code": room.room_code,
        "status": room.status,
        "mode": room.mode,
        "winner": room.winner.get_full_name() if room.winner else "Durang",
        "winner_id": room.winner_id,
        "scores": [
            {
                "user_id": p.player_id,
                "name": p.player.get_full_name() or p.player.email,
                "score": p.score,
                "correct": p.correct_answers,
                "is_bot": p.is_bot,
                "xp_earned": p.xp_earned,
                "coins_earned": p.coins_earned,
                "rating_change": p.rating_change,
            }
            for p in players
        ],
    }


def _award_game_score(user, xp: int, coins: int, correct: int, wrong: int, best_streak: int) -> None:
    """Accumulate duel rewards into the user's UserGameScore for the arena game."""
    from django.db.models.functions import Greatest

    from apps.games.models import UserGameScore

    game = get_arena_game()
    score_row, _ = UserGameScore.objects.get_or_create(user=user, game=game)
    UserGameScore.objects.filter(pk=score_row.pk).update(
        total_xp=F("total_xp") + xp,
        total_coins=F("total_coins") + coins,
        games_played=F("games_played") + 1,
        correct_answers=F("correct_answers") + correct,
        wrong_answers=F("wrong_answers") + wrong,
        best_streak=Greatest(F("best_streak"), best_streak),
        last_played_at=timezone.now(),
    )


# ---------------------------------------------------------------------------
# Achievements / badges (arena-specific)
# ---------------------------------------------------------------------------

def award_badges(user) -> list:
    """
    Check and award the arena achievement badges.

    Types handled here (defined in apps.games.Badge):
        duel_winner_10 — 10 duel wins
        night_owl      — win a duel between 00:00 and 05:59 (Tashkent time)
        essay_master   — N graded essays (default required_value=5)
        arena_elite    — ELO rating >= required_value (default 1200)
    """
    from apps.games.models import Badge, UserBadge

    profile = get_or_create_profile(user)
    earned_ids = set(
        UserBadge.objects.filter(user=user).values_list("badge_id", flat=True)
    )
    newly_earned = []

    for badge in Badge.objects.filter(
        badge_type__in=[
            Badge.BadgeType.DUEL_WINNER_10,
            Badge.BadgeType.NIGHT_OWL,
            Badge.BadgeType.ESSAY_MASTER,
            Badge.BadgeType.ARENA_ELITE,
        ]
    ):
        if badge.id in earned_ids:
            continue

        earned = False
        if badge.badge_type == Badge.BadgeType.DUEL_WINNER_10:
            earned = profile.wins >= badge.required_value

        elif badge.badge_type == Badge.BadgeType.ARENA_ELITE:
            earned = profile.rating >= badge.required_value

        elif badge.badge_type == Badge.BadgeType.NIGHT_OWL:
            earned = _has_night_owl_win(user)

        elif badge.badge_type == Badge.BadgeType.ESSAY_MASTER:
            earned = _graded_essay_count(user) >= badge.required_value

        if earned:
            UserBadge.objects.create(user=user, badge=badge)
            # Bonus XP into the arena game economy
            try:
                from apps.games.models import UserGameScore
                score_row, _ = UserGameScore.objects.get_or_create(user=user, game=get_arena_game())
                UserGameScore.objects.filter(pk=score_row.pk).update(
                    total_xp=F("total_xp") + badge.xp_bonus,
                )
            except Exception:
                logger.exception("Badge XP bonus failed: user=%s", user.id)
            newly_earned.append(badge)
            logger.info("Arena badge earned: user=%d, badge=%s", user.id, badge.badge_type)

    return newly_earned


def _graded_essay_count(user) -> int:
    from apps.essays.models import EssaySubmission
    return EssaySubmission.objects.filter(student=user, status="graded").count()


def _has_night_owl_win(user) -> bool:
    """A duel won between 00:00 and 05:59 local (Asia/Tashkent) time."""
    from .models import ArenaRoom
    from django.utils import timezone as tz

    wins = ArenaRoom.objects.filter(winner=user, finished_at__isnull=False)
    for room in wins.iterator():
        local = tz.localtime(room.finished_at)
        if 0 <= local.hour <= 5:
            return True
    return False
