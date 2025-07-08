from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from rest_framework.routers import DefaultRouter
from .views.sms import VerificationCodeAPIView
from .views.email import EmailVerificationCodeAPIView
from .views.user import (
    UserViewSet,  # 用户资源ViewSet
    AuthSessionAPIView,  # 认证会话API
    UserPasswordAPIView,  # 用户密码API
    FeatureFlagsAPIView,  # 功能开关状态API
)
from .views import oss
from .views.dream import DreamViewSet

# 创建路由器并注册ViewSet
router = DefaultRouter()
router.register(r'dreams', DreamViewSet, basename='dream')
router.register(r'users', UserViewSet, basename='user')

# 设置API URL前缀
api_urlpatterns = [
    # 认证会话API - 统一的登录/登出接口
    path('auth/sessions/', AuthSessionAPIView.as_view(), name='auth-sessions'),
    
    # 用户密码管理API
    path('users/password/', UserPasswordAPIView.as_view(), name='user-password'),
    
    # 功能开关状态API
    path('system/features/', FeatureFlagsAPIView.as_view(), name='feature-flags'),
    
    # JWT令牌API
    path('auth/tokens/', TokenObtainPairView.as_view(), name='token-obtain'),
    path('auth/tokens/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    
    # 验证码API
    path('verifications/sms/', VerificationCodeAPIView.as_view(), name='sms-verification'),
    path('verifications/email/', EmailVerificationCodeAPIView.as_view(), name='email-verification'),

    # OSS对象存储API
    path('uploads/images/', oss.upload_image, name='upload-image'),
    path('uploads/images/<str:image_id>/', oss.delete_image, name='delete-image'),
    
    # 包含ViewSet路由
    path('', include(router.urls)),
]

# 总路由
urlpatterns = [
    # API路由 - 所有API路由都以/api/前缀开始
    path('api/', include((api_urlpatterns, 'api'))),
]
