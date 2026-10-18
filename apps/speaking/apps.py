from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SpeakingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.speaking"
    verbose_name = _("AI Speaking Simulyatori")
