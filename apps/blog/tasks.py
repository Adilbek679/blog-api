"""Celery tasks for the blog application."""

import json
import logging
from typing import Any

from celery import shared_task  # type: ignore[import-untyped]
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.blog.models import Post, PostStatus  # noqa: E402

logger = logging.getLogger(__name__)

# Cache key prefix — must match the constant in views.py.
CACHE_KEY_POSTS_LIST: str = "published_posts_list"

# Redis SSE channel — must match the constant in notifications/views.py.
SSE_CHANNEL: str = "sse_post_published"


@shared_task(  # type: ignore[misc]
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def invalidate_posts_cache(self: Any) -> None:
    """Delete the cached posts list for every configured language.

    Why retries matter here:
        Cache invalidation talks to Redis.  If Redis is momentarily
        unavailable, the cache will serve stale data until the next
        successful invalidation.  Retrying quickly ensures freshness
        is restored as soon as Redis recovers.

    Args:
        self: Celery task instance (injected by ``bind=True``).
    """
    for lang_code, _ in settings.LANGUAGES:
        cache.delete(f"{CACHE_KEY_POSTS_LIST}:{lang_code}")

    logger.info("Posts list cache invalidated for all languages")


@shared_task(  # type: ignore[misc]
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def publish_scheduled_posts(self: Any) -> None:
    """Publish all posts whose ``publish_at`` time has passed.

    Runs every minute via Celery Beat.  For each post that transitions
    to ``published``, an SSE event is pushed to all connected clients.

    Why retries matter here:
        This task touches the database and Redis.  A transient error
        (DB overload, Redis blip) would leave scheduled posts stuck in
        the ``scheduled`` state.  Retrying ensures they are published
        as close to the intended time as possible.

    Args:
        self: Celery task instance (injected by ``bind=True``).
    """
    now = timezone.now()

    due_posts = Post.objects.filter(
        status=PostStatus.SCHEDULED,
        publish_at__lte=now,
    ).select_related("author")

    if not due_posts.exists():
        return

    published_count = 0
    for post in due_posts:
        post.status = PostStatus.PUBLISHED
        post.save(update_fields=["status"])
        _publish_sse_event(post)
        published_count += 1

    invalidate_posts_cache.delay()  # type: ignore[attr-defined]
    logger.info("Published %d scheduled post(s)", published_count)


@shared_task(  # type: ignore[misc]
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def generate_daily_stats(self: Any) -> None:
    """Log aggregate counts for the past 24 hours.

    Runs daily at 00:00 UTC via Celery Beat.

    Why retries matter here:
        DB queries can time-out under load.  Retrying ensures the stats
        are always logged for monitoring and alerting pipelines.

    Args:
        self: Celery task instance (injected by ``bind=True``).
    """
    from apps.blog.models import Comment  # noqa: PLC0415
    from apps.users.models import User  # noqa: PLC0415

    since = timezone.now() - timezone.timedelta(hours=24)

    new_posts: int = Post.objects.filter(
        created_at__gte=since
    ).count()
    new_comments: int = Comment.objects.filter(
        created_at__gte=since
    ).count()
    new_users: int = User.objects.filter(
        date_joined__gte=since
    ).count()

    logger.info(
        "Daily stats — posts: %d, comments: %d, users: %d",
        new_posts,
        new_comments,
        new_users,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _publish_sse_event(post: Post) -> None:
    """Push a post-published SSE event to Redis.

    Called synchronously inside ``publish_scheduled_posts`` — no Celery
    task needed because a single ``redis.publish()`` is fast and
    lightweight.

    Args:
        post: The :class:`~apps.blog.models.Post` instance just published.
    """
    import redis as redis_lib  # type: ignore[import-untyped]

    try:
        redis_client = redis_lib.Redis.from_url(  # type: ignore[attr-defined]
            settings.CACHES["default"]["LOCATION"]
        )
        payload: dict[str, Any] = {
            "post_id": post.pk,
            "title": post.title,
            "slug": post.slug,
            "author": {
                "id": post.author.pk,
                "email": post.author.email,
            },
            "published_at": timezone.now().isoformat(),
        }
        redis_client.publish(  # type: ignore[attr-defined]
            SSE_CHANNEL,
            json.dumps(payload),
        )
    except redis_lib.ConnectionError:  # type: ignore[attr-defined]
        logger.warning(
            "SSE publish failed for post %s: Redis unavailable",
            post.slug,
        )