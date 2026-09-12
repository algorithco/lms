"""
Certificates app URL configuration.

Endpoints:
    GET  /api/certificates/my-certificates/             — O'quvchining sertifikatlari
    GET  /api/certificates/{id}/download/               — PDF yuklab olish
    POST /api/certificates/verify/{certificate_number}/  — Tekshirish (public)
"""
from django.urls import path

from . import views

app_name = "certificates"

urlpatterns = [
    path(
        "my-certificates/",
        views.MyCertificatesView.as_view(),
        name="my-certificates",
    ),
    path(
        "<int:pk>/download/",
        views.CertificateDownloadView.as_view(),
        name="certificate-download",
    ),
    path(
        "verify/<str:certificate_number>/",
        views.CertificateVerifyView.as_view(),
        name="certificate-verify",
    ),
]
