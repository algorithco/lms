"""In-app Admin Panel URL configuration (mounted at /control-panel/)."""
from django.urls import path

from . import views

app_name = "panel"

urlpatterns = [
    # -- Dashboard ---------------------------------------------------------
    path("", views.dashboard_view, name="dashboard"),

    # -- Tests -------------------------------------------------------------
    path("tests/", views.test_list_view, name="test-list"),
    path("tests/create/", views.test_create_view, name="test-create"),
    path("tests/<int:test_id>/edit/", views.test_edit_view, name="test-edit"),
    path("tests/<int:test_id>/delete/", views.test_delete_view, name="test-delete"),
    path("tests/<int:test_id>/status/", views.test_status_view, name="test-status"),

    # -- Questions ---------------------------------------------------------
    path("tests/<int:test_id>/questions/", views.question_manage_view, name="question-manage"),
    path("tests/<int:test_id>/questions/add/", views.question_add_view, name="question-add"),
    path(
        "tests/<int:test_id>/questions/<int:question_id>/edit/",
        views.question_edit_view,
        name="question-edit",
    ),
    path(
        "tests/<int:test_id>/questions/<int:question_id>/delete/",
        views.question_delete_view,
        name="question-delete",
    ),

    # -- Essay topics ------------------------------------------------------
    path("essay-topics/", views.essay_topic_list_view, name="essay-topic-list"),
    path("essay-topics/create/", views.essay_topic_create_view, name="essay-topic-create"),
    path("essay-topics/<int:topic_id>/edit/", views.essay_topic_edit_view, name="essay-topic-edit"),
    path("essay-topics/<int:topic_id>/delete/", views.essay_topic_delete_view, name="essay-topic-delete"),

    # -- Users -------------------------------------------------------------
    path("users/", views.user_list_view, name="user-list"),
    path("users/<int:user_id>/role/", views.user_role_view, name="user-role"),
    path("users/<int:user_id>/block/", views.user_block_view, name="user-block"),
]