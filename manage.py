#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from pathlib import Path


def main() -> None:
    """Configure the settings module and execute the requested command.

    The settings module is resolved by reading ``BLOG_ENV_ID`` from
    ``settings/.env``.  Supported values are ``local`` and ``prod``,
    corresponding to ``settings/env/local.py`` and ``settings/env/prod.py``.

    Falls back to ``settings.env.local`` when the file is absent or the
    variable is not set.
    """
    # Attempt to read the environment identifier from the settings/.env file.
    env_file: Path = Path(__file__).resolve().parent / "settings" / ".env"
    if env_file.exists():
        with open(env_file) as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() == "BLOG_ENV_ID":
                    os.environ["DJANGO_SETTINGS_MODULE"] = (
                        f"settings.env.{value.strip()}"
                    )
                    break

    # Default to the local development settings if not already set.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.env.local")

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
