"""Middleware for debug-mode request logging."""

import logging
from typing import Callable

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger("blog.debug_requests")


class DebugRequestLoggingMiddleware:
    """Log every incoming request path when DEBUG is ``True``.

    The associated logger (``blog.debug_requests``) is configured with a
    ``RequireDebugTrue`` filter in the logging settings, so this middleware
    produces output **only** in development — no changes are needed here
    to suppress it in production.

    Args:
        get_response: The next middleware or view callable in the chain.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Log the HTTP method and full path, then pass the request along."""
        logger.debug("%s %s", request.method or "UNKNOWN", request.get_full_path())
        return self.get_response(request)
