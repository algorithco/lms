"""React SPA API — mounted at /api/v1/ (additive, HTML views untouched)."""
from django.urls import path

from apps.accounts import google_auth as google_auth_views
from . import (
    views_attendance,
    views_billing,
    views_reports,
    views_tuition,
    views_essays,
    views_games,
    views_panel,
    views_school,
)

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
    path("panel/tests/<int:test_id>/sections/", views_panel.sections_view, name="panel-sections"),
    path("panel/tests/<int:test_id>/passages/", views_panel.passages_view, name="panel-passages"),
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
    path("billing/entitlement/", views_billing.entitlement_view, name="billing-entitlement"),
    path("billing/subscribe/<int:plan_id>/", views_billing.subscribe_info_view, name="billing-subscribe"),
    path("billing/cancel/", views_billing.cancel_view, name="billing-cancel"),
    # -- Payments & Receipts ---------------------------------------------
    path("payments/card-info/", views_billing.card_info_view, name="payments-card-info"),
    path("payments/receipts/", views_billing.payment_receipt_upload_view, name="payments-receipt-upload"),
    path("payments/my-receipts/", views_billing.my_payment_receipts_view, name="payments-my-receipts"),
    # -- Google OAuth ----------------------------------------------------
    path("auth/google/", google_auth_views.google_auth_verify, name="auth-google"),
    path("auth/google/config/", google_auth_views.google_auth_config, name="auth-google-config"),
    path("auth/google/callback/", google_auth_views.google_auth_callback, name="auth-google-callback"),
    # -- School ----------------------------------------------------------
    path("school/groups/", views_school.groups_view, name="school-groups"),
    path("school/groups/<int:group_id>/", views_school.group_detail_view, name="school-group-detail"),
    path("school/groups/<int:group_id>/members/", views_school.group_members_view, name="school-group-members"),
    path("school/groups/<int:group_id>/analytics/", views_school.group_analytics_view, name="school-group-analytics"),
    path("school/groups/<int:group_id>/export/excel/", views_school.group_export_excel_view, name="school-group-export-excel"),
    path("school/groups/<int:group_id>/export/pdf/", views_school.group_export_pdf_view, name="school-group-export-pdf"),
    path("school/groups/join/", views_school.group_join_view, name="school-group-join"),
    path("school/students/", views_school.student_search_view, name="school-students"),
    path("school/parent/", views_school.parent_overview_view, name="school-parent"),
    path("school/teacher/", views_school.teacher_overview_view, name="school-teacher"),
    path("school/analytics/", views_school.analytics_view, name="school-analytics"),
    path("school/public-stats/", views_school.public_stats_view, name="school-public-stats"),
    path("school/essay-leaderboard/", views_school.essay_leaderboard_view, name="school-essay-leaderboard"),
    path("school/import-students/", views_school.import_students_view, name="school-import-students"),
    path("school/import-test/", views_school.import_test_view, name="school-import-test"),
    # -- School: attendance ------------------------------------------------
    path(
        "school/attendance/sessions/",
        views_attendance.attendance_sessions_view,
        name="school-attendance-sessions",
    ),
    path(
        "school/attendance/sessions/<int:session_id>/",
        views_attendance.attendance_session_detail_view,
        name="school-attendance-session-detail",
    ),
    path(
        "school/attendance/sessions/<int:session_id>/mark/",
        views_attendance.attendance_mark_view,
        name="school-attendance-session-mark",
    ),
    path(
        "school/attendance/sessions/<int:session_id>/mark-all-present/",
        views_attendance.attendance_mark_all_present_view,
        name="school-attendance-session-mark-all-present",
    ),
    path(
        "school/attendance/sessions/<int:session_id>/finalize/",
        views_attendance.attendance_finalize_view,
        name="school-attendance-session-finalize",
    ),
    path(
        "school/attendance/report/",
        views_attendance.attendance_report_view,
        name="school-attendance-report",
    ),
    path(
        "school/attendance/students/<int:student_id>/",
        views_attendance.attendance_student_view,
        name="school-attendance-student",
    ),
    # -- School: classroom observations ------------------------------------
    path(
        "school/observations/",
        views_attendance.observation_create_view,
        name="school-observation-create",
    ),
    path(
        "school/observations/<int:observation_id>/",
        views_attendance.observation_detail_view,
        name="school-observation-detail",
    ),
    path(
        "school/observations/<int:observation_id>/confirm/",
        views_attendance.observation_confirm_view,
        name="school-observation-confirm",
    ),
    # -- School: group essay reporting -------------------------------------
    path(
        "school/essay-results/",
        views_attendance.essay_results_view,
        name="school-essay-results",
    ),
    path(
        "school/essay-summary/",
        views_attendance.essay_summary_view,
        name="school-essay-summary",
    ),
    path(
        "school/assignments/",
        views_attendance.assignments_view,
        name="school-assignments",
    ),
    path(
        "school/assignments/<int:assignment_id>/completion/",
        views_attendance.assignment_completion_view,
        name="school-assignment-completion",
    ),
    # -- School: notifications ---------------------------------------------
    path(
        "school/notification-preferences/",
        views_attendance.notification_preferences_view,
        name="school-notification-preferences",
    ),
    path(
        "school/notification-destinations/",
        views_attendance.notification_destinations_view,
        name="school-notification-destinations",
    ),
    path(
        "school/notification-destinations/<int:destination_id>/approve/",
        views_attendance.notification_destination_approve_view,
        name="school-notification-destination-approve",
    ),
    path(
        "school/parent/attendance/",
        views_attendance.parent_attendance_view,
        name="school-parent-attendance",
    ),
    # -- Course tuition (separate from platform subscriptions) ----------
    path("billing/tuition/", views_tuition.my_tuition_view, name="billing-tuition-my"),
    path(
        "billing/tuition/invoices/<int:invoice_id>/",
        views_tuition.invoice_detail_view,
        name="billing-tuition-invoice-detail",
    ),
    path(
        "billing/tuition/invoices/<int:invoice_id>/payments/",
        views_tuition.invoice_detail_view,
        name="billing-tuition-invoice-payments",
    ),
    path(
        "billing/tuition/children/",
        views_tuition.child_tuition_view,
        name="billing-tuition-children",
    ),
    path(
        "billing/tuition/payments/",
        views_tuition.submit_payment_view,
        name="billing-tuition-payment-submit",
    ),
    path(
        "billing/tuition/payments/<int:payment_id>/",
        views_tuition.payment_detail_view,
        name="billing-tuition-payment-detail",
    ),
    path(
        "school/tuition/finance/",
        views_tuition.group_tuition_view,
        name="school-tuition-finance",
    ),
    path(
        "school/tuition/policies/",
        views_tuition.billing_policy_list_view,
        name="school-tuition-policies",
    ),
    path(
        "school/tuition/policies/create/",
        views_tuition.billing_policy_create_view,
        name="school-tuition-policy-create",
    ),
    path(
        "school/tuition/policies/<int:policy_id>/",
        views_tuition.billing_policy_detail_view,
        name="school-tuition-policy-detail",
    ),
    path(
        "school/tuition/invoices/",
        views_tuition.invoice_list_view,
        name="school-tuition-invoices",
    ),
    path(
        "school/tuition/invoices/<int:invoice_id>/due-date/",
        views_tuition.mark_invoice_overdue_view,
        name="school-tuition-invoice-due-date",
    ),
    path(
        "school/tuition/invoices/<int:invoice_id>/waive/",
        views_tuition.waive_invoice_view,
        name="school-tuition-invoice-waive",
    ),
    path(
        "school/tuition/invoices/<int:invoice_id>/payments/record/",
        views_tuition.record_invoice_payment_view,
        name="school-tuition-invoice-payment-record",
    ),
    path(
        "school/tuition/invoices/<int:invoice_id>/adjust/",
        views_tuition.adjust_invoice_view,
        name="school-tuition-invoice-adjust",
    ),
    path(
        "school/tuition/payments/",
        views_tuition.payment_queue_view,
        name="school-tuition-payment-queue",
    ),
    path(
        "school/tuition/payments/<int:payment_id>/verify/",
        views_tuition.verify_payment_view,
        name="school-tuition-payment-verify",
    ),
    path(
        "school/tuition/payments/<int:payment_id>/reject/",
        views_tuition.reject_payment_view,
        name="school-tuition-payment-reject",
    ),
    path(
        "school/tuition/audit/",
        views_tuition.tuition_audit_view,
        name="school-tuition-audit",
    ),
    path(
        "school/tuition/students/<int:student_id>/",
        views_tuition.admin_student_tuition_view,
        name="school-tuition-student",
    ),
    # -- Automated weekly academic reports ------------------------------
    path(
        "school/weekly-reports/",
        views_reports.weekly_report_list_view,
        name="school-weekly-reports",
    ),
    path(
        "school/weekly-reports/generate/",
        views_reports.weekly_report_generate_view,
        name="school-weekly-report-generate",
    ),
    path(
        "school/weekly-reports/<int:report_id>/",
        views_reports.weekly_report_detail_view,
        name="school-weekly-report-detail",
    ),
    path(
        "school/weekly-reports/<int:report_id>/regenerate/",
        views_reports.weekly_report_regenerate_view,
        name="school-weekly-report-regenerate",
    ),
    path(
        "school/weekly-student-reports/<int:report_id>/",
        views_reports.weekly_student_report_detail_view,
        name="school-weekly-student-report-detail",
    ),
    path(
        "school/weekly-student-reports/<int:report_id>/regenerate/",
        views_reports.weekly_student_report_regenerate_view,
        name="school-weekly-student-report-regenerate",
    ),
    path(
        "school/weekly-reports/<int:report_id>/send/",
        views_reports.weekly_report_send_view,
        name="school-weekly-report-send",
    ),
    path(
        "school/weekly-reports/schedule/",
        views_reports.report_schedule_view,
        name="school-weekly-report-schedule",
    ),
    path(
        "school/weekly-reports/deliveries/",
        views_reports.report_delivery_log_view,
        name="school-weekly-report-deliveries",
    ),
    path(
        "billing/weekly-reports/",
        views_reports.my_weekly_reports_view,
        name="billing-weekly-reports-my",
    ),
    path(
        "billing/report-period/",
        views_reports.report_period_preview_view,
        name="billing-report-period",
    ),
    path(
        "school/weekly-reports/retry-failed/",
        views_reports.report_delivery_log_view,
        name="school-weekly-report-retry-failed",
    ),
    # -- Essays teacher review & student actions -------------------------
    path("essays/teacher/queue/", views_essays.teacher_queue_view, name="essays-teacher-queue"),
    path("essays/teacher/<int:submission_id>/", views_essays.teacher_submission_view, name="essays-teacher-detail"),
    path("essays/teacher/<int:submission_id>/review/", views_essays.teacher_submit_review_view, name="essays-teacher-review"),
    path("essays/teacher/<int:submission_id>/edit/", views_essays.teacher_edit_submission_view, name="essays-teacher-edit"),
    path("essays/<int:submission_id>/improve/", views_essays.student_improve_view, name="essays-student-improve"),
    path("essays/<int:submission_id>/request-review/", views_essays.student_request_review_view, name="essays-student-request-review"),
]
