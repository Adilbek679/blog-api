from pathlib import Path

from ..base import *

DEBUG = True

# Logging file size constants (no magic numbers)
LOG_FILE_MAX_BYTES = 5242880  # 5 MB
LOG_APP_BACKUP_COUNT = 3
LOG_DEBUG_REQUESTS_BACKUP_COUNT = 2

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Logging for debug
LOGGING = {
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
            'filename': BASE_DIR / 'logs/app.log',
            'maxBytes': LOG_FILE_MAX_BYTES,
            'backupCount': LOG_APP_BACKUP_COUNT,
            'formatter': 'verbose',
        },
        'debug_requests': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/debug_requests.log',
            'maxBytes': LOG_FILE_MAX_BYTES,
            'backupCount': LOG_DEBUG_REQUESTS_BACKUP_COUNT,
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
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config['REDIS_URL'],
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}