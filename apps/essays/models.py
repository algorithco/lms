"""
Essays app — Ona tili Esse Tekshirish va Ustoz Nazorati.

Models:
    EssayTopic          — mavzu tanlash (title, word limits, time limit)
    EssaySubmission     — esse matni, holat (DRAFT → GRADED → PENDING_TEACHER → TEACHER_REVIEWED)
    EssayCriterionScore — 12-mezon baholash (har biri max 2 ball, jami 24)
    EssayGradingCache   — LLM baholash keshi (determinizm uchun)
    AIEvaluation        — Legacy AI bahosi (eski BMB 30-ballik, backward compat)
    TeacherReview       — ustoz bahosi (12-mezon, 24 ball)

12-Mezon Baholash Shkalasi (24 ball):
    Har bir mezon: 0 / 0.5 / 1 / 1.5 / 2 ball
    Jami: 12 × 2 = 24 ball
"""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


# Valid criterion IDs for the 12-mezon grading rubric
VALID_CRITERION_IDS = set(range(1, 13))  # {1, 2, ..., 12}


# ---------------------------------------------------------------------------
# EssayTopic  (essay writing topics)
# ---------------------------------------------------------------------------

class EssayTopic(models.Model):
    """
    A writing topic/prompt for essays.

    Teachers create topics; students choose one and write an essay.
    """

    class Category(models.TextChoices):
        ONA_TILI = "ona_tili", _("Ona tili")
        ADABIYOT = "adabiyot", _("Adabiyot")
        TARIX = "tarix", _("Tarix")
        UMUMIY = "umumiy", _("Umumiy")

    title = models.CharField(_("sarlavha"), max_length=300)
    description = models.TextField(
        _("tavsif / ko'rsatma"),
        help_text=_("O'quvchiga esse yozish uchun ko'rsatma."),
    )
    category = models.CharField(
        _("kategoriya"),
        max_length=20,
        choices=Category.choices,
        default=Category.ONA_TILI,
    )
    word_limit_min = models.PositiveIntegerField(
        _("minimal so'zlar soni"),
        default=150,
    )
    word_limit_max = models.PositiveIntegerField(
        _("maksimal so'zlar soni"),
        default=500,
    )
    time_limit_minutes = models.PositiveIntegerField(
        _("vaqt cheklovi (daqiqa)"),
        default=60,
    )
    sample_outline = models.TextField(
        _("namuna reja (outline)"),
        blank=True,
        help_text=_("O'quvchiga ko'rsatiladigan namunaviy reja/kirish-ma'no-xulosa struktura."),
    )
    grammar_strictness = models.PositiveSmallIntegerField(
        _("grammatika talabchanligi (%)"),
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_("AI baholashda grammatika mezonining talabchanlik darajasi."),
    )
    national_cert_scale = models.BooleanField(
        _("Milliy sertifikat shkalasi"),
        default=False,
        help_text=_("Yoqilganda — Milliy sertifikat ball shkalasi bo'yicha baholanadi."),
    )
    password = models.CharField(
        _("parol"),
        max_length=128,
        blank=True,
        default="",
        help_text=_("O'quvchi esse yozishni boshlash uchun kiritishi kerak bo'lgan parol. Bo'sh = parolsiz."),
    )
    is_active = models.BooleanField(_("faolmi"), default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_essay_topics",
        verbose_name=_("yaratgan o'qituvchi"),
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Esse mavzusi")
        verbose_name_plural = _("Esse mavzulari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        """Parolni hash qilib saqlash (agar yangi qo'shilgan bo'lsa)."""
        if self.password and not self.password.startswith(("pbkdf2_", "argon2", "bcrypt", "sha256")):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def check_password(self, raw_password: str) -> bool:
        """Parolni tekshirish (oddiy matn vs hash)."""
        if not self.password:
            return True  # parol o'rnatilmagan = har doim to'g'ri
        return check_password(raw_password, self.password)


# ---------------------------------------------------------------------------
# EssaySubmission  (student essay)
# ---------------------------------------------------------------------------

class EssaySubmission(models.Model):
    """
    A student's essay submission.

    Lifecycle:
        1. DRAFT          — o'quvchi yozmoqda (autosave)
        2. AI_EVALUATED   — AI tomonidan baholandi
        3. PENDING_TEACHER — o'quvchi ustoz tekshiruvini so'radi
        4. TEACHER_REVIEWED — ustoz yakuniy bahoni qo'ydi
    """

    class Status(models.TextChoices):
        DRAFT = "draft", _("Qoralama")
        PENDING = "pending", _("Baholanmoqda")
        GRADED = "graded", _("Baholandi")
        ERROR = "error", _("Xatolik")
        # Legacy statuses (kept for backward compatibility)
        AI_EVALUATED = "ai_evaluated", _("AI baholadi")
        PENDING_TEACHER = "pending_teacher", _("Ustoz tekshirishi kutilmoqda")
        TEACHER_REVIEWED = "teacher_reviewed", _("Ustoz bahosi tayyor")

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="essay_submissions",
        verbose_name=_("o'quvchi"),
    )
    topic = models.ForeignKey(
        EssayTopic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
        verbose_name=_("esse mavzusi"),
    )
    essay_text = models.TextField(
        _("esse matni"),
        blank=True,
        default="",
    )
    word_count = models.PositiveIntegerField(_("so'zlar soni"), default=0)
    status = models.CharField(
        _("holat"),
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )

    # -- Grading results (12-mezon system) ----------------------------------
    raw_result = models.JSONField(
        _("xom AI natijasi (JSON)"),
        default=dict,
        blank=True,
        help_text=_("LLM dan kelgan to'liq JSON javob."),
    )
    total_score = models.DecimalField(
        _("umumiy ball"),
        max_digits=4,
        decimal_places=1,
        default=0,
    )
    max_score = models.PositiveSmallIntegerField(
        _("maksimal ball"),
        default=24,
    )
    summary = models.TextField(
        _("xulosa"),
        blank=True,
        default="",
    )
    error_message = models.TextField(
        _("xatolik xabari"),
        blank=True,
        default="",
    )
    is_off_topic = models.BooleanField(
        _("mavzudan chetda"),
        default=False,
        help_text=_("Essa berilgan mavzuga mos yozilmaganmi."),
    )
    topic_match_reason = models.TextField(
        _("mavzu moslik sababi"),
        blank=True,
        default="",
        help_text=_("LLM tomonidan berilgan izoh: nega mos yoki mos emas."),
    )

    # -- Teacher Review Request (student-initiated) -------------------------
    teacher_review_requested = models.BooleanField(
        _("ustoz tekshiruvi so'ralgan"),
        default=False,
        help_text=_("O'quvchi AI bahosiga rozi bo'lmadi va ustozdan tekshirishni so'radi."),
    )
    teacher_review_requested_at = models.DateTimeField(
        _("tekshirish so'ralgan vaqt"),
        null=True,
        blank=True,
    )
    teacher_review_reason = models.TextField(
        _("tekshirish so'rab sabab"),
        blank=True,
        default="",
        help_text=_("O'quvchi nima uchun AI bahosiga rozi emasligini yozgan."),
    )

    # -- Assigned Reviewer (escalation) -------------------------------------
    assigned_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_essay_reviews",
        verbose_name=_("tayinlangan tekshiruvchi"),
        help_text=_("Guruh o'qituvchisi yoki admin — avtomatik tayinlanadi."),
    )

    # -- Final Score (teacher override) --------------------------------------
    final_score = models.DecimalField(
        _("o'qituvchi yakuniy bali"),
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
        help_text=_("O'qituvchi tomonidan tasdiqlangan yakuniy ball (agar mavjud bo'lsa)."),
    )

    graded_at = models.DateTimeField(
        _("baholangan"),
        null=True,
        blank=True,
    )

    # -- Auto-submit --------------------------------------------------------
    auto_submitted = models.BooleanField(
        _("avtomatik yuborilgan"),
        default=False,
        help_text=_("Vaqt tugagani sababli avtomatik yuborilganmi."),
    )

    # -- AI Improved Version -------------------------------------------------
    improved_content = models.TextField(
        _("AI yaxshilangan versiya"),
        blank=True,
        default="",
        help_text=_(
            "AI tomonidan yaratilgan yaxshilangan esse versiyasi "
            "(qayta yaratilishining oldini olish uchun saqlanadi)."
        ),
    )
    improved_at = models.DateTimeField(
        _("yaxshilangan vaqti"),
        null=True,
        blank=True,
    )

    # -- Timestamps ---------------------------------------------------------
    password_verified_at = models.DateTimeField(
        _("parol tasdiqlangan"),
        null=True,
        blank=True,
        help_text=_("Parol to'g'ri kiritilgan vaqt. Taymer shu paytdan boshlanadi."),
    )
    submitted_at = models.DateTimeField(_("topshirilgan"), null=True, blank=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Esse topshirish")
        verbose_name_plural = _("Esse topshirishlar")
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["student", "status"], name="idx_essay_stu_status"),
            models.Index(fields=["topic", "status"], name="idx_essay_topic_status"),
            # Celery beat auto-submit scan (runs every 2 minutes)
            models.Index(
                fields=["status", "auto_submitted", "password_verified_at"],
                name="idx_essay_auto_submit",
            ),
        ]

    def __str__(self) -> str:
        topic_title = self.topic.title if self.topic else "(no topic)"
        return f"{self.student} — {topic_title} [{self.get_status_display()}]"

    @property
    def score_percentage(self) -> float:
        """Ball foizi (0-100) — effective_score (final_score yoki total_score) asosida."""
        score = self.effective_score
        if score is None or self.max_score == 0:
            return 0.0
        return round(float(score) / self.max_score * 100, 1)

    @property
    def is_passed(self) -> bool:
        """60% dan yuqori ball olganmi."""
        return self.score_percentage >= 60.0

    @property
    def effective_score(self) -> Decimal | None:
        """Foydalanilishi kerak bo'lgan ball: o'qituvchi bali (agar bor) yoki AI bali."""
        if self.final_score is not None:
            return self.final_score
        return self.total_score if self.total_score else None

    @property
    def converted_score(self):
        """Xom ballni umumiy shkalaga (default 75) o'girish.

        Tartibi:
            1. O'qituvchi bali (final_score) — agar tasdiqlangan bo'lsa
            2. Mavzudan chetga chiqish — ESSAY_OFF_TOPIC_SCORE (35)
            3. AI bali (total_score) — odatdagi hisob
        Formula: score / max_score * TARGET_SCALE
        """
        # 1. Teacher's final score takes priority
        if self.final_score is not None:
            if not self.max_score:
                return None
            target = getattr(settings, "ESSAY_TARGET_SCALE", 75)
            return round(float(self.final_score) / self.max_score * target)
        # 2. Off-topic override
        if self.is_off_topic:
            return getattr(settings, "ESSAY_OFF_TOPIC_SCORE", 35)
        # 3. Standard AI score
        if self.total_score is None or not self.max_score:
            return None
        target = getattr(settings, "ESSAY_TARGET_SCALE", 75)
        return round(float(self.total_score) / self.max_score * target)

    @property
    def remaining_seconds(self) -> int:
        """Qolgan vaqt (soniyalarda) — server-side hisob. Manfiy bo'lsa = vaqt tugagan."""
        from django.utils import timezone as tz
        if not self.password_verified_at:
            return self.topic.time_limit_minutes * 60 if self.topic else 0
        elapsed = (tz.now() - self.password_verified_at).total_seconds()
        limit = self.topic.time_limit_minutes * 60 if self.topic else 3600
        return max(0, int(limit - elapsed))

    @property
    def is_expired(self) -> bool:
        """Vaqt tugaganmi (server-side)."""
        return self.remaining_seconds <= 0

    @property
    def is_within_word_limit(self) -> bool:
        """So'zlar soni chegarada ekanligini tekshirish."""
        if not self.topic:
            return True
        return self.topic.word_limit_min <= self.word_count <= self.topic.word_limit_max

    @property
    def word_status(self) -> str:
        """So'zlar soni holati."""
        if not self.topic:
            return "ok"
        if self.word_count < self.topic.word_limit_min:
            return "under"
        elif self.word_count > self.topic.word_limit_max:
            return "over"
        return "ok"


# ---------------------------------------------------------------------------
# AIEvaluation  (AI pre-grading results)
# ---------------------------------------------------------------------------

class AIEvaluation(models.Model):
    """
    AI-generated evaluation of an essay.

    Stores BMB criteria scores and detected errors in JSON format.

    criteria_scores format:
    {
        "topic_coverage": 8,        // Mavzuning yoritilishi (max 10)
        "argumentation": 6,         // Dalillash va asoslash (max 8)
        "grammar_spelling": 7,      // Grammatika, orfografiya (max 8)
        "style_vocabulary": 3,      // Uslub va lug'at (max 4)
        "total": 24,
        "max_total": 30,
        "percentage": 80.0
    }

    detected_errors format:
    [
        {"type": "spelling", "word": "xatolik", "suggestion": "xato", "line": 3},
        {"type": "grammar", "text": "...", "suggestion": "...", "line": 5},
        {"type": "punctuation", "text": "...", "suggestion": "...", "line": 7}
    ]
    """
    submission = models.OneToOneField(
        EssaySubmission,
        on_delete=models.CASCADE,
        related_name="ai_evaluation",
        verbose_name=_("esse topshirish"),
    )
    criteria_scores = models.JSONField(
        _("mezon bo'yicha ballar (JSON)"),
        default=dict,
        help_text=_("BMB mezonlari bo'yicha ballar."),
    )
    total_score = models.DecimalField(
        _("umumiy ball"),
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(30)],
    )
    detected_errors = models.JSONField(
        _("aniqlangan xatolar (JSON)"),
        default=list,
    )
    feedback_text = models.TextField(
        _("AI feedback"),
        blank=True,
        default="",
        help_text=_("AI tomonidan berilgan umumiy tahlil va tavsiyalar."),
    )
    model_used = models.CharField(
        _("AI model"),
        max_length=50,
        default="gpt-4o-mini",
        blank=True,
    )
    evaluated_at = models.DateTimeField(_("baholangan"), auto_now_add=True)

    class Meta:
        verbose_name = _("AI bahosi")
        verbose_name_plural = _("AI baholari")

    def __str__(self) -> str:
        return f"AI: {self.submission} — {self.total_score}/30"


# ---------------------------------------------------------------------------
# TeacherReview  (human review)
# ---------------------------------------------------------------------------

class TeacherReview(models.Model):
    """
    Teacher's final review and scoring.

    The teacher can:
        - Accept or modify AI scores
        - Add their own feedback
        - Override the final grade
    """
    submission = models.OneToOneField(
        EssaySubmission,
        on_delete=models.CASCADE,
        related_name="teacher_review",
        verbose_name=_("esse topshirish"),
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="essay_reviews",
        verbose_name=_("tekshirgan o'qituvchi"),
    )
    criteria_scores = models.JSONField(
        _("ustoz mezon ballari (JSON)"),
        default=dict,
        help_text=_("O'qituvchi tomonidan belgilangan ballar."),
    )
    final_score = models.DecimalField(
        _("yakuniy ball"),
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(24)],
    )
    teacher_comments = models.TextField(
        _("ustoz izohi"),
        blank=True,
        default="",
    )
    reviewed_at = models.DateTimeField(_("tekshirilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Ustoz bahosi")
        verbose_name_plural = _("Ustoz baholari")

    def __str__(self) -> str:
        return f"{self.teacher}: {self.submission} — {self.final_score}/24"


# ---------------------------------------------------------------------------
# EssayCriterionScore  (12-mezon grading rubric)
# ---------------------------------------------------------------------------

class EssayGradingCache(models.Model):
    """
    Cache for essay grading results.

    Stores the LLM grading result keyed by SHA-256 hash of the essay text.
    Ensures deterministic grading: same text always returns the same result.
    """
    text_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name=_("matn hash"),
        help_text=_("SHA-256 hash of normalized essay text."),
    )
    essay_text = models.TextField(
        verbose_name=_("esse matni"),
        help_text=_("Audit/debug uchun saqlanadi."),
    )
    raw_result = models.JSONField(
        verbose_name=_("xom AI natijasi (JSON)"),
    )
    total_score = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        verbose_name=_("umumiy ball"),
    )
    max_score = models.PositiveSmallIntegerField(
        verbose_name=_("maksimal ball"),
    )
    hit_count = models.PositiveIntegerField(
        default=1,
        verbose_name=_("ishlatilgan soni"),
        help_text=_("Necha marta keshdan foydalanilgani."),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("yaratilgan"),
    )
    last_used_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("oxirgi ishlatilgan"),
    )

    class Meta:
        verbose_name = _("Baholash keshi")
        verbose_name_plural = _("Baholash keshlari")
        ordering = ["-hit_count", "-last_used_at"]

    def __str__(self) -> str:
        return f"Cache {self.text_hash[:12]}… — {self.total_score}/{self.max_score} (×{self.hit_count})"

    @property
    def short_hash(self) -> str:
        """Hashning qisqartirilgan ko'rinishi (birinchi 12 belgi)."""
        return self.text_hash[:12]


# ---------------------------------------------------------------------------
# Valid criterion IDs for the 12-mezon grading rubric
# ---------------------------------------------------------------------------
VALID_CRITERION_IDS = set(range(1, 13))  # {1, 2, ..., 12}


class EssayCriterionScore(models.Model):
    """
    Individual criterion score for the 12-mezon grading rubric.

    Each essay submission can have up to 12 criterion scores,
    each scored on a {0, 0.5, 1, 1.5, 2} scale (max 2 points each).
    Total max score: 12 × 2 = 24.
    """
    CRITERION_NAMES = {
        1: "Uslub",
        2: "Ikkala qarash va shaxsiy fikr",
        3: "Dalillar bilan asoslanganlik",
        4: "Kirish/asosiy qism/xulosa",
        5: "Mantiqiy-qurilish",
        6: "Mantiqiy-mazmuniy izchillik",
        7: "Imlo xatolari",
        8: "Punktuatsiya xatolari",
        9: "Qo'shimcha qo'llash xatolari",
        10: "So'z qo'llash uslubiy xatolari",
        11: "Leksik xilma-xillik",
        12: "Sheva/vulgarizm/parazit so'zlar",
    }

    VALID_SCORES = {0, 0.5, 1, 1.5, 2}

    submission = models.ForeignKey(
        EssaySubmission,
        on_delete=models.CASCADE,
        related_name="criteria",
        verbose_name=_("esse topshirish"),
    )
    criterion_id = models.PositiveSmallIntegerField(
        _("mezon raqami"),
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text=_("Mezon raqami (1-12)."),
    )
    name = models.CharField(
        _("mezon nomi"),
        max_length=100,
    )
    score = models.DecimalField(
        _("ball"),
        max_digits=3,
        decimal_places=1,
        validators=[MinValueValidator(0), MaxValueValidator(2)],
    )
    reason = models.TextField(
        _("izoh"),
        blank=True,
        default="",
    )

    class Meta:
        verbose_name = _("Mezon bali")
        verbose_name_plural = _("Mezon ballari")
        ordering = ["criterion_id"]
        unique_together = ("submission", "criterion_id")
        indexes = [
            models.Index(
                fields=["submission", "criterion_id"],
                name="idx_crit_sub_criterion",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name}: {self.score}/2"

    def clean(self):
        """Validate score is in allowed set {0, 0.5, 1, 1.5, 2}."""
        from django.core.exceptions import ValidationError
        if self.score not in self.VALID_SCORES:
            raise ValidationError(
                f"Ball {self.score} yaroqsiz. Ruxsat etilgan ballar: {self.VALID_SCORES}"
            )
