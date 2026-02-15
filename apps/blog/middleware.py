"""Middleware for debug request logging (writes to logs/debug_requests.log when DEBUG=True)."""
import logging

logger = logging.getLogger('blog.debug_requests')


class DebugRequestLoggingMiddleware:
    """Log every incoming request when DEBUG is True (handler has RequireDebugTrue filter)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        logger.debug(
            '%s %s',
            request.method,
            request.get_full_path(),
        )
        return self.get_response(request)
