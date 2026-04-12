"""ViewSets for the blog application (Post with comments and stats)."""

import asyncio
import json
import logging
from typing import Any

import httpx
import pytz
import redis
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, QuerySet
from django.utils import timezone, translation
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit  # type: ignore[import-untyped]
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Comment, Post, PostStatus
from .permissions import IsAuthorOrReadOnly
from .serializers import (
    CommentSerializer,
    PostCreateUpdateSerializer,
    PostSerializer,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

CACHE_KEY_POSTS_LIST: str = "published_posts_list"
CACHE_TTL_SECONDS: int = 60

# ---------------------------------------------------------------------------
# Redis pub/sub client (optional — gracefully disabled when unavailable)
# ---------------------------------------------------------------------------

try:
    # redis.Redis is not generic at runtime in redis-py < 5 — use type: ignore
    # to suppress Pylance's reportInvalidTypeArguments for the type parameter.
    redis_client: redis.Redis | None = redis.Redis.from_url(  # type: ignore[type-arg]
        settings.CACHES["default"]["LOCATION"]
    )
    redis_client.ping()
except redis.ConnectionError:
    logger.warning("Redis connection failed, pub/sub disabled")
    redis_client = None


class PostViewSet(viewsets.ModelViewSet):
    """CRUD ViewSet for :class:`~apps.blog.models.Post`.

    Authenticated users can create posts and manage their own content.
    Unauthenticated users can only read published posts.

    Routes:
        GET    /api/posts/                 – list posts
        POST   /api/posts/                 – create a post  (auth required)
        GET    /api/posts/{slug}/          – retrieve a post
        PATCH  /api/posts/{slug}/          – partial-update  (author only)
        PUT    /api/posts/{slug}/          – full-update     (author only)
        DELETE /api/posts/{slug}/          – delete          (author only)
        GET    /api/posts/{slug}/comments/ – list comments
        POST   /api/posts/{slug}/comments/ – add comment     (auth required)
        GET    /api/posts/stats/           – blog statistics
    """

    queryset = Post.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    lookup_field = "slug"

    # ------------------------------------------------------------------
    # Serializer & queryset selection
    # ------------------------------------------------------------------

    def get_serializer_class(self) -> type[drf_serializers.BaseSerializer]:
        """Return the appropriate serializer class based on the current action."""
        if self.action in ("create", "update", "partial_update"):
            return PostCreateUpdateSerializer
        return PostSerializer

    def get_queryset(self) -> QuerySet[Post]:
        """Filter posts based on the authentication state.

        - Anonymous users: only published posts.
        - Authenticated users (list action): own posts + published posts.
        - Authenticated users (detail actions): all posts (permission
          layer enforces object-level access).
        """
        queryset: QuerySet[Post] = Post.objects.select_related(
            "author", "category"
        ).prefetch_related("tags", "comments")

        if not self.request.user.is_authenticated:
            # Anonymous: show only published content.
            queryset = queryset.filter(status=PostStatus.PUBLISHED)
        elif self.action == "list":
            # Authenticated list: own drafts + all published.
            queryset = queryset.filter(
                Q(status=PostStatus.PUBLISHED) | Q(author=self.request.user)
            )

        return queryset

    # ------------------------------------------------------------------
    # Standard actions
    # ------------------------------------------------------------------

    @method_decorator(ratelimit(key="user", rate="20/m", method="POST"))
    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Create a new post (rate-limited to 20 POSTs/min per user)."""
        logger.info("Post creation attempt by: %s", request.user.email)
        return super().create(request, *args, **kwargs)

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """List posts with language-aware caching for anonymous users.

        Cached responses are keyed by language code so that each locale
        gets its own entry. The cache is invalidated on every write.
        Authenticated users always receive a fresh, uncached response.
        """
        lang: str = translation.get_language() or "en"
        cache_key: str = f"{CACHE_KEY_POSTS_LIST}:{lang}"

        # Serve from cache for unauthenticated requests.
        if not request.user.is_authenticated:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.debug("Returning cached posts list for language %s", lang)
                return Response(cached_data)

        response: Response = super().list(request, *args, **kwargs)

        # Timezone validation for authenticated users.
        if request.user.is_authenticated and getattr(request.user, "timezone", None):
            try:
                pytz.timezone(request.user.timezone)
                # TODO: convert created_at/updated_at fields in response.data
                #       to the user's local timezone.
            except pytz.UnknownTimeZoneError:
                logger.warning("Unknown timezone: %s", request.user.timezone)

        # Store the freshly built response for anonymous users.
        if not request.user.is_authenticated:
            cache.set(cache_key, response.data, CACHE_TTL_SECONDS)
            logger.debug("Cached posts list for language %s", lang)

        return response

    def perform_create(self, serializer: drf_serializers.BaseSerializer) -> None:
        """Persist a new post and purge the posts-list cache for all locales."""
        post: Post = serializer.save()
        self._invalidate_list_cache()
        logger.info("Post created: %s", post.title)

    def perform_update(self, serializer: drf_serializers.BaseSerializer) -> None:
        """Persist post changes and purge the posts-list cache for all locales."""
        post: Post = serializer.save()
        self._invalidate_list_cache()
        logger.info("Post updated: %s", post.title)

    def perform_destroy(self, instance: Post) -> None:
        """Delete a post and purge the posts-list cache for all locales."""
        self._invalidate_list_cache()
        logger.info("Post deleted: %s", instance.title)
        instance.delete()

    # ------------------------------------------------------------------
    # Custom actions
    # ------------------------------------------------------------------

    @action(detail=True, methods=["get"])
    def comments(self, request: Request, slug: str | None = None) -> Response:
        """Return all comments for the post identified by *slug*."""
        post: Post = self.get_object()
        qs = post.comments.select_related("author").all()
        serializer = CommentSerializer(qs, many=True)
        return Response(serializer.data)

    @comments.mapping.post
    def add_comment(self, request: Request, slug: str | None = None) -> Response:
        """Append a new comment to the post and publish an event to Redis.

        The Redis pub/sub message is fire-and-forget: if the broker is
        unavailable the comment is still saved successfully.
        """
        post: Post = self.get_object()
        serializer = CommentSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        comment = Comment.objects.create(
            post=post,
            author=request.user,
            body=serializer.validated_data["body"],
        )

        # Publish comment event to Redis channel if the client is available.
        if redis_client is not None:
            redis_client.publish(
                "comments",
                json.dumps(
                    {
                        "post_id": post.id,
                        "post_slug": post.slug,
                        "post_title": post.title,
                        "author_id": request.user.pk,
                        "author_email": request.user.email,
                        "comment": comment.body,
                        "created_at": str(comment.created_at),
                    }
                ),
            )

        logger.info("Comment added to post: %s by %s", post.title, request.user.email)
        return Response(
            CommentSerializer(comment).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"])
    def stats(self, request: Request) -> Response:
        """Return aggregated blog statistics and live external data.

        Data sources are fetched **concurrently** via ``asyncio.gather`` to
        minimise wall-clock latency. If either external call fails, the
        corresponding field falls back to a safe default value.

        External APIs used:
            - ``open.er-api.com`` – USD exchange rates (KZT, RUB, EUR).
            - ``timeapi.io``       – current time in Asia/Almaty.
        """
        return Response(self._get_stats_sync(request))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _invalidate_list_cache(self) -> None:
        """Delete cached post lists for every configured language."""
        for lang_code, _ in settings.LANGUAGES:
            cache.delete(f"{CACHE_KEY_POSTS_LIST}:{lang_code}")

    def _get_stats_sync(self, request: Request) -> dict[str, Any]:
        """Run the async stats coroutine in a dedicated event loop.

        A *new* event loop is created so that this method is safe to call
        from both sync and async contexts without interfering with an
        existing loop.

        Args:
            request: The current HTTP request (forwarded to the async helper).

        Returns:
            dict with keys ``blog``, ``exchange_rates``, and ``current_time``.
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._get_stats_async(request))
        finally:
            loop.close()

    async def _get_stats_async(self, request: Request) -> dict[str, Any]:
        """Concurrently fetch DB counts and two external APIs.

        Args:
            request: The current HTTP request (reserved for future per-user
                stats filtering).

        Returns:
            dict with keys ``blog``, ``exchange_rates``, and ``current_time``.
        """
        async with httpx.AsyncClient() as client:
            # DB counts run in a thread pool to avoid blocking the event loop.
            blog_counts: dict[str, int] = await sync_to_async(
                self._get_blog_counts
            )()

            # Fire both HTTP requests concurrently.
            # return_exceptions=True means failures come back as Exception
            # instances instead of being raised — we check types below.
            results = await asyncio.gather(
                client.get("https://open.er-api.com/v6/latest/USD"),
                client.get(
                    "https://timeapi.io/api/time/current/zone?timeZone=Asia/Almaty"
                ),
                return_exceptions=True,
            )
            exchange_result: httpx.Response | BaseException = results[0]
            time_result: httpx.Response | BaseException = results[1]

            # --- Exchange rates -------------------------------------------------
            exchange_rates: dict[str, float] = {"KZT": 0.0, "RUB": 0.0, "EUR": 0.0}
            # Narrow the type to httpx.Response before accessing HTTP attributes.
            if isinstance(exchange_result, httpx.Response):
                if exchange_result.status_code == 200:
                    rates: dict[str, float] = exchange_result.json().get("rates", {})
                    exchange_rates = {
                        "KZT": rates.get("KZT", 0.0),
                        "RUB": rates.get("RUB", 0.0),
                        "EUR": rates.get("EUR", 0.0),
                    }
            else:
                logger.error("Exchange rate API error: %s", exchange_result)

            # --- Current time --------------------------------------------------
            current_time: str = timezone.now().isoformat()
            # Narrow the type to httpx.Response before accessing HTTP attributes.
            if isinstance(time_result, httpx.Response):
                if time_result.status_code == 200:
                    current_time = time_result.json().get("dateTime", current_time)
            else:
                logger.error("Time API error: %s", time_result)

            return {
                "blog": blog_counts,
                "exchange_rates": exchange_rates,
                "current_time": current_time,
            }

    @staticmethod
    def _get_blog_counts() -> dict[str, int]:
        """Query the database for aggregate blog statistics.

        Returns:
            dict with ``total_posts``, ``total_comments``, and ``total_users``.
        """
        # Deferred imports prevent circular-import issues when called via
        # sync_to_async from within the async context.
        from apps.blog.models import Comment, Post  # noqa: PLC0415
        from apps.users.models import User  # noqa: PLC0415

        return {
            "total_posts": Post.objects.count(),
            "total_comments": Comment.objects.count(),
            "total_users": User.objects.count(),
        }
