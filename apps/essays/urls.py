"""Essays app URL configuration."""
from django.urls import path

from . import views

app_name = "essays"

urlpatterns = [
    # Unified result page (handles both 12-mezon AND legacy BMB submissions)
    path("result/<int:submission_id>/", views.essay_result_view, name="result"),

    # Polling endpoint — asinxron baholash holatini tekshirish (JSON).
    # Frontend status=graded/ai_evaluated bo'lganda result sahifasiga o'tadi.
    path("api/<int:submission_id>/status/", views.essay_grading_status_view, name="grading-status"),

    # AI improved version (AJAX)
    path("result/<int:submission_id>/improve/", views.essay_improve_view, name="improve"),

    # 12-Mezon grading (new flow)
    path("submit/", views.essay_create_view, name="submit-new"),

    # Student flow: topic list → password gate → write → submit
    path("", views.essay_topics_view, name="topics"),
    path("<int:topic_id>/start/", views.essay_password_gate_view, name="password-gate"),
    path("write/<int:submission_id>/", views.essay_write_view, name="write"),
    path("api/autosave/", views.essay_autosave_view, name="autosave"),
    path("<int:submission_id>/submit/", views.essay_submit_view, name="submit"),
    path("<int:submission_id>/request-review/", views.essay_request_review_view, name="request-review"),

    # Teacher
    path("teacher/queue/", views.teacher_essay_queue_view, name="teacher-queue"),
    path("teacher/<int:submission_id>/review/", views.teacher_review_view, name="teacher-review"),
    path("teacher/<int:submission_id>/submit-review/", views.teacher_submit_review_view, name="teacher-submit-review"),
]
