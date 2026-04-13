"""Celery application configuration for the blog project."""

import os

from celery import Celery
from celery.schedules import crontab # type: ignore

# Tell Celery which Django settings module to use.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings.env.local")

app = Celery("blog") # type: ignore

# Read Celery config from Django settings — all keys prefixed with CELERY_.
app.config_from_object("django.conf:settings", namespace="CELERY") # type: ignore

# Auto-discover tasks in all INSTALLED_APPS (looks for tasks.py in each app).
app.autodiscover_tasks() # type: ignore

# ---------------------------------------------------------------------------
# Scheduled tasks (Celery Beat)
# ---------------------------------------------------------------------------

app.conf.beat_schedule = { # type: ignore
    # Publish posts whose publish_at <= now() every minute.
    "publish-scheduled-posts": {
        "task": "apps.blog.tasks.publish_scheduled_posts",
        "schedule": 60.0,  # every 60 seconds
    },
    # Delete notifications older than 30 days — runs daily at 03:00 UTC.
    "clear-expired-notifications": {
        "task": "apps.notifications.tasks.clear_expired_notifications",
        "schedule": crontab(hour=3, minute=0),
    },
    # Log daily stats — runs daily at 00:00 UTC.
    "generate-daily-stats": {
        "task": "apps.blog.tasks.generate_daily_stats",
        "schedule": crontab(hour=0, minute=0),
    },
}

app.conf.timezone = "UTC" # type: ignore