"""Custom user model with email-based authentication, language, and timezone support."""

import logging
from collections.abc import Iterable
from typing import Any

import pytz
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.core.validators import EmailValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class UserManager(BaseUserManager["User"]):
    """Manager for the custom :class:`User` model."""

    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        """Create, persist, and return a regular user.

        Args:
            email: The user's email address (used as the login identifier).
            password: Plain-text password; will be hashed before storage.
            **extra_fields: Additional model field values.

        Raises:
            ValueError: If *email* is empty or ``None``.

        Returns:
            The newly created :class:`User` instance.
        """
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user: User = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        logger.info("User created: %s", email)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        """Create a superuser with ``is_staff`` and ``is_superuser`` set to ``True``.

        Args:
            email: The superuser's email address.
            password: Plain-text password.
            **extra_fields: Additional model field values.

        Returns:
            The newly created superuser :class:`User` instance.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Application user identified by email address.

    Extends Django's :class:`~django.contrib.auth.models.AbstractBaseUser`
    with avatar upload, preferred display language, and IANA timezone.
    """

    # Supported UI languages — must align with ``settings.LANGUAGES``.
    LANGUAGE_CHOICES: list[tuple[str, str]] = [
        ("en", _("English")),
        ("ru", _("Russian")),
        ("kz", _("Kazakh")),
    ]

    email = models.EmailField(unique=True, validators=[EmailValidator()])
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    preferred_language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default="en",
        verbose_name=_("preferred language"),
    )
    timezone = models.CharField(
        max_length=50,
        default="UTC",
        # Build choices dynamically from pytz's common timezones list.
        choices=[(tz, tz) for tz in pytz.common_timezones],
        verbose_name=_("timezone"),
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        """Return the user's full name, stripped of surrounding whitespace."""
        return f"{self.first_name} {self.last_name}".strip()

    def save(
        self,
        force_insert: bool = False,
        force_update: bool = False,
        using: str | None = None,
        update_fields: Iterable[str] | None = None,
    ) -> None:
        """Persist the user, ensuring the email is always normalised.

        Args:
            force_insert: Force an SQL INSERT.
            force_update: Force an SQL UPDATE.
            using: Database alias to use.
            update_fields: Fields to update in an SQL UPDATE.
        """
        # Normalise via UserManager directly — Pylance knows normalize_email
        # lives on BaseUserManager, so accessing it through the typed manager
        # instance avoids the reportAttributeAccessIssue on self.__class__.objects.
        self.email = UserManager.normalize_email(self.email)
        super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )
