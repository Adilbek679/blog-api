#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def main():
    """Run administrative tasks."""
    # Read BLOG_ENV_ID from settings/.env to pick settings.env.local or settings.env.prod
    env_file = Path(__file__).resolve().parent / 'settings' / '.env'
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.split('=', 1)
                    if key.strip() == 'BLOG_ENV_ID':
                        os.environ['DJANGO_SETTINGS_MODULE'] = f"settings.env.{value.strip()}"
                        break
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings.env.local')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
