"""Management command: seed the database with test data."""

import random
from typing import Any

from django.core.management.base import BaseCommand

from apps.blog.models import Category, Comment, Post, PostStatus, Tag
from apps.users.models import User


class Command(BaseCommand):
    """Populate the database with test users, categories, tags, posts and comments.

    Usage::

        python manage.py seed
    """

    help = "Seed the database with test data"

    def handle(self, *args: Any, **options: Any) -> None:
        """Run the seed sequence."""
        self._create_superuser()
        users = self._create_users()
        categories = self._create_categories()
        tags = self._create_tags()
        posts = self._create_posts(users, categories, tags)
        self._create_comments(posts, users)
        self.stdout.write(self.style.SUCCESS("Database seeded successfully."))

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _create_superuser(self) -> None:
        """Create the admin superuser if it does not already exist."""
        if not User.objects.filter(email="admin@example.com").exists():
            User.objects.create_superuser( # type: ignore
                "admin@example.com",
                "admin123",
                first_name="Admin",
                last_name="User",
            )
            self.stdout.write("✓ Superuser created")
        else:
            self.stdout.write("✓ Superuser already exists")

    def _create_users(self) -> list[User]:
        """Create 5 test users and return them."""
        users: list[User] = []
        for i in range(1, 6):
            email = f"testuser{i}@example.com"
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": f"Test{i}",
                    "last_name": "User",
                    "preferred_language": random.choice(["en", "ru", "kz"]),
                },
            )
            if created:
                user.set_password("password123")
                user.save()
            users.append(user)
        self.stdout.write("✓ Test users created")
        return users

    def _create_categories(self) -> list[Category]:
        """Create blog categories and return them."""
        categories: list[Category] = []
        category_data = [
            ("Technology", "Технологии", "Технология"),
            ("Travel", "Путешествия", "Саяхат"),
            ("Food", "Еда", "Тағам"),
            ("Sports", "Спорт", "Спорт"),
        ]
        for name_en, name_ru, name_kz in category_data:
            cat, _ = Category.objects.get_or_create(
                slug=name_en.lower(),
                defaults={
                    "name_en": name_en,
                    "name_ru": name_ru,
                    "name_kz": name_kz,
                },
            )
            categories.append(cat)
        self.stdout.write("✓ Categories created")
        return categories

    def _create_tags(self) -> list[Tag]:
        """Create tags and return them."""
        tags: list[Tag] = []
        for name in ["Python", "Django", "API", "Tutorial", "News"]:
            tag, _ = Tag.objects.get_or_create(
                name=name,
                slug=name.lower(),
            )
            tags.append(tag)
        self.stdout.write("✓ Tags created")
        return tags

    def _create_posts(
        self,
        users: list[User],
        categories: list[Category],
        tags: list[Tag],
    ) -> list[Post]:
        """Create 25 test posts and return them."""
        posts: list[Post] = []
        for i in range(1, 26):
            post_status = (
                PostStatus.PUBLISHED if i > 5 else PostStatus.DRAFT
            )
            post, created = Post.objects.get_or_create(
                slug=f"sample-post-{i}",
                defaults={
                    "title": f"Sample Post {i}",
                    "author": random.choice(users),
                    "body": f"This is the body of sample post {i}. " * 10,
                    "category": random.choice(categories),
                    "status": post_status,
                },
            )
            if created:
                post.tags.set( # type: ignore
                    random.sample(tags, random.randint(1, 3))
                )
            posts.append(post)
        self.stdout.write("✓ Posts created")
        return posts

    def _create_comments(
        self,
        posts: list[Post],
        users: list[User],
    ) -> None:
        """Create comments on the first 20 posts."""
        for post in posts[:20]:
            for _ in range(random.randint(1, 5)):
                Comment.objects.get_or_create(
                    post=post,
                    author=random.choice(users),
                    defaults={
                        "body": f"This is a comment on {post.title}",
                    },
                )
        self.stdout.write("✓ Comments created")