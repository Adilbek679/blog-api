"""ASGI configuration for the blog project.

Supports both HTTP (Django) and WebSocket (Django Channels) protocols
via ``ProtocolTypeRouter``.
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.env.local")

# Initialise Django before importing any app code so that models and
# settings are available when the routing module is imported below.
django_asgi_app = get_asgi_application()

from apps.notifications.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        # Standard HTTP requests are handled by Django as usual.
        "http": django_asgi_app,
        # WebSocket connections are validated by origin, wrapped in the
        # standard Django session/auth middleware, then dispatched to the
        # URL router.
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(
                URLRouter(websocket_urlpatterns) # type: ignore
            )
        ),
    }
)