"""WebSocket URL routing for the notifications application."""

from django.urls import URLPattern, URLResolver, re_path

from . import consumers

# WebSocket URL patterns — mounted by settings/asgi.py via URLRouter.
#
# re_path() stubs only accept standard Django views, but Channels consumers
# use as_asgi() which returns an _ASGIApplicationProtocol — a type unknown
# to Django stubs.  We suppress the overload mismatch and annotate the list
# as list[URLPattern | URLResolver] which is what URLRouter expects.
websocket_urlpatterns: list[URLPattern | URLResolver] = [ # type: ignore
    re_path(  # type: ignore[arg-type]
        r"^ws/posts/(?P<slug>[-\w]+)/comments/$",
        consumers.CommentConsumer.as_asgi(), # pyright: ignore[reportArgumentType]
    ),
]