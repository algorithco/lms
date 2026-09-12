"""
Accounts signals — automatic Profile creation on User save.

When a new User is created, a corresponding Profile is automatically
created via Django's post_save signal. This eliminates the need for
manual Profile creation in every registration endpoint.
"""
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(
    sender: type,
    instance: "settings.AUTH_USER_MODEL",  # type: ignore[name-defined]
    created: bool,
    **kwargs,
) -> None:
    """
    Signal: Yangi User yaratilganda avtomatik Profile yaratadi.

    Args:
        sender: Model class (User).
        instance: Yaratilgan User instance.
        created: True agar yangi yaratilgan bo'lsa.
    """
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(
    sender: type,
    instance: "settings.AUTH_USER_MODEL",  # type: ignore[name-defined]
    **kwargs,
) -> None:
    """
    Signal: User saqlanganda Profile ni ham saqlaydi.

    Bu signal user.profile ni o'zgartirgandan keyin
    avtomatik save qilishni ta'minlaydi.
    """
    if hasattr(instance, "profile"):
        instance.profile.save()
