"""
Certificates views — download and verify endpoints.

OPTIMIZATIONS (Phase 7):
    1. Certificate verification reads current data for every request.
    2. Proper logging for all error paths.
    3. select_related on all querysets to eliminate N+1.
    4. File not found edge case handled gracefully.

API Endpoints:
    GET  /api/certificates/my-certificates/             — O'quvchining sertifikatlari
    GET  /api/certificates/{id}/download/               — PDF yuklab olish
    POST /api/certificates/verify/{certificate_number}/ — Tekshirish (public API)

Web Pages:
    GET  /certificates/verify/<number>/                  — Tekshirish sahifasi (HTML)
    GET  /certificates/<id>/download/                    — PDF yuklab olish (web)
"""
from __future__ import annotations

import logging
from typing import Any

from django.http import FileResponse, Http404
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsStudent
from apps.results.access import can_access_certificate
from apps.results.models import Certificate, Result

from .serializers import CertificateListSerializer, CertificateVerifySerializer

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# API: My Certificates List
# -------------------------------------------------------------------

class MyCertificatesView(generics.ListAPIView):
    """
    GET /api/certificates/my-certificates/

    O'quvchining barcha sertifikatlari.
    """

    serializer_class = CertificateListSerializer
    permission_classes = [IsAuthenticated, IsStudent]

    def get_queryset(self):
        return Certificate.objects.filter(
            student=self.request.user,
        ).select_related("test", "course", "result")


# -------------------------------------------------------------------
# API: Download Certificate PDF
# -------------------------------------------------------------------

class CertificateDownloadView(APIView):
    """
    GET /api/certificates/{id}/download/

    Sertifikat PDF faylini yuklab olish.
    Student faqat o'z sertifikatini yuklab oladi.

    Response: PDF fayl (Content-Type: application/pdf)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, pk: int, *args: Any, **kwargs: Any) -> Response:
        """PDF faylni qaytarish."""
        try:
            certificate = Certificate.objects.select_related(
                "student", "result",
            ).get(pk=pk)
        except Certificate.DoesNotExist:
            logger.warning("Certificate not found: pk=%d", pk)
            return Response(
                {"error": "Sertifikat topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not can_access_certificate(request.user, certificate):
            logger.warning(
                "Certificate access denied: pk=%d, user=%d",
                pk, request.user.id,
            )
            return Response(
                {"error": "Bu sertifikatni ko'rishga ruxsatingiz yo'q."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # PDF fayl mavjudmi?
        if not certificate.file:
            return Response(
                {
                    "error": "PDF fayl hali generatsiya qilinmagan.",
                    "status": certificate.status,
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        if certificate.status != Certificate.Status.GENERATED:
            return Response(
                {
                    "error": "Sertifikat hali tayyor emas.",
                    "status": certificate.status,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        # PDF faylni qaytarish
        try:
            response = FileResponse(
                certificate.file.open("rb"),
                content_type="application/pdf",
            )
            filename = f"{certificate.certificate_number}.pdf"
            response["Content-Disposition"] = (
                f'attachment; filename="{filename}"'
            )
            return response
        except FileNotFoundError:
            logger.error(
                "Certificate PDF file missing: cert=%s, path=%s",
                certificate.certificate_number, certificate.file.name,
            )
            return Response(
                {"error": "PDF fayl topilmadi."},
                status=status.HTTP_404_NOT_FOUND,
            )


# -------------------------------------------------------------------
# API: Verify Certificate (Public JSON API)
# -------------------------------------------------------------------

class CertificateVerifyView(APIView):
    """
    POST /api/certificates/verify/{certificate_number}/

    Sertifikat haqiqiyligini tekshirish — public API.
    Auth talab qilinmaydi (AllowAny).
    The HMAC is checked against current database state on every request.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request, certificate_number: str, *args: Any, **kwargs: Any) -> Response:
        """Sertifikatni tekshirish (JSON API)."""
        return self._verify(certificate_number)

    def get(self, request: Request, certificate_number: str, *args: Any, **kwargs: Any) -> Response:
        """Sertifikatni tekshirish (GET ham qo'llab-quvvatlaydi)."""
        return self._verify(certificate_number)

    def _verify(self, certificate_number: str) -> Response:
        try:
            certificate = Certificate.objects.select_related(
                "student", "test", "course",
            ).get(certificate_number=certificate_number)
        except Certificate.DoesNotExist:
            result = {
                "valid": False,
                "error": "Sertifikat topilmadi.",
            }
            return Response(result, status=status.HTTP_404_NOT_FOUND)

        # Anti-fraud verification
        from apps.certificates.services.anti_fraud import verify_certificate_checksum
        fraud_check = verify_certificate_checksum(certificate)

        result = {
            "valid": bool(
                fraud_check["valid"]
                and certificate.status == Certificate.Status.GENERATED
            ),
            "certificate_number": certificate.certificate_number,
            "student_name": certificate.student.get_full_name(),
            "course_title": certificate.course.title,
            "test_title": certificate.test.title,
            "percentage": str(certificate.result.percentage),
            "issued_at": certificate.issued_at,
            "status": certificate.status,
            "anti_fraud": {
                "verified": fraud_check["valid"],
                "reason": fraud_check["reason"],
                "checksum": certificate.fraud_checksum[:16] + "..." if certificate.fraud_checksum else None,
            },
        }

        response_status = (
            status.HTTP_200_OK
            if result["valid"]
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        return Response(result, status=response_status)


# -------------------------------------------------------------------
# Web: Verify Certificate Page (HTML)
# -------------------------------------------------------------------
def certificate_verify_page_view(request, certificate_number: str):
    """
    GET /certificates/verify/<certificate_number>/

    Public HTML page for certificate verification.
    No auth required — accessible via QR code scan.
    Checks the stored HMAC against current database state on every request.
    """
    certificate = None
    error = None

    try:
        certificate = Certificate.objects.select_related(
            "student", "test", "course", "result",
        ).get(certificate_number=certificate_number)
        from apps.certificates.services.anti_fraud import verify_certificate_checksum
        fraud_check = verify_certificate_checksum(certificate)
        if (
            not fraud_check["valid"]
            or certificate.status != Certificate.Status.GENERATED
        ):
            error = fraud_check["reason"]
            certificate = None
    except Certificate.DoesNotExist:
        error = "Sertifikat topilmadi."
        logger.info("Certificate verify page: not found=%s", certificate_number)

    ctx = {
        "certificate": certificate,
        "error": error,
        "certificate_number": certificate_number,
    }

    return render(request, "web/verify_certificate.html", ctx)


# -------------------------------------------------------------------
# Web: Certificate Download (HTML redirect)
# -------------------------------------------------------------------

def certificate_web_download_view(request, cert_id: int):
    """
    GET /certificates/<id>/download/

    Web-based PDF download (requires auth).
    """
    cert = get_object_or_404(Certificate, id=cert_id)

    if not can_access_certificate(request.user, cert):
        raise PermissionDenied

    if not cert.file:
        from django.contrib import messages
        messages.error(request, "PDF fayl hali generatsiya qilinmagan.")
        return redirect("web:my-certificates")

    try:
        response = FileResponse(cert.file.open("rb"), content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="{cert.certificate_number}.pdf"'
        )
        return response
    except FileNotFoundError:
        logger.error("Certificate PDF file missing: cert_id=%d", cert_id)
        from django.contrib import messages
        messages.error(request, "PDF fayl topilmadi.")
        return redirect("web:my-certificates")
