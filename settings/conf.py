from decouple import config


def get_config() -> dict:
    return {
        'SECRET_KEY': config('BLOG_SECRET_KEY'),
        'DEBUG': config('BLOG_DEBUG', default=False, cast=bool),
        'ALLOWED_HOSTS': config('BLOG_ALLOWED_HOSTS', default='', cast=lambda v: [s.strip() for s in v.split(',') if s]),
        'DATABASE_URL': config('BLOG_DATABASE_URL', default='sqlite:///db.sqlite3'),
        'REDIS_URL': config('BLOG_REDIS_URL', default='redis://localhost:6379/0'),
    }

