from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)

class RateLimitedTokenObtainPairView(TokenObtainPairView):
    """
    Token obtain view with rate limiting: 10 requests per minute per IP
    """
    
    @method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True))
    def post(self, request, *args, **kwargs):
        logger.info('Login attempt from IP: %s', request.META.get('REMOTE_ADDR'))
        
        # Проверяем, не заблокирован ли запрос ratelimit-ом
        if getattr(request, 'limited', False):
            logger.warning('Rate limit exceeded for login from IP: %s', 
                          request.META.get('REMOTE_ADDR'))
            return Response(
                {'detail': 'Too many login attempts. Try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        try:
            response = super().post(request, *args, **kwargs)
            if response.status_code == 200:
                logger.info('Login successful for user')
            else:
                logger.warning('Login failed: invalid credentials')
            return response
        except Exception as e:
            logger.exception('Login error: %s', str(e))
            raise

class RateLimitedTokenRefreshView(TokenRefreshView):
    """
    Token refresh view with rate limiting
    """
    
    @method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True))
    def post(self, request, *args, **kwargs):
        if getattr(request, 'limited', False):
            return Response(
                {'detail': 'Too many refresh attempts. Try again later.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        return super().post(request, *args, **kwargs)