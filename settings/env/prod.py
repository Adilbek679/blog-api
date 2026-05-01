from ..base import *  # noqa: F403

import dj_database_url

DEBUG = False  # type: ignore

# Hostnames the application will accept behind nginx.
ALLOWED_HOSTS = list(  # type: ignore
    {"localhost", "127.0.0.1", *config["ALLOWED_HOSTS"]}
)

# Trust X-Forwarded-Proto header from nginx to determine if the request is secure().
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# PostgreSQL (set BLOG_DATABASE_URL in settings/.env or environment)
DATABASES = {
    "default": dj_database_url.config(
        env="BLOG_DATABASE_URL",
        default="sqlite:///db.sqlite3",
        conn_max_age=600,
    )
}

# Redis cache (same as local; use BLOG_REDIS_URL)
CACHES = {  # type: ignore
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config["REDIS_URL"],  # noqa: F405
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}
