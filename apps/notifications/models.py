"""Models for the notifications application."""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.blog.models import Comment
from apps.users.models import User


class Notification(models.Model):
    """A notification created when someone comments on a user's post.

    Notifications are used by the HTTP polling endpoint to inform post
    authors about new activity without requiring a persistent connection.
    """

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("recipient"),
    )
    comment = models.ForeignKey(
        Comment,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name=_("comment"),
    )
    is_read = models.BooleanField(
        default=False,
        verbose_name=_("is read"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("created at"),
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("notification")
        verbose_name_plural = _("notifications")

    def __str__(self) -> str:
        # comment_id is a dynamic ForeignKey attribute (Django appends _id
        # to the field name). Pylance does not see it in stubs, hence ignore.
        comment_id = self.comment_id  # type: ignore[attr-defined]
        return (
            f"Notification for {self.recipient.email} "
            f"— comment #{comment_id}"
        )
