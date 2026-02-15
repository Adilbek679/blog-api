from rest_framework import serializers
from .models import Post, Comment, Category, Tag
from apps.users.serializers import UserSerializer
import logging

logger = logging.getLogger(__name__)

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug']

class CommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    
    class Meta:
        model = Comment
        fields = ['id', 'author', 'body', 'created_at']
        read_only_fields = ['id', 'author', 'created_at']

class PostSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)
    
    class Meta:
        model = Post
        fields = [
            'id', 'author', 'title', 'slug', 'body', 
            'category', 'tags', 'status', 'created_at', 
            'updated_at', 'comments_count'
        ]
        read_only_fields = ['id', 'author', 'slug', 'created_at', 'updated_at']

class PostCreateUpdateSerializer(serializers.ModelSerializer):
    category_id = serializers.IntegerField(write_only=True)
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Post
        fields = ['title', 'body', 'category_id', 'tag_ids', 'status']
    
    def create(self, validated_data: dict) -> Post:
        tag_ids = validated_data.pop('tag_ids', [])
        category_id = validated_data.pop('category_id')
        
        post = Post.objects.create(
            author=self.context['request'].user,
            category_id=category_id,
            **validated_data
        )
        
        if tag_ids:
            post.tags.set(tag_ids)
        
        logger.info('Post created: %s by %s', post.title, post.author.email)
        return post
    
    def update(self, instance: Post, validated_data: dict) -> Post:
        tag_ids = validated_data.pop('tag_ids', None)
        category_id = validated_data.pop('category_id', None)
        
        if category_id:
            instance.category_id = category_id
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        if tag_ids is not None:
            instance.tags.set(tag_ids)
        
        logger.info('Post updated: %s', instance.title)
        return instance