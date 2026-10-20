"""Canonical certificate generation — single source of truth.

Other modules (results tasks, notifications tasks, tests sync fallback) must
call generate_certificate() instead of duplicating PDF/HMAC logic.
Preserves format, HMAC/QR anti-fraud behavior, identifiers, idempotency.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def exam_uses_milliy_rules(test) -> bool:
    """True when a test actually uses Milliy features: any question assigned
    to a section or of a new type (gap_fill/matching/written). Legacy plain
    tests return False and keep the historical certificate path unchanged.
    Single indexed EXISTS query."""
    from django.db.models import Q

    from apps.tests.models import Question

    return test.questions.filter(
        Q(section__isnull=False)
        | Q(
            question_type__in=(
                Question.QuestionType.GAP_FILL,
                Question.QuestionType.MATCHING,
                Question.QuestionType.WRITTEN,
            )
        )
    ).exists()


def resolve_profile(test):
    """Effective scoring profile: the test's linked profile, else the
    shared default (auto-created, UNVERIFIED)."""
    linked = getattr(test, "scoring_profile", None)
    if linked is not None:
        # Refresh defensively: callers may hold a stale cached relation.
        linked.refresh_from_db(fields=["is_verified", "certificate_min_percentage"])
        return linked
    from apps.tests.models import ExamScoringProfile

    profile, _ = ExamScoringProfile.objects.get_or_create(
        name="default",
        version="v1",
        defaults={"is_active": True, "is_verified": False},
    )
    return profile


def certificate_status(result, *, is_milliy: bool | None = None, profile=None) -> str:
    """Canonical eligibility state for a Result. One of:
    pending_writing | rules_unverified | not_passed | below_threshold |
    eligible. Only `eligible` may produce a certificate.

    `is_milliy`/`profile` hints skip DB lookups when the caller already
    resolved them (hot grading path); cold callers omit them.
    """
    test = result.test
    if getattr(result, "grading_status", "graded") != "graded":
        return "pending_writing"
    milliy = exam_uses_milliy_rules(test) if is_milliy is None else is_milliy
    if not milliy:
        return "eligible" if result.is_passed else "not_passed"
    profile = resolve_profile(test) if profile is None else profile
    if not profile.is_verified:
        return "rules_unverified"
    try:
        threshold = float(profile.certificate_min_percentage)
    except (TypeError, ValueError):
        return "rules_unverified"
    if float(result.percentage) < threshold:
        return "below_threshold"
    return "eligible" if result.is_passed else "not_passed"


def generate_certificate(
    result: Any, *, is_milliy: bool | None = None, profile=None
) -> tuple[Any, bool]:
    """Create-or-reuse Certificate for *result* and generate its PDF.

    Returns (cert, created_or_generated_bool). Idempotent: existing GENERATED
    certs are reused. Format/verify URL preserved:
    {SITE_URL}/certificates/verify/<number>/ (canonical public path).

    Safety gates (checked before any PDF/row side effects beyond a PENDING
    placeholder): writing must be graded, and Milliy exams additionally
    require a VERIFIED scoring profile meeting its threshold. An unverified
    or placeholder profile NEVER issues a certificate — no Certificate row
    is even created in that case.
    """
    from django.conf import settings
    from django.core.files.base import ContentFile

    from apps.results.models import Certificate
    from apps.results.services.pdf_service import generate_certificate_pdf

    status = certificate_status(result, is_milliy=is_milliy, profile=profile)
    if status != "eligible":
        logger.info(
            "Certificate refused: result=%s status=%s (no PDF, no row)",
            getattr(result, "id", "?"),
            status,
        )
        try:
            existing = Certificate.objects.filter(result=result).first()
        except Exception:
            existing = None
        return existing, False

    cert, _ = Certificate.objects.get_or_create(
        result=result,
        defaults={
            "student": result.student,
            "test": result.test,
            "course": result.course,
        },
    )

    if cert.status == Certificate.Status.GENERATED and cert.file:
        return cert, False

    base_url = getattr(settings, "SITE_URL", "http://localhost:8000")
    verify_url = f"{base_url}/certificates/verify/{cert.certificate_number}/"

    pdf_bytes = generate_certificate_pdf(
        certificate_number=cert.certificate_number,
        student_full_name=result.student.get_full_name(),
        course_title=result.course.title,
        test_title=result.test.title,
        percentage=float(result.percentage),
        issued_at=cert.issued_at,
        verify_url=verify_url,
    )

    filename = f"{cert.certificate_number}.pdf"
    # FileSystemStorage.save() may append a suffix if the name exists;
    # delete the stale file first so the canonical name is preserved.
    if cert.file:
        try:
            cert.file.delete(save=False)
        except Exception:
            pass
    cert.file.save(filename, ContentFile(pdf_bytes), save=False)
    cert.status = Certificate.Status.GENERATED
    cert.save(update_fields=["file", "status"])

    from apps.certificates.services.anti_fraud import generate_and_store_checksum

    generate_and_store_checksum(cert)
    return cert, True


def mark_failed(result_id: int) -> None:
    """Mark certificate FAILED for *result_id* (best-effort, never raises)."""
    try:
        from apps.results.models import Certificate

        cert = Certificate.objects.get(result_id=result_id)
        cert.status = Certificate.Status.FAILED
        cert.save(update_fields=["status"])
    except Exception:
        pass
