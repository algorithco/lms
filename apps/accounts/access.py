"""Shared platform-administrator policy.

``is_staff`` permits entry to Django's admin site, subject to its model
permissions. It does not grant the LMS's global management powers.
"""


def is_platform_admin(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and (
            getattr(user, "is_superuser", False)
            or getattr(user, "role", None) == "admin"
        )
    )


def has_platform_permission(user, permission: str) -> bool:
    """Allow platform admins or an explicitly delegated Django permission."""
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and (is_platform_admin(user) or user.has_perm(permission))
    )
