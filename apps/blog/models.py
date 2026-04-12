"""Blog domain models: Category, Tag, Post, Comment."""

import logging
from collections.abc import Iterable

from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.users.models import User

logger = logging.getLogger(__name__)


class PostStatus(models.TextChoices):
    """Enumeration of allowed post publication states."""

    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"


class Category(models.Model):
    """Blog post category with multilingual name support (EN / RU / KZ)."""

    name_en = models.CharField(
        max_length=100,
        verbose_name=_("Name (English)"),
        blank=True,
    )
    name_ru = models.CharField(
        max_length=100,
        verbose_name=_("Name (Russian)"),
        blank=True,
    )
    name_kz = models.CharField(
        max_length=100,
        verbose_name=_("Name (Kazakh)"),
        blank=True,
    )
    slug = models.SlugField(unique=True)

    class Meta:
        verbose_name = _("category")
        verbose_name_plural = _("categories")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(
        self,
        force_insert: bool = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        """Auto-generate a unique slug from the English name if not set."""
        if not self.slug:
            base_name = self.name_en or "category"
            self.slug = slugify(base_name)

            # Append an incrementing counter until the slug is unique.
            original_slug = self.slug
            counter = 1
            while Category.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1

        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Return the category name in the currently active language.

        Resolution order:
        1. ``name_<lang>`` field for the active language (e.g. ``name_ru``).
        2. English name (``name_en``) as a fallback.
        3. Placeholder string ``"Unnamed Category"``.
        """
        from django.utils import translation  # local import avoids circular deps

        lang: str = translation.get_language() or "en"
        name_attr: str = f"name_{lang}"

        # Use "" as default so getattr always returns str instead of
        # Any | None — prevents Pylance reportAssignmentType error.
        name: str = getattr(self, name_attr, "") or ""

        if not name and self.name_en:
            name = self.name_en
        elif not name:
            name = "Unnamed Category"

        return name

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    """A short label that can be attached to multiple posts."""

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(unique=True)

    def save(
        self,
        force_insert: bool = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        """Auto-generate slug from name if not already set."""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def __str__(self) -> str:
        return self.name


class Post(models.Model):
    """A blog article written by a registered user."""

    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="posts",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    body = models.TextField()
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        related_name="posts",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    status = models.CharField(
        max_length=10,
        choices=PostStatus.choices,
        default=PostStatus.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("post")
        verbose_name_plural = _("posts")
        ordering = ["-created_at"]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(
        self,
        force_insert: bool = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        """Auto-generate a unique slug from the post title if not set."""
        if not self.slug:
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1

            # Ensure slug uniqueness by appending a counter when needed.
            while Post.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def __str__(self) -> str:
        return self.title


class Comment(models.Model):
    """A reader comment attached to a single blog post."""

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"Comment by {self.author.email} on {self.post.title}"
