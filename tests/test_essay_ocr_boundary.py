"""OCR / handwriting extraction boundary.

The critical behaviour is honesty: with no engine configured the boundary must
report that clearly (``OCRUnavailable``) instead of returning empty text that
would then be graded as a zero-score essay. Image validation must reject
oversized, empty and corrupt uploads before any provider is called.
"""

import io
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.essays.ocr import (
    DEFAULT_LANGUAGES,
    _REGISTRY,
    NullOCRProvider,
    OCRPage,
    OCRResult,
    OCRUnavailable,
    OCRValidationError,
    OpenRouterVisionProvider,
    _split_pages,
    extract_text,
    get_provider,
    normalize_image,
    ocr_available,
    validate_image_bytes,
)


def png_bytes(color=(255, 255, 255), size=(8, 8)) -> bytes:
    """A real, decodable PNG so validation actually exercises Pillow."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


class ImageValidationTests(TestCase):
    def test_empty_upload_is_rejected(self):
        with self.assertRaises(OCRValidationError) as ctx:
            validate_image_bytes(b"")
        self.assertIn("bo'sh", str(ctx.exception))

    def test_oversized_upload_is_rejected(self):
        with self.assertRaises(OCRValidationError) as ctx:
            validate_image_bytes(b"x" * 64, max_bytes=8)
        self.assertIn("juda katta", str(ctx.exception))

    def test_non_image_bytes_are_rejected(self):
        with self.assertRaises(OCRValidationError):
            validate_image_bytes(b"this is plainly not an image")

    def test_truncated_png_is_rejected(self):
        with self.assertRaises(OCRValidationError):
            validate_image_bytes(png_bytes()[:20])

    def test_valid_png_is_accepted_and_reports_its_mime_type(self):
        self.assertEqual(validate_image_bytes(png_bytes()), "image/png")

    def test_valid_jpeg_is_accepted(self):
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (8, 8), (10, 20, 30)).save(buffer, format="JPEG")
        self.assertEqual(validate_image_bytes(buffer.getvalue()), "image/jpeg")

    def test_normalization_reencodes_to_jpeg_for_the_provider(self):
        normalized, mime = normalize_image(png_bytes())
        self.assertEqual(mime, "image/jpeg")
        # The normalized bytes must themselves be a valid image.
        self.assertEqual(validate_image_bytes(normalized), "image/jpeg")

    def test_normalization_is_deterministic_for_the_same_input(self):
        first, _ = normalize_image(png_bytes(color=(1, 2, 3)))
        second, _ = normalize_image(png_bytes(color=(1, 2, 3)))
        self.assertEqual(first, second)


class ProviderResolutionTests(TestCase):
    @override_settings(ESSAY_OCR_PROVIDER="")
    def test_default_configuration_reports_ocr_as_unavailable(self):
        self.assertFalse(ocr_available())
        self.assertIsInstance(get_provider(), NullOCRProvider)

    @override_settings(ESSAY_OCR_PROVIDER="does-not-exist")
    def test_unknown_provider_name_degrades_to_unavailable(self):
        self.assertFalse(ocr_available())
        self.assertIsInstance(get_provider(), NullOCRProvider)

    @override_settings(
        ESSAY_OCR_PROVIDER="openrouter_vision", ESSAY_OCR_VISION_MODEL=""
    )
    def test_vision_provider_is_unavailable_without_a_model(self):
        self.assertFalse(get_provider("openrouter_vision").is_available())

    @override_settings(
        ESSAY_OCR_PROVIDER="openrouter_vision",
        ESSAY_OCR_VISION_MODEL="",
        OPENROUTER_API_KEY="",
        GROQ_API_KEY="",
    )
    def test_vision_provider_is_unavailable_without_credentials(self):
        self.assertFalse(OpenRouterVisionProvider().is_available())

    @override_settings(
        ESSAY_OCR_PROVIDER="openrouter_vision",
        ESSAY_OCR_VISION_MODEL="some/multimodal-model",
        OPENROUTER_API_KEY="sk-or-v1-testkey000000000000000000000000000000",
    )
    def test_vision_provider_activates_once_both_are_configured(self):
        self.assertTrue(ocr_available())
        self.assertTrue(OpenRouterVisionProvider().is_available())

    def test_null_provider_raises_instead_of_returning_empty_text(self):
        with self.assertRaises(OCRUnavailable) as ctx:
            NullOCRProvider().extract([png_bytes()], languages=DEFAULT_LANGUAGES)
        message = str(ctx.exception)
        self.assertIn("OCR", message)
        self.assertNotEqual(message.strip(), "")


class ExtractionTests(TestCase):
    @override_settings(ESSAY_OCR_PROVIDER="")
    def test_empty_page_list_is_rejected(self):
        with self.assertRaises(OCRValidationError):
            extract_text([])

    @override_settings(ESSAY_OCR_PROVIDER="", ESSAY_IMAGE_MAX_PAGES=2)
    def test_too_many_pages_is_rejected(self):
        pages = [png_bytes() for _ in range(3)]
        with self.assertRaises(OCRValidationError) as ctx:
            extract_text(pages)
        self.assertIn("sahifa", str(ctx.exception))

    @override_settings(ESSAY_OCR_PROVIDER="", ESSAY_IMAGE_MAX_PAGES=10)
    def test_page_count_within_the_limit_reaches_the_provider(self):
        """Two pages is inside the limit, so the failure must be unavailability."""
        pages = [png_bytes() for _ in range(2)]
        with self.assertRaises(OCRUnavailable):
            extract_text(pages)

    @override_settings(ESSAY_OCR_PROVIDER="")
    def test_unavailable_provider_never_yields_empty_or_placeholder_text(self):
        """The whole point: a picture must not silently become a zero score."""
        with self.assertRaises(OCRUnavailable):
            extract_text([png_bytes()])

    def test_an_invalid_page_is_rejected_before_the_provider_runs(self):
        provider = _RecordingProvider()
        with (
            patch.dict(_REGISTRY, {"recording": provider}),
            override_settings(
                ESSAY_OCR_PROVIDER="recording",
            ),
        ):
            with self.assertRaises(OCRValidationError):
                extract_text([png_bytes(), b"not-an-image"])
        self.assertEqual(provider.received, [])

    def test_pages_reach_the_provider_in_submission_order(self):
        first_page, _ = normalize_image(png_bytes(color=(255, 0, 0)))
        second_page, _ = normalize_image(png_bytes(color=(0, 0, 255)))
        provider = _RecordingProvider()

        with (
            patch.dict(_REGISTRY, {"recording": provider}),
            override_settings(
                ESSAY_OCR_PROVIDER="recording",
            ),
        ):
            result = extract_text(
                [
                    png_bytes(color=(255, 0, 0)),
                    png_bytes(color=(0, 0, 255)),
                ]
            )

        self.assertEqual(provider.received, [first_page, second_page])
        self.assertEqual(provider.languages, DEFAULT_LANGUAGES)
        self.assertIsInstance(result, OCRResult)
        self.assertEqual(result.provider, "recording")

    def test_multi_page_essay_is_one_extraction_call(self):
        """A three-page album is ONE image essay: one extraction, not three."""
        provider = _RecordingProvider()
        with (
            patch.dict(_REGISTRY, {"recording": provider}),
            override_settings(
                ESSAY_OCR_PROVIDER="recording",
            ),
        ):
            extract_text([png_bytes(), png_bytes(), png_bytes()])
        self.assertEqual(len(provider.received), 3)
        self.assertEqual(provider.extract_calls, 1)

    def test_a_very_short_transcription_is_flagged_for_review(self):
        provider = _RecordingProvider(text="ok")
        with (
            patch.dict(_REGISTRY, {"recording": provider}),
            override_settings(
                ESSAY_OCR_PROVIDER="recording",
            ),
        ):
            result = extract_text([png_bytes()])
        self.assertTrue(result.is_probably_incomplete)
        self.assertTrue(result.warnings)

    def test_a_full_transcription_is_not_flagged(self):
        provider = _RecordingProvider(
            text="Bu juda uzun va to'liq esse matni bo'lib, tekshirishga yaroqli.",
        )
        with (
            patch.dict(_REGISTRY, {"recording": provider}),
            override_settings(
                ESSAY_OCR_PROVIDER="recording",
            ),
        ):
            result = extract_text([png_bytes()])
        self.assertFalse(result.is_probably_incomplete)
        self.assertEqual(result.warnings, [])


class ResultShapeTests(TestCase):
    def test_short_text_is_incomplete_and_long_text_is_not(self):
        self.assertTrue(OCRResult(text="qisqa").is_probably_incomplete)
        self.assertFalse(OCRResult(text="a" * 200).is_probably_incomplete)

    def test_page_dataclass_keeps_the_page_index(self):
        page = OCRPage(index=2, text="Ikkinchi sahifa", confidence=0.9)
        self.assertEqual(page.index, 2)
        self.assertEqual(page.confidence, 0.9)

    def test_default_result_has_no_confidence_claim(self):
        """The vision provider exposes no confidence score, and we do not invent one."""
        self.assertIsNone(OCRResult(text="a" * 100).confidence)

    def test_provider_output_is_split_on_page_markers_in_order(self):
        raw = (
            "--- PAGE 1 ---\nBirinchi sahifa matni\n"
            "--- PAGE 2 ---\nIkkinchi sahifa matni\n"
            "--- PAGE 3 ---\nUchinchi sahifa matni"
        )
        pages = _split_pages(raw)
        self.assertEqual(len(pages), 3)
        self.assertIn("Birinchi", pages[0])
        self.assertIn("Ikkinchi", pages[1])
        self.assertIn("Uchinchi", pages[2])

    def test_split_without_markers_returns_the_whole_text(self):
        self.assertEqual(_split_pages("Faqat bitta sahifa"), ["Faqat bitta sahifa"])

    def test_split_ignores_marker_case_and_dashes(self):
        raw = "-- page 1 --\nAlpha\n---- Page 2 ----\nBeta"
        pages = _split_pages(raw)
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0], "Alpha")
        self.assertEqual(pages[1], "Beta")


class _RecordingProvider:
    """Test double that records the exact pages handed to a provider."""

    name = "recording"

    def __init__(self, text: str | None = None):
        self.received: list[bytes] = []
        self.languages: tuple[str, ...] = ()
        self.extract_calls = 0
        self._text = text or (
            "Bu sinov uchun yetarlicha uzun matn bo'lib, bir nechta jumladan iborat."
        )

    def is_available(self) -> bool:
        return True

    def extract(self, pages, *, languages):
        self.extract_calls += 1
        self.received = list(pages)
        self.languages = tuple(languages)
        return OCRResult(
            text=self._text,
            pages=[OCRPage(index=i, text=self._text) for i, _ in enumerate(pages)],
            provider=self.name,
        )
