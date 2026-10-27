"""
Pre-validation engine for essay submissions.

Executes a 3-stage instant (<0.01s) filter before invoking DeepSeek-R1
or consuming the user's AI quota:
1. Minimum word count (>= 60 words)
2. Gibberish & repetition detection (character repetition, >35-char tokens, keyboard smashes, repetitive word spam)
3. Language / lexical validity (vowel distribution & recognizable Uzbek/English vocabulary)
"""

from collections import Counter
import re


class PreValidationError(ValueError):
    """Raised when an essay fails instant pre-validation before AI grading."""

    pass


# Vowels for Uzbek (Latin + Cyrillic) and English
VOWELS_PATTERN = re.compile(r"[aeiouyAEIOUYаеёиоуыэюяАЕЁИОУЫЭЮЯ]")

# Single character repeated 5+ times (e.g. aaaaa, 11111, zzzzz)
CHAR_REPEAT_PATTERN = re.compile(
    r"([a-zA-Zа-яА-ЯёЁ0-9])\1{4,}",
    re.UNICODE,
)

# Keyboard smash patterns (e.g. asdfasdf, qwertyqwerty, asdasdasd)
KEYBOARD_SMASH_PATTERN = re.compile(
    r"(?:asdf|qwer|zxcv|asdasd|jkl;|ghjk|qwerty|tyui|dfgh|12345){2,}",
    re.IGNORECASE,
)

# 4+ consecutive identical words (e.g. 'salom salom salom salom')
CONSECUTIVE_WORDS_PATTERN = re.compile(
    r"\b(\w+)\b(?:\s+\1\b){3,}",
    re.IGNORECASE | re.UNICODE,
)

# High frequency recognized words in Uzbek (Latin & Cyrillic) and English
COMMON_VOCABULARY = {
    # Uzbek Latin
    "va",
    "ham",
    "bu",
    "bir",
    "bilan",
    "uchun",
    "deb",
    "esa",
    "bor",
    "yo'q",
    "yoq",
    "kerak",
    "men",
    "sen",
    "u",
    "biz",
    "siz",
    "ular",
    "o'z",
    "oz",
    "har",
    "hech",
    "qanday",
    "nima",
    "qachon",
    "nega",
    "chunki",
    "ammo",
    "lekin",
    "biroq",
    "agar",
    "go'yo",
    "yoki",
    "balki",
    "shu",
    "o'sha",
    "osha",
    "mana",
    "ana",
    "inson",
    "odam",
    "hayot",
    "ta'lim",
    "talim",
    "jamiyat",
    "davlat",
    "bola",
    "maktab",
    "kitob",
    "ilm",
    "fan",
    "rivojlanish",
    "kelajak",
    "vaqt",
    "kun",
    "yil",
    "muhim",
    "asosiy",
    "katta",
    "yangi",
    "yaxshi",
    "yomon",
    "to'g'ri",
    "togri",
    "xato",
    "fikr",
    "xulosa",
    "misol",
    "sabab",
    "natija",
    "shuning",
    "albatta",
    "darvoqe",
    "masalan",
    "avvalo",
    "birinchidan",
    "ikkinchidan",
    "yakunida",
    "ko'ra",
    "kora",
    "bo'yicha",
    "boyicha",
    "haqida",
    "tomonidan",
    "orqali",
    "qilish",
    "qilmoq",
    "bo'lish",
    "bolish",
    "aytish",
    "o'rganish",
    "organish",
    "yozish",
    "o'qish",
    "oqish",
    "ishlash",
    "yashash",
    "yoshlar",
    "farzand",
    "ota",
    "ona",
    "oila",
    "kasb",
    "hunar",
    "dunyo",
    "mamlakat",
    "shahar",
    "qishloq",
    "o'quvchi",
    "talaba",
    "ustoz",
    "o'qituvchi",
    "til",
    "ona tili",
    "adabiyot",
    "madaniyat",
    "tarix",
    "qadriyat",
    "tarbiya",
    "odob",
    "axloq",
    # Uzbek Cyrillic
    "ва",
    "ҳам",
    "бу",
    "бир",
    "билан",
    "учун",
    "деб",
    "эса",
    "бор",
    "йўқ",
    "керак",
    "мен",
    "сен",
    "у",
    "биз",
    "сиз",
    "улар",
    "ўз",
    "ҳар",
    "ҳеч",
    "қандай",
    "нима",
    "қачон",
    "нега",
    "чунки",
    "аммо",
    "лекин",
    "бироқ",
    "агар",
    "ёки",
    "балки",
    "шу",
    "ўша",
    "мана",
    "ана",
    "инсон",
    "одам",
    "ҳаёт",
    "таълим",
    "жамият",
    "давлат",
    "бола",
    "мактаб",
    "китоб",
    "илм",
    "фан",
    "ривожланиш",
    "келажак",
    "вақт",
    "кун",
    "йил",
    "муҳим",
    "асосий",
    "катта",
    "янги",
    "яхши",
    "ёмон",
    "тўғри",
    "хато",
    "фикр",
    "хулоса",
    "мисол",
    "сабаб",
    "натижа",
    "шунинг",
    "албатта",
    "масалан",
    "аввало",
    "биринчидан",
    "иккинчидан",
    "якунида",
    "кўра",
    "бўйича",
    "ҳақида",
    # English
    "the",
    "be",
    "to",
    "of",
    "and",
    "a",
    "in",
    "that",
    "have",
    "i",
    "it",
    "for",
    "not",
    "on",
    "with",
    "he",
    "as",
    "you",
    "do",
    "at",
    "this",
    "but",
    "his",
    "by",
    "from",
    "they",
    "we",
    "say",
    "her",
    "she",
    "or",
    "an",
    "will",
    "my",
    "one",
    "all",
    "would",
    "there",
    "their",
    "what",
    "so",
    "up",
    "out",
    "if",
    "about",
    "who",
    "get",
    "which",
    "go",
    "me",
    "when",
    "make",
    "can",
    "like",
    "time",
    "no",
    "just",
    "him",
    "know",
    "take",
    "people",
    "into",
    "year",
    "your",
    "good",
    "some",
    "could",
    "them",
    "see",
    "other",
    "than",
    "then",
    "now",
    "look",
    "only",
    "come",
    "its",
    "over",
    "think",
    "also",
    "back",
    "after",
    "use",
    "two",
    "how",
    "our",
    "work",
    "first",
    "well",
    "way",
    "even",
    "new",
    "want",
    "because",
    "any",
    "these",
    "give",
    "day",
    "most",
    "us",
    "education",
    "society",
    "development",
    "important",
    "future",
    "reason",
    "example",
    "conclusion",
    "however",
    "therefore",
    "furthermore",
    "moreover",
    "opinion",
    "believe",
    "agree",
    "disagree",
    "firstly",
    "secondly",
    "finally",
    "overall",
    "technology",
    "government",
    "problem",
    "solution",
    "environment",
    "health",
    "children",
    "students",
    "teachers",
    "school",
    "university",
    "world",
    "life",
    "many",
    "much",
    "such",
    "different",
    "several",
}

# Regex to extract words (supporting Uzbek apostrophes o' and g')
WORD_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁo'g'shch0-9\-']+", re.UNICODE)


def count_essay_words(text: str) -> int:
    """Accurately count words in essay text."""
    if not text:
        return 0
    return len(WORD_RE.findall(text))


def pre_validate_essay(text: str, topic_title: str = "", min_words: int = 60) -> dict:
    """
    Execute a 3-stage instant pre-validation filter on the submitted essay text.

    Args:
        text: The essay text submitted by the user.
        topic_title: Optional topic title for context.
        min_words: Minimum required words (defaults to 60).

    Returns:
        dict: {"valid": True, "word_count": int}

    Raises:
        PreValidationError: When the essay is too short (< min_words),
            contains gibberish / repetition, or fails language/lexical validity.
    """
    cleaned_text = (text or "").strip()
    if not cleaned_text:
        raise PreValidationError("Esse matni bo'sh.")

    words = WORD_RE.findall(cleaned_text)
    word_count = len(words)

    # ------------------------------------------------------------------
    # Stage 1: Word Count Check
    # ------------------------------------------------------------------
    if min_words > 0 and word_count < min_words:
        raise PreValidationError(
            f"⚠️ Esse juda qisqa (kamida {min_words} ta so'z bo'lishi shart). "
            f"Hozirgi so'zlar soni: {word_count} ta."
        )

    # ------------------------------------------------------------------
    # Stage 2: Gibberish & Repetition Check
    # ------------------------------------------------------------------
    # 2a. Character repetition (e.g. aaaaa, zzzzz)
    if CHAR_REPEAT_PATTERN.search(cleaned_text):
        raise PreValidationError(
            "⛔ Matn tushunarsiz yoki safsata deb topildi. Iltimos, haqiqiy esse matnini kiriting."
        )

    # 2b. Long unbroken token (> 35 characters)
    for word in words:
        # Strip internal apostrophes or hyphens for length check
        clean_w = word.replace("'", "").replace("-", "")
        if len(clean_w) > 35:
            raise PreValidationError(
                "⛔ Matn tushunarsiz yoki safsata deb topildi. Iltimos, haqiqiy esse matnini kiriting."
            )

    # 2c. Keyboard smash pattern (e.g. asdfasdf, qwertyqwerty)
    if KEYBOARD_SMASH_PATTERN.search(cleaned_text):
        raise PreValidationError(
            "⛔ Matn tushunarsiz yoki safsata deb topildi. Iltimos, haqiqiy esse matnini kiriting."
        )

    # 2d. 4+ consecutive identical words (e.g. "salom salom salom salom")
    if CONSECUTIVE_WORDS_PATTERN.search(cleaned_text):
        raise PreValidationError(
            "⛔ Matn tushunarsiz yoki safsata deb topildi. Iltimos, haqiqiy esse matnini kiriting."
        )

    # 2e. Single word dominance (one word repeating > 35% of total essay)
    counts = Counter(w.lower() for w in words)
    most_common_word, most_common_count = counts.most_common(1)[0]
    if (most_common_count / word_count) > 0.35 and word_count >= 60:
        raise PreValidationError(
            "⛔ Matn tushunarsiz yoki safsata deb topildi. Iltimos, haqiqiy esse matnini kiriting."
        )

    # ------------------------------------------------------------------
    # Stage 3: Language & Lexical Validity Check
    # ------------------------------------------------------------------
    # 3a. Vowel presence in words >= 3 characters
    significant_words = [w for w in words if len(w) >= 3]
    if significant_words:
        no_vowel_words = sum(
            1 for w in significant_words if not VOWELS_PATTERN.search(w)
        )
        if (no_vowel_words / len(significant_words)) > 0.30:
            raise PreValidationError(
                "⛔ Matn tushunarsiz yoki safsata deb topildi. Iltimos, haqiqiy esse matnini kiriting."
            )

    # 3b. Overall vowel-to-letter ratio (natural text is typically 25% - 65%)
    all_letters = re.findall(r"[a-zA-Zа-яА-ЯёЁ]", cleaned_text)
    if all_letters:
        vowel_letters = re.findall(r"[aeiouyAEIOUYаеёиоуыэюяАЕЁИОУЫЭЮЯ]", cleaned_text)
        vowel_ratio = len(vowel_letters) / len(all_letters)
        if vowel_ratio < 0.15 or vowel_ratio > 0.75:
            raise PreValidationError(
                "⛔ Matn tushunarsiz yoki safsata deb topildi. Iltimos, haqiqiy esse matnini kiriting."
            )

    # 3c. Lexical validity / recognizable vocabulary check
    # Check what fraction of words match either the common vocabulary set
    # OR standard grammatical suffixes (e.g. -lar, -ning, -ga, -da, -dan, -ing, -ed, -ly, -tion)
    recognized_count = 0
    for word in words:
        w_lower = word.lower().strip("'-")
        if w_lower in COMMON_VOCABULARY:
            recognized_count += 1
            continue

        # Morphological patterns for Uzbek & English
        # Uzbek suffixes: -lar, -ning, -ga, -da, -dan, -ni, -roq, -siz, -lik, -chi, -moq, -dilar
        # English suffixes: -ing, -ed, -ly, -tion, -ment, -ness, -able, -ful, -less, -ize
        uzbek_endings = (
            "lar",
            "ning",
            "ga",
            "da",
            "dan",
            "ni",
            "roq",
            "siz",
            "lik",
            "chi",
            "moq",
            "dilar",
            "shdi",
            "yapti",
            "gan",
            "kan",
            "qan",
            "uvchi",
            "ovchi",
            "vchi",
            "lari",
            "imiz",
            "ingiz",
            "miz",
            "siz",
            "dir",
            "dek",
            "day",
            "cha",
            "gacha",
        )
        english_endings = (
            "ing",
            "ed",
            "ly",
            "tion",
            "ment",
            "ness",
            "able",
            "ful",
            "less",
            "ize",
            "ise",
            "est",
            "er",
            "al",
            "ic",
            "ous",
            "ive",
            "ity",
        )
        if any(w_lower.endswith(end) for end in uzbek_endings) or any(
            w_lower.endswith(end) for end in english_endings
        ):
            recognized_count += 1
            continue

        # Valid 2-letter or 1-letter words in context
        if len(w_lower) in (1, 2) and any(
            c in "aeiouyаеёиоуыэюяuoi" for c in w_lower
        ):
            recognized_count += 1
            continue

        # If word has at least 1 vowel and reasonable consonant clusters (no 5+ consecutive consonants)
        if VOWELS_PATTERN.search(w_lower) and not re.search(
            r"[bcdfghjklmnpqrstvwxzBCDFGHJKLMNPQRSTVWXZ]{5,}", w_lower
        ):
            recognized_count += 1

    lexical_ratio = recognized_count / word_count
    if lexical_ratio < 0.60:
        raise PreValidationError(
            "⛔ Matn tushunarsiz yoki safsata deb topildi. Iltimos, haqiqiy esse matnini kiriting."
        )

    return {"valid": True, "word_count": word_count}
