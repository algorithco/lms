"""
Games app — Gamification & Interactive Learning Games.

Models:
    Game         — Game type definitions (Imlo Mina, G'azal Puzzle, Lug'at Match)
    GameLevel    — Individual levels/challenges within each game
    UserGameScore — Player XP, coins, and per-game stats
    Badge        — Achievement badges earned through gameplay

Design:
    - Game stores metadata + rules per game type.
    - GameLevel stores individual challenges with JSON answer data.
    - UserGameScore tracks cumulative XP/coins and per-game performance.
    - Badge provides motivation through achievement unlocks.
"""
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Game  (game type definitions)
# ---------------------------------------------------------------------------

class Game(models.Model):
    """
    Defines one type of interactive game.

    Each game has a unique slug, display info, and XP reward per correct answer.
    """

    class GameType(models.TextChoices):
        IMLO_MINA = "imlo_mina", _("Imlo Minalari")
        GAZAL_PUZZLE = "gazal_puzzle", _("Navoiy vs Dunyo")
        LUGAT_MATCH = "lugat_match", _("Eski So'zlar Dueli")
        ARENA_DUEL = "arena_duel", _("Quiz Arena Dueli")
        TELEGRAM_QUIZ = "telegram_quiz", _("Telegram Quiz")

    name = models.CharField(_("nomi"), max_length=100)
    slug = models.SlugField(_("slug"), max_length=50, unique=True, choices=GameType.choices)
    description = models.TextField(_("tavsif"))
    icon_emoji = models.CharField(
        _("ikonka emoji"),
        max_length=10,
        default="🎮",
        help_text=_("Game kartochkasida ko'rsatiladigan emoji."),
    )
    xp_per_correct = models.PositiveIntegerField(
        _("XP (to'g'ri javob uchun)"),
        default=10,
    )
    coins_per_correct = models.PositiveIntegerField(
        _("Coins (to'g'ri javob uchun)"),
        default=5,
    )
    combo_multiplier = models.DecimalField(
        _("Combo koeffitsienti"),
        max_digits=3,
        decimal_places=1,
        default=1.5,
        validators=[MinValueValidator(1.0)],
        help_text=_("Ketma-ket to'g'ri javoblar uchun bonus multiplier."),
    )
    is_active = models.BooleanField(_("faolmi"), default=True)
    sort_order = models.PositiveIntegerField(_("tartib"), default=0)

    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("O'yin")
        verbose_name_plural = _("O'yinlar")
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return f"{self.icon_emoji} {self.name}"


# ---------------------------------------------------------------------------
# GameLevel  (individual challenges)
# ---------------------------------------------------------------------------

class GameLevel(models.Model):
    """
    A single level/challenge within a game.

    `question_data` — JSON field containing level-specific data:
        - IMLO_MINA: {"text": "Matn...", "error_word": "xato", "correct_word": "togri", "position": 3}
        - GAZAL_PUZZLE: {"bayt_lines": ["satr1", "satr2", ...], "correct_order": [1,0,2,3]}
        - LUGAT_MATCH: {"pairs": [{"old": "eski_so'z", "new": "zamonaviy_ma'no"}, ...]}
    """
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="levels",
        verbose_name=_("o'yin"),
    )
    title = models.CharField(_("sarlavha"), max_length=200)
    difficulty = models.PositiveIntegerField(
        _("qiyinlik (1-10)"),
        default=1,
        validators=[MinValueValidator(1)],
    )
    question_data = models.JSONField(
        _("savol ma'lumoti (JSON)"),
        default=dict,
        help_text=_("O'yin turiga qarab JSON formatdagi savol/level ma'lumoti."),
    )
    hint = models.TextField(_("maslahat"), blank=True)
    time_limit_seconds = models.PositiveIntegerField(
        _("vaqt cheklovi (soniya)"),
        default=60,
    )
    xp_reward = models.PositiveIntegerField(
        _("XP mukofoti"),
        default=10,
    )
    is_active = models.BooleanField(_("faolmi"), default=True)
    sort_order = models.PositiveIntegerField(_("tartib"), default=0)

    class Meta:
        verbose_name = _("O'yin leveli")
        verbose_name_plural = _("O'yin levellari")
        ordering = ["game", "sort_order"]
        indexes = [
            models.Index(fields=["game", "difficulty"], name="idx_level_game_diff"),
        ]

    def __str__(self) -> str:
        return f"{self.game.name} — {self.title} (Lv.{self.difficulty})"


# ---------------------------------------------------------------------------
# UserGameScore  (player stats & XP)
# ---------------------------------------------------------------------------

class UserGameScore(models.Model):
    """
    Tracks a user's cumulative game stats and per-game performance.

    Updated after every game session completion.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="game_scores",
        verbose_name=_("foydalanuvchi"),
    )
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name="user_scores",
        verbose_name=_("o'yin"),
    )

    # -- Cumulative stats ---------------------------------------------------
    total_xp = models.PositiveIntegerField(_("umumiy XP"), default=0)
    total_coins = models.PositiveIntegerField(_("umumiy coins"), default=0)
    games_played = models.PositiveIntegerField(_("o'ynalgan o'yinlar"), default=0)
    correct_answers = models.PositiveIntegerField(_("to'g'ri javoblar"), default=0)
    wrong_answers = models.PositiveIntegerField(_("noto'g'ri javoblar"), default=0)
    best_streak = models.PositiveIntegerField(
        _("eng yaxshi streak"),
        default=0,
        help_text=_("Ketma-ket to'g'ri javoblar eng uzun zanjiri."),
    )
    best_time_seconds = models.PositiveIntegerField(
        _("eng yaxshi vaqt (soniya)"),
        default=0,
    )
    high_score = models.PositiveIntegerField(_("eng yuqori ball"), default=0)

    # -- Timestamps ---------------------------------------------------------
    last_played_at = models.DateTimeField(_("oxirgi o'ynalgan"), null=True, blank=True)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("O'yin natijasi")
        verbose_name_plural = _("O'yin natijalari")
        unique_together = ("user", "game")
        ordering = ["-total_xp"]
        indexes = [
            models.Index(fields=["user"], name="idx_score_user"),
            models.Index(fields=["-total_xp"], name="idx_score_xp"),
            # Composite index for leaderboard aggregation
            models.Index(
                fields=["user", "game", "-total_xp"],
                name="idx_score_user_game_xp",
            ),
            # Composite index for badge condition checks
            models.Index(
                fields=["game", "-correct_answers"],
                name="idx_score_game_correct",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} — {self.game.name}: {self.total_xp} XP"

    @property
    def accuracy(self) -> float:
        """To'g'ri javoblar foizi."""
        total = self.correct_answers + self.wrong_answers
        if total == 0:
            return 0.0
        return round(self.correct_answers / total * 100, 1)


# ---------------------------------------------------------------------------
# Badge  (achievement system)
# ---------------------------------------------------------------------------

class Badge(models.Model):
    """
    Achievement badges earned through gameplay.

    Each badge has a unique condition that is checked after every game.
    """

    class BadgeType(models.TextChoices):
        IMLO_MASTER = "imlo_master", _("Imlo Ustasi")
        GAZAL_SCHOLAR = "gazal_scholar", _("G'azal Bilimdon")
        LUGAT_ACADEMIC = "lugat_academic", _("Lug'at Akademigi")
        SPEED_DEMON = "speed_demon", _("Tezlik Shaytoni")
        COMBO_KING = "combo_king", _("Combo Qirol")
        PERFECT_GAME = "perfect_game", _("Mukammal O'yinchi")
        DAILY_PLAYER = "daily_player", _("Kunlik O'yinchi")
        XP_HUNTER = "xp_hunter", _("XP Ovchisi")
        COIN_COLLECTOR = "coin_collector", _("Tangalar Yig'uvchi")
        GRANDMASTER = "grandmaster", _("Grandmaster")
        DUEL_WINNER_10 = "duel_winner_10", _("10 G'alaba Streak")
        NIGHT_OWL = "night_owl", _("Tungi Boyqush")
        ESSAY_MASTER = "essay_master", _("Esse Ustasi")
        ARENA_ELITE = "arena_elite", _("Arena Elitasi")

    name = models.CharField(_("nomi"), max_length=100)
    badge_type = models.CharField(
        _("nishon turi"),
        max_length=30,
        choices=BadgeType.choices,
        unique=True,
    )
    description = models.TextField(_("tavsif"))
    icon_emoji = models.CharField(_("emoji"), max_length=10, default="🏅")
    required_value = models.PositiveIntegerField(
        _("kerakli qiymat"),
        default=1,
        help_text=_("Badge olish uchun kerakli minimal ko'rsatkich (masalan, 50 ta to'g'ri javob)."),
    )
    xp_bonus = models.PositiveIntegerField(
        _("bonus XP"),
        default=50,
        help_text=_("Badge olganda beriladigan bonus XP."),
    )

    class Meta:
        verbose_name = _("Nishon")
        verbose_name_plural = _("Nishonlar")
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.icon_emoji} {self.name}"


# ---------------------------------------------------------------------------
# UserBadge  (awarded badges)
# ---------------------------------------------------------------------------

class UserBadge(models.Model):
    """Tracks which badges a user has earned."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="badges",
        verbose_name=_("foydalanuvchi"),
    )
    badge = models.ForeignKey(
        Badge,
        on_delete=models.CASCADE,
        related_name="earned_by",
        verbose_name=_("nishon"),
    )
    earned_at = models.DateTimeField(_("erishilgan sana"), auto_now_add=True)

    class Meta:
        verbose_name = _("Foydalanuvchi nishoni")
        verbose_name_plural = _("Foydalanuvchi nishonlari")
        unique_together = ("user", "badge")
        ordering = ["-earned_at"]

    def __str__(self) -> str:
        return f"{self.user} — {self.badge}"


# ---------------------------------------------------------------------------
# Player Level (1-50, XP-based)
# ---------------------------------------------------------------------------

# XP thresholds for each level (level 1 = 0 XP, level 2 = 100 XP, ...)
LEVEL_THRESHOLDS = {
    1: 0, 2: 100, 3: 250, 4: 500, 5: 800,
    6: 1200, 7: 1700, 8: 2300, 9: 3000, 10: 4000,
    11: 5200, 12: 6500, 13: 8000, 14: 10000, 15: 12500,
    16: 15500, 17: 19000, 18: 23000, 19: 27500, 20: 32500,
    21: 38000, 22: 44000, 23: 50500, 24: 57500, 25: 65000,
    26: 73000, 27: 81500, 28: 90500, 29: 100000, 30: 110000,
    31: 121000, 32: 132500, 33: 144500, 34: 157000, 35: 170000,
    36: 184000, 37: 198500, 38: 213500, 39: 229000, 40: 245000,
    41: 262000, 42: 280000, 43: 299000, 44: 319000, 45: 340000,
    46: 362000, 47: 385000, 48: 410000, 49: 436000, 50: 465000,
}


def get_player_level(total_xp: int) -> dict:
    """
    Calculate player level from total XP.

    Returns: {"level": int, "current_xp": int, "next_level_xp": int,
              "progress": float (0-100), "xp_in_level": int}
    """
    level = 1
    for lvl in range(50, 0, -1):
        if total_xp >= LEVEL_THRESHOLDS[lvl]:
            level = lvl
            break

    current_threshold = LEVEL_THRESHOLDS[level]
    next_threshold = LEVEL_THRESHOLDS.get(level + 1, LEVEL_THRESHOLDS[50] + 50000)
    xp_range = next_threshold - current_threshold
    xp_in_level = total_xp - current_threshold
    progress = min(100.0, round(xp_in_level / xp_range * 100, 1)) if xp_range > 0 else 100.0

    return {
        "level": level,
        "current_xp": total_xp,
        "next_level_xp": next_threshold,
        "progress": progress,
        "xp_in_level": xp_in_level,
        "xp_needed": next_threshold - total_xp,
    }


# ---------------------------------------------------------------------------
# Weekly Challenge
# ---------------------------------------------------------------------------

class WeeklyChallenge(models.Model):
    """
    Haftalik challenge — o'quvchilarni rag'batlantirish uchun.

    Har hafta yangi challenge yaratiladi yoki avtomatik generatsiya qilinadi.
    """

    class ChallengeType(models.TextChoices):
        TEST_COUNT = "test_count", _("N ta test topshir")
        ESSAY_COUNT = "essay_count", _("N ta esse yoz")
        GAME_XP = "game_xp", _("N XP to'pla")
        PERFECT_SCORE = "perfect_score", _("100% ball oling")
        STREAK = "streak", _("N kun ketma-ket kiring")

    title = models.CharField(_("sarlavha"), max_length=200)
    description = models.TextField(_("tavsif"))
    challenge_type = models.CharField(
        _("challenge turi"),
        max_length=30,
        choices=ChallengeType.choices,
    )
    target_value = models.PositiveIntegerField(_("maqsadli qiymat"), default=5)
    xp_reward = models.PositiveIntegerField(_("XP mukofoti"), default=100)
    coin_reward = models.PositiveIntegerField(_("Tanga mukofoti"), default=50)
    starts_at = models.DateTimeField(_("boshlanish vaqti"))
    ends_at = models.DateTimeField(_("tugash vaqti"))
    is_active = models.BooleanField(_("faolmi"), default=True)

    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Haftalik challenge")
        verbose_name_plural = _("Haftalik challenge'lar")
        ordering = ["-starts_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.starts_at.strftime('%d.%m')}-{self.ends_at.strftime('%d.%m')})"

    @property
    def is_current(self) -> bool:
        from django.utils import timezone
        now = timezone.now()
        return self.starts_at <= now <= self.ends_at


# ---------------------------------------------------------------------------
# UserChallenge Progress
# ---------------------------------------------------------------------------

class UserChallenge(models.Model):
    """Foydalanuvchining challenge'dagi progressi."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="challenge_progress",
        verbose_name=_("foydalanuvchi"),
    )
    challenge = models.ForeignKey(
        WeeklyChallenge,
        on_delete=models.CASCADE,
        related_name="participants",
        verbose_name=_("challenge"),
    )
    current_value = models.PositiveIntegerField(_("joriy qiymat"), default=0)
    is_completed = models.BooleanField(_("tugallanganmi"), default=False)
    completed_at = models.DateTimeField(_("tugallangan vaqt"), null=True, blank=True)

    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Challenge progressi")
        verbose_name_plural = _("Challenge progresslari")
        unique_together = ("user", "challenge")
        ordering = ["-current_value"]

    def __str__(self) -> str:
        return f"{self.user} — {self.challenge}: {self.current_value}/{self.challenge.target_value}"

    @property
    def progress_pct(self) -> float:
        if self.challenge.target_value == 0:
            return 0.0
        return min(100.0, round(self.current_value / self.challenge.target_value * 100, 1))


# ---------------------------------------------------------------------------
# Daily Streak
# ---------------------------------------------------------------------------

class DailyStreak(models.Model):
    """
    Kunlik streak — foydalanuvchi har kuni tizimga kirganini kuzatish.

    Streak = ketma-ket kunlarda tizimga kirish.
    3 kun, 7 kun, 14 kun, 30 kun streak uchun bonus mukofotlar.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_streak",
        verbose_name=_("foydalanuvchi"),
    )
    current_streak = models.PositiveIntegerField(_("joriy streak"), default=0)
    best_streak = models.PositiveIntegerField(_("eng uzun streak"), default=0)
    last_login_date = models.DateField(_("oxirgi kirish sanasi"), null=True, blank=True)
    total_logins = models.PositiveIntegerField(_("jami kirishlar"), default=0)

    # Streak rewards claimed
    reward_3claimed = models.BooleanField(default=False)
    reward_7claimed = models.BooleanField(default=False)
    reward_14claimed = models.BooleanField(default=False)
    reward_30claimed = models.BooleanField(default=False)

    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Kunlik streak")
        verbose_name_plural = _("Kunlik streaklar")

    def __str__(self) -> str:
        return f"{self.user}: {self.current_streak} kunlik streak"

    def update_streak(self) -> dict:
        """
        Streak ni yangilash — har kirishda chaqiriladi.

        Returns: {"new_streak": int, "reward_claimed": str|None, "xp_earned": int}
        """
        from django.utils import timezone
        from django.db.models import F

        today = timezone.now().date()
        result = {"new_streak": self.current_streak, "reward_claimed": None, "xp_earned": 0}

        if self.last_login_date == today:
            # Already logged in today
            return result

        if self.last_login_date == today - timezone.timedelta(days=1):
            # Consecutive day — streak continues
            self.current_streak += 1
        else:
            # Streak broken — start new
            self.current_streak = 1

        self.last_login_date = today
        self.total_logins += 1

        if self.current_streak > self.best_streak:
            self.best_streak = self.current_streak

        # Check streak rewards
        streak_rewards = {
            3: ("3_day", 30, 15, "reward_3claimed"),
            7: ("7_day", 75, 35, "reward_7claimed"),
            14: ("14_day", 150, 75, "reward_14claimed"),
            30: ("30_day", 500, 250, "reward_30claimed"),
        }

        if self.current_streak in streak_rewards:
            reward_key, xp, coins, field = streak_rewards[self.current_streak]
            if not getattr(self, field):
                setattr(self, field, True)
                result["reward_claimed"] = reward_key
                result["xp_earned"] = xp

                # Award XP/coins to all game scores
                from django.db.models import F
                UserGameScore.objects.filter(user=self.user).update(
                    total_xp=F("total_xp") + xp,
                    total_coins=F("total_coins") + coins,
                )

        self.save()
        result["new_streak"] = self.current_streak
        return result
