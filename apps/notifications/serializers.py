# apps/notifications/serializers.py

from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    comment_body = serializers.CharField(source="comment.body", read_only=True)
    comment_author = serializers.EmailField(source="comment.author.email", read_only=True)
    post_slug = serializers.SlugField(source="comment.post.slug", read_only=True)

    class Meta:
        model = Notification
        fields = ["id", "is_read", "created_at", "comment_body", "comment_author", "post_slug"]