from functools import wraps
from django.http import JsonResponse
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

def rate_limit(key_prefix: str, limit: int, period: int = 60):
    """
    Custom rate limiting decorator using Redis cache.
    
    Args:
        key_prefix: Prefix for cache key
        limit: Number of allowed requests
        period: Time period in seconds (default 60)
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Get client IP
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            
            # Create cache key
            if request.user.is_authenticated:
                key = f"{key_prefix}:user:{request.user.id}"
            else:
                key = f"{key_prefix}:ip:{ip}"
            
            # Get current count
            count = cache.get(key, 0)
            
            if count >= limit:
                logger.warning('Rate limit exceeded for %s', key)
                return JsonResponse(
                    {'detail': 'Too many requests. Try again later.'},
                    status=429
                )
            
            # Increment count
            cache.set(key, count + 1, period)
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator