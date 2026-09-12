"""
Custom template tags for i18n support.

Usage:
    {% load i18n_extras %}
    {% t "login" %}
    {% t "register" %}
    {% current_language %}
"""
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def t(context, key: str, lang: str = "") -> str:
    """Translate a key using the user's language preference.

    An explicit ``lang`` argument overrides the request-based lookup —
    used by request-less renders such as email templates.
    """
    from apps.core.translations import t as translate, get_user_language

    if lang:
        return translate(key, lang)

    request = context.get("request")
    if request:
        language = get_user_language(request)
    else:
        language = "uz"

    return translate(key, language)


@register.simple_tag(takes_context=True)
def current_language(context) -> str:
    """Get current language code."""
    from apps.core.translations import get_user_language
    
    request = context.get("request")
    if request:
        return get_user_language(request)
    return "uz"


@register.simple_tag(takes_context=True)
def language_name(context) -> str:
    """Get current language display name."""
    from apps.core.translations import get_user_language, SUPPORTED_LANGUAGES
    
    request = context.get("request")
    if request:
        lang = get_user_language(request)
    else:
        lang = "uz"
    return SUPPORTED_LANGUAGES.get(lang, "O'zbek")
