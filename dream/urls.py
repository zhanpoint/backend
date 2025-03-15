from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views.sms import SendVerificationCodeAPIView
from .views.user import (
    UserRegistrationWithCodeAPIView,
    UserLoginAPIView,
    UserLogoutAPIView,
    UserProfileAPIView
)

# 设置API URL前缀
api_urlpatterns = [
    # 用户认证相关API
    path('auth/register-with-code/', UserRegistrationWithCodeAPIView.as_view(), name='api_register_with_code'),
    path('auth/login/', UserLoginAPIView.as_view(), name='api_login'),
    path('auth/logout/', UserLogoutAPIView.as_view(), name='api_logout'),
    path('auth/profile/', UserProfileAPIView.as_view(), name='api_profile'),

    # JWT令牌API
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # 短信验证码API
    path('sms/send-verification-code/', SendVerificationCodeAPIView.as_view(), name='send_verification_code'),
]

# 总路由
urlpatterns = [
    # API路由 - 所有API路由都以/api/前缀开始
    path('api/', include((api_urlpatterns, 'api'))),
]
