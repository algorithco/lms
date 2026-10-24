"""
Telegram Bot App Module (apps.bot).
Provides seamless integration between the Telegram Bot, Backend Services,
Quota Enforcement, and Teacher CRM.
"""

from apps.notifications.bot.handlers import setup_handlers

__all__ = ["setup_handlers"]
