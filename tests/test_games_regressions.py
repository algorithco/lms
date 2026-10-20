"""Regression tests for the server-rendered learning games."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.games.engine import gazal_puzzle_order
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

    def test_combo_rewards_ignore_client_input_and_use_server_state(self):
        gazal_game = Game.objects.create(
            name="Navoiy vs Dunyo",
            slug=Game.GameType.GAZAL_PUZZLE,
            description="Poem puzzle",
        )
        gazal_level = GameLevel.objects.create(
            game=gazal_game,
            title="Level 1",
            question_data={"bayt_lines": ["Birinchi satr", "Ikkinchi satr"]},
        )
        _shuffled_lines, expected_order = gazal_puzzle_order(
            gazal_level,
            self.user.pk,
            gazal_level.question_data,
        )
        submitted_order = ",".join(map(str, expected_order))
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
            {"level_id": gazal_level.pk, "order": submitted_order, "combo": 1_000_000},
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

        # The client can neither forge a giant combo nor reset it by sending
        # malformed input. Server-owned score state determines both rewards.
        second_gazal_response = self.client.post(
            reverse("webapi:games-check", args=[gazal_game.slug]),
            {
                "level_id": gazal_level.pk,
                "order": submitted_order,
                "combo": "not-a-number",
            },
        )

        self.assertEqual(gazal_response.status_code, 200)
        self.assertEqual(second_gazal_response.status_code, 200)
        self.assertEqual(lugat_response.status_code, 200)
        self.assertTrue(gazal_response.json()["is_correct"])
        self.assertEqual(gazal_response.json()["combo"], 1)
        self.assertEqual(gazal_response.json()["xp_earned"], gazal_game.xp_per_correct)
        self.assertEqual(second_gazal_response.json()["combo"], 1)
        self.assertEqual(second_gazal_response.json()["xp_earned"], 0)
        self.assertTrue(second_gazal_response.json()["already_completed"])
        self.assertEqual(
            gazal_game.user_scores.get(user=self.user).correct_answers,
            1,
        )
        self.assertTrue(lugat_response.json()["is_correct"])
        self.assertEqual(lugat_response.json()["combo"], 1)
        retry_match = self.client.post(
            reverse("webapi:games-check", args=[lugat_game.slug]),
            {
                "level_id": lugat_level.pk,
                "card1_id": "new_0",
                "card2_id": "old_0",
            },
        )
        self.assertTrue(retry_match.json()["is_correct"])
        self.assertEqual(retry_match.json()["xp_earned"], 0)

    def test_gazal_level_serializes_scramble_and_hides_answer(self):
        game = Game.objects.create(
            name="Gazal",
            slug=Game.GameType.GAZAL_PUZZLE,
            description="Puzzle",
        )
        level = GameLevel.objects.create(
            game=game,
            title="Test",
            question_data={
                "bayt_lines": ["First", "Second", "Third"],
                "correct_order": [2, 0, 1],
            },
        )
        self.client.force_login(self.user)
        play = self.client.get(reverse("webapi:games-play", args=[game.slug]))
        self.assertEqual(play.status_code, 200)
        _shuffled, expected_order = gazal_puzzle_order(
            level,
            self.user.pk,
            level.question_data,
        )
        self.assertNotIn("correct_order", play.json()["content"])
        self.assertEqual(play.json()["content"]["shuffled_lines"], _shuffled)
        wrong_order = ",".join(str((n + 1) % 3) for n in expected_order)
        response = self.client.post(
            reverse("webapi:games-check", args=[game.slug]),
            {"level_id": level.pk, "order": wrong_order},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_correct"])
        self.assertEqual(response.json()["answer"]["correct_order"], expected_order)
        correct_response = self.client.post(
            reverse("webapi:games-check", args=[game.slug]),
            {"level_id": level.pk, "order": ",".join(map(str, expected_order))},
        )
        self.assertTrue(correct_response.json()["is_correct"])

    def test_invalid_gazal_level_is_unavailable_without_awarding_rewards(self):
        game = Game.objects.create(
            name="Gazal",
            slug=Game.GameType.GAZAL_PUZZLE,
            description="Puzzle",
        )
        level = GameLevel.objects.create(
            game=game,
            title="Invalid",
            question_data={"bayt_lines": ["Only one line"], "correct_order": [0]},
        )
        self.client.force_login(self.user)
        play = self.client.get(reverse("webapi:games-play", args=[game.slug]))
        check = self.client.post(
            reverse("webapi:games-check", args=[game.slug]),
            {"level_id": level.pk, "order": "0"},
        )

        self.assertEqual(play.status_code, 503)
        self.assertEqual(check.status_code, 503)
        self.assertFalse(self.user.game_scores.exists())

    def test_imlo_reward_is_once_per_error_word(self):
        self.level.question_data = {
            "text": "Bu xato matn.",
            "error_word_index": 1,
        }
        self.level.save(update_fields=["question_data"])
        second_level = GameLevel.objects.create(
            game=self.game,
            title="Level 2",
            question_data={"text": "Yana xato", "error_word_index": 0},
        )
        self.client.force_login(self.user)

        first = self.client.post(
            reverse("webapi:games-check", args=[self.game.slug]),
            {"level_id": self.level.pk, "word_index": 1, "action": "fix"},
        )
        retry = self.client.post(
            reverse("webapi:games-check", args=[self.game.slug]),
            {"level_id": second_level.pk, "word_index": 0, "action": "fix"},
        )

        self.assertEqual(first.json()["xp_earned"], self.game.xp_per_correct)
        self.assertGreater(retry.json()["xp_earned"], 0)
        score = self.user.game_scores.get(game=self.game)
        self.assertEqual(score.correct_answers, 2)
        self.assertEqual(score.games_played, 2)

    def test_imlo_skip_does_not_award_correct_answer_rewards(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("webapi:games-check", args=[self.game.slug]),
            {"level_id": self.level.pk, "word_index": -1, "action": "skip"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_correct"])
        self.assertEqual(response.json()["xp_earned"], 0)
        self.assertEqual(response.json()["coins_earned"], 0)
        self.user.game_scores.get(game=self.game).refresh_from_db()
        score = self.user.game_scores.get(game=self.game)
        self.assertEqual(score.correct_answers, 0)
        self.assertEqual(score.wrong_answers, 1)
