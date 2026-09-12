"""Deployment checks for Telegram webhook authentication."""
from django.conf import settings
from django.core.checks import Error, register


@register(deploy=True)
def webhook_secret_check(app_configs, **kwargs):
    if (
        getattr(settings, "TELEGRAM_WEBHOOK_MODE", False)
        and not getattr(settings, "TELEGRAM_WEBHOOK_SECRET", "")
    ):
        return [Error(
            "Telegram webhook mode requires TELEGRAM_WEBHOOK_SECRET.",
            hint="Set the same secret in Django and Telegram setWebhook before deployment.",
            id="notifications.E001",
        )]
    return []
