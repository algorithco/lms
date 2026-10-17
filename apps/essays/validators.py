"""
Validators and constraints for essay submissions and topics.
"""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

MIN_WORDS_DEFAULT = 200
MAX_WORDS_DEFAULT = 500


def validate_essay_word_count(
    word_count: int,
    min_words: int = MIN_WORDS_DEFAULT,
    max_words: int = MAX_WORDS_DEFAULT,
) -> None:
    """Validate that the word count falls within [min_words, max_words]."""
    if word_count < min_words:
        raise ValidationError(
            _(f"Esse matni hajmi yetarli emas: {word_count}/{min_words} so'z.")
        )
    if max_words > 0 and word_count > max_words:
        raise ValidationError(
            _(f"Esse matni hajmi belgilangan chegaradan oshib ketdi: {word_count}/{max_words} so'z.")
        )
