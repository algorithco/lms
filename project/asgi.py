"""
ASGI Application with Lifespan support for graceful startup/shutdown.
"""
import os
import asyncio
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

from quiz.routing import websocket_urlpatterns
from essays.views import lifespan_manager

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project.settings')

# Initialize Django ASGI app early
django_asgi_app = get_asgi_application()


class LifespanWrapper:
    """
    Wraps ASGI app to handle lifespan protocol.
    Required for proper startup/shutdown with Uvicorn.
    """
    def __init__(self, app):
        self.app = app
        self._lifespan_ctx = lifespan_manager()
        self._started = False

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'lifespan':
            await self._handle_lifespan(receive, send)
        else:
            if not self._started:
                await self._lifespan_ctx.__aenter__()
                self._started = True
            await self.app(scope, receive, send)

    async def _handle_lifespan(self, receive, send):
        while True:
            message = await receive()
            if message['type'] == 'lifespan.startup':
                try:
                    await self._lifespan_ctx.__aenter__()
                    await send({'type': 'lifespan.startup.complete'})
                except Exception as e:
                    await send({'type': 'lifespan.startup.failed', 'message': str(e)})
            elif message['type'] == 'lifespan.shutdown':
                try:
                    await self._lifespan_ctx.__aexit__(None, None, None)
                    await send({'type': 'lifespan.shutdown.complete'})
                except Exception as e:
                    await send({'type': 'lifespan.shutdown.failed', 'message': str(e)})
                break


# Channel routing with auth middleware
websocket_application = AllowedHostsOriginValidator(
    AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    )
)

# Main ASGI application
application = ProtocolTypeRouter({
    'http': LifespanWrapper(django_asgi_app),
    'websocket': websocket_application,
})