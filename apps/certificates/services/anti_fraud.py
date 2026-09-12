"""
Anti-Fraud Certificate Verification Service.

Generates a cryptographic checksum for certificate data to prevent forgery.

Checksum algorithm:
    1. Collect certificate fields: number, student_name, course, percentage, date
    2. Concatenate into a canonical string
    3. Compute HMAC-SHA256 using a server-side secret key
    4. Store the checksum in the Certificate model
    5. Verification: recompute and compare

This ensures:
    - Certificate data hasn't been tampered with
    - Certificate is genuine (issued by our platform)
    - Cannot be forged without the secret key
"""
from __future__ import annotations

import hashlib
import hmac
import logging
from decimal import Decimal
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class AntiFraudService:
    """
    Cryptographic checksum generation and verification for certificates.
    """

    @classmethod
    def generate_checksum(cls, certificate) -> str:
        """
        Generate HMAC-SHA256 checksum for a certificate.

        Args:
            certificate: Certificate model instance.

        Returns:
            Hex-encoded checksum string (64 characters).
        """
        secret_key = cls._get_secret_key()
        canonical = cls._build_canonical_string(certificate)

        checksum = hmac.new(
            secret_key.encode(),
            canonical.encode(),
            hashlib.sha256,
        ).hexdigest()

        logger.debug(
            "Checksum generated: cert=%s, checksum=%s",
            certificate.certificate_number, checksum[:16],
        )

        return checksum

    @classmethod
    def verify_checksum(cls, certificate, provided_checksum: str) -> bool:
        """
        Verify a certificate's checksum.

        Args:
            certificate: Certificate model instance.
            provided_checksum: Checksum to verify against.

        Returns:
            True if checksum is valid, False otherwise.
        """
        if not provided_checksum or not certificate.fraud_checksum:
            return False

        # Recompute
        computed = cls.generate_checksum(certificate)

        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(computed, provided_checksum)

    @classmethod
    def _build_canonical_string(cls, certificate) -> str:
        """
        Build a canonical string from certificate fields.

        Order matters: always use the same field order.
        """
        parts = [
            str(certificate.certificate_number or ""),
            str(certificate.student_id),
            str(certificate.course_id),
            str(certificate.test_id),
            str(certificate.result_id),
            format(
                Decimal(str(certificate.result.percentage)).normalize(), "f"
            ) if certificate.result_id else "0",
            str(certificate.issued_at.strftime("%Y-%m-%d") if certificate.issued_at else ""),
            "LMS-PLATFORM-V2",
        ]
        return "|".join(parts)

    @classmethod
    def _get_secret_key(cls) -> str:
        """Get the secret key for HMAC."""
        key = getattr(settings, "CERTIFICATE_SECRET_KEY", None)
        if not key:
            # Derive from Django SECRET_KEY
            key = hashlib.sha256(
                f"lms-cert-{settings.SECRET_KEY}".encode()
            ).hexdigest()
        return key


def generate_and_store_checksum(certificate) -> str:
    """
    Generate checksum and store it in the certificate model.

    Called after certificate generation (in Celery task).
    """
    checksum = AntiFraudService.generate_checksum(certificate)

    # Store in the certificate model
    if hasattr(certificate, 'fraud_checksum'):
        certificate.fraud_checksum = checksum
        certificate.save(update_fields=["fraud_checksum"])

    return checksum


def verify_certificate_checksum(certificate) -> dict[str, Any]:
    """
    Full verification of a certificate.

    Returns:
        {"valid": bool, "reason": str}
    """
    if not certificate.fraud_checksum:
        return {"valid": False, "reason": "Sertifikatda xavfsizlik belgisi yo'q."}

    is_valid = AntiFraudService.verify_checksum(
        certificate, certificate.fraud_checksum
    )

    if is_valid:
        return {"valid": True, "reason": "Sertifikat haqiqiy va buzilmagan."}
    else:
        return {"valid": False, "reason": "Sertifikat ma'lumotlari o'zgartirilgan yoki soxta."}
