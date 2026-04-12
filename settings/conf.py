"""Project configuration loader using python-decouple."""

from typing import Any

from decouple import config


def get_config() -> dict[str, Any]:
    """Read environment variables and return a typed configuration dictionary.

    All variables are prefixed with ``BLOG_`` to avoid collisions with other
    applications running in the same environment.

    Returns:
        dict with keys:

        - ``SECRET_KEY`` (str): Django secret key.
        - ``DEBUG`` (bool): Enable debug mode.
        - ``ALLOWED_HOSTS`` (list[str]): Comma-separated host whitelist.
        - ``DATABASE_URL`` (str): DSN for the primary database.
        - ``REDIS_URL`` (str): Redis connection URL.
    """
    return {
        "SECRET_KEY": config("BLOG_SECRET_KEY"),
        "DEBUG": config("BLOG_DEBUG", default=False, cast=bool),
        "ALLOWED_HOSTS": config(
            "BLOG_ALLOWED_HOSTS",
            default="",
            cast=lambda v: [s.strip() for s in v.split(",") if s],
        ),
        "DATABASE_URL": config(
            "BLOG_DATABASE_URL",
            default="sqlite:///db.sqlite3",
        ),
        "REDIS_URL": config(
            "BLOG_REDIS_URL",
            default="redis://localhost:6379/0",
        ),
    }
