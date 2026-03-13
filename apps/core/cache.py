from django.core.cache import caches

def make_key(key, key_prefix, version):
    from django.utils import translation
    lang = translation.get_language()
    return f'{key_prefix}:{lang}:{version}:{key}'