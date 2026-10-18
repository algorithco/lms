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
        help_text=_("Rasmiy hisobot sarlavhasi, masalan 'GRAND EDUCATION Hamkor Markazi'"),
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
            while LearningCenter.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
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
    O'quv markazining filiali (masalan: Chilonzor, Yunusobod).
    """

    center = models.ForeignKey(
        LearningCenter,
        on_delete=models.CASCADE,
        related_name="branches",
        verbose_name=_("O'quv markazi"),
    )
    name = models.CharField(_("Filial nomi"), max_length=150)
    phone = models.CharField(_("Filial telefoni"), max_length=25, blank=True)
    address = models.CharField(_("Filial manzili"), max_length=255, blank=True)
    created_at = models.DateTimeField(_("Yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Filial")
        verbose_name_plural = _("Filiallar")
        ordering = ["center", "name"]
        unique_together = ("center", "name")

    def __str__(self) -> str:
        return f"{self.center.name} - {self.name}"
