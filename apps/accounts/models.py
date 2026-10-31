"""
Accounts app — Custom User Model and Profile.

Architecture decisions:
    - AbstractUser is extended (not AbstractBaseUser) to keep Django admin
      and auth back-works working out of the box.
    - `email` replaces `username` as the login identifier.
    - A separate Profile model holds optional biographical data so the
      User table stays lean.
"""

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.core.validators import validate_image_upload

from .managers import UserManager


# ---------------------------------------------------------------------------
# Choices
# ---------------------------------------------------------------------------


def generate_referral_code() -> str:
    import secrets

    return f"ref_{secrets.token_hex(4)}"


class User(AbstractUser):
    """
    Custom User model — the single source of truth for authentication.

    Roles:
        STUDENT  — o'quvchi; can take tests, view results.
        TEACHER  — o'qituvchi; can create courses and tests.
        ADMIN    — platform administrator; full access.
        PARENT   — ota-onalar; can view children's results.

    Key fields:
        email          — unique, used for login instead of username.
        role           — drives permissions and filtering across the platform.
        telegram_chat_id — (optional) set when user links their Telegram;
                          used for notification delivery.
    """

    class Role(models.TextChoices):
        STUDENT = "student", _("O'quvchi")
        TEACHER = "teacher", _("O'qituvchi")
        ADMIN = "admin", _("Admin")
        PARENT = "parent", _("Ota-ona")
        CENTER_ADMIN = "center_admin", _("O'quv markaz rahbari")

    # -- Login ----------------------------------------------------------------
    username = None  # type: ignore[assignment]  # disable username field
    email = models.EmailField(
        _("email address"),
        unique=True,
        db_index=True,
    )

    # -- Role -----------------------------------------------------------------
    role = models.CharField(
        _("role"),
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )

    # -- Organization (B2B SaaS) ----------------------------------------------
    learning_center = models.ForeignKey(
        "organizations.LearningCenter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name=_("o'quv markazi"),
    )
    branch = models.ForeignKey(
        "organizations.CenterBranch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        verbose_name=_("filial"),
    )

    # -- Telegram integration -------------------------------------------------
    telegram_chat_id = models.BigIntegerField(
        _("Telegram Chat ID"),
        null=True,
        blank=True,
        unique=True,
        help_text=_("Foydalanuvchi Telegram bot bilan bog'laganda o'rnatiladi."),
    )
    telegram_username = models.CharField(
        _("Telegram Username"),
        max_length=64,
        null=True,
        blank=True,
        help_text=_("Foydalanuvchining Telegram username'i (@username)."),
    )
    telegram_identity_verified_at = models.DateTimeField(
        _("Telegram identifikatori tasdiqlangan vaqt"),
        null=True,
        blank=True,
        help_text=_(
            "Numeric Telegram ID bot imzosi yoki ikki kanalli bog'lash "
            "orqali tasdiqlangan bo'lsa to'ldiriladi."
        ),
    )

    # -- Google OAuth ----------------------------------------------------------
    google_id = models.CharField(
        _("Google ID"),
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        help_text=_("Google OAuth orqali kirgan foydalanuvchi ID si."),
    )

    # -- Language preference --------------------------------------------------
    language = models.CharField(
        _("til"),
        max_length=5,
        default="uz",
        choices=[
            ("uz", "O'zbek"),
            ("ru", "Русский"),
            ("en", "English"),
        ],
        help_text=_("Tizim interfeysi tili."),
    )

    # -- Bot accounts (Arena AI opponents) -----------------------------------
    is_bot = models.BooleanField(
        _("botmi"),
        default=False,
        help_text=_("Sun'iy AI raqib (Arena bot) hisobi. Real foydalanuvchi emas."),
    )

    # -- Teacher creation permissions (Phase 4) -------------------------------
    can_create_essay_topic = models.BooleanField(
        _("esse mavzusi yaratish huquqi"),
        default=False,
        help_text=_(
            "O'qituvchiga esse mavzulari yaratishga ruxsat berish. Admin tomonidan boshqariladi."
        ),
    )
    can_create_test = models.BooleanField(
        _("test yaratish huquqi"),
        default=False,
        help_text=_(
            "O'qituvchiga testlar yaratish / import qilishga ruxsat berish. Admin tomonidan boshqariladi."
        ),
    )

    # -- Anti-fraud & Security ------------------------------------------------
    fraud_strikes = models.PositiveIntegerField(
        _("fraud strikes"),
        default=0,
        help_text=_("Qalbaki chek yuklashlar soni."),
    )
    is_banned = models.BooleanField(
        _("bloklangan"),
        default=False,
        help_text=_("Firibgarlik yoki qoidabuzarlik sababli bloklanganlik holati."),
    )
    ban_reason = models.TextField(
        _("bloklash sababi"),
        blank=True,
        default="",
        help_text=_("Foydalanuvchi bloklangan bo'lsa, sababi."),
    )
    banned_at = models.DateTimeField(
        _("bloklangan vaqt"),
        null=True,
        blank=True,
    )

    # -- Referral & Viral Growth ----------------------------------------------
    referral_code = models.CharField(
        _("referal kodi"),
        max_length=32,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text=_("Foydalanuvchining do'stlarni taklif qilish unikal kodi"),
    )
    bonus_tests = models.PositiveIntegerField(
        _("bonus testlar kvotasi"),
        default=0,
        help_text=_("Referal orqali olingan qo'shimcha testlar soni"),
    )
    bonus_essays = models.PositiveIntegerField(
        _("bonus esselar kvotasi"),
        default=0,
        help_text=_("Referal orqali olingan qo'shimcha esse tekshiruvlari soni"),
    )

    # -- Timestamps -----------------------------------------------------------
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    objects = UserManager()  # type: ignore[assignment]

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = ["first_name", "last_name"]

    class Meta:
        verbose_name = _("Foydalanuvchi")
        verbose_name_plural = _("Foydalanuvchilar")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["role"], name="idx_user_role"),
            models.Index(fields=["email"], name="idx_user_email"),
        ]
        constraints = [
            models.UniqueConstraint(Lower("email"), name="uniq_user_email_lower"),
        ]

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        else:
            self.email = ""
        if not self.referral_code:
            self.referral_code = generate_referral_code()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.get_full_name()} <{self.email}>"

    # -- Convenience helpers --------------------------------------------------
    @property
    def telegram_id(self) -> int | None:
        return self.telegram_chat_id

    @telegram_id.setter
    def telegram_id(self, val: int | None) -> None:
        self.telegram_chat_id = val

    @property
    def is_student(self) -> bool:
        return self.role == self.Role.STUDENT

    @property
    def is_teacher(self) -> bool:
        return self.role == self.Role.TEACHER

    @property
    def is_platform_admin(self) -> bool:
        from .access import is_platform_admin

        return is_platform_admin(self)

    @property
    def is_parent(self) -> bool:
        return self.role == self.Role.PARENT

    @property
    def is_center_admin(self) -> bool:
        return self.role == self.Role.CENTER_ADMIN

    @property
    def has_pro_access(self) -> bool:
        """True if user has PRO access (either via teacher role, teacher group, subscription or profile)."""
        if self.role in (self.Role.TEACHER, self.Role.ADMIN):
            return True
        if hasattr(self, "student_groups") and self.student_groups.exists():
            return True
        sub = getattr(self, "subscription", None)
        if sub and getattr(sub, "is_active", False):
            plan_type = getattr(sub.plan, "plan_type", "").lower()
            if plan_type in ("pro", "premium", "family"):
                return True
        profile = getattr(self, "profile", None)
        if profile and getattr(profile, "plan", "").lower() in (
            "pro",
            "premium",
            "family",
        ):
            return True
        return False

    @property
    def teacher_profile_obj(self):
        """TeacherProfile accessor; auto-creates if missing for teacher or admin users."""
        if not (self.is_teacher or self.is_platform_admin or self.is_superuser):
            return None
        profile, _ = TeacherProfile.objects.get_or_create(teacher=self)
        return profile

    @property
    def pro_quota_balance(self) -> int:
        prof = getattr(self, "teacher_profile", None)
        return prof.pro_quota_balance if prof else 0

    @property
    def premium_quota_balance(self) -> int:
        prof = getattr(self, "teacher_profile", None)
        return prof.premium_quota_balance if prof else 0


class Profile(models.Model):
    """
    One-to-one extension of User for biographical / optional fields.

    Rationale: Keeps User table slim. Profile data (bio, avatar, phone)
    is loaded only when needed (e.g. profile page).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("foydalanuvchi"),
    )
    avatar = models.ImageField(
        _("avatar"),
        upload_to="avatars/%Y/%m/",
        blank=True,
        null=True,
        validators=[validate_image_upload],
    )
    phone = models.CharField(
        _("telefon raqam"),
        max_length=20,
        blank=True,
        validators=[MinLengthValidator(7)],
    )
    bio = models.TextField(
        _("o'zini tanishtirish"),
        max_length=500,
        blank=True,
    )
    date_of_birth = models.DateField(
        _("tug'ilgan sana"),
        null=True,
        blank=True,
    )
    plan = models.CharField(
        _("tarif"),
        max_length=20,
        default="free",
        blank=True,
    )

    # -- Multi-Subject & Onboarding (EdTech Personalization) -------------------
    class SubjectChoice(models.TextChoices):
        UZBEK = "uzbek", _("Ona tili va adabiyot")
        ENGLISH = "english", _("Ingliz tili (IELTS & Multi-level)")

    active_subject = models.CharField(
        _("faol fan"),
        max_length=20,
        choices=SubjectChoice.choices,
        default=SubjectChoice.UZBEK,
        db_index=True,
        help_text=_("Foydalanuvchining hozirgi tanlagan fani: uzbek yoki english"),
    )

    class ExamTarget(models.TextChoices):
        NATIONAL_CERTIFICATE = "national_certificate", _("Milliy sertifikat")
        ATTESTATION = "attestation", _("Attestatsiya 2026")
        IELTS = "ielts", _("IELTS Academic / General")
        MULTILEVEL = "multilevel", _("Multi-level (CEFR B1–C1)")
        UNDECIDED = "undecided", _("Hali aniqlanmagan")

    exam_target = models.CharField(
        _("imtihon maqsadi"),
        max_length=32,
        choices=ExamTarget.choices,
        default=ExamTarget.UNDECIDED,
        db_index=True,
    )
    target_timeline_months = models.PositiveSmallIntegerField(
        _("tayyorgarlik muddati (oy)"),
        default=3,
        help_text=_("1, 3 yoki 6 oy"),
    )
    target_grade = models.CharField(
        _("maqsad darajasi"),
        max_length=32,
        default="A",
        help_text=_("A+, A, B+, oliy_toifa, birinchi_toifa"),
    )
    placement_score = models.DecimalField(
        _("placement test bali"),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("5 ta savoldan nechtasi to'g'ri (0–5)"),
    )
    onboarding_completed = models.BooleanField(
        _("onboarding yakunlanganmi"),
        default=False,
        db_index=True,
    )
    daily_plan_summary = models.JSONField(
        _("AI kunlik reja xulosasi"),
        default=dict,
        blank=True,
        help_text=_("AI tuzgan kunlik test va esse yuklamasi"),
    )

    # -- Gamification & Streak (🔥 Duolingo Style) ----------------------------
    current_streak = models.PositiveIntegerField(
        _("joriy streak"),
        default=0,
        help_text=_("Ketma-ket kunlik faollik (kunlar soni)."),
    )
    longest_streak = models.PositiveIntegerField(
        _("eng uzun streak"),
        default=0,
        help_text=_("Foydalanuvchining eng yuqori natijasi."),
    )
    last_activity_date = models.DateField(
        _("oxirgi faollik sanasi"),
        null=True,
        blank=True,
        db_index=True,
    )
    streak_freeze_count = models.PositiveSmallIntegerField(
        _("streak muzlatish qalqoni"),
        default=1,
        help_text=_("O'tkazib yuborilgan 1 kunni qutqaruvchi qalqon."),
    )
    xp_points = models.PositiveIntegerField(
        _("jami XP ballari"),
        default=0,
        db_index=True,
    )
    weekly_xp = models.PositiveIntegerField(
        _("haftalik XP"),
        default=0,
        db_index=True,
    )

    class LeagueChoice(models.TextChoices):
        BRONZE = "bronze", _("Bronza")
        SILVER = "silver", _("Kumush")
        GOLD = "gold", _("Oltin")
        DIAMOND = "diamond", _("Olmos")

    weekly_league = models.CharField(
        _("haftalik liga"),
        max_length=20,
        choices=LeagueChoice.choices,
        default=LeagueChoice.BRONZE,
        db_index=True,
    )

    # -- Teacher / Center White-Label Branding (B2B) ---------------------------
    center_name = models.CharField(
        _("o'quv markazi nomi"),
        max_length=200,
        blank=True,
        default="",
        help_text=_(
            "Ustoz yoki markazning rasmiy nomi (sertifikat va hisobotlar uchun)."
        ),
    )
    center_logo = models.ImageField(
        _("markaz logotipi"),
        upload_to="centers/logos/%Y/%m/",
        blank=True,
        null=True,
    )
    stamp_signature = models.ImageField(
        _("muhr / imzo tasviri"),
        upload_to="centers/stamps/%Y/%m/",
        blank=True,
        null=True,
        help_text=_("PDF hisobot va sertifikatlarga qo'yiladigan shaffof muhr/imzo."),
    )

    class Meta:
        verbose_name = _("Profil")
        verbose_name_plural = _("Profillar")

    def __str__(self) -> str:
        return f"Profile: {self.user.get_full_name()}"

    @property
    def has_pro_access(self) -> bool:
        return self.user.has_pro_access


class TelegramLinkChallenge(models.Model):
    """Short-lived proof that a web session and Telegram user are controlled together."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="telegram_link_challenges",
    )
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    telegram_id = models.BigIntegerField(null=True, blank=True)


class ParentStudentLink(models.Model):
    """
    Ota-ona va bola o'rtasidagi bog'lanish.
    Bitta o'ta-ona bir nechta bolaga bog'lanishi mumkin.
    """

    parent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="children_links",
        verbose_name=_("ota-ona"),
        limit_choices_to={"role": "parent"},
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_links",
        verbose_name=_("o'quvchi"),
        limit_choices_to={"role": "student"},
    )
    relationship = models.CharField(
        _("munosabat"),
        max_length=20,
        choices=[
            ("father", _("Ota")),
            ("mother", _("Ona")),
            ("guardian", _("Homiy")),
            ("other", _("Boshqa")),
        ],
        default="father",
    )
    is_approved = models.BooleanField(_("tasdiqlanganmi"), default=False)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Ota-ona-bola bog'lanishi")
        verbose_name_plural = _("Ota-ona-bola bog'lanishlari")
        unique_together = ("parent", "student")

    def __str__(self) -> str:
        return f"{self.parent.get_full_name()} → {self.student.get_full_name()}"


class ParentStudentRelation(models.Model):
    """
    Ota-onalar nazorati tizimi (Parent Monitoring & Smart Alerts).
    O'quvchining natijalarini ota-onasining Telegram botiga real vaqtda yuborish.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="parent_relations",
        verbose_name=_("o'quvchi"),
    )
    parent_phone = models.CharField(
        _("ota-ona telefon raqami"),
        max_length=20,
        db_index=True,
    )
    parent_telegram_id = models.BigIntegerField(
        _("ota-ona Telegram ID"),
        null=True,
        blank=True,
        db_index=True,
    )
    is_verified = models.BooleanField(
        _("tasdiqlanganmi"),
        default=False,
    )
    verification_code = models.CharField(
        _("tasdiqlash kodi"),
        max_length=6,
        blank=True,
    )
    weekly_report_enabled = models.BooleanField(
        _("haftalik hisobot yoqilgan"),
        default=True,
    )
    instant_alerts_enabled = models.BooleanField(
        _("tezkor xabarnomalar yoqilgan"),
        default=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Ota-ona va o'quvchi munosabati")
        verbose_name_plural = _("Ota-ona va o'quvchi munosabatlari")
        unique_together = ("student", "parent_phone")

    def __str__(self) -> str:
        status = "tasdiqlangan" if self.is_verified else "kutilmoqda"
        return f"{self.student.get_full_name()} ↔ {self.parent_phone} ({status})"


class TeacherProfile(models.Model):
    """
    O'qituvchi profili va litsenziya kvotalari (Admin kvotalari boshqaruvi).
    Ustoz o'z guruhidagi o'quvchilarga PRO yoki PREMIUM litsenziyalarni tarqata oladi.
    """

    teacher = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
        verbose_name=_("o'qituvchi"),
        limit_choices_to={"role": "teacher"},
    )
    pro_quota_balance = models.PositiveIntegerField(
        _("PRO kvota balansi"),
        default=0,
        help_text=_("Ustoz o'quvchilarga ulasha oladigan PRO litsenziyalar soni."),
    )
    premium_quota_balance = models.PositiveIntegerField(
        _("PREMIUM kvota balansi"),
        default=0,
        help_text=_("Ustoz o'quvchilarga ulasha oladigan PREMIUM litsenziyalar soni."),
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("O'qituvchi profili")
        verbose_name_plural = _("O'qituvchilar profillari")

    def __str__(self) -> str:
        return f"TeacherProfile: {self.teacher.get_full_name()} (PRO: {self.pro_quota_balance}, PREMIUM: {self.premium_quota_balance})"


class ReferralHistory(models.Model):
    """Tracks referral invites and bonus rewards."""

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referrals_sent",
        verbose_name=_("taklif qilgan"),
    )
    referred_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral_received",
        verbose_name=_("taklif qilingan"),
    )
    referral_code = models.CharField(_("ishlatilgan kod"), max_length=32)
    reward_given = models.BooleanField(_("mukofot berildimi"), default=True)
    referrer_bonus_tests = models.PositiveIntegerField(
        _("taklif qilganga test"), default=1
    )
    referred_bonus_tests = models.PositiveIntegerField(
        _("yangi foydalanuvchiga test"), default=1
    )
    referrer_bonus_essays = models.PositiveIntegerField(
        _("taklif qilganga esse"), default=1
    )
    referred_bonus_essays = models.PositiveIntegerField(
        _("yangi foydalanuvchiga esse"), default=1
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Referal tarixi")
        verbose_name_plural = _("Referal tarixlari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.referrer} -> {self.referred_user} ({self.referral_code})"
