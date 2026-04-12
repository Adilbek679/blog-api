"""Serializers for the notifications application."""

from rest_framework import serializers  # type: ignore[import-untyped]

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):  # type: ignore[misc]
    """Read serializer for user notifications."""

    # Flatten nested comment/post info for convenient client consumption.
    # type: ignore[reportUnknownMemberType] suppresses incomplete DRF stubs
    # that do not expose CharField and other field classes as known members.
    comment_body: serializers.CharField = (  # type: ignore[reportUnknownMemberType]
        serializers.CharField(  # type: ignore[reportUnknownMemberType]
            source="comment.body",
            read_only=True,
        )
    )
    post_slug: serializers.CharField = (  # type: ignore[reportUnknownMemberType]
        serializers.CharField(  # type: ignore[reportUnknownMemberType]
            source="comment.post.slug",
            read_only=True,
        )
    )
    post_title: serializers.CharField = (  # type: ignore[reportUnknownMemberType]
        serializers.CharField(  # type: ignore[reportUnknownMemberType]
            source="comment.post.title",
            read_only=True,
        )
    )
    author_email: serializers.CharField = (  # type: ignore[reportUnknownMemberType]
        serializers.CharField(  # type: ignore[reportUnknownMemberType]
            source="comment.author.email",
            read_only=True,
        )
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "is_read",
            "created_at",
            "comment_body",
            "post_slug",
            "post_title",
            "author_email",
        ]
        read_only_fields = fields