from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.users.views import AuthViewSet
from apps.blog.views import PostViewSet

# Rate-limited login: 10/minute per IP (per README)
RateLimitedTokenObtainPairView = method_decorator(
    ratelimit(key='ip', rate='10/m', method='POST'),
    name='post'
)(TokenObtainPairView)

router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='post')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API auth endpoints
    path('api/auth/register/', AuthViewSet.as_view({'post': 'register'}), name='register'),
    path('api/auth/token/', RateLimitedTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # API blog endpoints
    path('api/', include(router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
