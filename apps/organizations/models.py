"""
Organizations app — LearningCenter and CenterBranch models for B2B SaaS.
"""

from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


class LearningCenter(models.Model):
    """
    O'quv markazi (B2B SaaS / Enterprise Organization).
    Har bir markaz o'z filiallari, o'qituvchilari va o'quvchilariga ega.
    """

    name = models.CharField(_("Markaz nomi"), max_length=200)
    slug = models.SlugField(_("Slug"), max_length=220, unique=True, db_index=True)
    logo = models.ImageField(
        _("Logotip"),
        upload_to="centers/logos/%Y/%m/",
        blank=True,
        null=True,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_centers",
        verbose_name=_("Markaz rahbari / Direktori"),
    )
    student_seat_limit = models.PositiveIntegerField(
        _("Sotib olingan o'quvchi o'rinlari"),
        default=50,
        help_text=_("Markaz tizimga qo'sha oladigan maksimal o'quvchilar soni."),
    )
    subscription_expires_at = models.DateTimeField(
        _("Obuna tugash muddati"),
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(_("Faolmi"), default=True)
    phone = models.CharField(_("Aloqa telefoni"), max_length=25, blank=True)
    address = models.CharField(_("Manzil"), max_length=255, blank=True)
    stamp_signature = models.ImageField(
        _("Muhr / Imzo tasviri"),
        upload_to="centers/stamps/%Y/%m/",
        blank=True,
        null=True,
        help_text=_("PDF hisobot va sertifikatlarga qo'yiladigan shaffof muhr/imzo."),
    )
    brand_color = models.CharField(
        _("Brend rangi"),
        max_length=20,
        default="#0F766E",
        help_text=_("HEX rang kodi, masalan #0F766E"),
    )
    header_title = models.CharField(
        _("Hisobot sarlavhasi"),
        max_length=200,
        blank=True,
        default="",
        help_text=_(
            "Rasmiy hisobot sarlavhasi, masalan 'GRAND EDUCATION Hamkor Markazi'"
        ),
    )
    created_at = models.DateTimeField(_("Yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("O'quv markazi")
        verbose_name_plural = _("O'quv markazlari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "center"
            candidate = base_slug
            idx = 1
            while (
                LearningCenter.objects.filter(slug=candidate)
                .exclude(pk=self.pk)
                .exists()
            ):
                candidate = f"{base_slug}-{idx}"
                idx += 1
            self.slug = candidate
        super().save(*args, **kwargs)

    @property
    def total_students_count(self) -> int:
        return self.users.filter(role="student").count()

    @property
    def remaining_seats(self) -> int:
        used = self.total_students_count
        return max(0, self.student_seat_limit - used)


class CenterBranch(models.Model):
    """
    O'quv markazining filiali / Kursxona (masalan: Samarqand Markaziy Filiali, Registon Kursxonasi).
    """

    center = models.ForeignKey(
        LearningCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="branches",
        verbose_name=_("O'quv markazi"),
    )
    name = models.CharField(_("Filial / Kursxona nomi"), max_length=150)
    slug = models.SlugField(_("Slug"), max_length=160, blank=True, db_index=True)
    branch_code = models.CharField(
        _("Filial kodi"),
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Masalan: SAM-01, REG-01, TAS-02"),
    )
    region = models.CharField(_("Hudud / Viloyat"), max_length=100, blank=True, default="")
    phone = models.CharField(_("Filial telefoni"), max_length=25, blank=True)
    address = models.CharField(_("Filial manzili"), max_length=255, blank=True)
    telegram_channel = models.CharField(_("Telegram kanal / guruh"), max_length=120, blank=True, default="")
    director = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="directed_branches",
        verbose_name=_("Filial rahbari / Kursxona direktori"),
    )
    subjects_offered = models.JSONField(
        _("O'qitiladigan fanlar"),
        default=list,
        blank=True,
        help_text=_("Ro'yxat: uzbek, english, biology, chemistry, law"),
    )
    max_teachers_limit = models.PositiveIntegerField(
        _("Maksimal ustozlar limiti"),
        default=20,
    )
    max_students_limit = models.PositiveIntegerField(
        _("Maksimal o'quvchilar limiti"),
        default=500,
    )
    is_active = models.BooleanField(_("Faolmi"), default=True)
    created_at = models.DateTimeField(_("Yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Filial / Kursxona")
        verbose_name_plural = _("Filiallar / Kursxonalar")
        ordering = ["name"]

    def __str__(self) -> str:
        if self.center:
            return f"{self.center.name} - {self.name}"
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "branch"
            candidate = base_slug
            idx = 1
            while CenterBranch.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base_slug}-{idx}"
                idx += 1
            self.slug = candidate

        if not self.branch_code:
            import secrets
            prefix = (self.slug[:3] or "BR").upper()
            candidate = f"{prefix}-{secrets.token_hex(2).upper()}"
            while CenterBranch.objects.filter(branch_code=candidate).exclude(pk=self.pk).exists():
                candidate = f"{prefix}-{secrets.token_hex(2).upper()}"
            self.branch_code = candidate

        if not self.subjects_offered:
            self.subjects_offered = ["uzbek", "english", "biology", "chemistry", "law"]

        super().save(*args, **kwargs)

    @property
    def teachers_count(self) -> int:
        return self.users.filter(role="teacher", is_active=True).count()

    @property
    def students_count(self) -> int:
        return self.users.filter(role="student", is_active=True).count()

    @property
    def groups_count(self) -> int:
        return self.groups.count()

    @property
    def avg_performance(self) -> float:
        student_ids = list(self.users.filter(role="student").values_list("id", flat=True))
        if not student_ids:
            return 0.0
        from apps.results.models import Result
        agg = Result.objects.filter(student_id__in=student_ids).aggregate(models.Avg("percentage"))
        return round(float(agg["percentage__avg"] or 0.0), 1)


# Alias for convenience
Branch = CenterBranch

