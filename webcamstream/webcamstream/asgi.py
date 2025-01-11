"""
ASGI config for webcamstream project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path
from stream.consumers import CameraStreamConsumer, ScreenStreamConsumer  # unsolved reference ale dziala

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "webcamstream.settings")

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter([
                path("ws/camera/", CameraStreamConsumer.as_asgi()),  # WebSocket dla kamery
                path("ws/screen/", ScreenStreamConsumer.as_asgi()),  # WebSocket dla pulpitu
            ])
        )
    ),
})
