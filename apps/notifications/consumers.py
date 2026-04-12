"""WebSocket consumer for real-time comment notifications."""

import json
import logging
from typing import Any, cast

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken

from apps.blog.models import Post
from apps.users.models import User

logger = logging.getLogger(__name__)


class CommentConsumer(AsyncWebsocketConsumer):
    """Async WebSocket consumer that streams new comments for a single post.

    Connection URL:
        ws://<host>/ws/posts/<slug>/comments/?token=<jwt_access_token>

    Authentication:
        JWT access token passed as ``?token=`` query parameter.
        Unauthenticated connections are rejected with close code 4001.

    Post validation:
        If the post slug does not exist, the connection is rejected with
        close code 4004.

    Group naming convention:
        ``post_comments_<slug>`` — one Channels group per post.
        Messages are broadcast to all consumers in the group when a new
        comment is created via the REST API.

    Message format (received by the client)::

        {
            "comment_id": 42,
            "author": {"id": 1, "email": "user@example.com"},
            "body": "Great post!",
            "created_at": "2026-01-01T12:00:00Z"
        }
    """

    async def connect(self) -> None:
        """Authenticate the user, validate the post, and join the group."""
        # --- JWT authentication via query parameter -------------------------
        user = await self._authenticate()
        if user is None:
            # 4001 = unauthenticated
            await self.close(code=4001)
            return

        # --- Post existence check -------------------------------------------
        # scope["url_route"] is typed as _URLRoute (a TypedDict) by channels
        # stubs, which is not assignable to dict[str, Any] directly.
        # cast() tells Pylance to treat it as a plain dict so we can use
        # nested .get() calls safely without TypedDict access warnings.
        url_route = cast(dict[str, Any], self.scope.get("url_route", {}))
        slug: str = cast(dict[str, Any], url_route.get("kwargs", {})).get(
            "slug", ""
        )

        post_exists = await self._post_exists(slug)
        if not post_exists:
            # 4004 = not found
            await self.close(code=4004)
            return

        # --- Join the Channels group for this post --------------------------
        self.slug = slug
        self.group_name: str = f"post_comments_{slug}"
        self.user = user

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info(
            "WebSocket connected: user=%s post=%s", user.email, slug
        )

    async def disconnect(self, code: int) -> None:
        """Leave the Channels group on disconnect."""
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(
                self.group_name, self.channel_name
            )
            logger.info(
                "WebSocket disconnected: user=%s post=%s code=%s",
                getattr(self, "user", "unknown"),
                getattr(self, "slug", "unknown"),
                code,
            )

    async def receive(
        self,
        text_data: str | None = None,
        bytes_data: bytes | None = None,
        **kwargs: Any,
    ) -> None:
        """Ignore any messages sent by the client.

        This consumer is send-only: the server pushes comment events to
        the client; the client does not send messages.
        """

    # ------------------------------------------------------------------
    # Channels group message handler
    # ------------------------------------------------------------------

    async def new_comment(self, event: dict[str, Any]) -> None:
        """Forward a new-comment event from the Channels group to the client.

        This method is called by the Channels layer when another part of
        the application (e.g. a Celery task) sends a message to the group.

        Args:
            event: The message dict sent via ``channel_layer.group_send``.
                   Must contain a ``data`` key with the comment payload.
        """
        await self.send(text_data=json.dumps(event["data"]))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _authenticate(self) -> User | None:
        """Extract and validate the JWT token from the query string.

        Returns:
            The authenticated :class:`User` instance, or ``None`` if the
            token is missing, invalid, or the user does not exist.
        """
        query_string: bytes = self.scope.get("query_string", b"")
        params: dict[str, str] = dict(
            pair.split("=", 1)
            for pair in query_string.decode().split("&")
            if "=" in pair
        )
        token_str: str | None = params.get("token")

        if not token_str:
            logger.warning("WebSocket rejected: no token provided")
            return None

        try:
            # AccessToken.__init__ accepts a str token — the stub types the
            # parameter as Token | None, so we suppress the mismatch warning.
            token = AccessToken(token_str)  # type: ignore[arg-type]

            # token["user_id"] returns Any from the JWT payload; cast to int.
            user_id: int = int(token["user_id"])

            user = await sync_to_async(User.objects.get)(pk=user_id)
            return user
        except (TokenError, InvalidToken):
            logger.warning("WebSocket rejected: invalid token")
            return None
        except User.DoesNotExist:
            logger.warning("WebSocket rejected: user not found")
            return None

    @staticmethod
    async def _post_exists(slug: str) -> bool:
        """Return ``True`` if a post with the given slug exists.

        Args:
            slug: The post slug extracted from the URL.
        """
        return await sync_to_async(Post.objects.filter(slug=slug).exists)()
