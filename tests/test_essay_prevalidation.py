"""
Unit tests for AI Token Bleeding Pre-Validation Filter.

Validates the 3-stage instant filter:
1. Short word count (< 60 words) rejected immediately
2. Gibberish & repetition (character repeat, long tokens, keyboard smash, repetitive word spam)
3. Language / lexical validity (vowel distribution and recognized vocabulary)
"""

import pytest
from apps.essays.pre_validation import PreValidationError, count_essay_words, pre_validate_essay
from apps.essays.services import grade_essay, grade_ielts_essay


@pytest.mark.django_db
class TestEssayPreValidation:
    """Test instant pre-validation edge cases and integration with grading pipelines."""

    def test_empty_or_whitespace_text(self):
        with pytest.raises(PreValidationError, match="bo'sh"):
            pre_validate_essay("")

        with pytest.raises(PreValidationError, match="bo'sh"):
            pre_validate_essay("   \n\t  ")

    def test_short_essay_rejected(self):
        short_text = "Bu juda qisqa insho matni bo'lib, jami o'nta so'zdan iborat."
        with pytest.raises(PreValidationError) as exc_info:
            pre_validate_essay(short_text)
        assert "kamida 60 ta so'z" in str(exc_info.value)
        assert "⚠️ Esse juda qisqa" in str(exc_info.value)

    def test_character_repetition_rejected(self):
        # 60+ words but contains aaaaaa
        text = "Salom " * 59 + " aaaaaa "
        with pytest.raises(PreValidationError, match="safsata deb topildi"):
            pre_validate_essay(text)

    def test_long_token_rejected(self):
        # 60+ words but contains unbroken 36-char string
        long_tok = "a" * 36
        text = ("Bu bir sinov uchun yozilgan matn bo'lib insho hisoblanadi. " * 7) + f" {long_tok} xulosa."
        with pytest.raises(PreValidationError, match="safsata deb topildi"):
            pre_validate_essay(text)

    def test_keyboard_smash_rejected(self):
        text = ("Bu bir sinov uchun yozilgan matn bo'lib insho hisoblanadi. " * 8) + " asdfasdfasdf qwertyqwerty "
        with pytest.raises(PreValidationError, match="safsata deb topildi"):
            pre_validate_essay(text)

    def test_repetitive_word_spam_rejected(self):
        # Same word repeated 65 times
        text = "salom " * 65
        with pytest.raises(PreValidationError, match="safsata deb topildi"):
            pre_validate_essay(text)

    def test_consecutive_identical_words_rejected(self):
        text = ("Bu bir yaxshi ta'lim haqidagi insho bo'lib yozildi. " * 8) + " kitob kitob kitob kitob natija."
        with pytest.raises(PreValidationError, match="safsata deb topildi"):
            pre_validate_essay(text)

    def test_no_vowels_gibberish_rejected(self):
        # Many consonant words without vowels
        text = "bcdfghjklmnp " * 65
        with pytest.raises(PreValidationError, match="safsata deb topildi"):
            pre_validate_essay(text)

    def test_valid_uzbek_essay_passes(self):
        essay = (
            "Hozirgi zamonda ta'lim va tarbiya har bir jamiyatning kelajagini belgilab beruvchi eng asosiy "
            "omillardan biri hisoblanadi. Yoshlarning bilim olishga bo'lgan intilishi mamlakatimiz ravnaqi va "
            "rivojlanishi uchun nihoyatda muhimdir. Maktablarda va oliy ta'lim muassasalarida zamonaviy axborot "
            "texnologiyalarini keng joriy etish orqali yosh avlodga sifatli bilim berish mumkin. Shuningdek, "
            "har bir inson o'z ustida muntazam ishlab, yangi kasb-hunarlarni egallashi darkor. Xulosa qilib "
            "aytganda, ilm va ma'rifat barcha muammolarning eng to'g'ri va oqilona yechimidir. Shu sababli "
            "yoshlarimizni doimo qo'llab-quvvatlashimiz va ularga imkoniyat yaratishimiz lozim."
        )
        res = pre_validate_essay(essay, topic_title="Ta'limning jamiyatdagi o'rni")
        assert res["valid"] is True
        assert res["word_count"] >= 60

    def test_valid_english_essay_passes(self):
        essay = (
            "Education plays a crucial role in the development of modern society. Nowadays, young people have "
            "various opportunities to acquire knowledge and develop practical skills using digital technologies. "
            "Many schools and universities are integrating advanced methods to enhance the learning process. "
            "Furthermore, individuals should continuously improve their abilities to stay competitive in the "
            "rapidly changing global job market. In conclusion, investing in education is essential for ensuring "
            "sustainable progress and a prosperous future for the upcoming generations around the world."
        )
        res = pre_validate_essay(essay, topic_title="Importance of Education")
        assert res["valid"] is True
        assert res["word_count"] >= 60

    def test_grade_essay_rejects_gibberish_without_llm_call(self):
        with pytest.raises(PreValidationError):
            grade_essay("qisqa esse matni", topic_title="Mavzu")

    def test_grade_ielts_essay_rejects_short_without_llm_call(self):
        with pytest.raises(PreValidationError):
            grade_ielts_essay("This is a short text for testing.", topic_title="Topic")
