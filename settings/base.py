"""Base Django settings shared by all environments."""

from pathlib import Path
from typing import Any

from django.utils.translation import gettext_lazy as _

from .conf import get_config

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

config: dict[str, Any] = get_config()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR: Path = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Core security
# ---------------------------------------------------------------------------

SECRET_KEY: str = config["SECRET_KEY"]
DEBUG: bool = config["DEBUG"]
ALLOWED_HOSTS: list[str] = config["ALLOWED_HOSTS"]

# ---------------------------------------------------------------------------
# Application registry
# ---------------------------------------------------------------------------

INSTALLED_APPS: list[str] = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # API schema generation
    "drf_spectacular",
    "drf_spectacular_sidecar",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    # Local apps
    "apps.users",
    "apps.blog",
    "channels",
    "apps.notifications",
]

# ---------------------------------------------------------------------------
# Middleware stack
# ---------------------------------------------------------------------------

MIDDLEWARE: list[str] = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Language must be activated after AuthenticationMiddleware so the user
    # object is available when selecting the preferred_language.
    "apps.core.middleware.LanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Debug-only request logger (filtered via RequireDebugTrue in logging config).
    "apps.blog.middleware.DebugRequestLoggingMiddleware",
]

# ---------------------------------------------------------------------------
# E-mail (overridden per environment)
# ---------------------------------------------------------------------------

EMAIL_BACKEND: str = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# Cache (Redis via django-redis)
# ---------------------------------------------------------------------------

CACHES: dict[str, Any] = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config["REDIS_URL"],
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "blog_api",
        "VERSION": 1,
        # Language-aware key function — see apps/core/cache.py.
        "KEY_FUNCTION": "apps.core.cache.make_key",
    }
}

# ---------------------------------------------------------------------------
# URL routing
# ---------------------------------------------------------------------------

ROOT_URLCONF: str = "settings.urls"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

TEMPLATES: list[dict[str, Any]] = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION: str = "settings.wsgi.application"
# ASGI application — required for Django Channels
ASGI_APPLICATION = "settings.asgi.application"
 
# Channel layer — Redis backend for WebSocket group messaging
CHANNEL_LAYERS = { # type: ignore
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            # Use a separate Redis database (db=2) to avoid collisions
            # with the cache (db=0) and Celery broker (db=1).
            "hosts": [("redis", 6379)],
            "capacity": 1500,
            "expiry": 10,
        },
    },
}
 
# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS: list[dict[str, str]] = [
    {
        "NAME": (
            "django.contrib.auth.password_validation"
            ".UserAttributeSimilarityValidator"
        )
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------

LANGUAGE_CODE: str = "en-us"
TIME_ZONE: str = "UTC"
USE_I18N: bool = True
USE_TZ: bool = True

LANGUAGES: list[tuple[str, str]] = [
    ("en", _("English")),
    ("ru", _("Russian")),
    ("kz", _("Kazakh")),
]

LOCALE_PATHS: list[Path] = [BASE_DIR / "locale"]

# ---------------------------------------------------------------------------
# Static & media files
# ---------------------------------------------------------------------------

STATIC_URL: str = "static/"
STATIC_ROOT: Path = BASE_DIR / "staticfiles"
MEDIA_URL: str = "media/"
MEDIA_ROOT: Path = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Database primary key type
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD: str = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Custom user model
# ---------------------------------------------------------------------------

AUTH_USER_MODEL: str = "users.User"

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------

REST_FRAMEWORK: dict[str, Any] = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# ---------------------------------------------------------------------------
# drf-spectacular (OpenAPI schema)
# ---------------------------------------------------------------------------

SPECTACULAR_SETTINGS: dict[str, Any] = {
    "TITLE": "Blog API",
    "DESCRIPTION": "A comprehensive blog API with multilingual support",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
    },
}
