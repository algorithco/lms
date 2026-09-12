"""Arena admin."""
from django.contrib import admin
from .models import (
    ArenaAnswerLog,
    ArenaPlayer,
    ArenaProfile,
    ArenaQueueEntry,
    ArenaQuestion,
    ArenaRoom,
)


class ArenaPlayerInline(admin.TabularInline):
    model = ArenaPlayer
    extra = 0


class ArenaQuestionInline(admin.TabularInline):
    model = ArenaQuestion
    extra = 0


@admin.register(ArenaRoom)
class ArenaRoomAdmin(admin.ModelAdmin):
    list_display = ["room_code", "player1", "player2", "status", "mode", "winner", "current_question_index", "created_at"]
    list_filter = ["status", "mode"]
    search_fields = ["room_code", "player1__email", "player2__email"]
    raw_id_fields = ["player1", "player2", "winner", "bot_user"]
    inlines = [ArenaPlayerInline, ArenaQuestionInline]


@admin.register(ArenaPlayer)
class ArenaPlayerAdmin(admin.ModelAdmin):
    list_display = ["player", "room", "score", "correct_answers", "streak", "xp_earned", "rating_change", "is_connected"]
    raw_id_fields = ["player", "room"]


@admin.register(ArenaQuestion)
class ArenaQuestionAdmin(admin.ModelAdmin):
    list_display = ["room", "position", "question_text", "correct_answer", "points"]
    raw_id_fields = ["room"]


@admin.register(ArenaProfile)
class ArenaProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "rating", "wins", "losses", "draws", "current_win_streak", "duels_played"]
    list_filter = ["user__is_bot"]
    search_fields = ["user__email", "user__first_name"]
    raw_id_fields = ["user"]


@admin.register(ArenaQueueEntry)
class ArenaQueueEntryAdmin(admin.ModelAdmin):
    list_display = ["user", "rating", "status", "room", "created_at"]
    list_filter = ["status"]
    search_fields = ["user__email"]
    raw_id_fields = ["user", "room"]


@admin.register(ArenaAnswerLog)
class ArenaAnswerLogAdmin(admin.ModelAdmin):
    list_display = ["player", "position", "answer", "is_correct", "points", "time_taken_seconds", "streak"]
    list_filter = ["is_correct"]
    raw_id_fields = ["room", "player"]
