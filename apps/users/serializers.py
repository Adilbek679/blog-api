from rest_framework import serializers
from .models import User
import logging
from django.utils.translation import gettext_lazy as _
import pytz

logger = logging.getLogger(__name__)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'avatar', 'date_joined']
        read_only_fields = ['id', 'date_joined']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'password', 'password2', 'avatar']
    
    def validate(self, attrs: dict) -> dict:
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({
                "password": _("Passwords don't match")
            })
        return attrs
    
    def create(self, validated_data: dict) -> User:
        validated_data.pop('password2')
        password = validated_data.pop('password')
        
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        
        logger.info('User registered: %s', user.email)
        return user
    
class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['preferred_language']
        
    def validate_preferred_language(self, value):
        if value not in dict(User.LANGUAGE_CHOICES):
            raise serializers.ValidationError(
                _('Invalid language choice. Supported: en, ru, kz')
            )
        return value

class TimezoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['timezone']
        
    def validate_timezone(self, value):
        if value not in pytz.all_timezones:
            raise serializers.ValidationError(
                _('Invalid IANA timezone identifier')
            )
        return value
