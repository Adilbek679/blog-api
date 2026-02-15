from ..base import *

DEBUG = False

# PostgreSQL (set BLOG_DATABASE_URL in settings/.env or environment)
import dj_database_url
DATABASES = {
    'default': dj_database_url.config(
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Redis cache (same as local; use BLOG_REDIS_URL)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config['REDIS_URL'],
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
