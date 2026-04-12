"""Serializers for the blog application (Category, Tag, Post, Comment)."""

import logging
from typing import Any

from rest_framework import serializers

from apps.users.serializers import UserSerializer

from .models import Category, Comment, Post, Tag

logger = logging.getLogger(__name__)


class CategorySerializer(serializers.ModelSerializer):
    """Read-only serializer for post categories."""

    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class TagSerializer(serializers.ModelSerializer):
    """Read-only serializer for post tags."""

    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for reading and creating post comments."""

    # Author is always populated from the request context, never from input.
    author = UserSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ["id", "author", "body", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class PostSerializer(serializers.ModelSerializer):
    """Full read serializer for blog posts, including nested relations."""

    author = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    # Aggregate comment count via annotation-compatible source.
    comments_count = serializers.IntegerField(
        source="comments.count",
        read_only=True,
    )

    class Meta:
        model = Post
        fields = [
            "id",
            "author",
            "title",
            "slug",
            "body",
            "category",
            "tags",
            "status",
            "created_at",
            "updated_at",
            "comments_count",
        ]
        read_only_fields = ["id", "author", "slug", "created_at", "updated_at"]


class PostCreateUpdateSerializer(serializers.ModelSerializer):
    """Write serializer for creating and updating blog posts.

    Accepts ``category_id`` and an optional list of ``tag_ids`` instead of
    nested objects, keeping the payload simple and avoiding extra lookups.
    """

    category_id = serializers.IntegerField(write_only=True)
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = Post
        fields = ["title", "body", "category_id", "tag_ids", "status"]

    def create(self, validated_data: dict[str, Any]) -> Post:
        """Create a new post, assigning the current user as author.

        Args:
            validated_data: Cleaned data from the serializer.

        Returns:
            The newly created :class:`Post` instance.
        """
        tag_ids: list[int] = validated_data.pop("tag_ids", [])
        category_id: int = validated_data.pop("category_id")

        post = Post.objects.create(
            author=self.context["request"].user,
            category_id=category_id,
            **validated_data,
        )

        if tag_ids:
            post.tags.set(tag_ids)

        logger.info("Post created: %s by %s", post.title, post.author.email)
        return post

    def update(self, instance: Post, validated_data: dict[str, Any]) -> Post:
        """Update an existing post with the supplied fields.

        Args:
            instance: The :class:`Post` instance to update.
            validated_data: Cleaned data from the serializer.

        Returns:
            The updated :class:`Post` instance.
        """
        tag_ids: list[int] | None = validated_data.pop("tag_ids", None)
        category_id: int | None = validated_data.pop("category_id", None)

        if category_id is not None:
            instance.category_id = category_id  # type: ignore[assignment]

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # Only update tags when explicitly provided in the request.
        if tag_ids is not None:
            instance.tags.set(tag_ids)

        logger.info("Post updated: %s", instance.title)
        return instance
