"""
Tests app URL configuration.

Endpoints:
    GET  /api/tests/                             — Testlar ro'yxati
    GET  /api/tests/{id}/                        — Test tafsilotlari (savollar bilan)
    POST /api/tests/{id}/start/                  — Testni boshlash
    GET  /api/tests/attempts/{id}/               — Attempt status + timer + javoblar
    POST /api/tests/attempts/{id}/save-answer/   — Javob auto-save
    POST /api/tests/attempts/{id}/submit/        — Testni yakunlash
"""
from django.urls import path

from . import views

app_name = "tests"

urlpatterns = [
    # -- Test CRUD ------------------------------------------------------------
    path(
        "",
        views.TestListView.as_view(),
        name="test-list",
    ),
    path(
        "<int:pk>/",
        views.TestDetailView.as_view(),
        name="test-detail",
    ),

    # -- Attempt lifecycle ----------------------------------------------------
    path(
        "<int:test_id>/start/",
        views.StartAttemptView.as_view(),
        name="start-attempt",
    ),
    path(
        "attempts/<int:pk>/",
        views.AttemptDetailView.as_view(),
        name="attempt-detail",
    ),
    path(
        "attempts/<int:attempt_id>/save-answer/",
        views.SaveAnswerView.as_view(),
        name="save-answer",
    ),
    path(
        "attempts/<int:attempt_id>/submit/",
        views.SubmitAttemptView.as_view(),
        name="submit-attempt",
    ),
]
