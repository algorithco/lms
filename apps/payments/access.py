"""Payment administration authorization."""

from apps.accounts.access import has_platform_permission


def can_manage_payments(user) -> bool:
    """Only active platform administrators may approve or reject payments."""
    return has_platform_permission(user, "payments.change_paymentrequest")
