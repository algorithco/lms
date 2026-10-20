"""Speaking app URL configuration."""

from django.urls import path
from . import views

app_name = "speaking"

urlpatterns = [
    path("topics/", views.SpeakingTopicsListView.as_view(), name="topics-list"),
    path(
        "topics/<int:pk>/", views.SpeakingTopicDetailView.as_view(), name="topic-detail"
    ),
    path("submit/", views.SpeakingSubmitView.as_view(), name="speaking-submit"),
    path(
        "submissions/<int:pk>/",
        views.SpeakingSubmissionDetailView.as_view(),
        name="submission-detail",
    ),
    path(
        "my-submissions/",
        views.MySpeakingSubmissionsView.as_view(),
        name="my-submissions",
    ),
]
