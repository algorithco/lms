"""
Results app — Result and Certificate.

Result   — aggregated score for a completed TestAttempt.
Certificate — PDF certificate generated when a student passes.

Design:
    - Result is a *view model* materialized after an attempt completes.
      It's denormalized from TestAttempt to keep reads fast and to decouple
      analytics from the attempt lifecycle.
    - Certificate is created via a Celery task so the PDF generation
      (ReportLab) doesn't block the HTTP response.
"""
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
class Result(models.Model):
    """
    Aggregated, immutable result record for a completed test attempt.

    Created by a Celery task right after TestAttempt status → COMPLETED.
    This model powers the analytics dashboard and certificate eligibility.
    """

    attempt = models.OneToOneField(
        "tests.TestAttempt",
        on_delete=models.CASCADE,
        related_name="result",
        verbose_name=_("urinish"),
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="results",
        verbose_name=_("o'quvchi"),
    )
    test = models.ForeignKey(
        "tests.Test",
        on_delete=models.CASCADE,
        related_name="results",
        verbose_name=_("test"),
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="results",
        verbose_name=_("kurs"),
    )

    # -- Score breakdown ------------------------------------------------------
    total_questions = models.PositiveIntegerField(_("umumiy savollar"))
    correct_answers = models.PositiveIntegerField(_("to'g'ri javoblar"))
    wrong_answers = models.PositiveIntegerField(_("noto'g'ri javoblar"))
    unanswered = models.PositiveIntegerField(_("javob berilmagan"), default=0)
    score = models.DecimalField(_("yig'indi ball"), max_digits=7, decimal_places=2)
    max_score = models.DecimalField(_("maks ball"), max_digits=7, decimal_places=2)
    percentage = models.DecimalField(
        _("foiz"),
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    is_passed = models.BooleanField(_("o'tdimi"))
    time_taken_seconds = models.PositiveIntegerField(
        _("sarflangan vaqt (soniya)"),
        default=0,
    )

    # -- Meta -----------------------------------------------------------------
    calculated_at = models.DateTimeField(_("hisoblangan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Natija")
        verbose_name_plural = _("Natijalar")
        ordering = ["-calculated_at"]
        indexes = [
            models.Index(fields=["student"], name="idx_result_student"),
            models.Index(fields=["course"], name="idx_result_course"),
            models.Index(fields=["is_passed"], name="idx_result_passed"),
            # Composite index for student dashboard + analytics queries
            models.Index(
                fields=["student", "is_passed", "-calculated_at"],
                name="idx_result_student_passed_time",
            ),
            # Composite index for teacher dashboard queries
            models.Index(
                fields=["course", "-calculated_at"],
                name="idx_result_course_time",
            ),
            # Composite index for stats aggregation
            models.Index(
                fields=["student", "-percentage"],
                name="idx_result_student_pct",
            ),
        ]

    def __str__(self) -> str:
        status = "✓ PASS" if self.is_passed else "✗ FAIL"
        return f"{self.student} — {self.test} — {self.percentage}% {status}"


# ---------------------------------------------------------------------------
# Certificate
# ---------------------------------------------------------------------------
class Certificate(models.Model):
    """
    PDF certificate issued when a student passes a test.

    `file` stores the generated PDF (ReportLab) in MEDIA_ROOT.
    `certificate_number` is a unique human-readable ID like LMS-2026-000042.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Tayyorlanmoqda")
        GENERATED = "generated", _("Tayyor")
        FAILED = "failed", _("Xatolik")

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="certificates",
        verbose_name=_("o'quvchi"),
    )
    result = models.OneToOneField(
        Result,
        on_delete=models.CASCADE,
        related_name="certificate",
        verbose_name=_("natija"),
    )
    test = models.ForeignKey(
        "tests.Test",
        on_delete=models.CASCADE,
        related_name="certificates",
        verbose_name=_("test"),
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.CASCADE,
        related_name="certificates",
        verbose_name=_("kurs"),
    )

    # -- Certificate data -----------------------------------------------------
    certificate_number = models.CharField(
        _("sertifikat raqami"),
        max_length=30,
        unique=True,
        editable=False,
        help_text=_("Avto-generatsiya: LMS-YYYY-XXXXXX"),
    )
    issued_at = models.DateTimeField(_("berilgan sana"), auto_now_add=True)
    file = models.FileField(
        _("PDF fayl"),
        upload_to="certificates/%Y/%m/",
        blank=True,
        null=True,
    )
    status = models.CharField(
        _("holat"),
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )

    # Anti-fraud: HMAC-SHA256 checksum
    fraud_checksum = models.CharField(
        _("xavfsizlik belgisi"),
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        help_text=_("Sertifikat ma'lumotlarining kriptografik checksumi."),
    )

    class Meta:
        verbose_name = _("Sertifikat")
        verbose_name_plural = _("Sertifikatlar")
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["student"], name="idx_cert_student"),
            models.Index(fields=["certificate_number"], name="idx_cert_number"),
        ]

    def __str__(self) -> str:
        return f"Certificate {self.certificate_number} — {self.student}"

    def save(self, *args, **kwargs) -> None:
        if not self.certificate_number:
            self.certificate_number = Certificate._generate_number()
        super().save(*args, **kwargs)

    @staticmethod
    def _generate_number() -> str:
        """
        Generate a unique certificate number: LMS-YYYY-NNNNNN.

        Uses DB sequence (PostgreSQL) or atomic counter (SQLite fallback)
        to guarantee uniqueness under concurrency.
        """
        from datetime import date
        from django.db import connection, transaction
        from django.db.models import F

        year = date.today().year
        prefix = f"LMS-{year}-"

        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                # The sequence is installed by migration 0004. Schema changes
                # must never be attempted after a failed query in a transaction.
                cursor.execute("SELECT nextval('cert_number_seq')")
                seq = cursor.fetchone()[0]  # type: ignore[index]
        else:
            # An atomic database increment survives certificate deletion and
            # cannot hand the same number to concurrent issuers.
            with transaction.atomic():
                counter, _ = CertificateNumberCounter.objects.get_or_create(year=year)
                CertificateNumberCounter.objects.filter(year=year).update(
                    last_value=F("last_value") + 1,
                )
                counter.refresh_from_db(fields=["last_value"])
                seq = counter.last_value

        return f"{prefix}{seq:06d}"


class CertificateNumberCounter(models.Model):
    year = models.PositiveSmallIntegerField(primary_key=True)
    last_value = models.PositiveBigIntegerField(default=0)
