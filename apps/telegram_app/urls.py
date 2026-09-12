"""Telegram Mini App URL configuration."""
from django.urls import path

from . import views
from . import test_api

app_name = "telegram_app"

urlpatterns = [
    # TMA page
    path("", views.tma_index_view, name="index"),

    # API — Auth & Profile
    path("api/auth/", views.tma_auth_view, name="auth"),
    path("api/profile/", views.tma_profile_view, name="profile"),

    # API — Arena (stats, leaderboard, invites)
    path("api/arena/", views.tma_arena_view, name="arena"),

    # API — Tests (list)
    path("api/tests/", views.tma_tests_view, name="tests"),

    # API — Test Taking (start, answer, submit)
    path("api/tests/<int:test_id>/start/", test_api.tma_test_start_view, name="test-start"),
    path("api/tests/<int:test_id>/answer/", test_api.tma_test_answer_view, name="test-answer"),
    path("api/tests/<int:test_id>/submit/", test_api.tma_test_submit_view, name="test-submit"),
    path("api/attempts/<int:attempt_id>/result/", test_api.tma_attempt_result_view, name="attempt-result"),

    # API — Results
    path("api/results/", views.tma_results_view, name="results"),

    # API — Essays
    path("api/essays/topics/", views.tma_essay_topics_view, name="essay-topics"),
    path("api/essays/", views.tma_essay_submissions_view, name="essay-submissions"),
    path("api/essays/<int:topic_id>/start/", views.tma_essay_start_view, name="essay-start"),
    path("api/essays/<int:submission_id>/submit/", views.tma_essay_submit_view, name="essay-submit"),
    path("api/essays/<int:submission_id>/result/", views.tma_essay_result_view, name="essay-result"),
]
