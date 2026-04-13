"""ViewSets for the users application (registration, language, timezone)."""

import logging
from typing import Any, cast

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit, # type: ignore

from rest_framework import status, viewsets  # type: ignore[import-untyped]
from rest_framework.decorators import action  # type: ignore[import-untyped]
from rest_framework.permissions import (  # type: ignore[import-untyped]
    AllowAny,
    IsAuthenticated,
)
from rest_framework.request import Request  # type: ignore[import-untyped]
from rest_framework.response import Response  # type: ignore[import-untyped]
from rest_framework_simplejwt.tokens import (  # type: ignore[import-untyped]
    RefreshToken,
)

from apps.users.tasks import send_welcome_email

from .models import User
from .serializers import (
    LanguageSerializer,
    RegisterSerializer,
    TimezoneSerializer,
    UserSerializer,
)

logger = logging.getLogger(__name__)


class AuthViewSet(viewsets.GenericViewSet):  # type: ignore[misc]
    """Handles user registration and profile preference updates.

    Routes:
        POST  /api/auth/register/   – create a new account
        PATCH /api/auth/language/   – update preferred language
        (auth required)
        PATCH /api/auth/timezone/   – update timezone (auth required)
    """

    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    @action(detail=False, methods=["post"])  # type: ignore[misc]
    @method_decorator(
        ratelimit(  # type: ignore[arg-type]
            key="ip", rate="5/m", method="POST", block=True
        )
    )
    def register(self, request: Request) -> Response:
        """Register a new user and return JWT tokens with a welcome e-mail.

        Rate-limited to **5 POST requests per minute** per IP address.

        Args:
            request: The incoming HTTP request containing registration data.

        Returns:
            ``201 Created`` with user data and JWT pair on success.
            ``400 Bad Request`` with validation errors on failure.
        """
        # cast: request.data is Any in DRF stubs
        data: dict[str, Any] = cast(  # type: ignore[misc]
            dict[str, Any], request.data # type: ignore
        )

        logger.info("Registration attempt for email: %s", data.get("email"))

        serializer = RegisterSerializer(
            data=data,
            context=self.get_serializer_context(),  # type: ignore[misc]
        )

        if not serializer.is_valid():  # type: ignore[misc]
            errors: Any = serializer.errors  # type: ignore[misc]
            logger.warning("Registration failed: %s", errors) # type: ignore
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        user: User = cast(User, serializer.save())  # type: ignore[misc]

        user_language: str = str(data.get("preferred_language") or "en")

        # Dispatch welcome e-mail as a Celery task so the registration
        # response is not blocked by SMTP latency.
        send_welcome_email.delay(  # type: ignore[attr-defined]
            user.pk, user_language
        )

        refresh: RefreshToken = RefreshToken.for_user(user)
        logger.info("User registered successfully: %s", user.email)

        return Response(
            {
                "user": UserSerializer(user).data,  # type: ignore[misc]
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_201_CREATED,
        )

    # ------------------------------------------------------------------
    # Preference updates (authenticated only)
    # ------------------------------------------------------------------

    @action(  # type: ignore[misc]
        detail=False,
        methods=["patch"],
        permission_classes=[IsAuthenticated],
    )
    def language(self, request: Request) -> Response:
        """Update the authenticated user's preferred display language.

        Args:
            request: Request containing ``{"preferred_language": "<code>"}``.

        Returns:
            ``200 OK`` with the updated language field, or ``400`` on error.
        """
        data: dict[str, Any] = cast(  # type: ignore[misc]
            dict[str, Any], request.data # type: ignore
        )
        user: User = getattr(request, "user")

        serializer = LanguageSerializer(user, data=data, partial=True)

        if not serializer.is_valid():  # type: ignore[misc]
            return Response(
                serializer.errors,  # type: ignore[misc]
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()  # type: ignore[misc]
        logger.info(
            "User %s updated language to %s",
            user.email,
            data.get("preferred_language"),
        )
        return Response(serializer.data)  # type: ignore[misc]

    @action(  # type: ignore[misc]
        detail=False,
        methods=["patch"],
        permission_classes=[IsAuthenticated],
    )
    def timezone(self, request: Request) -> Response:
        """Update the authenticated user's timezone preference.

        Args:
            request: Request containing ``{"timezone": "<IANA timezone>"}``.

        Returns:
            ``200 OK`` with the updated timezone field, or ``400`` on error.
        """
        data: dict[str, Any] = cast(  # type: ignore[misc]
            dict[str, Any], request.data # type: ignore
        )
        user: User = getattr(request, "user")

        serializer = TimezoneSerializer(user, data=data, partial=True)

        if not serializer.is_valid():  # type: ignore[misc]
            return Response(
                serializer.errors,  # type: ignore[misc]
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()  # type: ignore[misc]
        logger.info(
            "User %s updated timezone to %s",
            user.email,
            data.get("timezone"),
        )
        return Response(serializer.data)  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def get_serializer_context(self) -> dict[str, Any]:
        """Extend the default serializer context with the current request.

        Returns:
            dict containing ``request``, ``format``, and ``view`` keys.
        """
        return super().get_serializer_context()  # type: ignore[misc]