"""Views for the notifications application.

Implements three real-time / near-real-time communication patterns:

1. **WebSocket** (CommentConsumer in consumers.py) — persistent bidirectional
   connection; ideal for interactive, low-latency comment feeds.

2. **SSE** (PostStreamView) — persistent server-to-client stream; ideal for
   one-way event broadcasts such as "a new post was published".  Simpler than
   WebSockets because no bidirectional protocol is needed.  Choose WebSockets
   when the client also needs to send messages; choose SSE when the flow is
   server → client only.

3. **HTTP Polling** (NotificationCountView, NotificationListView,
   MarkNotificationsReadView) — the client periodically requests the current
   state.  Trade-off: simple to implement and debug, but introduces latency
   equal to the polling interval and adds constant server load even when
   there is nothing new.  Acceptable when near-real-time (seconds of delay)
   is sufficient and the user base is small.  Switch to WebSockets or SSE
   when you need sub-second updates or have many concurrent users.
"""

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, cast

from django.conf import settings
from django.http import HttpRequest, StreamingHttpResponse
from rest_framework.permissions import (  # type: ignore[import-untyped]
    IsAuthenticated,
)
from rest_framework.request import Request  # type: ignore[import-untyped]
from rest_framework.response import Response  # type: ignore[import-untyped]
from rest_framework.views import APIView  # type: ignore[import-untyped]

from apps.users.models import User

from .models import Notification
from .serializers import (  # type: ignore[attr-defined]
    NotificationSerializer,
)

logger = logging.getLogger(__name__)

# Redis channel used to fan out SSE post-publication events.
SSE_CHANNEL: str = "sse_post_published"


# ---------------------------------------------------------------------------
# SSE — post publication stream
# ---------------------------------------------------------------------------


class PostStreamView(APIView):  # type: ignore[misc]
    """Stream newly published posts as Server-Sent Events.

    Endpoint: GET /api/posts/stream/

    No authentication required — the feed is public.

    Why SSE here instead of WebSockets?
    ------------------------------------
    Post-publication events flow in one direction only: server → client.
    SSE uses a plain HTTP connection and is natively supported by browsers
    via the ``EventSource`` API, making it simpler to implement and deploy
    (no upgrade handshake, no extra protocol).  WebSockets would be overkill
    here because the client never needs to send messages back to the server.
    """

    authentication_classes: list[Any] = []
    permission_classes: list[Any] = []

    async def get(
        self,
        request: HttpRequest,
        *args: Any,
        **kwargs: Any,
    ) -> StreamingHttpResponse:
        """Open an SSE stream and forward post-publication events.

        Args:
            request: The incoming HTTP request.

        Returns:
            A streaming ``text/event-stream`` response.
        """
        return StreamingHttpResponse(
            # Encode each str chunk to bytes — StreamingHttpResponse
            # requires AsyncIterable[bytes], not AsyncIterable[str].
            self._event_stream_bytes(),
            content_type="text/event-stream",
            headers={
                # Prevent proxies and browsers from buffering the stream.
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    async def _event_stream_bytes(
        self,
    ) -> AsyncGenerator[bytes, None]:
        """Wrap ``_event_stream`` and encode each chunk to UTF-8 bytes.

        ``StreamingHttpResponse`` requires ``AsyncIterable[bytes]``.

        Yields:
            bytes: UTF-8 encoded SSE chunks.
        """
        async for chunk in self._event_stream():
            yield chunk.encode("utf-8")

    @staticmethod
    async def _event_stream() -> AsyncGenerator[str, None]:
        """Subscribe to Redis and yield SSE-formatted string events.

        Yields:
            str: SSE-formatted event strings (``data: ...\\n\\n``).
        """
        # local import — optional dependency
        import redis.asyncio as aioredis

        redis_url: str = settings.CACHES["default"]["LOCATION"]

        # redis.asyncio stubs are incomplete — suppress unknown-member
        # warnings for from_url / pubsub / subscribe / unsubscribe.
        # type: ignore comments suppress incomplete redis.asyncio stubs.
        redis_conn = await aioredis.from_url(  # type: ignore[misc]
            redis_url,
            decode_responses=True,
        )
        pubsub = redis_conn.pubsub()  # type: ignore[reportUnknownMemberType]
        await pubsub.subscribe(  # type: ignore[misc]
            SSE_CHANNEL
        )

        yield ": keep-alive\n\n"

        try:
            # pubsub.listen() yields untyped messages — cast each message
            # to a known dict shape so downstream access is type-safe.
            async for raw_message in (  # type: ignore[misc]
                pubsub.listen()  # type: ignore
            ):
                message: dict[str, str] = cast(
                    dict[str, str], raw_message
                )
                if message.get("type") != "message":
                    continue
                try:
                    raw_data: str = message.get("data", "")
                    data: dict[str, Any] = json.loads(raw_data)
                    yield f"data: {json.dumps(data)}\n\n"
                except json.JSONDecodeError:
                    logger.warning("SSE: invalid JSON in Redis message")
        finally:
            await pubsub.unsubscribe(  # type: ignore[reportUnknownMemberType]
                SSE_CHANNEL
            )
            await redis_conn.aclose()


# ---------------------------------------------------------------------------
# HTTP Polling — notification endpoints
# ---------------------------------------------------------------------------


class NotificationCountView(APIView):  # type: ignore[misc]
    """Return the number of unread notifications for the current user.

    Endpoint: GET /api/notifications/count/

    Polling trade-off
    -----------------
    Polling is simple: no persistent connection, no special infrastructure.
    The downside is latency (equal to the polling interval) and wasted
    requests when nothing has changed.  It is acceptable here because
    notification counts are not time-critical — a few seconds of delay is
    fine.  If the product required instant alerts (e.g. a live chat badge),
    WebSockets or SSE would be the right choice.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """Return the unread notification count.

        Args:
            request: The authenticated HTTP request.

        Returns:
            ``200 OK`` with ``{"unread_count": <int>}``.
        """
        # getattr bypasses Pylance's Unknown resolution for DRF Request.user.
        # The explicit User annotation makes all downstream access type-safe.
        user: User = getattr(request, "user")
        count: int = Notification.objects.filter(
            recipient=user,
            is_read=False,
        ).count()
        return Response({"unread_count": count})


class NotificationListView(APIView):  # type: ignore[misc]
    """List the current user's notifications (paginated).

    Endpoint: GET /api/notifications/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """Return a paginated list of notifications for the current user.

        Args:
            request: The authenticated HTTP request.

        Returns:
            ``200 OK`` with a list of serialized notifications.
        """
        user: User = getattr(request, "user")
        notifications = Notification.objects.filter(
            recipient=user,
        ).select_related("comment", "comment__author", "comment__post")

        serializer = NotificationSerializer(  # type: ignore[operator]
            notifications, many=True
        )
        return Response(serializer.data)  # type: ignore[union-attr]


class MarkNotificationsReadView(APIView):  # type: ignore[misc]
    """Mark all unread notifications as read for the current user.

    Endpoint: POST /api/notifications/read/
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """Mark all unread notifications as read.

        Args:
            request: The authenticated HTTP request.

        Returns:
            ``200 OK`` with ``{"marked_read": <int>}`` — the number of
            notifications that were updated.
        """
        user: User = getattr(request, "user")
        updated: int = Notification.objects.filter(
            recipient=user,
            is_read=False,
        ).update(is_read=True)

        logger.info(
            "Marked %d notifications as read for user %s",
            updated,
            user.email,
        )
        return Response({"marked_read": updated})