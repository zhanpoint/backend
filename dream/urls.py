from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from rest_framework.routers import DefaultRouter
from .views.sms import SendVerificationCodeAPIView
from .views.user import (
    UserRegistrationWithCodeAPIView,  # 手机号验证码注册API
    UserLoginAPIView,  # 用户名密码登录API
    PhoneLoginWithCodeAPIView,  # 手机号验证码登录API
    UserLogoutAPIView,  # 用户登出API
    UserProfileAPIView,  # 用户资料API
    ResetPasswordAPIView,  # 密码重置API
)
from .views import oss
from .views.dream import DreamViewSet

# 创建路由器并注册ViewSet
router = DefaultRouter()
router.register(r'dreams', DreamViewSet, basename='dream')

# 设置API URL前缀
api_urlpatterns = [
    # 用户认证相关API
    path('auth/register-with-code/', UserRegistrationWithCodeAPIView.as_view(), name='register'),
    path('auth/login/', UserLoginAPIView.as_view(), name='login'),
    path('auth/login-with-code/', PhoneLoginWithCodeAPIView.as_view(), name='login-with-code'),
    path('auth/logout/', UserLogoutAPIView.as_view(), name='logout'),
    path('auth/profile/', UserProfileAPIView.as_view(), name='profile'),
    path('auth/reset-password/', ResetPasswordAPIView.as_view(), name='reset-password'),

    
    # JWT令牌API
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # 短信验证码API
    path('sms/send-verification-code/', SendVerificationCodeAPIView.as_view(), name='send-code'),

    # OSS对象存储API
    path('image/upload/', oss.upload_image, name='upload-image'),
    path('image/delete/', oss.delete_image, name='delete-image'),
    
    # 包含ViewSet路由
    path('', include(router.urls)),
]

# 总路由
urlpatterns = [
    # API路由 - 所有API路由都以/api/前缀开始
    path('api/', include((api_urlpatterns, 'api'))),
]
