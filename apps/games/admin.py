"""Games admin — admin panel configuration."""
from django.contrib import admin
from .models import Game, GameLevel, UserGameScore, Badge, UserBadge


@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "icon_emoji", "xp_per_correct", "is_active", "sort_order"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(GameLevel)
class GameLevelAdmin(admin.ModelAdmin):
    list_display = ["title", "game", "difficulty", "xp_reward", "is_active", "sort_order"]
    list_filter = ["game", "difficulty", "is_active"]
    search_fields = ["title"]


@admin.register(UserGameScore)
class UserGameScoreAdmin(admin.ModelAdmin):
    list_display = ["user", "game", "total_xp", "total_coins", "games_played",
                    "correct_answers", "best_streak", "high_score"]
    list_filter = ["game"]
    search_fields = ["user__email", "user__first_name"]
    raw_id_fields = ["user"]


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = ["name", "badge_type", "icon_emoji", "required_value", "xp_bonus"]
    list_filter = ["badge_type"]


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ["user", "badge", "earned_at"]
    list_filter = ["badge"]
    raw_id_fields = ["user"]
