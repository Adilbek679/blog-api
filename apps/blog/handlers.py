"""Custom HTTP error handlers for the blog project."""

from django.http import HttpRequest, JsonResponse
from django_ratelimit.exceptions import Ratelimited  # type: ignore[import-untyped]

# Reusable message string to keep the rate-limit response consistent.
_RATE_LIMIT_MESSAGE: str = "Too many requests. Try again later."


def handler403(
    request: HttpRequest,
    exception: Exception | None = None,
) -> JsonResponse:
    """Return a JSON error response for 403 Forbidden conditions.

    When the exception is a :class:`~django_ratelimit.exceptions.Ratelimited`
    instance the response status is elevated to **429 Too Many Requests**;
    all other cases return a standard **403 Forbidden**.

    Args:
        request: The current HTTP request object.
        exception: The exception that triggered this handler, if any.

    Returns:
        A :class:`~django.http.JsonResponse` with an appropriate status code
        and a ``detail`` message body.
    """
    if isinstance(exception, Ratelimited):
        return JsonResponse({"detail": _RATE_LIMIT_MESSAGE}, status=429)

    return JsonResponse({"detail": "Permission denied."}, status=403)
