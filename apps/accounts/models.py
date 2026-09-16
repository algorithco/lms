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

from .managers import UserManager


# ---------------------------------------------------------------------------
# Choices
# ---------------------------------------------------------------------------

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

    # -- Telegram integration -------------------------------------------------
    telegram_chat_id = models.BigIntegerField(
        _("Telegram Chat ID"),
        null=True,
        blank=True,
        unique=True,
        help_text=_("Foydalanuvchi Telegram bot bilan bog'laganda o'rnatiladi."),
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
        help_text=_("O'qituvchiga esse mavzulari yaratishga ruxsat berish. Admin tomonidan boshqariladi."),
    )
    can_create_test = models.BooleanField(
        _("test yaratish huquqi"),
        default=False,
        help_text=_("O'qituvchiga testlar yaratish / import qilishga ruxsat berish. Admin tomonidan boshqariladi."),
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
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.get_full_name()} <{self.email}>"

    # -- Convenience helpers --------------------------------------------------
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

    class Meta:
        verbose_name = _("Profil")
        verbose_name_plural = _("Profillar")

    def __str__(self) -> str:
        return f"Profile: {self.user.get_full_name()}"


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
