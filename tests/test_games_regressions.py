"""Regression tests for the server-rendered learning games."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.games.models import Game, GameLevel


User = get_user_model()


class GamesRegressionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="games@example.com",
            password="StrongPass123!",
            role=User.Role.STUDENT,
        )
        self.game = Game.objects.create(
            name="Imlo Minalari",
            slug=Game.GameType.IMLO_MINA,
            description="Spelling practice",
        )
        self.level = GameLevel.objects.create(
            game=self.game,
            title="Level 1",
            question_data={
                "text": "Bu matn.",
                "error_word_index": 1,
            },
        )

    def test_anonymous_game_hub_redirects_to_login(self):
        response = self.client.get(reverse("web:games:index"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            f"/login?next={reverse('web:games:index')}",
        )

    def test_imlo_check_rejects_non_numeric_word_index(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("web:games:imlo-check"),
            {
                "level_id": self.level.pk,
                "word_index": "not-a-number",
                "action": "fix",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.user.game_scores.count(), 0)

    def test_other_game_checks_tolerate_non_numeric_combo(self):
        gazal_game = Game.objects.create(
            name="Navoiy vs Dunyo",
            slug=Game.GameType.GAZAL_PUZZLE,
            description="Poem puzzle",
        )
        gazal_level = GameLevel.objects.create(
            game=gazal_game,
            title="Level 1",
            question_data={"bayt_lines": ["Birinchi satr"]},
        )
        lugat_game = Game.objects.create(
            name="Eski So'zlar Dueli",
            slug=Game.GameType.LUGAT_MATCH,
            description="Word matching",
        )
        lugat_level = GameLevel.objects.create(
            game=lugat_game,
            title="Level 1",
            question_data={"pairs": [{"old": "qalam", "new": "yozuv quroli"}]},
        )
        self.client.force_login(self.user)

        gazal_response = self.client.post(
            reverse("webapi:games-check", args=[gazal_game.slug]),
            {"level_id": gazal_level.pk, "order": "0", "combo": "not-a-number"},
        )
        lugat_response = self.client.post(
            reverse("webapi:games-check", args=[lugat_game.slug]),
            {
                "level_id": lugat_level.pk,
                "card1_id": "old_0",
                "card2_id": "new_0",
                "combo": "not-a-number",
            },
        )

        self.assertEqual(gazal_response.status_code, 200)
        self.assertEqual(lugat_response.status_code, 200)
        self.assertEqual(gazal_response.json()["combo"], 1)
        self.assertEqual(lugat_response.json()["combo"], 1)
