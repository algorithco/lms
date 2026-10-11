"""OCR / handwriting extraction boundary for image-based essay submissions.

A photograph cannot be handed to the text grading pipeline directly, so image
essays go through this module first: validate → orient → order → extract →
confirm. The canonical grading workflow only ever receives *confirmed,
normalized text*, so the global grading cache keys on text rather than on an
image hash.

Provider status
---------------
There is no locally installed OCR engine in this deployment (no Tesseract /
no ``pytesseract``), and no vision model is configured by default. Rather than
pretend otherwise:

* :class:`NullOCRProvider` is the default and raises :class:`OCRUnavailable`
  with an actionable message, so image essays fail *loudly and safely* instead
  of producing empty text or being silently dropped.
* :class:`OpenRouterVisionProvider` reuses the project's existing
  OpenRouter/Groq credentials with a vision-capable model. It activates only
  when ``ESSAY_OCR_VISION_MODEL`` names a model *and* an API key is present.

Configure with::

    ESSAY_OCR_PROVIDER = "openrouter_vision"      # or "" (unavailable)
    ESSAY_OCR_VISION_MODEL = "google/gemini-flash-1.5"  # a multimodal model

Nothing in this module claims that recognition has been exercised in
production; that requires a configured multimodal provider and real images.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field
from typing import Protocol

from django.conf import settings

logger = logging.getLogger(__name__)

#: Recognized writing systems, in the order we ask a provider to consider them.
DEFAULT_LANGUAGES = ("uz-Latn", "uz-Cyrl", "ru")

#: Image formats accepted from Telegram / the web uploader.
ALLOWED_MIME_TYPES = {
    "image/jpeg": "JPEG",
    "image/jpg": "JPEG",
    "image/png": "PNG",
    "image/webp": "WEBP",
    "image/heic": "HEIF",
    "image/heif": "HEIF",
}

#: Guards against decompression bombs (gigapixel images) before decode.
MAX_PIXELS = 50_000_000


class OCRValidationError(ValueError):
    """The uploaded image is unusable (too large, corrupt, wrong format)."""


class OCRUnavailable(RuntimeError):
    """No OCR provider is configured/operational."""


class OCRFailed(RuntimeError):
    """The configured provider was reachable but did not return usable text."""


@dataclass
class OCRPage:
    index: int
    text: str
    confidence: float | None = None


@dataclass
class OCRResult:
    text: str
    pages: list[OCRPage] = field(default_factory=list)
    confidence: float | None = None
    provider: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def is_probably_incomplete(self) -> bool:
        """Heuristic guard against grading severely truncated OCR output.

        Requires an explicit minimum amount of extracted text; a page of
        handwriting that yields only a few characters is almost certainly a
        failed extraction rather than a one-word essay.
        """
        return len(self.text.strip()) < 30


# ---------------------------------------------------------------------------
# Image validation / normalization
# ---------------------------------------------------------------------------

def validate_image_bytes(data: bytes, *, max_bytes: int | None = None) -> str:
    """Validate raw image bytes and return the detected MIME type.

    Raises:
        OCRValidationError: on oversized, empty, corrupt or unsupported images.
    """
    limit = max_bytes if max_bytes is not None else int(
        getattr(settings, "ESSAY_IMAGE_MAX_BYTES", 10 * 1024 * 1024)
    )
    if not data:
        raise OCRValidationError("Rasm bo'sh.")
    if len(data) > limit:
        raise OCRValidationError(
            f"Rasm hajmi juda katta ({len(data) // 1024} KB). "
            f"Maksimal {limit // (1024 * 1024)} MB."
        )
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - Pillow is a hard dependency here
        raise OCRUnavailable(
            "Rasmni tekshirish uchun Pillow kutubxonasi o'rnatilmagan."
        ) from exc

    import io

    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        # verify() invalidates the object; reopen to read the format/pixels.
        with Image.open(io.BytesIO(data)) as image:
            fmt = (image.format or "").upper()
            width, height = image.size
    except OCRValidationError:
        raise
    except Exception as exc:
        raise OCRValidationError("Rasm buzuq yoki o'qib bo'lmaydigan format.") from exc

    if width * height > MAX_PIXELS:
        raise OCRValidationError("Rasm o'lchami juda katta.")
    if fmt not in {"JPEG", "PNG", "WEBP", "HEIF", "MPO", "GIF", "BMP", "TIFF"}:
        raise OCRValidationError(f"Qo'llab-quvvatlanmaydigan rasm formati: {fmt}")
    for mime, expected in ALLOWED_MIME_TYPES.items():
        if expected == fmt:
            return mime
    return "image/jpeg"


def normalize_image(data: bytes) -> tuple[bytes, str]:
    """Apply EXIF orientation and downscale absurdly large scans.

    Returns ``(normalized_bytes, mime_type)``. Falls back to the original bytes
    when Pillow cannot process the image further — validation already ran.
    """
    import io

    try:
        from PIL import Image, ImageOps
    except ImportError as exc:  # pragma: no cover
        raise OCRUnavailable("Pillow o'rnatilmagan.") from exc

    try:
        with Image.open(io.BytesIO(data)) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            # Most handwriting is legible well below this; it just makes the
            # request cheaper and the provider more reliable.
            max_side = 2400
            if max(image.size) > max_side:
                ratio = max_side / float(max(image.size))
                image = image.resize(
                    (int(image.width * ratio), int(image.height * ratio)),
                )
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=88, optimize=True)
            return buffer.getvalue(), "image/jpeg"
    except OCRUnavailable:
        raise
    except Exception as exc:
        raise OCRValidationError("Rasmni tayyorlab bo'lmadi.") from exc


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

class OCRProvider(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def extract(self, pages: list[bytes], *, languages: tuple[str, ...]) -> OCRResult: ...


class NullOCRProvider:
    """Default provider: reports clearly that OCR is not configured."""

    name = "unavailable"

    def is_available(self) -> bool:
        return False

    def extract(self, pages: list[bytes], *, languages: tuple[str, ...]) -> OCRResult:
        raise OCRUnavailable(
            "Rasmli esse uchun OCR xizmati hozircha sozlanmagan. "
            "Administrator multimodal (ko'rish) modelni yoqishi kerak, "
            "yoki esseni matn ko'rinishida yuboring."
        )


_PROMPT = (
    "Transcribe the handwritten or printed text in these essay page images "
    "exactly as written. Do not translate, correct, summarize or add anything. "
    "Preserve paragraph breaks and the original spelling. The text may be "
    "Uzbek Latin, Uzbek Cyrillic or Russian. Return ONLY the transcribed text, "
    "without commentary or markdown fences."
)


class OpenRouterVisionProvider:
    """Reuses the platform's OpenRouter credentials with a multimodal model."""

    name = "openrouter_vision"

    def __init__(self, model: str | None = None):
        self.model = model or getattr(settings, "ESSAY_OCR_VISION_MODEL", "") or ""

    def _api_key(self) -> str:
        return (
            getattr(settings, "OPENROUTER_API_KEY", "")
            or getattr(settings, "GROQ_API_KEY", "")
            or ""
        )

    def is_available(self) -> bool:
        return bool(self.model and self._api_key())

    def _base_url(self) -> str:
        if getattr(settings, "OPENROUTER_API_KEY", ""):
            return getattr(settings, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        return "https://api.groq.com/openai/v1"

    def extract(self, pages: list[bytes], *, languages: tuple[str, ...]) -> OCRResult:
        if not self.is_available():
            raise OCRUnavailable("Vision model yoki API kalit sozlanmagan.")

        import urllib.error
        import urllib.request

        content: list[dict] = [{"type": "text", "text": _PROMPT}]
        for index, page in enumerate(pages, 1):
            # Page markers keep multi-page order explicit even if the model
            # decides to comment on the sequence.
            content.append({"type": "text", "text": f"--- PAGE {index} ---"})
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": "data:image/jpeg;base64," + base64.b64encode(page).decode("ascii"),
                },
            })

        body = json.dumps({
            "model": self.model,
            "temperature": 0,
            "messages": [{"role": "user", "content": content}],
        }).encode("utf-8")

        request = urllib.request.Request(
            f"{self._base_url().rstrip('/')}/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key()}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        timeout = int(getattr(settings, "ESSAY_OCR_TIMEOUT", 120))
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")[:400]
            except Exception:  # pragma: no cover
                pass
            logger.warning("OCR vision HTTP %s: %s", exc.code, detail)
            raise OCRFailed("Rasmdan matn ajratib bo'lmadi (xizmat xatosi).") from exc
        except Exception as exc:
            logger.warning("OCR vision request failed: %s", exc)
            raise OCRFailed("Rasmdan matn ajratib bo'lmadi (aloqa xatosi).") from exc

        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise OCRFailed("OCR xizmati bo'sh javob qaytardi.") from exc

        text = (text or "").strip()
        if not text:
            raise OCRFailed("OCR xizmati bo'sh matn qaytardi.")

        # Split the model output back into pages so the student can review the
        # per-page result, and so the order is preserved end-to-end.
        chunks = _split_pages(text)
        result_pages = [
            OCRPage(index=i, text=chunk) for i, chunk in enumerate(chunks)
        ]
        return OCRResult(
            text=text,
            pages=result_pages,
            confidence=None,  # provider does not expose a confidence score
            provider=self.name,
        )


def _split_pages(text: str) -> list[str]:
    import re

    marker = re.compile(r"^\s*-{2,}\s*PAGE\s+\d+\s*-{2,}\s*$", re.IGNORECASE)
    chunks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if marker.match(line):
            if current:
                chunks.append("\n".join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        chunks.append("\n".join(current).strip())
    return [c for c in chunks if c] or [text.strip()]


#: Factories, not instances: providers read configuration at construction, so
#: caching a singleton here would freeze the settings value from import time
#: (and make ``override_settings`` ineffective).
_REGISTRY: dict[str, type[OCRProvider]] = {
    "openrouter_vision": OpenRouterVisionProvider,
}


def get_provider(name: str | None = None) -> OCRProvider:
    """Resolve the configured OCR provider, or the unavailable default."""
    target = name if name is not None else getattr(settings, "ESSAY_OCR_PROVIDER", "")
    if not target:
        return NullOCRProvider()
    entry = _REGISTRY.get(target)
    if entry is None:
        logger.warning("Unknown ESSAY_OCR_PROVIDER=%r", target)
        return NullOCRProvider()
    # The registry holds factories so configuration is read per call; an
    # already-constructed provider (e.g. a test double registered through
    # patch.dict) is used as-is.
    return entry() if callable(entry) else entry


def ocr_available() -> bool:
    return get_provider().is_available()


def extract_text(
    raw_pages: list[bytes],
    *,
    languages: tuple[str, ...] = DEFAULT_LANGUAGES,
    provider: str | None = None,
    max_pages: int | None = None,
) -> OCRResult:
    """Validate, orient and transcribe multi-page essay images in order.

    Raises:
        OCRValidationError: bad page set (too many pages, corrupt, oversized).
        OCRUnavailable: no provider is configured.
        OCRFailed: the provider ran but returned nothing usable.
    """
    limit = max_pages if max_pages is not None else int(
        getattr(settings, "ESSAY_IMAGE_MAX_PAGES", 10)
    )
    if not raw_pages:
        raise OCRValidationError("Hech qanday rasm qabul qilinmadi.")
    if len(raw_pages) > limit:
        raise OCRValidationError(
            f"Bitta essening maksimal sahifa soni: {limit}."
        )

    max_bytes = int(getattr(settings, "ESSAY_IMAGE_MAX_BYTES", 10 * 1024 * 1024))
    prepared: list[bytes] = []
    for data in raw_pages:
        validate_image_bytes(data, max_bytes=max_bytes)
        normalized, _mime = normalize_image(data)
        prepared.append(normalized)

    result = get_provider(provider).extract(tuple(prepared), languages=languages)
    if result.is_probably_incomplete:
        result.warnings.append(
            "Rasmdan juda kam matn aniqlandi — iltimos, matnni tekshiring."
        )
    return result
