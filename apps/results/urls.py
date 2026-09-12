"""
Results app URL configuration.

Endpoints:
    GET /api/results/my-results/      — O'quvchining barcha natijalari
    GET /api/results/{id}/detail/     — Natija tafsilotlari
    GET /api/results/stats/           — Umumiy statistika
"""
from django.urls import path

from . import views

app_name = "results"

urlpatterns = [
    path(
        "my-results/",
        views.MyResultsView.as_view(),
        name="my-results",
    ),
    path(
        "stats/",
        views.ResultStatsView.as_view(),
        name="result-stats",
    ),
    path(
        "<int:pk>/detail/",
        views.ResultDetailView.as_view(),
        name="result-detail",
    ),
]
