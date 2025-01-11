from django.urls import path
from stream.consumers import CameraStreamConsumer, ScreenStreamConsumer  # unsolved reference ale dziala

websocket_urlpatterns = [
    path("ws/camera/", CameraStreamConsumer.as_asgi()),  # Routing kamery
    path("ws/screen/", ScreenStreamConsumer.as_asgi()),  # Routing pulpitu
]
