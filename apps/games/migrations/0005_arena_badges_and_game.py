"""
Data migration — Arena achievements & the arena_duel Game row.

Creates (idempotently):
    Game:  arena_duel  (Quiz Arena Dueli — hidden from the web games hub)
    Badges: duel_winner_10, night_owl, essay_master, arena_elite

Badge conditions are evaluated by apps.arena.services.award_badges().
"""
from django.db import migrations


def seed_arena_data(apps, schema_editor):
    Game = apps.get_model("games", "Game")
    Badge = apps.get_model("games", "Badge")

    if not Game.objects.filter(slug="arena_duel").exists():
        Game.objects.create(
            name="Quiz Arena Dueli",
            slug="arena_duel",
            description="1v1 real-time quiz duel — ELO reyting, kombo va tezlik bonuslari.",
            icon_emoji="⚔️",
            xp_per_correct=10,
            coins_per_correct=5,
            is_active=False,  # hidden from the web games hub; tracked via /arena/
            sort_order=4,
        )

    badges = [
        {
            "badge_type": "duel_winner_10",
            "name": "10 G'alaba Streak",
            "description": "Arena'da 10 ta duel g'alabasi",
            "icon_emoji": "🏆",
            "required_value": 10,
            "xp_bonus": 300,
        },
        {
            "badge_type": "night_owl",
            "name": "Tungi Boyqush",
            "description": "Kechasi (00:00-05:59) duel g'alaba qozonish",
            "icon_emoji": "🦉",
            "required_value": 1,
            "xp_bonus": 100,
        },
        {
            "badge_type": "essay_master",
            "name": "Esse Ustasi",
            "description": "5 ta esse AI tomonidan baholanishi",
            "icon_emoji": "✍️",
            "required_value": 5,
            "xp_bonus": 200,
        },
        {
            "badge_type": "arena_elite",
            "name": "Arena Elitasi",
            "description": "1200+ ELO reytingga erishish",
            "icon_emoji": "👑",
            "required_value": 1200,
            "xp_bonus": 250,
        },
    ]

    for b in badges:
        if not Badge.objects.filter(badge_type=b["badge_type"]).exists():
            Badge.objects.create(**b)


def unseed_arena_data(apps, schema_editor):
    """Reverse: remove the seeded rows (safe — deletes only if no one earned them)."""
    Game = apps.get_model("games", "Game")
    Badge = apps.get_model("games", "Badge")
    UserBadge = apps.get_model("games", "UserBadge")

    for badge in Badge.objects.filter(
        badge_type__in=["duel_winner_10", "night_owl", "essay_master", "arena_elite"]
    ):
        if not UserBadge.objects.filter(badge=badge).exists():
            badge.delete()

    game = Game.objects.filter(slug="arena_duel").first()
    if game and not game.user_scores.exists():
        game.delete()


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0004_alter_badge_badge_type_alter_game_slug"),
    ]

    operations = [
        migrations.RunPython(seed_arena_data, unseed_arena_data),
    ]