"""
Speaking app models — IELTS & Multi-level AI Speaking Simulator.

Models:
    SpeakingTopic       — Part 1, Part 2 (Cue Card), Part 3 discussion topics
    SpeakingSubmission  — Audio recording, transcript, 4 criteria scores & AI feedback
"""

from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class SpeakingTopic(models.Model):
    class PartChoice(models.TextChoices):
        PART1 = "part1", _("Part 1: Introduction & Short Questions")
        PART2 = "part2", _("Part 2: Cue Card (Long Turn)")
        PART3 = "part3", _("Part 3: Two-way Discussion")
        MULTILEVEL = "multilevel", _("Multi-level Speaking (CEFR B1–C1)")

    class Difficulty(models.TextChoices):
        EASY = "easy", _("Oson (Band 5.5 - 6.0)")
        MEDIUM = "medium", _("O'rta (Band 6.5 - 7.0)")
        HARD = "hard", _("Yuqori (Band 7.5 - 8.5)")

    title = models.CharField(_("Mavzu sarlavhasi"), max_length=255)
    subject = models.CharField(
        _("Fan"),
        max_length=20,
        default="english",
        choices=[("english", _("Ingliz tili (IELTS & Multi-level)"))],
        db_index=True,
    )
    part = models.CharField(
        _("Imtihon bo'limi"),
        max_length=20,
        choices=PartChoice.choices,
        default=PartChoice.PART2,
        db_index=True,
    )
    prompt = models.TextField(
        _("Savol / Cue Card yo'riqnomasi"),
        help_text=_(
            "Masalan: Describe a book you have recently read that had a strong impact on you."
        ),
    )
    bullet_points = models.JSONField(
        _("Cue Card reja bandlari"),
        default=list,
        blank=True,
        help_text=_("Part 2 uchun 'You should say:' bandlari ro'yxati."),
    )
    follow_up_questions = models.JSONField(
        _("Qo'shimcha savollar"),
        default=list,
        blank=True,
        help_text=_("Part 3 munozara yoki Part 1 qo'shimcha savollari."),
    )
    prep_time_seconds = models.PositiveIntegerField(
        _("Tayyorgarlik vaqti (soniya)"),
        default=60,
        help_text=_("Part 2 uchun standart 60 soniya (1 daqiqa)."),
    )
    speak_time_seconds = models.PositiveIntegerField(
        _("Nutq so'zlash vaqti (soniya)"),
        default=120,
        help_text=_("Standart 120 soniya (2 daqiqa)."),
    )
    difficulty = models.CharField(
        _("Qiyinlik darajasi"),
        max_length=20,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
    )
    is_active = models.BooleanField(_("Faolmi"), default=True)
    created_at = models.DateTimeField(_("Yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Speaking mavzusi")
        verbose_name_plural = _("Speaking mavzulari")
        ordering = ["part", "-created_at"]

    def __str__(self) -> str:
        return f"[{self.get_part_display()}] {self.title}"


class SpeakingSubmission(models.Model):
    class Status(models.TextChoices):
        EVALUATING = "evaluating", _("Baholanmoqda")
        COMPLETED = "completed", _("Yakunlandi")
        ERROR = "error", _("Xatolik yuz berdi")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="speaking_submissions",
        verbose_name=_("Foydalanuvchi"),
    )
    topic = models.ForeignKey(
        SpeakingTopic,
        on_delete=models.CASCADE,
        related_name="submissions",
        verbose_name=_("Speaking mavzusi"),
    )
    audio_file = models.FileField(
        _("Ovoz yozuvi"),
        upload_to="speaking/audio/%Y/%m/",
        blank=True,
        null=True,
    )
    duration_seconds = models.PositiveIntegerField(_("Davomiyligi (soniya)"), default=0)
    transcript = models.TextField(_("Ovoz matni (Transcript)"), blank=True, default="")

    # 4 Official IELTS Evaluation Criteria (0.0 to 9.0)
    fluency_score = models.DecimalField(
        _("Fluency and Coherence (FC)"),
        max_digits=3,
        decimal_places=1,
        default=Decimal("0.0"),
    )
    lexical_score = models.DecimalField(
        _("Lexical Resource (LR)"),
        max_digits=3,
        decimal_places=1,
        default=Decimal("0.0"),
    )
    grammar_score = models.DecimalField(
        _("Grammatical Range and Accuracy (GRA)"),
        max_digits=3,
        decimal_places=1,
        default=Decimal("0.0"),
    )
    pronunciation_score = models.DecimalField(
        _("Pronunciation (PR)"),
        max_digits=3,
        decimal_places=1,
        default=Decimal("0.0"),
    )
    overall_band = models.DecimalField(
        _("Umumiy IELTS Band"),
        max_digits=3,
        decimal_places=1,
        default=Decimal("0.0"),
    )

    feedback = models.JSONField(
        _("AI Tahlili va tavsiyalari"),
        default=dict,
        blank=True,
        help_text=_(
            "Strengths, weaknesses, vocabulary improvements, grammar corrections."
        ),
    )
    status = models.CharField(
        _("Holat"),
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
        db_index=True,
    )
    created_at = models.DateTimeField(_("Yuborilgan vaqt"), auto_now_add=True)

    class Meta:
        verbose_name = _("Speaking topshirig'i")
        verbose_name_plural = _("Speaking topshiriqlari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Speaking #{self.pk} - {self.user} ({self.overall_band} Band)"
