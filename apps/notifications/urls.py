"""URL configuration for the notifications application."""

from django.urls import path

from .views import (
    MarkNotificationsReadView,
    NotificationCountView,
    NotificationListView,
    PostStreamView,
)

urlpatterns = [ # type: ignore
    # SSE — real-time post publication stream (no auth required)
    path("posts/stream/", PostStreamView.as_view(), name="post-stream"), # type: ignore
    # HTTP Polling — notification endpoints (auth required)
    path(
        "notifications/",
        NotificationListView.as_view(), # type: ignore
        name="notification-list",
    ),
    path(
        "notifications/count/",
        NotificationCountView.as_view(), # type: ignore
        name="notification-count",
    ),
    path(
        "notifications/read/",
        MarkNotificationsReadView.as_view(), # type: ignore
        name="notification-read",
    ),
]