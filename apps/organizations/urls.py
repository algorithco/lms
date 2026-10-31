"""
URLs for organizations app.
"""

from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.enterprise_dashboard_view, name="enterprise_dashboard"),
    path("centers/", views.enterprise_create_center_view, name="enterprise_centers"),
    path(
        "centers/create/",
        views.enterprise_create_center_view,
        name="enterprise_create_center",
    ),
    path(
        "students/bulk-import/",
        views.enterprise_bulk_import_view,
        name="enterprise_bulk_import",
    ),
    path(
        "report/download/",
        views.enterprise_report_export_view,
        name="enterprise_report_export",
    ),
]
