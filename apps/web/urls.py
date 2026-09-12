"""
Web app URL configuration — HTML page routes.

All routes render Django templates (server-side rendered).
"""
from django.urls import include, path

from . import views
from apps.certificates.views import certificate_verify_page_view

app_name = "web"

urlpatterns = [
    # -- Home / Landing -------------------------------------------------------
    path("", views.home_view, name="home"),

    # -- Auth -----------------------------------------------------------------
    path("login/", views.LoginView.as_view(), name="login"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("logout/", views.logout_view, name="logout"),
    path("set-language/<str:lang>/", views.set_language_view, name="set-language"),

    # -- Password Reset -------------------------------------------------------
    path("password-reset/", views.SecurePasswordResetView.as_view(
        template_name="registration/password_reset.html",
        email_template_name="registration/password_reset_email.txt",
        html_email_template_name="registration/password_reset_email.html",
        subject_template_name="registration/password_reset_subject.txt",
        success_url="/password-reset/done/",
    ), name="password-reset"),
    path("password-reset/done/", views.PasswordResetDoneView.as_view(
        template_name="registration/password_reset_done.html",
    ), name="password-reset-done"),
    path("password-reset/<uidb64>/<token>/", views.PasswordResetConfirmView.as_view(
        template_name="registration/password_reset_confirm.html",
        success_url="/password-reset/complete/",
    ), name="password-reset-confirm"),
    path("password-reset/complete/", views.PasswordResetCompleteView.as_view(
        template_name="registration/password_reset_complete.html",
    ), name="password-reset-complete"),

    # -- Dashboard ------------------------------------------------------------
    path("dashboard/", views.dashboard_view, name="dashboard"),

    # -- Tests ----------------------------------------------------------------
    path("tests/", views.test_list_view, name="test-list"),
    path("tests/<int:test_id>/take/", views.take_test_view, name="take-test"),

    # -- Results --------------------------------------------------------------
    path("results/", views.my_results_view, name="my-results"),
    path("results/<int:result_id>/", views.result_detail_view, name="result-detail"),

    # -- Certificates ---------------------------------------------------------
    path("certificates/", views.my_certificates_view, name="my-certificates"),
    path("certificates/<int:cert_id>/download/", views.certificate_download_view, name="certificate-download"),
    # Public certificate verification (accessible via QR code, no auth required)
    path(
        "certificates/verify/<str:certificate_number>/",
        certificate_verify_page_view,
        name="certificate-verify",
    ),

    # -- Teacher --------------------------------------------------------------
    path("teacher/dashboard/", views.teacher_results_view, name="teacher-dashboard"),
    path("teacher/analytics/", views.analytics_view, name="analytics"),
    path("api/teacher/analytics/", views.analytics_api_view, name="analytics-api"),

    # -- Essay Leaderboard ----------------------------------------------------
    path("essay-leaderboard/", views.essay_leaderboard_view, name="essay-leaderboard"),

    # -- Admin: Teacher Management ---------------------------------------------
    path("manage-teachers/", views.manage_teachers_view, name="manage-teachers"),
    path("manage-teachers/<int:user_id>/promote/", views.promote_user_view, name="promote-user"),
    path("manage-teachers/<int:user_id>/demote/", views.demote_user_view, name="demote-user"),

    # -- Teacher: Student Groups -----------------------------------------------
    path("groups/", views.group_list_view, name="group-list"),
    path("groups/create/", views.group_create_view, name="group-create"),
    path("groups/<int:group_id>/", views.group_detail_view, name="group-detail"),
    path("groups/<int:group_id>/edit/", views.group_edit_view, name="group-edit"),
    path("groups/<int:group_id>/delete/", views.group_delete_view, name="group-delete"),

    # -- Games ----------------------------------------------------------------
    path("games/", include("apps.games.urls", namespace="games")),

    # -- Parent Portal --------------------------------------------------------
    path("parent/", views.parent_portal_view, name="parent-portal"),

    # -- CSV Import -----------------------------------------------------------
    path("import/students/", views.csv_import_view, name="csv-import"),
    path("import/tests/", views.bulk_test_import_view, name="bulk-test-import"),
]
