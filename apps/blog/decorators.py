"""Custom view decorators for the blog application."""

import logging
from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from django.core.cache import cache
from django.http import HttpRequest, JsonResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Generic type variables used to preserve the wrapped function's signature.
# ParamSpec captures *args / **kwargs types; TypeVar captures the return type.
# ---------------------------------------------------------------------------
P = ParamSpec("P")
R = TypeVar("R")


def rate_limit(
    key_prefix: str,
    limit: int,
    period: int = 60,
) -> Callable[[Callable[P, R]], Callable[P, R | JsonResponse]]:
    """Limit the call rate for a view using the Django cache backend.

    Requests are bucketed per authenticated user (by user id) or per
    anonymous IP address.  Once *limit* requests have been made within
    *period* seconds the view returns HTTP 429.

    Args:
        key_prefix: Namespace prefix used to build the cache key, e.g.
            ``"api:comments"``.
        limit: Maximum number of requests allowed within *period*.
        period: Sliding window size in seconds.  Defaults to ``60``.

    Returns:
        A decorator that wraps a Django view function and preserves its
        full signature (parameters and return type) for static analysis.

    Example::

        @rate_limit("blog:create", limit=10, period=60)
        def my_view(request: HttpRequest) -> JsonResponse:
            ...
    """

    def decorator(
        view_func: Callable[P, R],
    ) -> Callable[P, R | JsonResponse]:
        @wraps(view_func)
        def _wrapped_view(
            *args: P.args,
            **kwargs: P.kwargs,
        ) -> R | JsonResponse:
            # The first positional argument of every Django view is request.
            request: HttpRequest = args[0]  # type: ignore[assignment]

            # Resolve client identifier: prefer user id, fall back to IP.
            forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if forwarded_for:
                # Take only the first (client) IP when behind a proxy chain.
                ip: str = forwarded_for.split(",")[0].strip()
            else:
                ip = request.META.get("REMOTE_ADDR", "unknown")

            if request.user.is_authenticated:
                # user.pk is always an int for the custom User model.
                cache_key = f"{key_prefix}:user:{request.user.pk}"
            else:
                cache_key = f"{key_prefix}:ip:{ip}"

            # Atomically increment the request counter.
            # cache.get() returns None when the key does not exist yet,
            # so we initialise it to 1 with a fresh TTL on first request.
            # cache.incr() is atomic in Redis — no race condition between
            # reading and writing the counter value.
            count: int | None = cache.get(cache_key)
            if count is None:
                # First request in this window — create the counter.
                cache.set(cache_key, 1, period)
                count = 1
            else:
                # Atomic increment; TTL is NOT reset so the window is fixed.
                count = cache.incr(cache_key)

            if count > limit:
                logger.warning("Rate limit exceeded for %s", cache_key)
                return JsonResponse(
                    {"detail": "Too many requests. Try again later."},
                    status=429,
                )

            return view_func(*args, **kwargs)

        return _wrapped_view

    return decorator
