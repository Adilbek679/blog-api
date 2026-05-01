"""Production-style Django settings.

Used inside Docker Compose where the application is fronted by nginx.  All
external traffic enters through nginx on port 80, so ``ALLOWED_HOSTS`` only
needs to cover the hostnames nginx will set in the proxied ``Host`` header.
"""

from typing import Any

import dj_database_url

from ..base import *  # noqa: F401, F403
from ..base import config  # explicit import for type-checkers

# ---------------------------------------------------------------------------
# Core security
# ---------------------------------------------------------------------------

# DEBUG must be False in production-style runs so that:
#   • Django does not serve static files itself (nginx does).
#   • Detailed tracebacks are not leaked to clients.
#   • SecurityMiddleware enforces its full set of headers.
DEBUG: bool = False  # type: ignore[assignment]

# Hostnames the application will accept.  When sitting behind nginx on the
# developer's machine, requests arrive with `Host: localhost`; we also allow
# `127.0.0.1` for direct loopback testing, plus any value supplied via the
# `BLOG_ALLOWED_HOSTS` environment variable.
_ENV_HOSTS: list[str] = config["ALLOWED_HOSTS"]
ALLOWED_HOSTS: list[str] = list(  # type: ignore[assignment]
    {"localhost", "127.0.0.1", *_ENV_HOSTS}
)

# ---------------------------------------------------------------------------
# Database — PostgreSQL via BLOG_DATABASE_URL
# ---------------------------------------------------------------------------
# Falls back to a local SQLite file only if the env variable is missing,
# so the settings module remains importable for tooling (migrations dry-run,
# `manage.py check`, etc.) outside Docker Compose.
DATABASES: dict[str, Any] = {  # type: ignore[assignment]
    "default": dj_database_url.config(
        env="BLOG_DATABASE_URL",
        default="sqlite:///db.sqlite3",
        conn_max_age=600,
    )
}

# ---------------------------------------------------------------------------
# Cache — Redis via BLOG_REDIS_URL
# ---------------------------------------------------------------------------
CACHES: dict[str, Any] = {  # type: ignore[assignment]
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config["REDIS_URL"],
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# ---------------------------------------------------------------------------
# Reverse-proxy awareness
# ---------------------------------------------------------------------------
# nginx forwards the original request scheme via `X-Forwarded-Proto`; this
# tells Django to trust that header so `request.is_secure()` is correct
# behind a TLS-terminating proxy in the future.
SECURE_PROXY_SSL_HEADER: tuple[str, str] = ("HTTP_X_FORWARDED_PROTO", "https")