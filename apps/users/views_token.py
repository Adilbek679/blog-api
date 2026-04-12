"""Rate-limited JWT token views."""

import logging
from typing import Any

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit  # type: ignore[import-untyped]
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

logger = logging.getLogger(__name__)

# Shared rate-limit error message.
_RATE_LIMIT_MSG: str = "Too many requests. Try again later."


class RateLimitedTokenObtainPairView(TokenObtainPairView):
    """JWT login view limited to **10 POST requests per minute** per IP address.

    When the limit is exceeded, returns ``429 Too Many Requests`` instead
    of the default Django-ratelimit 403 response.
    """

    @method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True))
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Authenticate and issue a JWT token pair.

        Args:
            request: The login request containing ``email`` and ``password``.
            *args: Positional arguments forwarded to the parent view.
            **kwargs: Keyword arguments forwarded to the parent view.

        Returns:
            ``200 OK`` with ``access`` and ``refresh`` tokens on success.
            ``429 Too Many Requests`` when the rate limit is exceeded.
            ``401 Unauthorized`` on invalid credentials.
        """
        logger.info("Login attempt from IP: %s", request.META.get("REMOTE_ADDR"))

        # django-ratelimit sets this flag when ``block=True`` and the limit
        # is exceeded; check it before delegating to the parent view.
        if getattr(request, "limited", False):
            logger.warning(
                "Rate limit exceeded for login from IP: %s",
                request.META.get("REMOTE_ADDR"),
            )
            return Response(
                {"detail": "Too many login attempts. Try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            response = super().post(request, *args, **kwargs)
            if response.status_code == status.HTTP_200_OK:
                logger.info("Login successful")
            else:
                logger.warning("Login failed: invalid credentials")
            return response
        except Exception:
            logger.exception("Unexpected login error")
            raise


class RateLimitedTokenRefreshView(TokenRefreshView):
    """JWT refresh view limited to **10 POST requests per minute** per IP address."""

    @method_decorator(ratelimit(key="ip", rate="10/m", method="POST", block=True))
    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Refresh a JWT access token.

        Args:
            request: The request containing the ``refresh`` token.
            *args: Positional arguments forwarded to the parent view.
            **kwargs: Keyword arguments forwarded to the parent view.

        Returns:
            ``200 OK`` with a new ``access`` token on success.
            ``429 Too Many Requests`` when the rate limit is exceeded.
        """
        if getattr(request, "limited", False):
            return Response(
                {"detail": _RATE_LIMIT_MSG},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        return super().post(request, *args, **kwargs)
