"""Custom error handlers for the project."""
from typing import Optional

from django.http import HttpRequest, JsonResponse
from django_ratelimit.exceptions import Ratelimited

RATE_LIMIT_MESSAGE = 'Too many requests. Try again later.'


def handler403(request: HttpRequest, exception: Optional[Exception] = None) -> JsonResponse:
    """Return 429 with required body when rate limit exceeded, else 403."""
    if exception is not None and isinstance(exception, Ratelimited):
        return JsonResponse(
            {'detail': RATE_LIMIT_MESSAGE},
            status=429,
        )
    return JsonResponse(
        {'detail': 'Permission denied.'},
        status=403,
    )
