"""Core middleware: language activation based on user preference or request headers."""

import logging
from collections.abc import Callable

from django.conf import settings
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpRequest, HttpResponse
from django.utils import translation
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class LanguageMiddleware(MiddlewareMixin):
    """Activate the correct language for every request.

    Resolution order (first match wins):

    1. Authenticated user's ``preferred_language`` profile field.
    2. ``?lang=<code>`` query-string parameter (must be in ``settings.LANGUAGES``).
    3. Django's standard ``Accept-Language`` header negotiation.
    4. ``settings.LANGUAGE_CODE`` fallback.

    Args:
        get_response: The next middleware or view callable.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        # Build a frozenset of supported language codes for O(1) membership tests.
        self._supported_langs: frozenset[str] = frozenset(
            code for code, _ in settings.LANGUAGES
        )
        super().__init__(get_response)

    def process_request(self, request: HttpRequest) -> None:
        """Detect and activate the appropriate language before the view runs.

        Args:
            request: The incoming HTTP request object.
        """
        language: str | None = None

        # 1. Use the authenticated user's stored preference.
        if hasattr(request, "user") and request.user.is_authenticated:
            language = getattr(request.user, "preferred_language", None)

        # 2. Fall back to an explicit ``?lang=`` query parameter.
        if not language:
            lang_param = request.GET.get("lang", "")
            if lang_param in self._supported_langs:
                language = lang_param

        # 3. Negotiate from the Accept-Language header.
        # get_language_from_request expects WSGIRequest; cast is safe because
        # Django always passes a WSGIRequest through the WSGI middleware stack.
        if not language and isinstance(request, WSGIRequest):
            language = translation.get_language_from_request(request)

        # 4. Final fallback to the project default.
        if not language:
            language = settings.LANGUAGE_CODE

        # Resolve any remaining None before passing to activate(), which
        # requires a plain str (not str | None).
        resolved_language: str = language or settings.LANGUAGE_CODE

        translation.activate(resolved_language)

        # LANGUAGE_CODE is a Django convention set by LocaleMiddleware;
        # HttpRequest stubs don't declare it, hence the type: ignore.
        request.LANGUAGE_CODE = resolved_language  # type: ignore[attr-defined]
