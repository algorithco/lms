"""
Integration tests for the Quiz Arena (1v1 duels).

Covers:
    1. ELO-based matchmaking (rating windows, unmatched players stay queued)
    2. Custom rooms with invite codes
    3. AI bot fallback when no human opponent appears
    4. Duel scoring: streak (combo) bonus + speed (time) bonus
    5. Duel rewards: XP/coins through the games economy, ELO updates
    6. Achievements: duel_winner_10, night_owl, essay_master, arena_elite
    7. Arena REST API (leaderboard, stats, rooms, invites)
    8. WebSocket end-to-end duels (human vs human, human vs bot)

WebSocket tests use TransactionTestCase (no transaction wrapping) so the
consumer's worker-thread DB access can see everything.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.arena import services
from apps.arena.consumers import QuizArenaConsumer
from apps.arena.models import (
    ArenaAnswerLog,
    ArenaPlayer,
    ArenaProfile,
    ArenaQuestion,
    ArenaQueueEntry,
    ArenaRoom,
)
from apps.essays.models import EssaySubmission, EssayTopic
from apps.games.models import Badge, UserBadge, UserGameScore

from .conftest import LMSBaseTestCase

User = get_user_model()

ARENA_FAST = override_settings(
    ARENA_COUNTDOWN_SECONDS=0.05,
    ARENA_BOT_FALLBACK_SECONDS=0.1,
    ARENA_BOT_ANSWER_DELAY_RANGE=(0.05, 0.1),
    ARENA_QUESTIONS_PER_DUEL=4,
    ARENA_TIME_PER_QUESTION=15,
)


def _make_user(email: str, first: str = "A", last: str = "User") -> "User":
    return User.objects.create_user(
        email=email,
        password="testpass123",
        first_name=first,
        last_name=last,
        role="student",
    )


def _set_rating(user, rating: int) -> ArenaProfile:
    profile = services.get_or_create_profile(user)
    profile.rating = rating
    profile.save(update_fields=["rating"])
    return profile


def _wrong_answer(q: "ArenaQuestion") -> str:
    """An incorrect option for a question (deterministic)."""
    options = ["a", "b", "c", "d"]
    for opt in options:
        if opt != q.correct_answer:
            return opt
    return "a"


# ============================================================================
# 1. MATCHMAKING & ROOMS
# ============================================================================

class MatchmakingTests(LMSBaseTestCase):

    def test_elo_matching_pairs_close_ratings(self):
        a = self.student
        b = _make_user("b@test.com", first="B")
        c = _make_user("c@test.com", first="C")
        _set_rating(a, 1000)
        _set_rating(b, 1005)
        _set_rating(c, 1400)

        entry_a, room_a = services.join_matchmaking_queue(a)
        self.assertIsNone(room_a, "single queued player must stay waiting")

        entry_b, room_b = services.join_matchmaking_queue(b)
        self.assertIsNotNone(room_b, "close ratings (1000 vs 1005) must match")
        self.assertEqual(room_b.mode, ArenaRoom.Mode.QUEUE)
        self.assertEqual(
            {room_b.player1_id, room_b.player2_id}, {a.id, b.id}
        )
        self.assertEqual(
            ArenaQuestion.objects.filter(room=room_b).count(),
            room_b.total_questions,
            "duel questions must be generated",
        )
        # Both queue entries are marked matched
        entry_a.refresh_from_db()
        entry_b.refresh_from_db()
        self.assertEqual(entry_a.status, ArenaQueueEntry.Status.MATCHED)
        self.assertEqual(entry_b.status, ArenaQueueEntry.Status.MATCHED)

        # Far-rating player does not match with 1000-rated player
        entry_c, room_c = services.join_matchmaking_queue(c)
        self.assertIsNone(room_c, "1400 ELO must not match 1000 ELO (window 150)")

    def test_rejoining_queue_expires_old_entries(self):
        a = self.student
        entry1, _ = services.join_matchmaking_queue(a)
        entry2, _ = services.join_matchmaking_queue(a)
        entry1.refresh_from_db()
        self.assertEqual(entry1.status, ArenaQueueEntry.Status.EXPIRED)
        self.assertEqual(entry2.status, ArenaQueueEntry.Status.WAITING)

    def test_custom_room_invite_flow(self):
        room = services.create_custom_room(self.student)
        self.assertEqual(room.status, ArenaRoom.Status.WAITING)
        self.assertEqual(room.mode, ArenaRoom.Mode.CUSTOM)
        self.assertTrue(room.room_code)

        joined, error = services.join_custom_room(room.room_code, self.teacher)
        self.assertIsNone(error)
        self.assertEqual(joined.status, ArenaRoom.Status.STARTED)
        self.assertEqual(joined.player2_id, self.teacher.id)
        self.assertGreater(ArenaQuestion.objects.filter(room=joined).count(), 0)

        third = type(self.student).objects.create_user(
            email="third-player@example.com", password="pass",
        )
        duplicate_join, duplicate_error = services.join_custom_room(room.room_code, third)
        self.assertIsNone(duplicate_join)
        self.assertIsNotNone(duplicate_error)
        room.refresh_from_db()
        self.assertEqual(room.player2_id, self.teacher.id)

    def test_custom_room_join_errors(self):
        room = services.create_custom_room(self.student)
        # Unknown code
        joined, error = services.join_custom_room("NOPE99", self.teacher)
        self.assertIsNone(joined)
        self.assertIn("topilmadi", error)
        # Creator cannot join their own room
        joined, error = services.join_custom_room(room.room_code, self.student)
        self.assertIsNone(joined)
        self.assertIn("o'zingiz", error)

    def test_bot_fallback_assigns_ai_opponent(self):
        entry, room = services.join_matchmaking_queue(self.student)
        self.assertIsNone(room)

        bot_room = services.assign_bot_opponent(entry.pk)
        self.assertIsNotNone(bot_room)
        self.assertEqual(bot_room.mode, ArenaRoom.Mode.BOT)
        self.assertTrue(bot_room.bot_user.is_bot)
        self.assertTrue(bot_room.player2.is_bot)
        self.assertEqual(bot_room.status, ArenaRoom.Status.STARTED)

        entry.refresh_from_db()
        self.assertEqual(entry.status, ArenaQueueEntry.Status.MATCHED)

        # The bot has a playable rating profile
        bot_profile = services.get_or_create_profile(bot_room.bot_user)
        self.assertEqual(bot_profile.rating, services.ELO_INITIAL)

    def test_bot_fallback_skipped_when_human_appears(self):
        entry_a, _ = services.join_matchmaking_queue(self.student)
        entry_b, room = services.join_matchmaking_queue(self.teacher)
        self.assertIsNotNone(room, "second queued player must match the first")

        result = services.assign_bot_opponent(entry_a)
        self.assertIsNone(result, "already-matched entry must not get a bot")


# ============================================================================
# 2. SCORING: STREAK + TIME BONUS
# ============================================================================

class ScoringTests(LMSBaseTestCase):

    def setUp(self):
        super().setUp()
        self.room = services.create_bot_room(self.student)
        self.player = ArenaPlayer.objects.get(room=self.room, player=self.student)
        self.bot_player = ArenaPlayer.objects.get(room=self.room, is_bot=True)
        self.questions = list(ArenaQuestion.objects.filter(room=self.room).order_by("position"))

    def test_time_bonus_and_combo(self):
        q0 = self.questions[0]
        r1 = services.submit_answer(self.room, self.student.id, q0.correct_answer, 0, time_seconds=2.0)
        self.assertIsNotNone(r1)
        self.assertEqual(r1["streak"], 1)
        # base 10 + 0 combo + 50% time bonus (5) = 15
        self.assertEqual(r1["points"], 15)
        self.assertEqual(r1["time_bonus"], 5)
        self.assertEqual(r1["combo_bonus"], 0)

        q1 = self.questions[1]
        r2 = services.submit_answer(self.room, self.student.id, q1.correct_answer, 1, time_seconds=4.0)
        self.assertEqual(r2["streak"], 2)
        # base 10 + combo min(2-1,5)*2=2 + time 30% of 10 = 3 → 15
        self.assertEqual(r2["points"], 15)
        self.assertEqual(r2["combo_bonus"], 2)
        self.assertEqual(r2["time_bonus"], 3)

        self.player.refresh_from_db()
        self.assertEqual(self.player.score, 30)
        self.assertEqual(self.player.best_streak, 2)
        self.assertEqual(self.player.total_time_seconds, 6)
        self.assertEqual(ArenaAnswerLog.objects.filter(player=self.player).count(), 2)

    def test_wrong_answer_resets_streak(self):
        q0 = self.questions[0]
        services.submit_answer(self.room, self.student.id, q0.correct_answer, 0, time_seconds=1.0)

        q1 = self.questions[1]
        wrong = "a" if q1.correct_answer != "a" else "b"
        r = services.submit_answer(self.room, self.student.id, wrong, 1, time_seconds=1.0)
        self.assertFalse(r["is_correct"])
        self.assertEqual(r["streak"], 0)
        self.assertEqual(r["points"], 0)

        self.player.refresh_from_db()
        self.assertEqual(self.player.streak, 0)
        self.assertEqual(self.player.best_streak, 1)

    def test_duplicate_answer_rejected(self):
        q0 = self.questions[0]
        first = services.submit_answer(self.room, self.student.id, q0.correct_answer, 0, time_seconds=1.0)
        self.assertIsNotNone(first)
        duplicate = services.submit_answer(self.room, self.student.id, "b", 0, time_seconds=1.0)
        self.assertIsNone(duplicate, "a player must not answer the same question twice")
        self.assertEqual(ArenaAnswerLog.objects.filter(player=self.player).count(), 1)

    def test_invalid_answer_ignored(self):
        result = services.submit_answer(self.room, self.student.id, "e", 0, time_seconds=1.0)
        self.assertIsNone(result)

    def test_mark_question_sent_starts_speed_clock_at_display_time(self):
        """The speed-bonus clock starts when the question is broadcast, not at
        match start (which includes the pre-game countdown)."""
        self.room.refresh_from_db()
        self.assertIsNone(self.room.question_started_at)

        services.mark_question_sent(self.room.room_code, 0)
        self.room.refresh_from_db()
        self.assertIsNotNone(self.room.question_started_at)
        first_ts = self.room.question_started_at

        # Reconnect re-broadcasts the same question and must preserve deadline.
        services.mark_question_sent(self.room.room_code, 0)
        self.room.refresh_from_db()
        self.assertEqual(self.room.question_started_at, first_ts)

        # A stale send (question already advanced) must NOT reset the clock
        self.room.current_question_index = 3
        self.room.save(update_fields=["current_question_index"])
        services.mark_question_sent(self.room.room_code, 0)
        self.room.refresh_from_db()
        self.assertEqual(self.room.question_started_at, first_ts)


# ============================================================================
# 3. REWARDS: XP, COINS, ELO
# ============================================================================

class RewardsTests(LMSBaseTestCase):

    def _play_bot_duel(self, student_wins: bool = True):
        """Drive a full bot duel where the student answers everything."""
        room = services.create_bot_room(self.student)
        questions = list(ArenaQuestion.objects.filter(room=room).order_by("position"))
        bot_player = ArenaPlayer.objects.get(room=room, is_bot=True)

        for i, q in enumerate(questions):
            services.submit_answer(room, self.student.id, q.correct_answer, i, time_seconds=1.0)
            wrong = "a" if q.correct_answer != "a" else "b"
            services.submit_answer(room, bot_player.player_id, wrong, i, time_seconds=1.0)

        return room

    def test_win_awards_xp_coins_and_elo(self):
        profile_before = services.get_or_create_profile(self.student)
        self.assertEqual(profile_before.rating, 1000)

        room = self._play_bot_duel(student_wins=True)
        summary = services.finish_duel(room.room_code)
        room.refresh_from_db()

        self.assertEqual(room.status, ArenaRoom.Status.FINISHED)
        self.assertEqual(room.winner_id, self.student.id)
        self.assertIsNotNone(summary)

        profile = services.get_or_create_profile(self.student)
        self.assertEqual(profile.wins, 1)
        self.assertEqual(profile.losses, 0)
        self.assertEqual(profile.duels_played, 1)
        self.assertEqual(profile.current_win_streak, 1)
        self.assertGreater(profile.rating, 1000, "winner's ELO must increase")

        # XP/coins through the games economy
        game_score = UserGameScore.objects.get(
            user=self.student, game__slug=services.ARENA_GAME_SLUG
        )
        self.assertGreaterEqual(game_score.total_xp, services.REWARD_WIN[0])
        self.assertGreaterEqual(game_score.total_coins, services.REWARD_WIN[1])
        self.assertEqual(game_score.games_played, 1)
        self.assertGreaterEqual(game_score.correct_answers, 1)

        # Summary exposes per-player rewards
        my_row = next(s for s in summary["scores"] if s["user_id"] == self.student.id)
        self.assertGreater(my_row["xp_earned"], 0)
        self.assertGreater(my_row["rating_change"], 0)

    def test_finish_duel_is_idempotent(self):
        room = self._play_bot_duel()
        first = services.finish_duel(room.room_code)
        game_score = UserGameScore.objects.get(
            user=self.student, game__slug=services.ARENA_GAME_SLUG
        )
        xp_after_first = game_score.total_xp

        second = services.finish_duel(room.room_code)
        game_score.refresh_from_db()
        self.assertEqual(game_score.total_xp, xp_after_first, "no double rewards")
        self.assertEqual(first["winner"], second["winner"])

    def test_draw_changes_elo_toward_each_other(self):
        a = self.student
        b = _make_user("rival@test.com", first="Rival")
        _set_rating(a, 1200)
        _set_rating(b, 800)

        entry_a, room_a = services.join_matchmaking_queue(a)
        entry_b, room_b = services.join_matchmaking_queue(b)
        room = room_a or room_b
        self.assertIsNotNone(room)

        # Both answer the same questions correctly → equal scores → draw
        questions = list(ArenaQuestion.objects.filter(room=room).order_by("position"))
        for i, q in enumerate(questions):
            services.submit_answer(room, a.id, q.correct_answer, i, time_seconds=5.0)
            services.submit_answer(room, b.id, q.correct_answer, i, time_seconds=5.0)

        summary = services.finish_duel(room.room_code)
        self.assertIsNone(room.winner_id, "equal scores must be a draw")

        pa = services.get_or_create_profile(a)
        pb = services.get_or_create_profile(b)
        self.assertLess(pa.rating, 1200, "higher-rated player loses ELO on a draw")
        self.assertGreater(pb.rating, 800, "lower-rated player gains ELO on a draw")
        self.assertEqual(pa.draws, 1)
        self.assertEqual(pb.draws, 1)


# ============================================================================
# 4. ACHIEVEMENTS / BADGES
# ============================================================================

class BadgeTests(LMSBaseTestCase):

    def _badge(self, badge_type: str) -> Badge:
        return Badge.objects.get(badge_type=badge_type)

    def test_arena_elite_and_win_streak_badges(self):
        profile = services.get_or_create_profile(self.student)
        profile.wins = 10
        profile.rating = 1250
        profile.save(update_fields=["wins", "rating"])

        earned = services.award_badges(self.student)
        earned_types = {b.badge_type for b in earned}
        self.assertIn(Badge.BadgeType.DUEL_WINNER_10, earned_types)
        self.assertIn(Badge.BadgeType.ARENA_ELITE, earned_types)

        # Bonus XP awarded
        game_score = UserGameScore.objects.get(
            user=self.student, game__slug=services.ARENA_GAME_SLUG
        )
        expected_bonus = (
            self._badge("duel_winner_10").xp_bonus
            + self._badge("arena_elite").xp_bonus
        )
        self.assertEqual(game_score.total_xp, expected_bonus)

        # Idempotent
        self.assertEqual(services.award_badges(self.student), [])

    def test_night_owl_badge(self):
        # A duel won at 02:00 local time
        room = services.create_bot_room(self.student)
        night = timezone.make_aware(
            timezone.datetime(2026, 1, 15, 2, 0),
            timezone.get_current_timezone(),
        )
        ArenaRoom.objects.filter(pk=room.pk).update(
            status=ArenaRoom.Status.FINISHED,
            winner=self.student,
            finished_at=night,
        )

        earned = services.award_badges(self.student)
        self.assertIn(Badge.BadgeType.NIGHT_OWL, {b.badge_type for b in earned})

    def test_essay_master_badge(self):
        topic = EssayTopic.objects.create(
            title="Mavzu",
            description="Tavsif",
            word_limit_min=50,
            word_limit_max=200,
            time_limit_minutes=30,
        )
        for _ in range(5):
            EssaySubmission.objects.create(
                student=self.student,
                topic=topic,
                status=EssaySubmission.Status.GRADED,
                total_score=Decimal("18"),
                max_score=24,
            )

        earned = services.award_badges(self.student)
        self.assertIn(Badge.BadgeType.ESSAY_MASTER, {b.badge_type for b in earned})

    def test_no_badges_for_weak_profile(self):
        self.assertEqual(services.award_badges(self.student), [])


# ============================================================================
# 5. REST API
# ============================================================================

class ArenaAPITests(LMSBaseTestCase):
    """Arena REST endpoints are session-based @login_required views."""

    def _login(self, email: str = "student@test.com"):
        self.client.login(email=email, password="testpass123")

    def test_leaderboard_api(self):
        _set_rating(self.student, 1200)
        other = _make_user("lb@test.com", first="LB")
        _set_rating(other, 900)
        bot = services.get_bot_user()  # must be excluded
        self._login()

        response = self.client.get("/arena/api/leaderboard/")
        self.assertEqual(response.status_code, 200)
        rows = response.json()["leaderboard"]
        self.assertEqual(rows[0]["user_id"], self.student.id)
        self.assertEqual(rows[0]["rating"], 1200)
        self.assertNotIn(bot.id, [r["user_id"] for r in rows])

    def test_stats_api(self):
        _set_rating(self.student, 1150)
        self._login()
        response = self.client.get("/arena/api/stats/")
        self.assertEqual(response.status_code, 200)
        stats = response.json()["stats"]
        self.assertEqual(stats["rating"], 1150)
        self.assertEqual(stats["wins"], 0)
        self.assertIn("rank", stats)
        self.assertIn("accuracy", stats)

    def test_room_create_and_join_api(self):
        self._login()
        resp = self.client.post("/arena/api/rooms/create/")
        self.assertEqual(resp.status_code, 201)
        code = resp.json()["room_code"]

        # Second user joins via the code
        self._login(email="teacher@test.com")
        resp2 = self.client.post(
            "/arena/api/rooms/join/",
            {"code": code},
            format="json",
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.json()["room_code"], code)

        room = ArenaRoom.objects.get(room_code=code)
        self.assertEqual(room.status, ArenaRoom.Status.STARTED)
        self.assertEqual(room.player2_id, self.teacher.id)

    def test_room_join_bad_code(self):
        self._login()
        resp = self.client.post(
            "/arena/api/rooms/join/",
            {"code": "ZZZZ99"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("error", resp.json())

    def test_invites_api(self):
        services.create_custom_room(self.student)
        self._login()
        response = self.client.get("/arena/api/invites/")
        self.assertEqual(response.status_code, 200)
        invites = response.json()["invites"]
        self.assertEqual(len(invites), 1)
        self.assertTrue(invites[0]["room_code"])

    def test_queue_api(self):
        self._login()
        resp = self.client.post("/arena/api/queue/")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["matched"])
        self.assertGreaterEqual(resp.json()["position"], 1)

    def test_leaderboard_requires_auth(self):
        response = self.client.get("/arena/api/leaderboard/")
        self.assertEqual(response.status_code, 302)  # login_required redirect

    def test_post_apis_work_in_real_browser_without_csrf_token(self):
        """
        The lobby JS posts create/join/queue via fetch() without a CSRF token.

        Django's test client skips CSRF by default, so the views must be
        explicitly csrf_exempt — otherwise every browser POST gets a 403.
        An enforce_csrf_checks=True client simulates the real browser.
        """
        self.client = type(self.client)(enforce_csrf_checks=True)
        self.client.login(email="student@test.com", password="testpass123")

        resp = self.client.post("/arena/api/rooms/create/")
        self.assertEqual(resp.status_code, 201, resp.content[:200])
        code = resp.json()["room_code"]

        # A different user joins via the invite code
        self.client.login(email="teacher@test.com", password="testpass123")
        resp2 = self.client.post(
            "/arena/api/rooms/join/",
            {"code": code},
            format="json",
        )
        self.assertEqual(resp2.status_code, 200, resp2.content[:200])

        resp3 = self.client.post("/arena/api/queue/")
        self.assertEqual(resp3.status_code, 200, resp3.content[:200])


# ============================================================================
# 6. WEB SOCKET END-TO-END
# ============================================================================

class ArenaConsumerTests(TransactionTestCase):
    """End-to-end WebSocket duels. TransactionTestCase: consumer threads see data."""

    def setUp(self):
        self.student = _make_user("ws1@test.com", first="W1")
        self.other = _make_user("ws2@test.com", first="W2")

    async def _drain_to(self, comm, event_type: str, timeout: float = 10.0, label: str = "comm"):
        while True:
            msg = await comm.receive_json_from(timeout=timeout)
            if msg.get("type") == event_type:
                return msg

    @ARENA_FAST
    def test_human_vs_human_duel_over_websocket(self):
        async def scenario():
            comm1 = WebsocketCommunicator(QuizArenaConsumer.as_asgi(), "/ws/arena/")
            comm1.scope["user"] = self.student
            comm2 = WebsocketCommunicator(QuizArenaConsumer.as_asgi(), "/ws/arena/")
            comm2.scope["user"] = self.other

            connected1, _ = await comm1.connect()
            connected2, _ = await comm2.connect()
            self.assertTrue(connected1)
            self.assertTrue(connected2)

            await comm1.send_json_to({"type": "join_queue"})
            await comm2.send_json_to({"type": "join_queue"})

            mf1 = await self._drain_to(comm1, "match_found")
            mf2 = await self._drain_to(comm2, "match_found")
            self.assertEqual(mf1["room_code"], mf2["room_code"])
            room_code = mf1["room_code"]
            self.assertEqual(mf1["mode"], "queue")

            room = await database_sync_to_async(ArenaRoom.objects.get)(room_code=room_code)
            total = room.total_questions

            for i in range(total):
                q = await database_sync_to_async(
                    lambda: ArenaQuestion.objects.get(room=room, position=i)
                )()

                q1 = await self._drain_to(comm1, "send_question", label=f"c1-q{i}")
                q2 = await self._drain_to(comm2, "send_question", label=f"c2-q{i}")
                self.assertEqual(q1["question_index"], i)
                self.assertEqual(q2["question_index"], i)
                # CRITICAL: the answer must never be sent with the question
                self.assertNotIn("correct_answer", q1["question"])
                self.assertNotIn("correct_answer", q2["question"])

                # Player 1 (student) always answers correctly; player 2 misses
                # the last question so the duel has a deterministic winner.
                answer1 = q.correct_answer
                answer2 = q.correct_answer if i < total - 1 else _wrong_answer(q)
                await comm1.send_json_to({
                    "type": "submit_answer", "room_code": room_code,
                    "answer": answer1, "question_index": i,
                })
                await comm2.send_json_to({
                    "type": "submit_answer", "room_code": room_code,
                    "answer": answer2, "question_index": i,
                })

            go1 = await self._drain_to(comm1, "game_over", label="c1")
            go2 = await self._drain_to(comm2, "game_over", label="c2")
            self.assertEqual(go1["winner"], go2["winner"])
            self.assertEqual(go1["winner_id"], self.student.id)
            self.assertEqual(len(go1["scores"]), 2)

            # Both players were persisted with rewards
            def check_rewards():
                players = list(
                    ArenaPlayer.objects.filter(room__room_code=room_code)
                )
                self.assertEqual(len(players), 2)
                for p in players:
                    self.assertGreaterEqual(p.xp_earned, 0)
                    self.assertNotEqual(p.rating_change, 0)

            await database_sync_to_async(check_rewards)()

            await comm1.disconnect()
            await comm2.disconnect()

        async_to_sync(scenario)()

    @ARENA_FAST
    def test_bot_duel_over_websocket(self):
        async def scenario():
            comm = WebsocketCommunicator(QuizArenaConsumer.as_asgi(), "/ws/arena/")
            comm.scope["user"] = self.student

            connected, _ = await comm.connect()
            self.assertTrue(connected)

            await comm.send_json_to({"type": "join_queue"})
            # queue_update first, then the bot fallback kicks in
            mf = await self._drain_to(comm, "match_found")
            self.assertEqual(mf["mode"], "bot")
            room_code = mf["room_code"]

            room = await database_sync_to_async(ArenaRoom.objects.get)(room_code=room_code)
            self.assertIsNotNone(room.bot_user_id)
            total = room.total_questions

            for i in range(total):
                q = await database_sync_to_async(
                    lambda: ArenaQuestion.objects.get(room=room, position=i)
                )()
                msg = await self._drain_to(comm, "send_question", label=f"bot-q{i}")
                self.assertEqual(msg["question_index"], i)
                self.assertNotIn("correct_answer", msg["question"])

                await comm.send_json_to({
                    "type": "submit_answer", "room_code": room_code,
                    "answer": q.correct_answer, "question_index": i,
                })

            go = await self._drain_to(comm, "game_over", label="bot-go")
            self.assertIn(go["winner_id"], (None, self.student.id))
            self.assertEqual(len(go["scores"]), 2)
            bot_row = next(s for s in go["scores"] if s["is_bot"])
            self.assertTrue(bot_row["is_bot"])

            await comm.disconnect()

        async_to_sync(scenario)()

    def test_websocket_rejects_non_participant(self):
        async def scenario():
            room = await database_sync_to_async(services.create_bot_room)(self.student)
            intruder = await database_sync_to_async(_make_user)("intruder@test.com")

            comm = WebsocketCommunicator(QuizArenaConsumer.as_asgi(), "/ws/arena/")
            comm.scope["user"] = intruder
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            await comm.send_json_to({"type": "join_room", "room_code": room.room_code})
            err = await self._drain_to(comm, "error")
            self.assertIn("ishtirokchisi emassiz", err["message"])

            await comm.disconnect()

        async_to_sync(scenario)()

    def test_unauth_socket_closed(self):
        async def scenario():
            comm = WebsocketCommunicator(QuizArenaConsumer.as_asgi(), "/ws/arena/")
            comm.scope["user"] = None
            connected, _ = await comm.connect()
            self.assertFalse(connected)

        async_to_sync(scenario)()

    @ARENA_FAST
    def test_bot_duel_resumes_after_disconnect_rejoin(self):
        """
        The queue runs on the LOBBY socket; when the browser redirects to the
        duel page that socket closes and a fresh one joins the room. A bot
        duel must survive the disconnect (staying STARTED) and resume when
        the player rejoins — the join path re-sends the current question and
        re-arms the timer/bot flow. Disconnecting must NOT finish the duel
        (that would kill every queued bot match at the redirect step).
        """
        async def scenario():
            comm = WebsocketCommunicator(QuizArenaConsumer.as_asgi(), "/ws/arena/")
            comm.scope["user"] = self.student
            connected, _ = await comm.connect()
            self.assertTrue(connected)

            await comm.send_json_to({"type": "join_queue"})
            mf = await self._drain_to(comm, "match_found")
            self.assertEqual(mf["mode"], "bot")
            room_code = mf["room_code"]

            # The redirect closes the lobby socket mid-countdown
            await comm.disconnect()

            room = await database_sync_to_async(ArenaRoom.objects.get)(room_code=room_code)
            self.assertEqual(room.status, ArenaRoom.Status.STARTED)

            # The duel page reconnects and rejoins the room
            comm2 = WebsocketCommunicator(QuizArenaConsumer.as_asgi(), "/ws/arena/")
            comm2.scope["user"] = self.student
            connected2, _ = await comm2.connect()
            self.assertTrue(connected2)
            await comm2.send_json_to({"type": "join_room", "room_code": room_code})

            # And the resumed game can be played to completion (the join
            # itself delivers the first question).
            for i in range(room.total_questions):
                msg = await self._drain_to(comm2, "send_question")
                self.assertEqual(msg["question_index"], i)
                self.assertNotIn("correct_answer", msg["question"])
                question_row = await database_sync_to_async(
                    lambda: ArenaQuestion.objects.get(room=room, position=i)
                )()
                await comm2.send_json_to({
                    "type": "submit_answer", "room_code": room_code,
                    "answer": question_row.correct_answer, "question_index": i,
                })

            go = await self._drain_to(comm2, "game_over")
            self.assertEqual(len(go["scores"]), 2)

            await comm2.disconnect()

        async_to_sync(scenario)()
