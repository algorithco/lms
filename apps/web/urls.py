"""
Web app URL configuration — Minimal routes for test compatibility.

Most page routes are now handled by the React SPA. This module keeps
only the routes that existing tests and backend code depend on.
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
    # Kept for URL namespace compatibility; React handles via JSON API.
    path(
        "password-reset/",
        views.SecurePasswordResetView.as_view(
            email_template_name="registration/password_reset_email.txt",
            html_email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
            success_url="/password-reset/done/",
        ),
        name="password-reset",
    ),
    path(
        "password-reset/done/",
        views.password_reset_done_view,
        name="password-reset-done",
    ),
    path(
        "password-reset/<uidb64>/<token>/",
        views.password_reset_confirm_view,
        name="password-reset-confirm",
    ),
    path(
        "password-reset/complete/",
        views.password_reset_complete_view,
        name="password-reset-complete",
    ),
    # -- Dashboard ------------------------------------------------------------
    path("dashboard/", views.dashboard_view, name="dashboard"),
    # -- Results --------------------------------------------------------------
    # Preserved for security tests (permission checks)
    path("results/<int:result_id>/", views.result_detail_view, name="result-detail"),
    # -- Teacher Management ---------------------------------------------------
    # Preserved for security tests (admin-only permission checks)
    path("manage-teachers/", views.manage_teachers_view, name="manage-teachers"),
    path(
        "manage-teachers/<int:user_id>/promote/",
        views.promote_user_view,
        name="promote-user",
    ),
    path(
        "manage-teachers/<int:user_id>/demote/",
        views.demote_user_view,
        name="demote-user",
    ),
    # -- Games (namespace required by tests) ----------------------------------
    path("games/", include("apps.games.urls", namespace="games")),
    # -- Certificate verification (public, no auth) ---------------------------
    path(
        "certificates/verify/<str:certificate_number>/",
        certificate_verify_page_view,
        name="certificate-verify",
    ),
]
