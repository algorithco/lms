"""
ai_smoke_test management command testlari — offline (haqiqiy API so'roqsiz).

Live rejim client mock orqali sinovdan o'tkaziladi: birinchi model OK,
birinchi model fail → keyingi modelga o'tish, butun zanjir fail → CommandError,
mock mode yoqilgan bo'lsa --live rad etilishi.
"""
from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

OR_KEY = "sk-or-v1-testopenrouterkey00000000000000000000000"

CHAIN = [
    "nvidia/nemotron-3.5-lightning:free",
    "liquid/lfm-2.5-2.6b:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]


def _ok_response(content: str = "PONG") -> MagicMock:
    resp = MagicMock()
    resp.choices[0].message.content = content
    return resp


@override_settings(
    ESSAY_AI_PROVIDER="openrouter",
    OPENROUTER_API_KEY=OR_KEY,
    ESSAY_AI_MOCK_MODE=False,
    ESSAY_AI_MODEL="",
    OPENROUTER_FALLBACK_MODELS=CHAIN[1:],
)
class AiSmokeTestDryRunTests(SimpleTestCase):
    """--live berilmagan holat: faqat hisobot, API so'roqsiz."""

    def test_dry_run_prints_config_and_skips_api(self):
        out = StringIO()
        with patch(
            "apps.essays.management.commands.ai_smoke_test._get_llm_client"
        ) as mock_client:
            call_command("ai_smoke_test", stdout=out)
            mock_client.assert_not_called()

        text = out.getvalue()
        self.assertIn("openrouter", text)
        for model in CHAIN:
            self.assertIn(model, text)
        self.assertIn("--live", text)  # hint berilgan


@override_settings(
    ESSAY_AI_PROVIDER="openrouter",
    OPENROUTER_API_KEY=OR_KEY,
    ESSAY_AI_MOCK_MODE=False,
    ESSAY_AI_MODEL="",
    OPENROUTER_FALLBACK_MODELS=CHAIN[1:],
)
class AiSmokeTestLiveTests(SimpleTestCase):
    """--live rejim: mock client orqali zanjir simulyatsiyasi."""

    def _run(self, side_effect) -> StringIO:
        out = StringIO()
        client = MagicMock()
        client.chat.completions.create.side_effect = side_effect
        with patch(
            "apps.essays.management.commands.ai_smoke_test._get_llm_client",
            return_value=client,
        ):
            call_command("ai_smoke_test", live=True, stdout=out)
        return out

    def test_first_model_ok(self):
        out = self._run([_ok_response()])
        text = out.getvalue()
        self.assertIn("OK", text)
        self.assertIn(CHAIN[0], text)
        self.assertIn("PONG", text)

    def test_first_model_fail_falls_to_next(self):
        out = self._run(
            [Exception("Error code: 400 - bad-model:free is not a valid model ID"), _ok_response()]
        )
        text = out.getvalue()
        self.assertIn("FAIL", text)
        self.assertIn(CHAIN[0], text)
        self.assertIn("OK", text)
        self.assertIn(CHAIN[1], text)

    def test_chain_exhausted_raises_command_error(self):
        out = StringIO()
        client = MagicMock()
        client.chat.completions.create.side_effect = Exception(
            "Error code: 400 - bad-model:free is not a valid model ID"
        )
        with patch(
            "apps.essays.management.commands.ai_smoke_test._get_llm_client",
            return_value=client,
        ):
            with self.assertRaises(CommandError):
                call_command("ai_smoke_test", live=True, stdout=out)

        text = out.getvalue()
        for model in CHAIN:
            self.assertIn(f"FAIL {model}", text)


@override_settings(
    ESSAY_AI_PROVIDER="openrouter",
    OPENROUTER_API_KEY="",  # kalit yo'q
)
class AiSmokeTestNoKeyTests(SimpleTestCase):
    """API kalit yo'q: live rejim tushunarli hint bilan rad etiladi
    (xom 401 yoki tracebek emas — _resolve_provider ImproperlyConfigured
    beradi, komanda buni CommandError'ga aylantiradi)."""

    def test_live_rejected_without_api_key(self):
        out = StringIO()
        with self.assertRaises(CommandError) as ctx:
            call_command("ai_smoke_test", live=True, stdout=out)
        self.assertIn("OPENROUTER_API_KEY", str(ctx.exception))


@override_settings(
    ESSAY_AI_PROVIDER="openrouter",
    OPENROUTER_API_KEY=OR_KEY,
    ESSAY_AI_MOCK_MODE=False,
    ESSAY_AI_MODEL="",
    OPENROUTER_FALLBACK_MODELS=CHAIN[1:],
)
@patch(
    "apps.essays.management.commands.ai_smoke_test._fetch_provider_model_ids",
    return_value={CHAIN[0], CHAIN[1]},  # uchinchisi katalogda yo'q
)
class AiSmokeTestValidateModelsTests(SimpleTestCase):
    """--validate-models: ID'lar provayder katalogi bilan solishtiriladi
    (katalog mock'dan keladi, tarmoq ishlatilmaydi)."""

    def test_missing_id_reported_and_fails(self, _mock_fetch):
        out = StringIO()
        with self.assertRaises(CommandError) as ctx:
            call_command("ai_smoke_test", validate_models=True, stdout=out)
        text = out.getvalue()
        self.assertIn(f"MAVJUD  {CHAIN[0]}", text)
        self.assertIn(f"MAVJUD  {CHAIN[1]}", text)
        self.assertIn(f"YO'Q    {CHAIN[2]}", text)
        self.assertIn(CHAIN[2], str(ctx.exception))

    def test_validation_passes_when_all_known(self, _mock_fetch):
        out = StringIO()
        call_command(
            "ai_smoke_test", validate_models=True, stdout=out,
            model=CHAIN[0],  # faqat katalogda bor modelni tekshiramiz
        )
        text = out.getvalue()
        self.assertIn("MAVJUD", text)
        self.assertIn("Barcha model ID'lar", text)
        self.assertNotIn("YO'Q", text)
