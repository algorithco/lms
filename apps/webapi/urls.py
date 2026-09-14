"""React SPA API — mounted at /api/v1/ (additive, HTML views untouched)."""
from django.urls import path

from . import views_billing, views_essays, views_games, views_panel, views_school

app_name = "webapi"

urlpatterns = [
    # -- Games -----------------------------------------------------------
    path("games/", views_games.hub_view, name="games-hub"),
    path("games/leaderboard/", views_games.leaderboard_view, name="games-leaderboard"),
    path("games/<slug:slug>/play/", views_games.play_view, name="games-play"),
    path("games/<slug:slug>/check/", views_games.check_view, name="games-check"),
    # -- Panel -----------------------------------------------------------
    path("panel/dashboard/", views_panel.dashboard_view, name="panel-dashboard"),
    path("panel/tests/", views_panel.tests_view, name="panel-tests"),
    path("panel/tests/<int:test_id>/", views_panel.test_detail_view, name="panel-test-detail"),
    path("panel/tests/<int:test_id>/status/", views_panel.test_status_view, name="panel-test-status"),
    path("panel/tests/<int:test_id>/questions/", views_panel.questions_view, name="panel-questions"),
    path(
        "panel/tests/<int:test_id>/questions/<int:question_id>/",
        views_panel.question_detail_view,
        name="panel-question-detail",
    ),
    path("panel/topics/", views_panel.topics_view, name="panel-topics"),
    path("panel/topics/<int:topic_id>/", views_panel.topic_detail_view, name="panel-topic-detail"),
    path("panel/users/", views_panel.users_view, name="panel-users"),
    path("panel/users/<int:user_id>/role/", views_panel.user_role_view, name="panel-user-role"),
    path("panel/users/<int:user_id>/block/", views_panel.user_block_view, name="panel-user-block"),
    # -- Billing ---------------------------------------------------------
    path("billing/plans/", views_billing.plans_view, name="billing-plans"),
    path("billing/my/", views_billing.my_view, name="billing-my"),
    path("billing/subscribe/<int:plan_id>/", views_billing.subscribe_info_view, name="billing-subscribe"),
    path("billing/cancel/", views_billing.cancel_view, name="billing-cancel"),
    # -- School ----------------------------------------------------------
    path("school/groups/", views_school.groups_view, name="school-groups"),
    path("school/groups/<int:group_id>/", views_school.group_detail_view, name="school-group-detail"),
    path("school/groups/<int:group_id>/members/", views_school.group_members_view, name="school-group-members"),
    path("school/students/", views_school.student_search_view, name="school-students"),
    path("school/parent/", views_school.parent_overview_view, name="school-parent"),
    path("school/teacher/", views_school.teacher_overview_view, name="school-teacher"),
    path("school/analytics/", views_school.analytics_view, name="school-analytics"),
    path("school/public-stats/", views_school.public_stats_view, name="school-public-stats"),
    path("school/essay-leaderboard/", views_school.essay_leaderboard_view, name="school-essay-leaderboard"),
    path("school/import-students/", views_school.import_students_view, name="school-import-students"),
    path("school/import-test/", views_school.import_test_view, name="school-import-test"),
    # -- Essays teacher review -------------------------------------------
    path("essays/teacher/queue/", views_essays.teacher_queue_view, name="essays-teacher-queue"),
    path("essays/teacher/<int:submission_id>/", views_essays.teacher_submission_view, name="essays-teacher-detail"),
    path("essays/teacher/<int:submission_id>/review/", views_essays.teacher_submit_review_view, name="essays-teacher-review"),
]
