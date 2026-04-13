"""Settings package — load Celery app on Django startup."""

# This ensures the Celery app is always imported when Django starts,
# so that shared_task decorators use the correct app instance.
from .celery import app as celery_app # type: ignore

__all__ = ["celery_app"]