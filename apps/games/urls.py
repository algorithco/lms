"""Games app URL configuration."""
from django.urls import path

from . import views

app_name = "games"

urlpatterns = [
    # Game hub
    path("", views.games_index_view, name="index"),

    # Imlo Minalari
    path("imlo-mina/", views.imlo_mines_view, name="imlo-mina"),
    path("api/imlo-mina/check/", views.imlo_check_view, name="imlo-check"),

    # Navoiy vs Dunyo
    path("gazal-puzzle/", views.gazal_puzzle_view, name="gazal-puzzle"),
    path("api/gazal-puzzle/check/", views.gazal_check_view, name="gazal-check"),

    # Eski So'zlar Dueli
    path("lugat-match/", views.lugat_match_view, name="lugat-match"),
    path("api/lugat-match/check/", views.lugat_check_view, name="lugat-check"),

    # Leaderboard
    path("leaderboard/", views.leaderboard_full_view, name="leaderboard"),
    path("api/leaderboard/", views.leaderboard_partial_view, name="leaderboard-api"),
]
