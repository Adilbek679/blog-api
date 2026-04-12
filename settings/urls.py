"""Root URL configuration for the blog project."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpRequest, JsonResponse
from django.urls import include, path
from django_ratelimit.exceptions import Ratelimited  # type: ignore[import-untyped]
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.routers import DefaultRouter

from apps.blog.views import PostViewSet
from apps.users.views import AuthViewSet
from apps.users.views_token import (
    RateLimitedTokenObtainPairView,
    RateLimitedTokenRefreshView,
)

# ---------------------------------------------------------------------------
# Router — auto-generates standard CRUD URLs for registered ViewSets
# ---------------------------------------------------------------------------

router = DefaultRouter()
router.register(r"posts", PostViewSet, basename="post") # type: ignore

# ---------------------------------------------------------------------------
# URL patterns
# ---------------------------------------------------------------------------

urlpatterns = [ # type: ignore
    path("admin/", admin.site.urls),
    # --- Authentication endpoints -------------------------------------------
    path(
        "api/auth/register/",
        AuthViewSet.as_view({"post": "register"}), # type: ignore
        name="register",
    ),
    path(
        "api/auth/token/",
        RateLimitedTokenObtainPairView.as_view(), # type: ignore
        name="token_obtain_pair",
    ),
    path(
        "api/auth/token/refresh/",
        RateLimitedTokenRefreshView.as_view(), # type: ignore
        name="token_refresh",
    ),
    # --- Blog API (router-generated routes) ---------------------------------
    path("api/", include(router.urls)), # type: ignore
    # --- OpenAPI schema & docs ----------------------------------------------
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"), # type: ignore
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"), # type: ignore
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"), # type: ignore
        name="redoc",
    ),
    path("api/", include("apps.notifications.urls")),
]

# Serve user-uploaded media files in development only.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) # type: ignore


# ---------------------------------------------------------------------------
# Custom error handlers
# ---------------------------------------------------------------------------


def handler403(
    request: HttpRequest,
    exception: Exception | None = None,
) -> JsonResponse:
    """Return 429 when a rate-limit is hit; otherwise return 403 Forbidden.

    Args:
        request: The current HTTP request.
        exception: The exception that triggered the 403, if any.

    Returns:
        A JSON response with the appropriate status code.
    """
    if isinstance(exception, Ratelimited):
        return JsonResponse(
            {"detail": "Too many requests. Try again later."},
            status=429,
        )
    return JsonResponse({"detail": "Permission denied."}, status=403)
