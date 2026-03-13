import json
import logging
import asyncio
import httpx
import pytz
import redis
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import translation
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from .models import Post, Comment, PostStatus
from .permissions import IsAuthorOrReadOnly
from .serializers import (
    CommentSerializer,
    PostCreateUpdateSerializer,
    PostSerializer,
)

logger = logging.getLogger(__name__)

# Constants
CACHE_KEY_POSTS_LIST = 'published_posts_list'
CACHE_TTL_SECONDS = 60

# Redis connection for pub/sub
try:
    redis_client = redis.Redis.from_url(settings.CACHES['default']['LOCATION'])
    redis_client.ping()
except redis.ConnectionError:
    logger.warning('Redis connection failed, pub/sub disabled')
    redis_client = None

class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    permission_classes = [IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    lookup_field = 'slug'
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return PostCreateUpdateSerializer
        return PostSerializer
    
    def get_queryset(self):
        queryset = Post.objects.select_related('author', 'category')\
                               .prefetch_related('tags', 'comments')
        
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(status=PostStatus.PUBLISHED)
        elif self.action == 'list':
            queryset = queryset.filter(
                Q(status=PostStatus.PUBLISHED) | Q(author=self.request.user)
            )
        
        return queryset
    
    @method_decorator(ratelimit(key='user', rate='20/m', method='POST'))
    def create(self, request, *args, **kwargs) -> Response:
        logger.info('Post creation attempt by: %s', request.user.email)
        return super().create(request, *args, **kwargs)
    
    def list(self, request, *args, **kwargs) -> Response:
        """
        List posts with language-aware caching and timezone conversion.
        """
        lang = translation.get_language()
        cache_key = f'{CACHE_KEY_POSTS_LIST}:{lang}'
        
        # Try cache for unauthenticated users
        if not request.user.is_authenticated:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.debug('Returning cached posts list for language %s', lang)
                return Response(cached_data)
        
        # Get fresh data
        response = super().list(request, *args, **kwargs)
        
        # Convert dates to user's timezone if authenticated
        if request.user.is_authenticated and request.user.timezone:
            try:
                user_tz = pytz.timezone(request.user.timezone)
                for post in response.data.get('results', []):
                    if 'created_at' in post:
                        # Convert string to datetime, convert timezone, and format
                        # This is a placeholder - actual implementation depends on your date format
                        pass
            except pytz.UnknownTimeZoneError:
                logger.warning('Unknown timezone: %s', request.user.timezone)
        
        # Cache for unauthenticated users
        if not request.user.is_authenticated:
            cache.set(cache_key, response.data, CACHE_TTL_SECONDS)
            logger.debug('Cached posts list for language %s', lang)
        
        return response
    
    def perform_create(self, serializer) -> None:
        """Create post and invalidate cache for all languages."""
        post = serializer.save()
        # Invalidate cache for ALL languages
        for lang_code, _ in settings.LANGUAGES:
            cache.delete(f'{CACHE_KEY_POSTS_LIST}:{lang_code}')
        logger.info('Post created: %s', post.title)

    def perform_update(self, serializer) -> None:
        post = serializer.save()
        for lang_code, _ in settings.LANGUAGES:
            cache.delete(f'{CACHE_KEY_POSTS_LIST}:{lang_code}')
        logger.info('Post updated: %s', post.title)

    def perform_destroy(self, instance) -> None:
        for lang_code, _ in settings.LANGUAGES:
            cache.delete(f'{CACHE_KEY_POSTS_LIST}:{lang_code}')
        logger.info('Post deleted: %s', instance.title)
        instance.delete()
    
    @action(detail=True, methods=['get'])
    def comments(self, request, slug=None) -> Response:
        """List comments for a specific post."""
        post = self.get_object()
        comments = post.comments.select_related('author').all()
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)
    
    @comments.mapping.post
    def add_comment(self, request, slug=None) -> Response:
        """Add a comment to a post and publish to Redis."""
        post = self.get_object()
        serializer = CommentSerializer(data=request.data)
        
        if serializer.is_valid():
            comment = Comment.objects.create(
                post=post,
                author=request.user,
                body=serializer.validated_data['body']
            )
            
            # Publish to Redis channel if available
            if redis_client:
                redis_client.publish('comments', json.dumps({
                    'post_id': post.id,
                    'post_slug': post.slug,
                    'post_title': post.title,
                    'author_id': request.user.id,
                    'author_email': request.user.email,
                    'comment': comment.body,
                    'created_at': str(comment.created_at)
                }))
            
            logger.info('Comment added to post: %s by %s', post.title, request.user.email)
            
            return Response(
                CommentSerializer(comment).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get blog statistics with external API data.
        
        This endpoint uses async to fetch data concurrently from external APIs.
        If written synchronously, total time would be sum of both API calls (~300-500ms).
        With asyncio.gather, we wait for both concurrently, so total time is only
        as long as the slowest call.
        """
        return Response(self._get_stats_sync(request))
    
    def _get_stats_sync(self, request):
        """Synchronous wrapper for async stats gathering."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self._get_stats_async(request))
        finally:
            loop.close()
    
    async def _get_stats_async(self, request):
        """Async implementation that fetches data concurrently."""
        async with httpx.AsyncClient() as client:
            # Fetch blog counts from database
            blog_counts = await sync_to_async(self._get_blog_counts)()
            
            # Fetch external data concurrently
            exchange_task = client.get('https://open.er-api.com/v6/latest/USD')
            time_task = client.get('https://timeapi.io/api/time/current/zone?timeZone=Asia/Almaty')
            
            exchange_response, time_response = await asyncio.gather(
                exchange_task, 
                time_task,
                return_exceptions=True
            )
            
            # Process exchange rates
            exchange_rates = {'KZT': 0, 'RUB': 0, 'EUR': 0}
            if not isinstance(exchange_response, Exception) and exchange_response.status_code == 200:
                data = exchange_response.json()
                rates = data.get('rates', {})
                exchange_rates = {
                    'KZT': rates.get('KZT', 0),
                    'RUB': rates.get('RUB', 0),
                    'EUR': rates.get('EUR', 0),
                }
            elif isinstance(exchange_response, Exception):
                logger.error('Exchange rate API error: %s', exchange_response)
            
            # Process current time
            current_time = timezone.now().isoformat()
            if not isinstance(time_response, Exception) and time_response.status_code == 200:
                data = time_response.json()
                current_time = data.get('dateTime', current_time)
            elif isinstance(time_response, Exception):
                logger.error('Time API error: %s', time_response)
            
            return {
                'blog': blog_counts,
                'exchange_rates': exchange_rates,
                'current_time': current_time
            }
    
    def _get_blog_counts(self):
        """Get blog statistics from database."""
        from apps.blog.models import Post, Comment
        from apps.users.models import User
        
        return {
            'total_posts': Post.objects.count(),
            'total_comments': Comment.objects.count(),
            'total_users': User.objects.count(),
        }