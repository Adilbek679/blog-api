"""Celery tasks for the notifications application."""

import logging
from typing import Any

from celery import shared_task  # type: ignore[import-untyped]

from apps.blog.models import Comment
from apps.notifications.models import Notification

logger = logging.getLogger(__name__)

# Channels group name pattern — must match consumers.py.
COMMENT_GROUP_PATTERN: str = "post_comments_{slug}"


@shared_task(  # type: ignore[misc]
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def process_new_comment(self: Any, comment_id: int) -> None:
    """Handle all side-effects of a new comment in a single Celery task.

    Side-effects:
        1. Create a :class:`~apps.notifications.models.Notification` for
           the post author (if the commenter is not the author).
        2. Publish a WebSocket message to the Channels group for the post
           so all connected browsers receive the comment in real time.

    Why retries matter here:
        This task creates DB records and talks to Redis (Channels layer).
        A transient failure would silently drop the notification or the
        WebSocket event.  Retrying with back-off guarantees delivery
        without duplicating notifications (get_or_create is idempotent).

    Args:
        self: Celery task instance (injected by ``bind=True``).
        comment_id: Primary key of the newly created comment.
    """
    from asgiref.sync import async_to_sync  # noqa: PLC0415
    from channels.layers import get_channel_layer  # type: ignore[import-untyped]  # noqa: PLC0415

    try:
        comment = Comment.objects.select_related(
            "post", "post__author", "author"
        ).get(pk=comment_id)
    except Comment.DoesNotExist:
        logger.error(
            "process_new_comment: comment %d not found", comment_id
        )
        return

    post = comment.post
    post_author = post.author

    # --- 1. Create notification (skip if author comments on own post) -----
    if comment.author != post_author:
        Notification.objects.get_or_create(
            recipient=post_author,
            comment=comment,
        )
        logger.info(
            "Notification created for user %s (comment #%d)",
            post_author.email,
            comment_id,
        )

    # --- 2. Publish WebSocket event to the Channels group -----------------
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning(
            "process_new_comment: channel layer not configured, "
            "skipping WebSocket publish"
        )
        return

    group_name: str = COMMENT_GROUP_PATTERN.format(slug=post.slug)
    message: dict[str, Any] = {
        "type": "new_comment",  # maps to CommentConsumer.new_comment()
        "data": {
            "comment_id": comment.pk,
            "author": {
                "id": comment.author.pk,
                "email": comment.author.email,
            },
            "body": comment.body,
            "created_at": comment.created_at.isoformat(),
        },
    }

    # async_to_sync bridges the sync Celery task and async channel layer.
    async_to_sync(channel_layer.group_send)(group_name, message)

    logger.info(
        "WebSocket event published to group %s for comment #%d",
        group_name,
        comment_id,
    )


@shared_task(  # type: ignore[misc]
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def clear_expired_notifications(self: Any) -> None:
    """Delete notifications older than 30 days.

    Runs daily at 03:00 UTC via Celery Beat.

    Why retries matter here:
        A bulk DELETE on a large table can time out under heavy load.
        Retrying ensures old records are eventually cleaned up, keeping
        the notifications table from growing unboundedly.

    Args:
        self: Celery task instance (injected by ``bind=True``).
    """
    from django.utils import timezone  # noqa: PLC0415

    cutoff = timezone.now() - timezone.timedelta(days=30)
    deleted, _ = Notification.objects.filter(
        created_at__lt=cutoff
    ).delete()

    logger.info("Deleted %d expired notification(s)", deleted)