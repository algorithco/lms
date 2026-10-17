"""
WebSocket Consumer for Real-time Tournament Live Leaderboard.
"""
from __future__ import annotations

import json
import logging
from typing import Any
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from apps.arena.services_tournament import (
    get_tournament_leaderboard,
    submit_tournament_answers,
)

logger = logging.getLogger(__name__)


class TournamentConsumer(AsyncWebsocketConsumer):
    """
    Real-time E-Sport Tournament Leaderboard WebSocket consumer.
    """

    async def connect(self):
        self.tournament_id = self.scope["url_route"]["kwargs"].get("tournament_id")
        self.room_group_name = f"tournament_{self.tournament_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()

        # Send initial leaderboard
        leaderboard = await database_sync_to_async(get_tournament_leaderboard)(
            int(self.tournament_id)
        )
        await self.send(
            text_data=json.dumps({
                "type": "init",
                "tournament_id": self.tournament_id,
                "leaderboard": leaderboard,
            })
        )

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
        try:
            data = json.loads(text_data)
        except Exception:
            return

        action = data.get("action")
        if action == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))
            return

        if action == "submit":
            user = self.scope.get("user")
            if not user or not user.is_authenticated:
                await self.send(text_data=json.dumps({"type": "error", "message": "Avtorizatsiyadan o'tilmagan"}))
                return

            answers = data.get("answers", {})
            time_taken = data.get("time_taken_seconds", 0)

            result = await database_sync_to_async(submit_tournament_answers)(
                tournament_id=int(self.tournament_id),
                user=user,
                answers_dict=answers,
                time_taken_seconds=time_taken,
            )
            await self.send(text_data=json.dumps({"type": "submit_success", "result": result}))

    async def tournament_leaderboard_update(self, event):
        """Handler called when group receives leaderboard broadcast."""
        await self.send(
            text_data=json.dumps({
                "type": "leaderboard_update",
                "leaderboard": event["leaderboard"],
            })
        )
