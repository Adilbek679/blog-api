from ..base import *  # noqa: F403

DEBUG = True # type: ignore

import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        env='BLOG_DATABASE_URL',
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600,
    )
}

# Logging for debug
LOGGING = { # type: ignore
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
        'verbose': {
            'format': '{asctime} {levelname} {name} {module} {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/app.log',  # noqa: F405
            'maxBytes': 5242880,  # 5 MB
            'backupCount': 3,
            'formatter': 'verbose',
        },
        'debug_requests': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/debug_requests.log',  # noqa: F405
            'maxBytes': 5242880,
            'backupCount': 2,
            'formatter': 'verbose',
            'filters': ['require_debug_true'],
        },
    },
    'loggers': {
        'apps.users': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.blog': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['file'],
            'level': 'WARNING',
            'propagate': False,
        },
        'blog.debug_requests': {
            'handlers': ['debug_requests'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Cache with Redis
CACHES = { # type: ignore
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config['REDIS_URL'],  # noqa: F405
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}