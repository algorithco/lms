"""
Arena WebSocket Consumer — Real-time 1v1 Quiz Duel.

Protocol Events:
    Client → Server:
        join_queue     — Join matchmaking queue (ELO-based, bot fallback after 15s)
        join_room      — Join existing room by code (custom rooms, reconnects)
        submit_answer  — Submit answer for current question
        leave_room     — Leave the room

    Server → Client:
        connected        — Socket accepted
        queue_update     — Queue position + bot fallback countdown
        match_found      — Opponent found (human or bot), game starting
        room_joined      — Successfully joined an existing room
        send_question    — New question with timer (never contains the answer)
        answer_result    — Per-player grading (correct + points + streak)
        live_score_update — Live scores for both players (WebSocket streaming)
        game_over        — Final results with XP/coin/ELO rewards
        error            — Error message

Notes:
    - The correct answer is NEVER sent with the question; it is only revealed
      to the answering player via `answer_result`.
    - All business rules (ELO matchmaking, scoring, rewards, badges) live in
      apps.arena.services and are exercised by integration tests.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from . import services

logger = logging.getLogger(__name__)


def _countdown_seconds() -> float:
    return services._countdown_seconds()


class QuizArenaConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for the 1v1 Quiz Arena."""

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self):
        self.user = self.scope.get("user")
        self.room_code: str | None = None
        self.room_group: str | None = None
        self.is_player1 = False
        self._bot_fallback_task: asyncio.Task | None = None
        self._question_timer_task: asyncio.Task | None = None
        self._bot_answer_task: asyncio.Task | None = None

        if self.user and self.user.is_authenticated:
            await self.accept()
            await self.send(text_data=json.dumps({
                "type": "connected",
                "message": "Arena ga ulandingiz!",
                "user_id": self.user.id,
                "username": self.user.get_full_name(),
            }))
        else:
            await self.close(code=4001)

    async def disconnect(self, code):
        await self._cancel_tasks()

        if self.room_group:
            await self.channel_layer.group_discard(
                self.room_group,
                self.channel_name,
            )

        # Expire any still-waiting queue entries so an offline user can't
        # be matched (DB-backed queue survives across processes).
        if self.user and self.user.is_authenticated:
            await self._expire_waiting_entries(self.user.id)

        if self.room_code:
            await self._set_player_connected(self.room_code, self.user.id, False)

        logger.info("Player disconnected: user=%s, code=%s", self.user, self.room_code)

    async def _cancel_tasks(self):
        for attr in ("_bot_fallback_task", "_question_timer_task", "_bot_answer_task"):
            task = getattr(self, attr, None)
            if task and not task.done():
                task.cancel()

    # ------------------------------------------------------------------
    # Inbound events
    # ------------------------------------------------------------------

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            event_type = data.get("type", "")

            if event_type == "join_queue":
                await self._join_queue(data)
            elif event_type == "join_room":
                await self._join_room(data)
            elif event_type == "submit_answer":
                await self._submit_answer(data)
            elif event_type == "leave_room":
                await self._leave_room()
            else:
                await self.send(text_data=json.dumps({
                    "type": "error",
                    "message": f"Noma'lum event: {event_type}",
                }))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Noto'g'ri JSON format",
            }))
        except Exception as exc:
            logger.exception("WebSocket receive error: user=%s", getattr(self.user, "id", "?"))
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Server xatoligi yuz berdi.",
            }))

    # ------------------------------------------------------------------
    # Matchmaking (ELO queue + bot fallback)
    # ------------------------------------------------------------------

    async def _join_queue(self, data):
        entry, room = await database_sync_to_async(services.join_matchmaking_queue)(
            self.user, self.channel_name
        )

        if room is not None:
            await self._setup_match(room, channels=[self.channel_name])
            return

        position = await database_sync_to_async(services.queue_position)(self.user)
        wait = int(_countdown_seconds() + services._bot_fallback_seconds())
        await self.send(text_data=json.dumps({
            "type": "queue_update",
            "message": (
                f"Navbatdasiz. {position}-o'rinda. "
                f"Raqib topilmasa ~{wait}s dan keyin bot bilan o'ynaysiz 🤖"
            ),
            "position": position,
            "bot_fallback_seconds": int(services._bot_fallback_seconds()),
        }))

        self._bot_fallback_task = asyncio.create_task(self._bot_fallback(entry.pk))

    async def _bot_fallback(self, entry_id: int):
        """Wait the fallback window, then assign the AI opponent if still unmatched."""
        await asyncio.sleep(services._bot_fallback_seconds())
        room = await database_sync_to_async(services.assign_bot_opponent)(entry_id)
        if room is None:
            return  # matched with a human or expired in the meantime
        await self._setup_match(room, channels=[self.channel_name])

    async def _setup_match(self, room, channels: list[str] | None = None):
        """Wire both consumers into the room group and start the countdown."""
        room_code = room.room_code
        self.room_code = room_code
        self.room_group = f"arena_{room_code}"
        self.is_player1 = room.player1_id == self.user.id

        # Gather every connected channel for this room (queue entries carry
        # the waiting players' channel names; the current one is always added).
        room_channels = await self._room_queue_channels(room_code)
        channels = set(channels or []) | set(room_channels) | {self.channel_name}
        for ch in channels:
            if ch:
                await self.channel_layer.group_add(self.room_group, ch)

        await self.channel_layer.group_send(self.room_group, {
            "type": "match_found",
            "room_code": room_code,
            "mode": room.mode,
            "player1": {
                "id": room.player1_id,
                "name": room.player1.get_full_name() or room.player1.email,
                "is_bot": room.player1.is_bot,
            },
            "player2": {
                "id": room.player2_id if room.player2 else None,
                "name": (room.player2.get_full_name() or room.player2.email) if room.player2 else "?",
                "is_bot": bool(room.player2 and room.player2.is_bot),
            },
            "total_questions": room.total_questions,
        })

        await database_sync_to_async(services.mark_question_started)(room_code)
        await asyncio.sleep(_countdown_seconds())
        await self._send_question(room_code, 0)

    # ------------------------------------------------------------------
    # Room join (custom rooms + reconnects)
    # ------------------------------------------------------------------

    async def _join_room(self, data):
        room_code = data.get("room_code", "")
        if not room_code:
            await self.send(text_data=json.dumps({
                "type": "error", "message": "Xona kodi ko'rsatilmagan.",
            }))
            return

        room = await self._get_room(room_code)
        if room is None:
            await self.send(text_data=json.dumps({
                "type": "error", "message": f"'{room_code}' xonasi topilmadi.",
            }))
            return

        # Only the two participants may attach (prevents spectators via WS)
        if room.player1_id != self.user.id and room.player2_id != self.user.id:
            await self.send(text_data=json.dumps({
                "type": "error", "message": "Siz bu xonaning ishtirokchisi emassiz.",
            }))
            return

        self.room_code = room_code
        self.room_group = f"arena_{room_code}"
        self.is_player1 = room.player1_id == self.user.id

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self._save_player_channel(room_code, self.user.id, self.channel_name)
        await self._set_player_connected(room_code, self.user.id, True)

        # Pull the other participant's channel in so the broadcast below
        # reaches them too (custom-room creator on the lobby, for example).
        for ch in await self._room_player_channels(room_code):
            if ch and ch != self.channel_name:
                await self.channel_layer.group_add(self.room_group, ch)

        await self.send(text_data=json.dumps({
            "type": "room_joined",
            "room_code": room_code,
            "status": room.status,
            "mode": room.mode,
            "is_bot_duel": room.mode == "bot",
            "player1": {
                "id": room.player1_id,
                "name": room.player1.get_full_name() or room.player1.email,
                "is_bot": room.player1.is_bot,
            },
            "player2": {
                "id": room.player2_id if room.player2 else None,
                "name": (room.player2.get_full_name() or room.player2.email) if room.player2 else "?",
                "is_bot": bool(room.player2 and room.player2.is_bot),
            },
            "total_questions": room.total_questions,
            "time_per_question": room.time_per_question,
            "current_question_index": room.current_question_index,
            "message": "Xonaga qo'shildingiz.",
        }))

        # A freshly STARTED room (custom join / bot) needs one consumer to
        # drive the countdown — exactly one wins mark_question_started().
        if room.status == "started":
            started = await database_sync_to_async(services.mark_question_started)(room_code)
            if started:
                await self.channel_layer.group_send(self.room_group, {
                    "type": "match_found",
                    "room_code": room_code,
                    "mode": room.mode,
                    "player1": {
                        "id": room.player1_id,
                        "name": room.player1.get_full_name() or room.player1.email,
                        "is_bot": room.player1.is_bot,
                    },
                    "player2": {
                        "id": room.player2_id,
                        "name": room.player2.get_full_name() or room.player2.email,
                        "is_bot": bool(room.player2 and room.player2.is_bot),
                    },
                    "total_questions": room.total_questions,
                })
                await asyncio.sleep(_countdown_seconds())
                await self._send_question(room_code, room.current_question_index)
            elif room.current_question_index < room.total_questions:
                # Mid-game reconnect — deliver the current question immediately
                await self._send_question(room_code, room.current_question_index)

        logger.info("Player joined room: user=%s, code=%s, is_p1=%s",
                    self.user.id, room_code, self.is_player1)

    # ------------------------------------------------------------------
    # Game logic
    # ------------------------------------------------------------------

    async def _send_question(self, room_code: str, question_index: int):
        """Broadcast the question (without the answer) and arm the timers."""
        question = await self._get_question(room_code, question_index)
        if question is None:
            logger.error("Question not found: room=%s, index=%d", room_code, question_index)
            return

        room = await self._get_room(room_code)
        if room is None or room.status != "started":
            return

        await self.channel_layer.group_send(self.room_group, {
            "type": "send_question",
            "question_index": question_index,
            "question": {
                "question_text": question.question_text,
                "option_a": question.option_a,
                "option_b": question.option_b,
                "option_c": question.option_c,
                "option_d": question.option_d,
                "position": question.position,
                "points": question.points,
            },
            "time_limit": room.time_per_question,
        })

        # Start the speed-bonus clock at actual display time (not countdown start)
        await database_sync_to_async(services.mark_question_sent)(room_code, question_index)

        # Per-question server timer (advances even if nobody answers)
        if self._question_timer_task and not self._question_timer_task.done():
            self._question_timer_task.cancel()
        self._question_timer_task = asyncio.create_task(
            self._question_timer(room_code, question_index, room.time_per_question)
        )

        # In bot duels, the human's consumer schedules the bot's answer
        if room.mode == "bot" and room.bot_user_id:
            if self._bot_answer_task and not self._bot_answer_task.done():
                self._bot_answer_task.cancel()
            self._bot_answer_task = asyncio.create_task(
                self._bot_answer_flow(room_code, question_index, room.bot_user_id)
            )

    async def _question_timer(self, room_code: str, question_index: int, time_limit: int):
        await asyncio.sleep(time_limit)
        try:
            room = await self._get_room(room_code)
            if room is None or room.status != "started":
                return
            if room.current_question_index != question_index:
                return
            both = await database_sync_to_async(services.both_answered)(room_code)
            if both:
                return
            await self._advance(room_code, expected_index=question_index, force=True)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Question timer error: room=%s", room_code)

    async def _bot_answer_flow(self, room_code: str, question_index: int, bot_user_id: int):
        try:
            room = await self._get_room(room_code)
            if room is None or room.status != "started":
                return
            decision = await database_sync_to_async(services.bot_decide_answer)(
                room, question_index, bot_user_id
            )
            await asyncio.sleep(decision["delay"])

            # Re-check before submitting (question may have advanced)
            room = await self._get_room(room_code)
            if room is None or room.status != "started":
                return
            if room.current_question_index != question_index:
                return

            result = await database_sync_to_async(services.submit_answer)(
                room, bot_user_id, decision["answer"], question_index, decision["delay"]
            )
            if result is None:
                return

            scores = await database_sync_to_async(services.get_scores)(room_code)
            await self.channel_layer.group_send(self.room_group, {
                "type": "live_score_update",
                "scores": scores,
                "answered_by": bot_user_id,
            })
            await self._check_advance(room_code, expected_index=question_index)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Bot answer error: room=%s", room_code)

    async def _submit_answer(self, data):
        room_code = data.get("room_code", self.room_code)
        answer = data.get("answer", "").lower()
        question_index = data.get("question_index", 0)

        if not room_code or answer not in ("a", "b", "c", "d"):
            return

        room = await self._get_room(room_code)
        if room is None or room.status != "started":
            return

        # Anti-cheat: questions are pre-created, so only the CURRENT question
        # may be answered — a malicious client can't score future questions early.
        try:
            question_index = int(question_index)
        except (TypeError, ValueError):
            return
        if question_index != room.current_question_index:
            return

        # Response time measured server-side (anti-cheat)
        time_seconds = 0.0
        if room.question_started_at:
            time_seconds = (timezone.now() - room.question_started_at).total_seconds()

        result = await database_sync_to_async(services.submit_answer)(
            room, self.user.id, answer, question_index, time_seconds
        )
        if result is None:
            return

        # Reveal grading ONLY to the answering player
        await self.send(text_data=json.dumps({
            "type": "answer_result",
            "is_correct": result["is_correct"],
            "points": result["points"],
            "base_points": result["base_points"],
            "combo_bonus": result["combo_bonus"],
            "time_bonus": result["time_bonus"],
            "correct_answer": result["correct_answer"],
            "streak": result["streak"],
        }))

        scores = await database_sync_to_async(services.get_scores)(room_code)
        await self.channel_layer.group_send(self.room_group, {
            "type": "live_score_update",
            "scores": scores,
            "answered_by": self.user.id,
        })

        await self._check_advance(room_code, expected_index=question_index)

    async def _check_advance(self, room_code: str, expected_index: int | None = None):
        both = await database_sync_to_async(services.both_answered)(room_code)
        if not both:
            return
        await self._advance(room_code, expected_index=expected_index, force=False)

    async def _advance(self, room_code: str, expected_index: int | None = None, force: bool = False):
        adv = await database_sync_to_async(services.advance_question)(
            room_code, expected_index=expected_index, force=force
        )
        if adv["finished"]:
            await self._finish(room_code)
        elif adv.get("advanced"):
            # Only the consumer that actually moved the room forward
            # broadcasts the next question (prevents duplicates).
            await self._send_question(room_code, adv["index"])

    async def _finish(self, room_code: str):
        # NOTE: broadcast BEFORE cancelling tasks. _finish can be invoked from
        # inside _bot_answer_task / _question_timer_task; cancelling first
        # would cancel the *running* task and kill this coroutine at the next
        # await — after the DB commit but before the game_over broadcast,
        # leaving clients staring at a finished-but-silent room.
        summary = await database_sync_to_async(services.finish_duel)(room_code)
        if summary is None:
            return

        await self.channel_layer.group_send(self.room_group, {
            "type": "game_over",
            "winner": summary["winner"],
            "winner_id": summary["winner_id"],
            "scores": summary["scores"],
            "mode": summary["mode"],
        })

        await self._cancel_tasks()

    async def _leave_room(self):
        if self.room_group:
            await self.channel_layer.group_discard(self.room_group, self.channel_name)
            self.room_group = None
            self.room_code = None

        await self.send(text_data=json.dumps({
            "type": "left_room",
            "message": "Xonadan chiqdingiz.",
        }))

    # ------------------------------------------------------------------
    # Outbound group event handlers
    # ------------------------------------------------------------------

    async def match_found(self, event):
        self.room_code = event["room_code"]
        self.room_group = f"arena_{event['room_code']}"
        await self.send(text_data=json.dumps({
            "type": "match_found",
            "room_code": event["room_code"],
            "mode": event.get("mode", "queue"),
            "player1": event["player1"],
            "player2": event["player2"],
            "total_questions": event["total_questions"],
            "message": "Raqib topildi! Tayyorlaning...",
        }))

    async def send_question(self, event):
        await self.send(text_data=json.dumps({
            "type": "send_question",
            "question_index": event["question_index"],
            "question": event["question"],
            "time_limit": event["time_limit"],
            "message": "Savol!",
        }))

    async def live_score_update(self, event):
        await self.send(text_data=json.dumps({
            "type": "live_score_update",
            "scores": event["scores"],
            "answered_by": event["answered_by"],
        }))

    async def game_over(self, event):
        await self.send(text_data=json.dumps({
            "type": "game_over",
            "winner": event["winner"],
            "winner_id": event["winner_id"],
            "scores": event["scores"],
            "mode": event.get("mode", "queue"),
            "message": "O'yin tugadi!",
        }))

    # ------------------------------------------------------------------
    # Database helpers (sync → async)
    # ------------------------------------------------------------------

    @database_sync_to_async
    def _get_room(self, room_code):
        from .models import ArenaRoom
        return ArenaRoom.objects.select_related("player1", "player2").filter(
            room_code=room_code
        ).first()

    @database_sync_to_async
    def _get_question(self, room_code, question_index):
        from .models import ArenaQuestion, ArenaRoom
        try:
            room = ArenaRoom.objects.get(room_code=room_code)
            return ArenaQuestion.objects.get(room=room, position=question_index)
        except (ArenaRoom.DoesNotExist, ArenaQuestion.DoesNotExist):
            return None

    @database_sync_to_async
    def _set_player_connected(self, room_code, user_id, connected):
        from .models import ArenaPlayer, ArenaRoom
        try:
            room = ArenaRoom.objects.get(room_code=room_code)
            ArenaPlayer.objects.filter(room=room, player_id=user_id).update(
                is_connected=connected
            )
        except ArenaRoom.DoesNotExist:
            pass

    @database_sync_to_async
    def _save_player_channel(self, room_code, user_id, channel_name):
        from .models import ArenaPlayer, ArenaRoom
        try:
            room = ArenaRoom.objects.get(room_code=room_code)
            ArenaPlayer.objects.filter(room=room, player_id=user_id).update(
                channel_name=channel_name, is_connected=True
            )
        except ArenaRoom.DoesNotExist:
            pass

    @database_sync_to_async
    def _room_queue_channels(self, room_code):
        """Channel names of the queue entries matched into this room."""
        from .models import ArenaQueueEntry, ArenaRoom
        try:
            room = ArenaRoom.objects.get(room_code=room_code)
        except ArenaRoom.DoesNotExist:
            return []
        return list(
            ArenaQueueEntry.objects.filter(room=room)
            .exclude(channel_name="")
            .values_list("channel_name", flat=True)
        )

    @database_sync_to_async
    def _room_player_channels(self, room_code):
        """Channel names of all connected players in the room."""
        from .models import ArenaPlayer, ArenaRoom
        try:
            room = ArenaRoom.objects.get(room_code=room_code)
        except ArenaRoom.DoesNotExist:
            return []
        return list(
            ArenaPlayer.objects.filter(room=room)
            .exclude(channel_name="")
            .values_list("channel_name", flat=True)
        )

    @database_sync_to_async
    def _expire_waiting_entries(self, user_id):
        from .models import ArenaQueueEntry
        ArenaQueueEntry.objects.filter(
            user_id=user_id, status=ArenaQueueEntry.Status.WAITING
        ).update(status=ArenaQueueEntry.Status.EXPIRED)