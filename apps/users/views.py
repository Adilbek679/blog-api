"""ViewSets for the users application (registration, language, timezone)."""

import logging
from typing import Any, cast

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import translation
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit  # type: ignore[import-untyped]
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import (
    LanguageSerializer,
    RegisterSerializer,
    TimezoneSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)

# Sender address used for all transactional e-mails.
_NO_REPLY_EMAIL: str = "noreply@blogapi.com"


class AuthViewSet(viewsets.GenericViewSet):
    """Handles user registration and profile preference updates.

    Routes:
        POST  /api/auth/register/   – create a new account
        PATCH /api/auth/language/   – update preferred language  (auth required)
        PATCH /api/auth/timezone/   – update timezone preference  (auth required)
    """

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    @action(detail=False, methods=["post"])
    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def register(self, request: Request) -> Response:  # type: ignore[override]
        """Register a new user and return JWT tokens along with a welcome e-mail.

        Rate-limited to **5 POST requests per minute** per IP address.

        Args:
            request: The incoming HTTP request containing registration data.

        Returns:
            ``201 Created`` with user data and JWT pair on success.
            ``400 Bad Request`` with validation errors on failure.
        """
        data: dict[str, Any] = cast(dict[str, Any], request.data)

        logger.info("Registration attempt for email: %s", data.get("email"))

        # Instantiate the serializer directly instead of via get_serializer()
        # to avoid DRF stub issues where get_serializer() is typed as NoReturn,
        # which causes Pylance to mark all subsequent code as unreachable.
        serializer = RegisterSerializer(data=data, context=self.get_serializer_context())

        if not serializer.is_valid():
            logger.warning("Registration failed: %s", serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user: User = cast(User, serializer.save())

        # Resolve the preferred language; fall back to English.
        user_language: str = str(data.get("preferred_language") or "en")

        with translation.override(user_language):
            subject: str = render_to_string(
                "emails/welcome/subject.txt"
            ).strip()
            message: str = render_to_string(
                "emails/welcome/body.txt",
                {"user": user, "user_language": user_language},
            )
            send_mail(
                subject=subject,
                message=message,
                from_email=_NO_REPLY_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )

        refresh: RefreshToken = RefreshToken.for_user(user)
        logger.info("User registered successfully: %s", user.email)

        return Response(
            {
                "user": UserSerializer(user).data,
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_201_CREATED,
        )

    # ------------------------------------------------------------------
    # Preference updates (authenticated only)
    # ------------------------------------------------------------------

    @action(detail=False, methods=["patch"], permission_classes=[IsAuthenticated])
    def language(self, request: Request) -> Response:
        """Update the authenticated user's preferred display language.

        Args:
            request: Request containing ``{"preferred_language": "<code>"}``.

        Returns:
            ``200 OK`` with the updated language field, or ``400`` on error.
        """
        data: dict[str, Any] = cast(dict[str, Any], request.data)

        serializer = LanguageSerializer(
            request.user,
            data=data,
            partial=True,
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        cast(User, serializer.save())
        logger.info(
            "User %s updated language to %s",
            request.user.email,
            data.get("preferred_language"),
        )
        return Response(serializer.data)

    @action(detail=False, methods=["patch"], permission_classes=[IsAuthenticated])
    def timezone(self, request: Request) -> Response:
        """Update the authenticated user's timezone preference.

        Args:
            request: Request containing ``{"timezone": "<IANA timezone>"}``.

        Returns:
            ``200 OK`` with the updated timezone field, or ``400`` on error.
        """
        data: dict[str, Any] = cast(dict[str, Any], request.data)

        serializer = TimezoneSerializer(
            request.user,
            data=data,
            partial=True,
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        cast(User, serializer.save())
        logger.info(
            "User %s updated timezone to %s",
            request.user.email,
            data.get("timezone"),
        )
        return Response(serializer.data)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def get_serializer_context(self) -> dict[str, Any]:
        """Extend the default serializer context with the current request.

        Returns:
            dict containing ``request``, ``format``, and ``view`` keys.
        """
        return super().get_serializer_context()
