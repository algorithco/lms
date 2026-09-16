"""
Management command: ai_smoke_test

OpenRouter/LLM provayder sozlamalarini va model zanjirini tekshirish.
400 "is not a valid model ID" kabi xatolarni productionga qo'yishdan OLDIN
aniqlash uchun.

Ishlatish:
    python manage.py ai_smoke_test                  # faqat konfiguratsiya hisoboti (API so'roqsiz)
    python manage.py ai_smoke_test --live           # zanjir bo'ylab bitta arzon haqiqiy so'rov
    python manage.py ai_smoke_test --live --model liquid/lfm-2.5-2.6b:free
    python manage.py ai_smoke_test --validate-models  # ID'larni provayder katalogi bilan solishtirish

--live rejimi zanjirdagi modellarni ketma-ket sinab, birinchi muvaffaqiyatli
javobda to'xtaydi (grading'dagi _chat_with_fallback mantiqiga o'xshash).
Har bir model uchun OK/FAIL va ketgan vaqt chop etiladi.

--validate-models provayderning /models katalogini so'raydi (haqiqiy grading
so'rovini yubormaydi) va zanjirdagi har bir ID mavjudligini tekshiradi:
eski/yaroqsiz ID'lar (400 "is not a valid model ID" manbai) shu yerda ko'rinadi.
"""
from __future__ import annotations

import time

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand, CommandError

from apps.essays.services import (
    _get_llm_client,
    _is_mock_mode,
    _model_candidates,
    _resolve_provider,
)

PING_MESSAGE = [{"role": "user", "content": "Ping. Faqat PONG deb javob bering."}]

# Nemotron kabi reasoning-modellar JSON so'ralganda ham ko'pincha
# "Here's a thinking process:" bilan boshlanadigan matn qaytaradi.
_THINKING_MARKERS = ("thinking process", "let me think", "here's how")


def _provider_base_url(provider: str) -> str:
    """Resolved provider uchun OpenAI-mos endpoint (settings'dan)."""
    if provider == "groq":
        return getattr(settings, "GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    return getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")


def _provider_key(provider: str) -> str:
    if provider == "groq":
        return getattr(settings, "GROQ_API_KEY", "") or ""
    return getattr(settings, "OPENROUTER_API_KEY", "") or ""


def _fetch_provider_model_ids(base_url: str, api_key: str, timeout: float) -> set[str]:
    """Provayder /models katalogidagi barcha model ID'lar to'plami."""
    import httpx

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    resp = httpx.get(f"{base_url.rstrip('/')}/models", headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return {m["id"] for m in data.get("data", []) if m.get("id")}


class Command(BaseCommand):
    help = (
        "AI provayder (OpenRouter/Groq) sozlamalarini va model zanjirini "
        "tekshirish. --live: bitta arzon haqiqiy so'rov; --validate-models: "
        "model ID'larni provayder katalogi bilan solishtirish."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--live",
            action="store_true",
            help="Haqiqiy API so'rovini yuborish (kichik max_tokens bilan — arzon).",
        )
        parser.add_argument(
            "--validate-models",
            action="store_true",
            help="Zanjirdagi ID'larni provayder /models katalogi bilan solishtirish.",
        )
        parser.add_argument(
            "--model",
            default="",
            help="Faqat shu modelni sinash (default: butun fallback zanjiri).",
        )
        parser.add_argument(
            "--timeout",
            type=float,
            default=None,
            help="Har bir so'rov uchun HTTP timeout (sekund), default ESSAY_AI_REQUEST_TIMEOUT.",
        )

    def handle(self, *args, **options):
        live: bool = options["live"]
        validate_models: bool = options["validate_models"]
        single_model: str = options["model"].strip()
        timeout_opt = options.get("timeout")
        timeout: float = (
            float(timeout_opt)
            if timeout_opt is not None
            else float(getattr(settings, "ESSAY_AI_REQUEST_TIMEOUT", 60.0))
        )

        # ---- 1. Konfiguratsiya hisoboti ---------------------------------
        try:
            provider = _resolve_provider()
        except ImproperlyConfigured as e:
            raise CommandError(
                f"Provayder sozlanmagan: {e}\n"
                "Hint: .env faylida OPENROUTER_API_KEY (yoki GROQ_API_KEY) o'rnating."
            ) from e

        candidates = [single_model] if single_model else _model_candidates()
        if not candidates:
            raise CommandError(
                "Model zanjiri bo'sh — ESSAY_AI_MODEL/OPENROUTER_FALLBACK_MODELS ni tekshiring."
            )

        self.stdout.write(f"Provider            : {provider}")
        mock_str = "HA (haqiqiy API ishlatilmaydi)" if _is_mock_mode() else "yo'q"
        self.stdout.write(f"Mock mode           : {mock_str}")
        self.stdout.write(f"Request timeout     : {timeout}s")
        eager = bool(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False))
        backoff = getattr(settings, "ESSAY_THREAD_RETRY_BACKOFF", (5.0, 10.0, 15.0))
        try:
            backoff_str = ",".join(str(float(b)) for b in backoff)
        except (TypeError, ValueError):
            backoff_str = str(backoff)
        self.stdout.write(
            f"Eager (thread path) : {'HA — grading background thread da' if eager else 'yoq — Celery worker'}"
        )
        self.stdout.write(f"Thread backoff      : {backoff_str}s")
        self.stdout.write("Model zanjiri       :")
        for i, m in enumerate(candidates, 1):
            marker = " (asosiy)" if i == 1 else ""
            self.stdout.write(f"  {i}. {m}{marker}")

        # ---- 2. --validate-models: katalog solishtirish -----------------
        if validate_models:
            base_url = _provider_base_url(provider)
            self.stdout.write(f"\nKatalog so'ralmoqda : {base_url}/models")
            try:
                known_ids = _fetch_provider_model_ids(base_url, _provider_key(provider), timeout)
            except Exception as e:
                raise CommandError(f"Katalogni olish muvaffaqiyatsiz: {e}") from e

            missing = [m for m in candidates if m not in known_ids]
            for m in candidates:
                if m in known_ids:
                    self.stdout.write(self.style.SUCCESS(f"  MAVJUD  {m}"))
                else:
                    self.stdout.write(self.style.ERROR(f"  YO'Q    {m}  <- 400 'is not a valid model ID' beradi"))

            if missing:
                raise CommandError(
                    "Zanjirda provayder katalogida yo'q model ID'lar bor:\n"
                    f"  {', '.join(missing)}\n"
                    "Hint: OPENROUTER_FALLBACK_MODELS (va ESSAY_AI_MODEL) ni to'g'rilang — "
                    "masalan ':free' qo'shimchasi bo'lmagan yoki retire bo'lgan ID'lar."
                )
            self.stdout.write(
                self.style.SUCCESS("Barcha model ID'lar provayder katalogida mavjud [OK]")
            )
            if not live:
                return

        if not live:
            self.stdout.write(
                self.style.NOTICE(
                    "\n--live berilmadi: faqat konfiguratsiya ko'rsatildi. "
                    "Haqiqiy so'rov uchun: python manage.py ai_smoke_test --live"
                )
            )
            return

        # ---- 3. Live tekshiruv ------------------------------------------
        if _is_mock_mode():
            raise CommandError(
                "Mock mode yoqilgan (ESSAY_AI_MOCK_MODE=True va API key yo'q) — "
                "haqiqiy API'ni sinash mumkin emas."
            )

        try:
            client = _get_llm_client(timeout=timeout)
        except ImproperlyConfigured as e:
            raise CommandError(str(e)) from e

        for candidate in candidates:
            started = time.monotonic()
            try:
                response = client.chat.completions.create(
                    model=candidate,
                    messages=PING_MESSAGE,
                    max_tokens=10,
                    temperature=0.0,
                )
                content = (
                    response.choices[0].message.content
                    if response.choices and response.choices[0].message
                    else ""
                )
                elapsed = time.monotonic() - started
                self.stdout.write(
                    self.style.SUCCESS(
                        f"OK   {candidate} — {elapsed:.1f}s — javob: {content!r}"
                    )
                )
                lowered = (content or "").lower()
                if any(marker in lowered for marker in _THINKING_MARKERS):
                    self.stdout.write(
                        self.style.WARNING(
                            "  [!] Model fikrlash matni qaytardi — free reasoning modellar uchun "
                            "odatiy. Grading yo'li buni parse_llm_json va CRITICAL prompt "
                            "sarlavhasi bilan ushlaydi; bu yerda shunchaki ma'lumot."
                        )
                    )
                self.stdout.write(
                    self.style.SUCCESS(f"\nZanjir ishlaydi: birinchi muvaffaqiyatli model = {candidate}")
                )
                return
            except Exception as e:
                elapsed = time.monotonic() - started
                self.stdout.write(
                    self.style.ERROR(
                        f"FAIL {candidate} — {elapsed:.1f}s — {e}"
                    )
                )
                self.stdout.write("  -> keyingi modelga o'tilmoqda...")

        raise CommandError(
            "Butun model zanjiri ishlamadi. Yuqoridagi FAIL qatorlarida sabablarini ko'ring "
            "(masalan, 400 'is not a valid model ID' = model ID OpenRouter'da yo'q — "
            "OPENROUTER_FALLBACK_MODELS ni yangilang yoki --validate-models ni ishga tushiring)."
        )
