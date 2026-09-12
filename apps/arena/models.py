"""
Arena app — Real-time WebSocket Quiz Arena (1v1 Duel).

Models:
    ArenaRoom    — Duel room with 2 players, status, questions
    ArenaPlayer  — Player in a room (score, answers, connected status)
    ArenaQuestion — Individual question in a duel round
"""
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class ArenaRoom(models.Model):
    """
    A 1v1 duel room.

    Lifecycle:
        1. WAITING   — 1 ta o'yinchi kutmoqda
        2. STARTED   — 2 ta o'yinchi topildi, savollar yuklandi
        3. FINISHED  — Duel tugadi, natija aniqlandi
    """

    class Status(models.TextChoices):
        WAITING = "waiting", _("Kutilmoqda")
        STARTED = "started", _("Boshlandi")
        FINISHED = "finished", _("Tugadi")

    class Mode(models.TextChoices):
        QUEUE = "queue", _("Navbat")
        CUSTOM = "custom", _("Shaxsiy xona")
        BOT = "bot", _("Bot bilan")

    player1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="arena_rooms_as_player1",
        verbose_name=_("1-o'yinchi"),
    )
    player2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="arena_rooms_as_player2",
        verbose_name=_("2-o'yinchi"),
    )
    status = models.CharField(
        _("holat"),
        max_length=20,
        choices=Status.choices,
        default=Status.WAITING,
    )
    mode = models.CharField(
        _("rejim"),
        max_length=10,
        choices=Mode.choices,
        default=Mode.QUEUE,
    )
    bot_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="arena_bot_rooms",
        verbose_name=_("bot hisob"),
        help_text=_("BOT rejimida ishlatiladigan sun'iy raqib hisobi."),
    )
    winner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="arena_wins",
        verbose_name=_("g'olib"),
    )
    total_questions = models.PositiveIntegerField(_("jami savollar"), default=10)
    time_per_question = models.PositiveIntegerField(_("savol uchun vaqt (soniya)"), default=15)
    current_question_index = models.PositiveIntegerField(_("joriy savol indeksi"), default=0)
    room_code = models.CharField(_("xona kodi"), max_length=10, unique=True, blank=True)

    # -- Timing --------------------------------------------------------------
    question_started_at = models.DateTimeField(
        _("savol boshlangan"),
        null=True, blank=True,
        help_text=_("Joriy savol yuborilgan vaqt — tezlik bonusi hisoblash uchun."),
    )

    # -- ELO snapshot --------------------------------------------------------
    p1_rating_before = models.PositiveIntegerField(_("1-o'yinchi ELO"), null=True, blank=True)
    p2_rating_before = models.PositiveIntegerField(_("2-o'yinchi ELO"), null=True, blank=True)
    p1_rating_change = models.IntegerField(_("1-o'yinchi ELO o'zgarishi"), default=0)
    p2_rating_change = models.IntegerField(_("2-o'yinchi ELO o'zgarishi"), default=0)

    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    started_at = models.DateTimeField(_("boshlangan"), null=True, blank=True)
    finished_at = models.DateTimeField(_("tugagan"), null=True, blank=True)

    class Meta:
        verbose_name = _("Arena xonasi")
        verbose_name_plural = _("Arena xonalari")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Arena: {self.player1} vs {self.player2 or '?'} [{self.get_status_display()}]"

    def save(self, *args, **kwargs):
        if not self.room_code:
            import random
            import string
            self.room_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        super().save(*args, **kwargs)

    @property
    def player1_score(self):
        return self.players.filter(player=self.player1).first()

    @property
    def player2_score(self):
        if self.player2:
            return self.players.filter(player=self.player2).first()
        return None


class ArenaPlayer(models.Model):
    """
    Player record within a duel room.
    """
    room = models.ForeignKey(
        ArenaRoom,
        on_delete=models.CASCADE,
        related_name="players",
        verbose_name=_("xona"),
    )
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="arena_players",
        verbose_name=_("o'yinchi"),
    )
    score = models.PositiveIntegerField(_("ball"), default=0)
    correct_answers = models.PositiveIntegerField(_("to'g'ri javoblar"), default=0)
    answered_questions = models.PositiveIntegerField(_("javob berilgan"), default=0)
    is_connected = models.BooleanField(_("ulanganmi"), default=False)
    is_bot = models.BooleanField(_("botmi"), default=False)
    channel_name = models.CharField(
        _("kanal nomi"),
        max_length=200,
        blank=True,
        default="",
        help_text=_("Foydalanuvchining WebSocket kanali — jonli xabarlar uchun."),
    )

    # -- Streak / time -------------------------------------------------------
    streak = models.PositiveIntegerField(_("joriy kombo"), default=0)
    best_streak = models.PositiveIntegerField(_("eng yaxshi kombo"), default=0)
    total_time_seconds = models.PositiveIntegerField(
        _("jami javob vaqti (soniya)"),
        default=0,
        help_text=_("Barcha javoblarga ketgan umumiy vaqt — tezlik statistikasi."),
    )

    # -- Rewards -------------------------------------------------------------
    xp_earned = models.PositiveIntegerField(_("olgan XP"), default=0)
    coins_earned = models.PositiveIntegerField(_("olgan tangalar"), default=0)
    rating_before = models.PositiveIntegerField(_("dueldan oldingi ELO"), null=True, blank=True)
    rating_change = models.IntegerField(_("ELO o'zgarishi"), default=0)

    joined_at = models.DateTimeField(_("qo'shilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Arena o'yinchisi")
        verbose_name_plural = _("Arena o'yinchilari")
        unique_together = ("room", "player")

    def __str__(self) -> str:
        return f"{self.player} in {self.room}"


class ArenaQuestion(models.Model):
    """
    Individual question in a duel round.
    """
    room = models.ForeignKey(
        ArenaRoom,
        on_delete=models.CASCADE,
        related_name="questions",
        verbose_name=_("xona"),
    )
    question_text = models.TextField(_("savol matni"))
    option_a = models.CharField(_("A variant"), max_length=300)
    option_b = models.CharField(_("B variant"), max_length=300)
    option_c = models.CharField(_("C variant"), max_length=300)
    option_d = models.CharField(_("D variant"), max_length=300)
    correct_answer = models.CharField(
        _("to'g'ri javob"),
        max_length=1,
        choices=[("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")],
    )
    position = models.PositiveIntegerField(_("tartib"), default=0)
    points = models.PositiveIntegerField(_("ball"), default=10)

    class Meta:
        verbose_name = _("Arena savoli")
        verbose_name_plural = _("Arena savollari")
        ordering = ["position"]

    def __str__(self) -> str:
        return f"Q{self.position}: {self.question_text[:50]}..."


# ---------------------------------------------------------------------------
# ArenaProfile  (ELO rating & duel stats per user)
# ---------------------------------------------------------------------------

class ArenaProfile(models.Model):
    """
    ELO rating and duel statistics for one player.

    Rating starts at 1000 and is updated with a K=32 Elo algorithm after
    every finished duel (win / loss / draw).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="arena_profile",
        verbose_name=_("foydalanuvchi"),
    )
    rating = models.PositiveIntegerField(_("ELO reyting"), default=1000)
    wins = models.PositiveIntegerField(_("g'alabalar"), default=0)
    losses = models.PositiveIntegerField(_("mag'lubiyatlar"), default=0)
    draws = models.PositiveIntegerField(_("duranglar"), default=0)
    duels_played = models.PositiveIntegerField(_("o'ynalgan duellar"), default=0)
    current_win_streak = models.PositiveIntegerField(_("joriy g'alaba seriyasi"), default=0)
    best_win_streak = models.PositiveIntegerField(_("eng uzun g'alaba seriyasi"), default=0)
    total_correct = models.PositiveIntegerField(_("jami to'g'ri javoblar"), default=0)
    total_answers = models.PositiveIntegerField(_("jami javoblar"), default=0)
    total_time_seconds = models.PositiveIntegerField(_("jami javob vaqti"), default=0)

    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    updated_at = models.DateTimeField(_("yangilangan"), auto_now=True)

    class Meta:
        verbose_name = _("Arena profili")
        verbose_name_plural = _("Arena profillari")
        indexes = [
            models.Index(fields=["-rating"], name="idx_arena_rating"),
        ]

    def __str__(self) -> str:
        return f"{self.user}: {self.rating} ELO ({self.wins}W/{self.losses}L)"

    @property
    def win_rate(self) -> float:
        if self.duels_played == 0:
            return 0.0
        return round(self.wins / self.duels_played * 100, 1)

    @property
    def accuracy(self) -> float:
        if self.total_answers == 0:
            return 0.0
        return round(self.total_correct / self.total_answers * 100, 1)


# ---------------------------------------------------------------------------
# ArenaQueueEntry  (matchmaking queue, DB-backed)
# ---------------------------------------------------------------------------

class ArenaQueueEntry(models.Model):
    """
    One row per player waiting in the matchmaking queue.

    DB-backed so matching works across processes/workers. `channel_name`
    lets the creating consumer be reached for the `match_found` broadcast.
    """

    class Status(models.TextChoices):
        WAITING = "waiting", _("Kutmoqda")
        MATCHED = "matched", _("Topildi")
        EXPIRED = "expired", _("Bekor qilingan")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="arena_queue_entries",
        verbose_name=_("foydalanuvchi"),
    )
    rating = models.PositiveIntegerField(_("ELO reyting"), default=1000)
    status = models.CharField(
        _("holat"),
        max_length=10,
        choices=Status.choices,
        default=Status.WAITING,
    )
    channel_name = models.CharField(
        _("kanal nomi"),
        max_length=200,
        blank=True,
        default="",
        help_text=_("Navbatga tushgan WebSocket kanali — match topilganda xabar yuborish uchun."),
    )
    room = models.ForeignKey(
        ArenaRoom,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="queue_entries",
        verbose_name=_("xona"),
    )
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)
    matched_at = models.DateTimeField(_("topilgan"), null=True, blank=True)

    class Meta:
        verbose_name = _("Arena navbati")
        verbose_name_plural = _("Arena navbatlari")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "rating"], name="idx_queue_status_rating"),
        ]

    def __str__(self) -> str:
        return f"{self.user} ({self.rating}) [{self.get_status_display()}]"


# ---------------------------------------------------------------------------
# ArenaAnswerLog  (per-answer audit trail)
# ---------------------------------------------------------------------------

class ArenaAnswerLog(models.Model):
    """
    One row per answered question inside a duel — audit + stats source.

    Stores the answer, correctness, response time, streak at answer time and
    the exact points awarded (base + combo + time bonus breakdown).
    """

    room = models.ForeignKey(
        ArenaRoom,
        on_delete=models.CASCADE,
        related_name="answer_logs",
        verbose_name=_("xona"),
    )
    player = models.ForeignKey(
        ArenaPlayer,
        on_delete=models.CASCADE,
        related_name="answer_logs",
        verbose_name=_("o'yinchi"),
    )
    position = models.PositiveIntegerField(_("savol tartibi"), default=0)
    answer = models.CharField(_("javob"), max_length=1)
    is_correct = models.BooleanField(_("to'g'rimi"), default=False)
    time_taken_seconds = models.FloatField(_("javob vaqti (soniya)"), default=0.0)
    points = models.PositiveIntegerField(_("ball"), default=0)
    base_points = models.PositiveIntegerField(_("asosiy ball"), default=0)
    combo_bonus = models.PositiveIntegerField(_("kombo bonusi"), default=0)
    time_bonus = models.PositiveIntegerField(_("tezlik bonusi"), default=0)
    streak = models.PositiveIntegerField(_("joriy kombo"), default=0)
    created_at = models.DateTimeField(_("yaratilgan"), auto_now_add=True)

    class Meta:
        verbose_name = _("Arena javobi")
        verbose_name_plural = _("Arena javoblari")
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=["player", "position"],
                name="uq_arena_answer_player_position",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.player.player} → Q{self.position}: {'✓' if self.is_correct else '✗'} +{self.points}"
