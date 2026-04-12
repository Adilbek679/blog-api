"""Custom Django cache key function with language-aware namespacing."""

from django.utils import translation


def make_key(key: str, key_prefix: str, version: int) -> str:
    """Build a cache key that includes the currently active language.

    Injecting the language code ensures that cached values for different
    locales never collide, which is important for multilingual content
    (e.g. translated category names in serialized posts).

    This function is referenced in ``settings/base.py`` via:

    .. code-block:: python

        CACHES = {
            "default": {
                ...
                "KEY_FUNCTION": "apps.core.cache.make_key",
            }
        }

    Args:
        key: The raw cache key produced by the calling code.
        key_prefix: The ``KEY_PREFIX`` value from the cache config.
        version: The ``VERSION`` value from the cache config.

    Returns:
        A fully-qualified cache key string in the form
        ``<prefix>:<lang>:<version>:<key>``.
    """
    lang: str = translation.get_language() or "en"
    return f"{key_prefix}:{lang}:{version}:{key}"
