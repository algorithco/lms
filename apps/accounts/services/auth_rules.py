"""
SimpleJWT authentication rules for account security and ban checks.
"""


def user_authentication_rule(user):
    """
    Ensures user is active and not banned due to fraud strikes.
    """
    return bool(
        user is not None and user.is_active and not getattr(user, "is_banned", False)
    )
