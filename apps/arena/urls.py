"""Arena URL configuration."""
from django.urls import path

from . import views

app_name = "arena"

urlpatterns = [
    # Pages
    path("", views.arena_lobby_view, name="lobby"),
    path("<str:room_code>/", views.arena_room_view, name="room"),

    # JSON API
    path("api/leaderboard/", views.arena_api_leaderboard, name="api-leaderboard"),
    path("api/stats/", views.arena_api_stats, name="api-stats"),
    path("api/invites/", views.arena_api_invites, name="api-invites"),
    path("api/rooms/create/", views.arena_api_room_create, name="api-room-create"),
    path("api/rooms/join/", views.arena_api_room_join, name="api-room-join"),
    path("api/queue/", views.arena_api_queue, name="api-queue"),
]