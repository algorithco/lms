"""
ASGI config for LMS Platform.

Supports both HTTP and WebSocket protocols via Django Channels.
"""
import os

from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

# Initialize Django ASGI application
django_asgi_app = get_asgi_application()

# Import WebSocket routing
from apps.arena.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    # HTTP requests
    "http": django_asgi_app,

    # WebSocket requests
    "websocket": AllowedHostsOriginValidator(AuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    )),
})
