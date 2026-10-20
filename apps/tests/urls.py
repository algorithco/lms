"""
Tests app URL configuration.

Endpoints:
    GET  /api/tests/                             — Testlar ro'yxati
    GET  /api/tests/{id}/                        — Test tafsilotlari (savollar bilan)
    POST /api/tests/{id}/start/                  — Testni boshlash
    GET  /api/tests/attempts/{id}/               — Attempt status + timer + javoblar
    POST /api/tests/attempts/{id}/save-answer/   — Javob auto-save
    POST /api/tests/attempts/{id}/submit/        — Testni yakunlash
    POST /api/tests/attempts/{id}/finalize/     — Kutilayotgan yozma bahoni yakunlash
"""

from django.urls import path

from . import views, views_omr, views_placement

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
    path(
        "attempts/<int:attempt_id>/finalize/",
        views.FinalizeAttemptView.as_view(),
        name="finalize-attempt",
    ),
    path(
        "attempts/<int:attempt_id>/report-violation/",
        views.ReportViolationView.as_view(),
        name="report-violation",
    ),
    # -- 24/7 AI Tutor & Diagnostics ------------------------------------------
    path(
        "results/<int:result_id>/diagnostics/",
        views.ResultDiagnosticsView.as_view(),
        name="result-diagnostics",
    ),
    path(
        "questions/<int:question_id>/explain-mistake/",
        views.QuestionExplainMistakeView.as_view(),
        name="question-explain-mistake",
    ),
    # -- Fast Key-Based Mock Tests --------------------------------------------
    path(
        "mock/create/",
        views.QuickMockCreateView.as_view(),
        name="quick-mock-create",
    ),
    path(
        "mock/join/",
        views.QuickMockJoinView.as_view(),
        name="quick-mock-join",
    ),
    path(
        "mock/<int:test_id>/leaderboard/",
        views.MockLeaderboardView.as_view(),
        name="mock-leaderboard",
    ),
    # -- 5-Minute Smart Onboarding Placement Quiz -----------------------------
    path(
        "placement-quiz/",
        views_placement.placement_quiz_view,
        name="placement-quiz",
    ),
    path(
        "placement-quiz/submit/",
        views_placement.placement_quiz_submit_view,
        name="placement-quiz-submit",
    ),
    # -- OMR Answer Sheet Auto-Scanner ----------------------------------------
    path(
        "scan-omr/",
        views_omr.ScanOMRView.as_view(),
        name="scan-omr",
    ),
]
