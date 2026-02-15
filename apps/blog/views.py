from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.core.cache import cache
from django.db.models import Q
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from .models import Post, Comment
from .serializers import (
    PostSerializer, PostCreateUpdateSerializer, 
    CommentSerializer
)
from .permissions import IsAuthorOrReadOnly
import json
import logging
import redis
from django.conf import settings

logger = logging.getLogger(__name__)

# Redis connection for pub/sub
redis_client = redis.Redis.from_url(settings.CACHES['default']['LOCATION'])

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
        
        # Only show published posts to unauthenticated users
        if not self.request.user.is_authenticated:
            queryset = queryset.filter(status='published')
        elif self.action == 'list':
            # Authors can see their own drafts
            queryset = queryset.filter(
                Q(status='published') | Q(author=self.request.user)
            )
        
        return queryset
    
    @method_decorator(ratelimit(key='user', rate='20/m', method='POST'))
    def create(self, request, *args, **kwargs):
        logger.info('Post creation attempt by: %s', request.user.email)
        return super().create(request, *args, **kwargs)
    
    def list(self, request, *args, **kwargs):
        # Try to get from cache
        cache_key = 'published_posts_list'
        cached_data = cache.get(cache_key)
        
        if cached_data and not request.user.is_authenticated:
            logger.debug('Returning cached posts list')
            return Response(cached_data)
        
        response = super().list(request, *args, **kwargs)
        
        # Cache for unauthenticated users only
        if not request.user.is_authenticated:
            cache.set(cache_key, response.data, 60)  # 60 seconds
            logger.debug('Cached posts list')
        
        return response
    
    def perform_create(self, serializer):
        post = serializer.save()
        # Invalidate cache
        cache.delete('published_posts_list')
        logger.info('Post created: %s', post.title)
    
    def perform_update(self, serializer):
        post = serializer.save()
        cache.delete('published_posts_list')
        logger.info('Post updated: %s', post.title)
    
    def perform_destroy(self, instance):
        cache.delete('published_posts_list')
        logger.info('Post deleted: %s', instance.title)
        instance.delete()
    
    @action(detail=True, methods=['get'])
    def comments(self, request, slug=None):
        post = self.get_object()
        comments = post.comments.select_related('author').all()
        serializer = CommentSerializer(comments, many=True)
        return Response(serializer.data)
    
    @comments.mapping.post
    def add_comment(self, request, slug=None):
        post = self.get_object()
        serializer = CommentSerializer(data=request.data)
        
        if serializer.is_valid():
            comment = Comment.objects.create(
                post=post,
                author=request.user,
                body=serializer.validated_data['body']
            )
            
            # Publish to Redis channel (JSON for listen_comments)
            redis_client.publish('comments', json.dumps({
                'post_id': post.id,
                'post_title': post.title,
                'author': request.user.email,
                'comment': comment.body,
                'created_at': str(comment.created_at)
            }))
            
            logger.info('Comment added to post: %s by %s', post.title, request.user.email)
            
            return Response(
                CommentSerializer(comment).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)