"""
Unit & integration tests for 1v1 Arena WebSocket Network Resilience.
Covers:
1. Ping/pong heartbeat exchange
2. Disconnect grace period checking
3. Forfeit duel logic (remaining player awarded win on disconnect timeout)
"""

import pytest
from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from apps.arena.consumers import QuizArenaConsumer
from apps.arena.models import ArenaPlayer, ArenaRoom
from apps.arena import services

User = get_user_model()


class TestArenaWsReconnect(TransactionTestCase):
    """Test ping/pong and disconnect forfeit resilience."""

    def setUp(self):
        super().setUp()
        self.p1 = User.objects.create_user(
            email="arena_p1@grandec.uz",
            password="testpass12345",
            first_name="Player",
            last_name="One",
            role="student",
        )
        self.p2 = User.objects.create_user(
            email="arena_p2@grandec.uz",
            password="testpass12345",
            first_name="Player",
            last_name="Two",
            role="student",
        )

    def test_ping_pong_heartbeat_websocket(self):
        """Test WebSocket client sending ping receives immediate pong."""
        async def scenario():
            comm = WebsocketCommunicator(QuizArenaConsumer.as_asgi(), "/ws/arena/")
            comm.scope["user"] = self.p1
            connected, _ = await comm.connect()
            assert connected is True

            # Initial connected greeting frame
            greeting = await comm.receive_json_from()
            assert greeting.get("type") == "connected"

            # Send heartbeat ping
            test_ts = 1730000000
            await comm.send_json_to({"type": "ping", "timestamp": test_ts})

            # Expect pong response
            pong = await comm.receive_json_from()
            assert pong.get("type") == "pong"
            assert pong.get("timestamp") == test_ts

            await comm.disconnect()

        async_to_sync(scenario)()

    def test_is_player_connected_helper(self):
        """Test is_player_connected returns correct connectivity state."""
        room = ArenaRoom.objects.create(
            room_code="TEST_CONN_ROOM",
            player1=self.p1,
            player2=self.p2,
            status=ArenaRoom.Status.STARTED,
        )
        ArenaPlayer.objects.create(room=room, player=self.p1, is_connected=True)
        ArenaPlayer.objects.create(room=room, player=self.p2, is_connected=False)

        assert services.is_player_connected(room.room_code, self.p1.id) is True
        assert services.is_player_connected(room.room_code, self.p2.id) is False

    def test_forfeit_duel_awards_win_to_opponent(self):
        """Test forfeit_duel awards win to the remaining player and updates stats."""
        room = ArenaRoom.objects.create(
            room_code="FORFEIT_ROOM_1",
            player1=self.p1,
            player2=self.p2,
            status=ArenaRoom.Status.STARTED,
        )
        player_row1 = ArenaPlayer.objects.create(room=room, player=self.p1, is_connected=False)
        player_row2 = ArenaPlayer.objects.create(room=room, player=self.p2, is_connected=True)

        summary = services.forfeit_duel(room.room_code, self.p1.id)

        assert summary is not None
        assert summary["winner_id"] == self.p2.id

        room.refresh_from_db()
        assert room.status == ArenaRoom.Status.FINISHED
        assert room.winner_id == self.p2.id

        player_row1.refresh_from_db()
        player_row2.refresh_from_db()
        assert player_row1.rating_change <= 0
        assert player_row2.rating_change >= 0
