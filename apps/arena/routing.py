"""Arena WebSocket routing."""

from django.urls import re_path

from . import consumers, consumers_tournament

websocket_urlpatterns = [
    re_path(r"ws/arena/(?P<room_code>\w+)/$", consumers.QuizArenaConsumer.as_asgi()),
    re_path(r"ws/arena/$", consumers.QuizArenaConsumer.as_asgi()),
    re_path(
        r"ws/tournaments/(?P<tournament_id>\d+)/$",
        consumers_tournament.TournamentConsumer.as_asgi(),
    ),
]
