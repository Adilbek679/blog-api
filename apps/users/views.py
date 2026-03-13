from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from .models import User
from .serializers import UserSerializer, RegisterSerializer
from .serializers import LanguageSerializer, TimezoneSerializer
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import translation
import logging

logger = logging.getLogger(__name__)

class AuthViewSet(viewsets.GenericViewSet):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['post'])
    @method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True))
    def register(self, request) -> Response:
        logger.info('Registration attempt for email: %s', request.data.get('email'))
        serializer = self.get_serializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()   
            user_language = request.data.get('preferred_language', 'en')
            with translation.override(user_language):
                subject = render_to_string('emails/welcome/subject.txt').strip()
                message = render_to_string('emails/welcome/body.txt', {
                    'user': user,
                    'user_language': user_language
                })
                send_mail(
                    subject=subject,
                    message=message,
                    from_email='noreply@blogapi.com',
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            
            refresh = RefreshToken.for_user(user)
            logger.info('User registered successfully: %s', user.email)
            
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        
        logger.warning('Registration failed: %s', serializer.errors)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    
    @action(detail=False, methods=['patch'], permission_classes=[IsAuthenticated])
    def language(self, request):
        serializer = LanguageSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info('User %s updated language to %s', request.user.email, request.data.get('preferred_language'))
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['patch'], permission_classes=[IsAuthenticated])
    def timezone(self, request):
        serializer = TimezoneSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info('User %s updated timezone to %s', request.user.email, request.data.get('timezone'))
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
