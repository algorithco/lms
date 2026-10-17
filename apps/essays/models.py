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
from django.contrib.auth.hashers import check_password, identify_hasher, make_password
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# Valid criterion IDs for the 12-mezon grading rubric
VALID_CRITERION_IDS = set(range(1, 13))  # {1, 2, ..., 12}


def is_password_hashed(value: str) -> bool:
    """True when `value` already looks like a Django password hash.

    Uses identify_hasher() so every configured hasher (pbkdf2, argon2,
    bcrypt, scrypt — and md5 in the test settings) is recognized. A plain
    new password never parses as a hash, so it gets hashed on save.
    """
    try:
        identify_hasher(value)
    except ValueError:
        return False
    return True


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
        default=200,
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
        indexes = [
            models.Index(fields=["is_active"], name="idx_essaytopic_active"),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs):
        """Parolni hash qilib saqlash (agar yangi qo'shilgan bo'lsa)."""
        if self.password and not is_password_hashed(self.password):
            self.password = make_password(self.password)
        super().save(*args, **kwargs)

    def check_password(self, raw_password: str) -> bool:
        """Parolni tekshirish (oddiy matn vs hash)."""
        if not self.password:
            return True  # parol o'rnatilmagan = har doim to'g'ri
        return check_password(raw_password, self.password)


# ---------------------------------------------------------------------------
# EssayAssignment  (teacher assigns a topic to one group)
# ---------------------------------------------------------------------------

class EssayAssignment(models.Model):
    """An explicit teacher→group assignment of an essay topic.

    Group-essay reporting must NOT be inferred from mere group membership: a
    student can belong to several groups, and an essay written for one group
    is not automatically "for" the others. This row is the explicit context a
    submission attaches to, and it is also what makes "not submitted yet"
    counts meaningful (expected roster minus submissions).
    """

    topic = models.ForeignKey(
        EssayTopic,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name=_("esse mavzusi"),
    )
    group = models.ForeignKey(
        "courses.StudentGroup",
        on_delete=models.CASCADE,
        related_name="essay_assignments",
        verbose_name=_("guruh"),
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="essay_assignments",
        verbose_name=_("tayinlagan o'qituvchi"),
    )
    due_at = models.DateTimeField(_("muddat"), null=True, blank=True)
    instructions = models.TextField(_("qo'shimcha ko'rsatma"), blank=True)
    is_active = models.BooleanField(_("faolmi"), default=True)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Esse topshirig'i")
        verbose_name_plural = _("Esse topshiriqlari")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["topic", "group"],
                name="uniq_essay_assignment_topic_group",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.topic_id} → group {self.group_id}"

    def expected_students(self):
        """Current roster of the assigned group (membership is live)."""
        return self.group.students.filter(is_active=True, role="student")


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

    # Central status-transition policy (single source of truth).
    # Every status change must go through transition_to() or an atomic
    # conditional update honouring this map — never assign .status blindly.
    STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
        Status.DRAFT: frozenset({Status.PENDING, Status.PENDING_TEACHER, Status.GRADED, Status.ERROR}),
        Status.PENDING: frozenset({
            Status.GRADED, Status.ERROR, Status.PENDING_TEACHER,
        }),
        Status.ERROR: frozenset({Status.DRAFT}),
        Status.PENDING_TEACHER: frozenset({
            Status.DRAFT, Status.TEACHER_REVIEWED,
        }),
        Status.GRADED: frozenset({
            Status.PENDING_TEACHER, Status.TEACHER_REVIEWED,
        }),
        Status.AI_EVALUATED: frozenset({
            Status.PENDING_TEACHER, Status.TEACHER_REVIEWED,
        }),
        Status.TEACHER_REVIEWED: frozenset(),
    }

    def transition_to(self, new_status: str) -> None:
        """Validate and assign a new status (caller still saves).

        Raises:
            ValueError: when the transition is not in STATUS_TRANSITIONS.
        """
        allowed = self.STATUS_TRANSITIONS.get(self.status, frozenset())
        if new_status not in allowed:
            raise ValueError(
                f"Esse holatini {self.status!r} dan {new_status!r} ga "
                f"o'tkazib bo'lmaydi."
            )
        self.status = new_status

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
    grading_started_at = models.DateTimeField(
        _("AI baholash boshlangan vaqt"),
        null=True,
        blank=True,
        db_index=True,
        help_text=_(
            "AI grading dispatch vaqti. PENDING holati cheksiz qolmasligi "
            "uchun ishlatiladi."
        ),
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

    # -- AI Grading provenance (shared cache) --------------------------------
    class GradingSource(models.TextChoices):
        AI = "ai", _("AI baholash")
        CACHE = "cache", _("Saqlangan AI baholash natijasi")
        MOCK = "mock", _("Sinov rejimi (AI emas)")

    class CacheScope(models.TextChoices):
        """Assessment policy for cross-account grade reuse.

        Only ``PRACTICE`` is cacheable by default; supervised/restricted/
        official assessments are graded per student and never share a grade.
        """

        PRACTICE = "practice", _("Amaliy topshiriq")
        EXAM = "exam", _("Nazorat/eksamen")
        HIGH_STAKES = "high_stakes", _("Yuqori ahamiyatli (Milliy Sertifikat)")

    class Source(models.TextChoices):
        """Which channel created the submission (for teacher reporting)."""

        WEB = "web", _("Veb-sayt")
        TELEGRAM = "telegram", _("Telegram bot")
        TMA = "tma", _("Telegram Mini App")
        EXAM = "exam", _("Milliy imtihon ko'prigi")

    class GroupVisibility(models.TextChoices):
        """Whether a submission may appear in a teacher's group report.

        ``ASSIGNMENT_ONLY`` is the default and the privacy-safe choice: a
        submission shows up only through an explicit
        :class:`EssayAssignment`. ``GROUP_VISIBLE`` is an explicit opt-in for
        general essays the student wants their teacher groups to see.
        """

        ASSIGNMENT_ONLY = "assignment_only", _("Faqat tayinlangan topshiriq")
        GROUP_VISIBLE = "group_visible", _("Guruhga ko'rinadi")
        PRIVATE = "private", _("Maxfiy (guruhga ko'rinmaydi)")

    grading_source = models.CharField(
        _("baholash manbasi"),
        max_length=16,
        choices=GradingSource.choices,
        default=GradingSource.AI,
        help_text=_(
            "Baholash qanday olindi: haqiqiy AI javobi, umumiy keshlangan "
            "natija yoki sinov rejimi."
        ),
    )
    grading_cache_key = models.CharField(
        _("baholash kesh kaliti"),
        max_length=64,
        blank=True,
        default="",
        help_text=_(
            "Baholash konteksti bo'yicha kesh kaliti (foydalanuvchiga "
            "ko'rsatilmaydi). Kutayotgan submissionlarni topish uchun."
        ),
    )
    grading_cache = models.ForeignKey(
        "EssayGradingCache",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reusing_submissions",
        verbose_name=_("ishlatilgan kesh yozuvi"),
        help_text=_("Qayta ishlatilgan umumiy AI baholash natijasi."),
    )
    cache_scope = models.CharField(
        _("baholash siyosati"),
        max_length=16,
        choices=CacheScope.choices,
        default=CacheScope.PRACTICE,
        help_text=_(
            "Cross-account kesh ruxsat etilgan kontekst (practice) yoki "
            "taqiqlangan kontekst (exam/high_stakes)."
        ),
    )

    # -- Provenance & teacher-group visibility ------------------------------
    source = models.CharField(
        _("yuborilgan kanal"),
        max_length=16,
        choices=Source.choices,
        default=Source.WEB,
        db_index=True,
        help_text=_("Esse qaysi kanaldan yuborilgan: veb-sayt, bot, TMA."),
    )
    assignment = models.ForeignKey(
        EssayAssignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
        verbose_name=_("topshiriq"),
        help_text=_("O'qituvchi guruhga tayinlagan topshiriq (bo'lsa)."),
    )
    group_visibility = models.CharField(
        _("guruhga ko'rinishi"),
        max_length=20,
        choices=GroupVisibility.choices,
        default=GroupVisibility.ASSIGNMENT_ONLY,
        help_text=_(
            "Teacher guruh hisobotida qanday ko'rinadi. Standart — faqat "
            "tayinlangan topshiriq bo'yicha (maxfiylik uchun xavfsiz)."
        ),
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
            # Teacher review queue lookups
            models.Index(
                fields=["assigned_reviewer", "status"],
                name="idx_essay_reviewer_status",
            ),
            models.Index(
                fields=["teacher_review_requested", "status"],
                name="idx_essay_reviewreq_status",
            ),
            models.Index(fields=["graded_at"], name="idx_essay_graded_at"),
            # Waiting submissions for one shared cache key (leader completes →
            # followers apply the canonical evaluation).
            models.Index(
                fields=["grading_cache_key", "status"],
                name="idx_essay_cachekey_status",
            ),
        ]
        constraints = []

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
        if self.total_score is None:
            return None
        if self.status in (
            self.Status.GRADED,
            self.Status.AI_EVALUATED,
            self.Status.TEACHER_REVIEWED,
        ):
            # NOTE: explicit status check — Decimal("0") is falsy but a real
            # 0/24 grade must stay 0, not become None (ungraded).
            return self.total_score
        # Zero is a valid score — use `is not None`, never truthiness.
        return self.total_score

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
        if self.topic is None:
            # No topic → no time limit. Return 0 only when there is no active
            # timer start; callers must check is_expired (False) not this value.
            # Use a day-scale default once the timer has started so polling UIs
            # do not show an instant timeout.
            if not self.password_verified_at:
                return 0
            elapsed = (tz.now() - self.password_verified_at).total_seconds()
            return max(0, int(3600 - elapsed))
        if not self.password_verified_at:
            return self.topic.time_limit_minutes * 60
        elapsed = (tz.now() - self.password_verified_at).total_seconds()
        limit = self.topic.time_limit_minutes * 60
        return max(0, int(limit - elapsed))

    @property
    def is_expired(self) -> bool:
        """Vaqt tugaganmi (server-side)."""
        # Topic-less submissions have no time limit — never expire solely
        # because the nullable topic relationship is absent.
        if self.topic is None:
            return False
        # A zero-minute limit means the essay is unlimited. Keep
        # remaining_seconds at zero for clients so they do not show a fake
        # countdown, but do not treat that value as an expired submission.
        if self.topic.time_limit_minutes <= 0:
            return False
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
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="essay_reviews",
        verbose_name=_("tekshirgan o'qituvchi"),
        help_text=_(
            "O'qituvchi o'chirilganda tarix saqlanib qoladi (SET_NULL)."
        ),
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
        teacher = self.teacher or "—"
        return f"{teacher}: {self.submission} — {self.final_score}/24"


# ---------------------------------------------------------------------------
# EssayCriterionScore  (12-mezon grading rubric)
# ---------------------------------------------------------------------------

class EssayGradingCache(models.Model):
    """
    Shared, cross-account persistent cache of validated AI essay grades.

    ``cache_key`` (stored in the legacy column name ``text_hash``) is a
    context-aware fingerprint: normalized essay text **plus** every grading
    input that can change the evaluation (topic, rubric version, prompt
    version, provider/model chain, language, scoring configuration, cache
    scope, schema version). Two identical essays with a different rubric or
    topic therefore never share a grade.

    The row is also the distributed lock: ``status`` + ``lease_owner`` +
    ``lease_expires_at`` implement leader/follower coordination so exactly one
    paid AI request runs per cache key (see apps/essays/services.py).

    No student identity, teacher note or submission metadata is ever stored
    here: only the canonical validated AI evaluation needed to reproduce it.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Navbatda")
        PROCESSING = "processing", _("Baholanmoqda")
        COMPLETED = "completed", _("Yakunlangan")
        FAILED = "failed", _("Xatolik")

    #: Bumped whenever the persisted payload schema changes incompatibly.
    #: Rows written under an older schema are never reused.
    CACHE_SCHEMA_VERSION = 2

    text_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        verbose_name=_("kesh kaliti"),
        help_text=_(
            "Context-aware HMAC fingerprint of the normalized essay and its "
            "full grading context (rubric, prompt, model, topic, scope)."
        ),
    )
    essay_text = models.TextField(
        verbose_name=_("esse matni"),
        help_text=_("Audit/debug uchun saqlanadi."),
    )
    raw_result = models.JSONField(
        verbose_name=_("xom AI natijasi (JSON)"),
        default=dict,
        blank=True,
    )
    total_score = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=0,
        verbose_name=_("umumiy ball"),
    )
    max_score = models.PositiveSmallIntegerField(
        default=24,
        verbose_name=_("maksimal ball"),
    )
    hit_count = models.PositiveIntegerField(
        default=1,
        verbose_name=_("ishlatilgan soni"),
        help_text=_(
            "Necha marta ishlatilgani: 1 — dastlabki AI baholash, keyingilari "
            "qayta ishlatish (reuse_count = hit_count - 1)."
        ),
    )
    # -- Lifecycle / distributed lock ---------------------------------------
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.COMPLETED,
        db_index=True,
        verbose_name=_("holat"),
    )
    lease_owner = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("ijara egasi"),
        help_text=_("Leader jarayon tokeni (bo'sh bo'lsa ijara yo'q)."),
    )
    lease_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("ijara tugash vaqti"),
    )
    failure_count = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_("xatolik soni"),
    )
    error_summary = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("xatolik qisqacha"),
    )
    waiting_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("kutayotgan yuborishlar"),
        help_text=_("Shu kalit uchun natijani kutayotgan submissionlar."),
    )
    invalidated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("bekor qilingan"),
    )
    invalidated_reason = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("bekor qilish sababi"),
    )
    # -- Identity / provenance (never contains student identity) -------------
    text_fingerprint = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        verbose_name=_("matn barmoqizi"),
        help_text=_("Faqat matn bo'yicha fingerprint (diagnostika uchun)."),
    )
    grading_context_fingerprint = models.CharField(
        max_length=64,
        blank=True,
        default="",
        db_index=True,
        verbose_name=_("kontekst barmoqizi"),
        help_text=_("Baholash konteksti (rubrika/prompt/model/mavzu) barmoqizi."),
    )
    grading_context = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("baholash konteksti"),
        help_text=_(
            "Baholash identifikatori: rubrika, prompt, model, til, scope "
            "(shaxsiy ma'lumot saqlanmaydi)."
        ),
    )
    rubric_version = models.CharField(
        max_length=64,
        blank=True,
        default="",
        verbose_name=_("rubrika versiyasi"),
    )
    prompt_version = models.CharField(
        max_length=32,
        blank=True,
        default="",
        verbose_name=_("prompt versiyasi"),
    )
    model_identifier = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("model identifikatori"),
    )
    provider = models.CharField(
        max_length=32,
        blank=True,
        default="",
        verbose_name=_("provider"),
    )
    cache_schema_version = models.PositiveSmallIntegerField(
        default=CACHE_SCHEMA_VERSION,
        verbose_name=_("kesh sxemasi versiyasi"),
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("yakunlangan vaqt"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("yaratilgan"),
    )
    last_used_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("oxirgi ishlatilgan"),
        help_text=_("Oxirgi marta keshdan foydalanilgan vaqt (last_accessed_at)."),
    )

    class Meta:
        verbose_name = _("Baholash keshi")
        verbose_name_plural = _("Baholash keshlari")
        ordering = ["-hit_count", "-last_used_at"]
        indexes = [
            models.Index(fields=["status", "lease_expires_at"]),
            models.Index(fields=["cache_schema_version", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"Cache {self.text_hash[:12]}… — {self.total_score}/{self.max_score} (×{self.hit_count})"

    # -- Compatibility aliases for the documented cache vocabulary -----------
    @property
    def cache_key(self) -> str:
        """The context-aware cache key (legacy column name is ``text_hash``)."""
        return self.text_hash

    @property
    def raw_score(self):
        """Raw rubric score; ``0`` is a valid, cacheable score."""
        return self.total_score

    @property
    def reuse_count(self) -> int:
        """How many times this evaluation was reused by another submission."""
        return max(self.hit_count - 1, 0)

    @property
    def last_accessed_at(self):
        return self.last_used_at

    @property
    def short_hash(self) -> str:
        """Hashning qisqartirilgan ko'rinishi (birinchi 12 belgi)."""
        return self.text_hash[:12]

    def is_reusable(self, *, now=None) -> bool:
        """A completed, schema-current, non-invalidated evaluation.

        The payload itself is additionally re-validated by the service layer
        before it is served, and an incompatible ``cache_schema_version`` is
        treated as invalid so it is re-graded instead of reused.
        """
        return (
            self.status == self.Status.COMPLETED
            and self.invalidated_at is None
            and self.cache_schema_version >= self.CACHE_SCHEMA_VERSION
            and bool(self.raw_result)
        )

    def lease_is_active(self, *, now=None) -> bool:
        now = now or timezone.now()
        return (
            self.status == self.Status.PROCESSING
            and bool(self.lease_owner)
            and self.lease_expires_at is not None
            and self.lease_expires_at > now
        )


class EssayRewriteCache(models.Model):
    """Persistent cache of improved essay text, keyed by essay + grading context."""
    text_hash = models.CharField(max_length=64, unique=True, db_index=True)
    essay_text = models.TextField()
    improved_content = models.TextField()
    hit_count = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Yaxshilangan esse keshi")
        verbose_name_plural = _("Yaxshilangan esse keshlari")
        ordering = ["-hit_count", "-last_used_at"]

    def __str__(self) -> str:
        return f"Rewrite cache {self.text_hash[:12]}… (×{self.hit_count})"


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
