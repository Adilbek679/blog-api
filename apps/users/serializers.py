"""Serializers for the users application."""

import logging
from typing import Any

import pytz
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .models import User

logger = logging.getLogger(__name__)


class UserSerializer(serializers.ModelSerializer):
    """Read-only public representation of a user."""

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "avatar", "date_joined"]
        read_only_fields = ["id", "date_joined"]


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for new user registration.

    Validates that both password fields match before creating the user.
    ``password2`` is used only for validation and is never persisted.
    """

    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "password", "password2", "avatar"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Ensure both password fields are identical.

        Args:
            attrs: The raw validated field data.

        Raises:
            serializers.ValidationError: If the passwords do not match.

        Returns:
            The validated attribute dictionary.
        """
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError(
                {"password": _("Passwords don't match")}
            )
        return attrs

    def create(self, validated_data: dict[str, Any]) -> User:
        """Create and return a new user with a hashed password.

        Args:
            validated_data: Cleaned data after validation.

        Returns:
            The newly created :class:`User` instance.
        """
        validated_data.pop("password2")
        password: str = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        logger.info("User registered: %s", user.email)
        return user


class LanguageSerializer(serializers.ModelSerializer):
    """Partial-update serializer for the user's preferred display language."""

    class Meta:
        model = User
        fields = ["preferred_language"]

    def validate_preferred_language(self, value: str) -> str:
        """Reject any language code not present in :attr:`User.LANGUAGE_CHOICES`.

        Args:
            value: The submitted language code string.

        Raises:
            serializers.ValidationError: If *value* is not a supported code.

        Returns:
            The validated language code.
        """
        if value not in dict(User.LANGUAGE_CHOICES):
            raise serializers.ValidationError(
                _("Invalid language choice. Supported: en, ru, kz")
            )
        return value


class TimezoneSerializer(serializers.ModelSerializer):
    """Partial-update serializer for the user's IANA timezone preference."""

    class Meta:
        model = User
        fields = ["timezone"]

    def validate_timezone(self, value: str) -> str:
        """Reject timezone strings that are not valid IANA identifiers.

        Args:
            value: The submitted timezone string.

        Raises:
            serializers.ValidationError: If *value* is not found in
                ``pytz.all_timezones``.

        Returns:
            The validated timezone string.
        """
        if value not in pytz.all_timezones:
            raise serializers.ValidationError(
                _("Invalid IANA timezone identifier")
            )
        return value
