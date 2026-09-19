"""
Unit tests for the essay AI provider resolution (OpenRouter / Groq).

Regression coverage for the 401 "Missing Authentication header" bug:
a Groq key (gsk_...) in .env was aliased into OPENROUTER_API_KEY and sent to
OpenRouter's endpoint, which rejected it with a misleading 401. The fix:

  - settings no longer share keys across providers,
  - ESSAY_AI_PROVIDER=auto picks the provider whose key exists,
  - key-format guards fail fast with a clear message instead of a raw 401.

All tests are offline — OpenAI client objects are constructed but never
called, and provider resolution never hits the network.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from apps.essays.services import (
    _chat_with_fallback,
    _get_ai_model,
    _get_llm_client,
    _grade_via_llm,
    _is_mock_mode,
    _model_candidates,
    _resolve_provider,
    grade_essay,
    parse_llm_json,
)

GROQ_KEY = "gsk_testgroqkey0000000000000000000000000000000"
OR_KEY = "sk-or-v1-testopenrouterkey00000000000000000000000"


class ProviderResolutionTests(TestCase):
    """ESSAY_AI_PROVIDER / key resolution."""

    @override_settings(
        ESSAY_AI_PROVIDER="auto",
        OPENROUTER_API_KEY="",
        GROQ_API_KEY=GROQ_KEY,
    )
    def test_auto_picks_groq_when_only_groq_key(self):
        self.assertEqual(_resolve_provider(), "groq")

    @override_settings(
        ESSAY_AI_PROVIDER="auto",
        OPENROUTER_API_KEY=OR_KEY,
        GROQ_API_KEY="",
    )
    def test_auto_picks_openrouter_when_only_openrouter_key(self):
        self.assertEqual(_resolve_provider(), "openrouter")

    @override_settings(
        ESSAY_AI_PROVIDER="auto",
        OPENROUTER_API_KEY=OR_KEY,
        GROQ_API_KEY=GROQ_KEY,
    )
    def test_auto_prefers_openrouter_when_both_keys(self):
        self.assertEqual(_resolve_provider(), "openrouter")

    @override_settings(
        ESSAY_AI_PROVIDER="auto",
        OPENROUTER_API_KEY="",
        GROQ_API_KEY="",
    )
    def test_auto_without_keys_raises_clear_error(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            _resolve_provider()
        self.assertIn("API kalit topilmadi", str(ctx.exception))

    @override_settings(
        ESSAY_AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY="",
        GROQ_API_KEY=GROQ_KEY,
    )
    def test_forced_openrouter_without_its_key_raises(self):
        """The exact old bug class: only a Groq key exists, provider forced to OpenRouter."""
        with self.assertRaises(ImproperlyConfigured) as ctx:
            _resolve_provider()
        self.assertIn("OPENROUTER_API_KEY sozlanmagan", str(ctx.exception))

    @override_settings(ESSAY_AI_PROVIDER="bogus")
    def test_invalid_provider_value_raises(self):
        with self.assertRaises(ImproperlyConfigured):
            _resolve_provider()


class KeyFormatGuardTests(TestCase):
    """Wrong key format for a provider must fail fast with a helpful hint."""

    @override_settings(
        ESSAY_AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY=GROQ_KEY,  # a Groq key configured as OpenRouter's
        GROQ_API_KEY="",
    )
    def test_groq_key_as_openrouter_key_raises_with_hint(self):
        """This is the original 401 scenario — now a clear config error."""
        with self.assertRaises(ImproperlyConfigured) as ctx:
            _resolve_provider()
        msg = str(ctx.exception)
        self.assertIn("sk-or-", msg)
        self.assertIn("Groq kaliti", msg)

    @override_settings(
        ESSAY_AI_PROVIDER="groq",
        OPENROUTER_API_KEY="",
        GROQ_API_KEY=OR_KEY,  # an OpenRouter key configured as Groq's
    )
    def test_openrouter_key_as_groq_key_raises_with_hint(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            _resolve_provider()
        msg = str(ctx.exception)
        self.assertIn("gsk_", msg)
        self.assertIn("OpenRouter kaliti", msg)


class ModelSelectionTests(TestCase):
    @override_settings(
        ESSAY_AI_PROVIDER="auto",
        OPENROUTER_API_KEY="",
        GROQ_API_KEY=GROQ_KEY,
        ESSAY_AI_MODEL="",
    )
    def test_groq_default_model(self):
        self.assertEqual(_get_ai_model(), "llama-3.3-70b-versatile")

    @override_settings(
        ESSAY_AI_PROVIDER="auto",
        OPENROUTER_API_KEY=OR_KEY,
        GROQ_API_KEY="",
        ESSAY_AI_MODEL="",
    )
    def test_openrouter_default_model(self):
        # Must be a valid OpenRouter free-model id (provider-prefixed, :free)
        model = _get_ai_model()
        self.assertTrue(model.startswith(""))
        self.assertIn(":free", model)
        self.assertIn("/", model)

    @override_settings(
        ESSAY_AI_PROVIDER="auto",
        OPENROUTER_API_KEY="",
        GROQ_API_KEY=GROQ_KEY,
        ESSAY_AI_MODEL="my/custom-model",
    )
    def test_explicit_override_wins(self):
        self.assertEqual(_get_ai_model(), "my/custom-model")

    @override_settings(
        ESSAY_AI_PROVIDER="auto",
        OPENROUTER_API_KEY="",
        GROQ_API_KEY="",
        ESSAY_AI_MODEL="",
    )
    def test_no_key_falls_back_to_openrouter_default(self):
        """Mock mode / no-key path: model lookup must not crash."""
        model = _get_ai_model()
        self.assertIn(":free", model)
        self.assertIn("/", model)


class ClientConstructionTests(TestCase):
    """The OpenAI-compatible client gets the provider's OWN key and base URL."""

    @override_settings(
        ESSAY_AI_PROVIDER="auto",
        OPENROUTER_API_KEY="",
        GROQ_API_KEY=GROQ_KEY,
        GROQ_BASE_URL="https://api.groq.com/openai/v1",
    )
    def test_groq_client_uses_groq_key_and_url(self):
        client = _get_llm_client()
        self.assertEqual(client.api_key, GROQ_KEY)
        self.assertIn("api.groq.com", str(client.base_url))
        self.assertNotIn("openrouter", str(client.base_url))

    @override_settings(
        ESSAY_AI_PROVIDER="auto",
        OPENROUTER_API_KEY=OR_KEY,
        GROQ_API_KEY="",
        OPENROUTER_BASE_URL="https://openrouter.ai/api/v1",
    )
    def test_openrouter_client_uses_openrouter_key_and_url(self):
        client = _get_llm_client()
        self.assertEqual(client.api_key, OR_KEY)
        self.assertIn("openrouter.ai", str(client.base_url))

    @override_settings(
        ESSAY_AI_PROVIDER="auto",
        OPENROUTER_API_KEY="",
        GROQ_API_KEY=GROQ_KEY,
        ESSAY_AI_MOCK_MODE=True,
    )
    def test_mock_flag_with_key_still_uses_real_provider(self):
        """Mock is ONLY active with no key — a half-mocked client pointed at a
        live endpoint would 401 (the exact 'Missing Authentication header'
        failure mode when mock flag + real key coexist)."""
        self.assertFalse(_is_mock_mode())
        client = _get_llm_client()
        self.assertEqual(client.api_key, GROQ_KEY)
        self.assertIn("api.groq.com", str(client.base_url))

    @override_settings(
        ESSAY_AI_PROVIDER="auto",
        OPENROUTER_API_KEY="",
        GROQ_API_KEY="",
        ESSAY_AI_MOCK_MODE=True,
    )
    def test_mock_mode_without_keys(self):
        self.assertTrue(_is_mock_mode())
        client = _get_llm_client()
        self.assertEqual(client.api_key, "mock-key")

class FallbackChainTests(TestCase):
    """
    3-stage model chain: primary -> fallback #1 -> fallback #2.

    An exception is raised only after the WHOLE chain is exhausted;
    non-transient (auth) errors fail fast without fallback attempts.
    """

    CHAIN = [
        "nvidia/nemotron-3.5-lightning:free",
        "liquid/lfm-2.5-2.6b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
    ]

    def _rate_limit(self):
        import openai

        return openai.RateLimitError(
            "429", response=MagicMock(status_code=429, headers={}), body=None
        )

    def _auth_error(self):
        import openai

        return openai.AuthenticationError(
            "401", response=MagicMock(status_code=401, headers={}), body=None
        )

    @override_settings(
        ESSAY_AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY=OR_KEY,
        ESSAY_AI_MODEL="",
        OPENROUTER_FALLBACK_MODELS=CHAIN[1:],
    )
    def test_chain_order(self):
        self.assertEqual(_model_candidates(), self.CHAIN)

    @override_settings(
        ESSAY_AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY=OR_KEY,
        ESSAY_AI_MODEL="",
        OPENROUTER_FALLBACK_MODELS=CHAIN[1:],
    )
    def test_raises_only_after_all_three_fail(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = self._rate_limit()
        with patch("apps.essays.services.time.sleep"):
            with self.assertRaises(Exception):
                _chat_with_fallback(
                    client, self.CHAIN[0], self.CHAIN[1:],
                    messages=[], max_tokens=5, temperature=0, max_attempts=1,
                )
        tried = [c.kwargs["model"] for c in client.chat.completions.create.call_args_list]
        self.assertEqual(tried, self.CHAIN)

    @override_settings(
        ESSAY_AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY=OR_KEY,
        ESSAY_AI_MODEL="",
        OPENROUTER_FALLBACK_MODELS=CHAIN[1:],
    )
    def test_failover_to_second_model(self):
        client = MagicMock()
        ok = MagicMock()
        ok.choices[0].message.content = "javob"
        client.chat.completions.create.side_effect = [self._rate_limit(), ok]
        with patch("apps.essays.services.time.sleep"):
            _, used = _chat_with_fallback(
                client, self.CHAIN[0], self.CHAIN[1:],
                messages=[], max_tokens=5, temperature=0, max_attempts=1,
            )
        self.assertEqual(used, self.CHAIN[1])

    @override_settings(
        ESSAY_AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY=OR_KEY,
        ESSAY_AI_MODEL="",
        OPENROUTER_FALLBACK_MODELS=CHAIN[1:],
    )
    def test_auth_error_fails_fast_without_fallback(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = self._auth_error()
        with self.assertRaises(Exception):
            _chat_with_fallback(
                client, self.CHAIN[0], self.CHAIN[1:],
                messages=[], max_tokens=5, temperature=0,
            )
        self.assertEqual(client.chat.completions.create.call_count, 1)

    @override_settings(
        ESSAY_AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY=OR_KEY,
        ESSAY_AI_MODEL="",
        OPENROUTER_FALLBACK_MODELS=[],
        OPENROUTER_FALLBACK_MODEL="",
    )
    def test_empty_chain_disabled(self):
        client = MagicMock()
        ok = MagicMock()
        ok.choices[0].message.content = "javob"
        client.chat.completions.create.return_value = ok
        _, used = _chat_with_fallback(
            client, self.CHAIN[0], [], messages=[], max_tokens=5, temperature=0,
        )
        self.assertEqual(used, self.CHAIN[0])
        self.assertEqual(client.chat.completions.create.call_count, 1)


class JsonParsingTests(TestCase):
    """parse_llm_json mustahkamligi — fikrlash matni, ```json qobig'i,
    `\'` escape xatolari va kesilgan JSON (loglardagi uch xatoning manbai)."""

    def test_pure_json(self):
        self.assertEqual(
            parse_llm_json('{"a": 1, "b": "salom"}'),
            {"a": 1, "b": "salom"},
        )

    def test_thinking_text_around_json(self):
        """'Here's a thinking process' matni oldida — JSON blok uzib olinadi."""
        raw = (
            "Here's a thinking process:\n\n1. Analyze the essay carefully...\n\n"
            '{"criteria": [], "total_score": 18, "max_score": 24}'
        )
        result = parse_llm_json(raw)
        self.assertEqual(result["total_score"], 18)
        self.assertFalse(result.get("_parse_failed"))

    def test_markdown_fence(self):
        raw = '```json\n{"a": 1}\n```'
        self.assertEqual(parse_llm_json(raw), {"a": 1})

    def test_invalid_apostrophe_escape_repaired(self):
        """Model `\'` (Invalid \\escape) chiqarsa — `'` ga tuzatiladi."""
        raw = '{"reason": "to\\\'g\\\'ri dalillar"}'
        result = parse_llm_json(raw)
        self.assertEqual(result["reason"], "to'g'ri dalillar")
        self.assertFalse(result.get("_parse_failed"))

    def test_trailing_text_after_json(self):
        result = parse_llm_json('{"a": 1}\n\nThat was my answer.')
        self.assertEqual(result, {"a": 1})

    def test_truncated_json_returns_parse_failed(self):
        result = parse_llm_json('{"criteria": [{"id": 1, "score": 2}, ')
        self.assertTrue(result.get("_parse_failed"))

    def test_garbage_text_returns_parse_failed(self):
        result = parse_llm_json("Javob topa olmadim, kechirasiz.")
        self.assertTrue(result.get("_parse_failed"))

    def test_empty_returns_parse_failed(self):
        self.assertTrue(parse_llm_json("").get("_parse_failed"))


class GradingResponseFallbackTests(TestCase):
    def test_invalid_json_tries_next_model_and_keeps_real_scores(self):
        client = MagicMock()
        bad = MagicMock()
        bad.choices[0].message.content = '{"criteria": ['
        good = MagicMock()
        good.choices[0].message.content = json.dumps({
            "criteria": [
                {"id": i, "name": f"Criterion {i}", "score": 1.5, "reason": "izoh"}
                for i in range(1, 13)
            ],
            "total_score": 0,
            "max_score": 24,
            "summary": "Haqiqiy model javobi.",
        })
        client.chat.completions.create.side_effect = [bad, good]

        result, used_model = _grade_via_llm(
            client, ["primary", "fallback"], "essay", "normal prompt", "simple prompt",
        )

        self.assertEqual(used_model, "fallback")
        self.assertEqual(result["total_score"], 18.0)
        calls = client.chat.completions.create.call_args_list
        self.assertEqual([call.kwargs["model"] for call in calls], ["primary", "fallback"])
        self.assertEqual(calls[1].kwargs["messages"][0]["content"], "simple prompt")

    def test_all_invalid_responses_raise_without_a_grade(self):
        client = MagicMock()
        bad = MagicMock()
        bad.choices[0].message.content = '{"criteria": ['
        client.chat.completions.create.return_value = bad

        with self.assertRaisesRegex(ValueError, "JSON formatida"):
            _grade_via_llm(client, ["primary", "fallback"], "essay", "normal", "simple")

        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_invalid_rubric_tries_next_model(self):
        client = MagicMock()
        invalid = MagicMock()
        invalid.choices[0].message.content = json.dumps({
            "criteria": [{"id": 1, "name": "Uslub", "score": 2}],
            "summary": "To'liq emas.",
        })
        valid = MagicMock()
        valid.choices[0].message.content = json.dumps({
            "criteria": [
                {"id": i, "name": f"Criterion {i}", "score": 2, "reason": "izoh"}
                for i in range(1, 13)
            ],
            "summary": "To'liq baho.",
        })
        client.chat.completions.create.side_effect = [invalid, valid]

        result, used_model = _grade_via_llm(
            client, ["primary", "fallback"], "essay", "normal", "simple",
        )

        self.assertEqual(used_model, "fallback")
        self.assertEqual(result["total_score"], 24.0)

    @override_settings(
        ESSAY_AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY=OR_KEY,
        ESSAY_AI_MODEL="primary",
        OPENROUTER_FALLBACK_MODELS=["fallback"],
    )
    def test_invalid_chain_does_not_cache_or_invent_a_grade(self):
        from apps.essays.models import EssayGradingCache

        client = MagicMock()
        bad = MagicMock()
        bad.choices[0].message.content = '{"criteria": ['
        client.chat.completions.create.return_value = bad
        with patch("apps.essays.services._get_llm_client", return_value=client):
            with self.assertRaisesRegex(ValueError, "JSON formatida"):
                grade_essay("Bu haqiqiy baho olinmagan esse matni")

        self.assertEqual(EssayGradingCache.objects.count(), 0)

    def test_authentication_error_stops_before_fallback(self):
        import openai

        client = MagicMock()
        client.chat.completions.create.side_effect = openai.AuthenticationError(
            "401 invalid key", response=MagicMock(status_code=401, headers={}), body=None,
        )
        with self.assertRaisesRegex(ValueError, "API xatolik"):
            _grade_via_llm(client, ["primary", "fallback"], "essay", "normal", "simple")
        self.assertEqual(client.chat.completions.create.call_count, 1)

    def test_all_rate_limited_models_remain_retryable(self):
        import openai

        client = MagicMock()
        client.chat.completions.create.side_effect = openai.RateLimitError(
            "429 temporarily busy", response=MagicMock(status_code=429, headers={}), body=None,
        )
        with self.assertRaises(openai.RateLimitError):
            _grade_via_llm(client, ["primary", "fallback"], "essay", "normal", "simple")
        self.assertEqual(client.chat.completions.create.call_count, 2)

    def test_celery_soft_limit_is_not_converted_to_permanent_error(self):
        from billiard.exceptions import SoftTimeLimitExceeded

        client = MagicMock()
        client.chat.completions.create.side_effect = SoftTimeLimitExceeded()
        with self.assertRaises(SoftTimeLimitExceeded):
            _grade_via_llm(client, ["primary", "fallback"], "essay", "normal", "simple")
        self.assertEqual(client.chat.completions.create.call_count, 1)

    @override_settings(
        ESSAY_AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY=OR_KEY,
        ESSAY_AI_MODEL="primary",
        OPENROUTER_FALLBACK_MODELS=["fallback-one", "fallback-two"],
        ESSAY_AI_REQUEST_TIMEOUT=60,
    )
    def test_grade_request_uses_shared_deadline(self):
        from time import monotonic

        valid = {
            "criteria": [
                {"id": i, "name": f"Criterion {i}", "score": 1, "reason": "izoh"}
                for i in range(1, 13)
            ],
            "total_score": 12,
            "max_score": 24,
            "summary": "Haqiqiy model javobi.",
        }
        before = monotonic()
        with (
            patch("apps.essays.services._get_llm_client") as get_client,
            patch("apps.essays.services._grade_via_llm", return_value=(valid, "primary")) as grader,
        ):
            result = grade_essay("Sinov uchun esse matni")
        after = monotonic()

        self.assertEqual(result["total_score"], 12)
        get_client.assert_called_once_with(timeout=60)
        self.assertEqual(grader.call_args.kwargs["request_timeout"], 60)
        deadline = grader.call_args.kwargs["deadline"]
        self.assertGreaterEqual(deadline, before + 170)
        self.assertLessEqual(deadline, after + 170)

    def test_model_request_timeout_uses_remaining_budget(self):
        client = MagicMock()
        ok = MagicMock()
        ok.choices[0].message.content = '{"ok": true}'
        client.chat.completions.create.return_value = ok

        with patch("apps.essays.services.time.monotonic", return_value=100.0):
            _chat_with_fallback(
                client, "primary", messages=[], max_tokens=5, temperature=0,
                deadline=145.0, request_timeout=60.0,
            )

        timeout = client.chat.completions.create.call_args.kwargs["timeout"]
        self.assertEqual(timeout.read, 45.0)
        self.assertEqual(timeout.connect, 10.0)


class ResponseFormatTests(TestCase):
    """_chat_with_fallback response_format=json_object ni uzatadi; model
    qo'llamasa (400) json-rejimsiz qayta urinadi (boshqa modelga o'tmaydi)."""

    CHAIN = [
        "nvidia/nemotron-3.5-lightning:free",
        "liquid/lfm-2.5-2.6b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
    ]

    @override_settings(
        ESSAY_AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY=OR_KEY,
    )
    def test_response_format_and_params_passed_to_client(self):
        client = MagicMock()
        ok = MagicMock()
        ok.choices[0].message.content = '{"ok": true}'
        client.chat.completions.create.return_value = ok

        _chat_with_fallback(
            client, self.CHAIN[0], [],
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=3000, temperature=0.1,
            response_format={"type": "json_object"},
        )
        kwargs = client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["response_format"], {"type": "json_object"})
        self.assertEqual(kwargs["temperature"], 0.1)
        self.assertEqual(kwargs["max_tokens"], 3000)

    @override_settings(
        ESSAY_AI_PROVIDER="openrouter",
        OPENROUTER_API_KEY=OR_KEY,
    )
    def test_response_format_rejected_retries_without_it(self):
        import openai

        client = MagicMock()
        ok = MagicMock()
        ok.choices[0].message.content = '{"ok": true}'
        bad = openai.BadRequestError(
            "400 Unsupported parameter: 'response_format'",
            response=MagicMock(status_code=400, headers={}),
            body=None,
        )
        client.chat.completions.create.side_effect = [bad, ok]

        _chat_with_fallback(
            client, self.CHAIN[0], [],
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=3000, temperature=0.1,
            response_format={"type": "json_object"},
        )
        calls = client.chat.completions.create.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(
            calls[0].kwargs["response_format"], {"type": "json_object"},
        )
        self.assertNotIn("response_format", calls[1].kwargs)


class InvalidModelFallbackTests(TestCase):
    """OpenRouter 400 "X is not a valid model ID" (masalan, olib
    tashlangan nvidia/nemotron-3-super:free) — task o'lib qolmasligi kerak:
    darhol zanjirdagi keyingi modelga o'tiladi va warning log yoziladi."""

    CHAIN = [
        "nvidia/nemotron-3.5-lightning:free",
        "liquid/lfm-2.5-2.6b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
    ]

    @staticmethod
    def _invalid_model_error():
        import openai

        return openai.BadRequestError(
            "Error code: 400 - nvidia/nemotron-3-super:free is not a valid model ID",
            response=MagicMock(status_code=400, headers={}),
            body=None,
        )

    def test_classifier_matches_invalid_model_id(self):
        import openai

        from apps.essays.services import _is_invalid_model_error

        self.assertTrue(_is_invalid_model_error(self._invalid_model_error()))
        self.assertFalse(
            _is_invalid_model_error(
                openai.BadRequestError(
                    "400 Unsupported parameter: 'response_format'",
                    response=MagicMock(status_code=400, headers={}),
                    body=None,
                )
            )
        )
        # auth/bad-request xatolari mos kelmasligi shart
        self.assertFalse(
            _is_invalid_model_error(
                openai.BadRequestError(
                    "400 Invalid request: max_tokens too large",
                    response=MagicMock(status_code=400, headers={}),
                    body=None,
                )
            )
        )

    def test_invalid_model_skips_to_next_model_without_attempts(self):
        client = MagicMock()
        ok = MagicMock()
        ok.choices[0].message.content = "javob"
        client.chat.completions.create.side_effect = [
            self._invalid_model_error(),
            ok,
        ]
        _, used = _chat_with_fallback(
            client, self.CHAIN[0], self.CHAIN[1:],
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=3000, temperature=0.1, max_attempts=2,
        )
        self.assertEqual(used, self.CHAIN[1])
        calls = client.chat.completions.create.call_args_list
        # 1 urinish model 1'da (skip), 1 urinish model 2'da — qayta urinish
        # sarflanmagan va zanjir oxirigacha yetib bormagan
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].kwargs["model"], self.CHAIN[0])
        self.assertEqual(calls[1].kwargs["model"], self.CHAIN[1])

    def test_invalid_model_exhausted_chain_raises(self):
        client = MagicMock()
        client.chat.completions.create.side_effect = self._invalid_model_error()
        with self.assertRaises(Exception):
            _chat_with_fallback(
                client, self.CHAIN[0], self.CHAIN[1:],
                messages=[], max_tokens=5, temperature=0, max_attempts=1,
            )
        tried = [c.kwargs["model"] for c in client.chat.completions.create.call_args_list]
        self.assertEqual(tried, self.CHAIN)

    def test_other_400_still_fails_fast(self):
        """Boshqa 400'lar (masalan, noto'g'ri request) fail-fast qoladi."""
        import openai

        client = MagicMock()
        client.chat.completions.create.side_effect = openai.BadRequestError(
            "400 Invalid request: messages is empty",
            response=MagicMock(status_code=400, headers={}),
            body=None,
        )
        with self.assertRaises(Exception):
            _chat_with_fallback(
                client, self.CHAIN[0], self.CHAIN[1:],
                messages=[], max_tokens=5, temperature=0,
            )
        self.assertEqual(client.chat.completions.create.call_count, 1)
