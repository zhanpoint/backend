from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from rest_framework.routers import DefaultRouter
from .views.sms import VerificationCodeAPIView
from .views.email import EmailVerificationCodeAPIView
from .views.user import (
    UserViewSet,
    AuthSessionAPIView,
    UserPasswordAPIView,
    FeatureFlagsAPIView,
)
from .views import oss
from .views.dream import DreamViewSet, DreamJournalViewSet, SleepPatternViewSet

# 创建路由器并注册ViewSet
router = DefaultRouter()
router.register(r'dreams', DreamViewSet, basename='dream')
router.register(r'dream-journals', DreamJournalViewSet, basename='dream-journal')
router.register(r'sleep-patterns', SleepPatternViewSet, basename='sleep-pattern')
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

    # OSS文件存储API - RESTful规范，支持图片软删除
    path('files/upload-signature/', oss.upload_signature, name='file-upload-signature'),
    path('files/', oss.list_files, name='file-list'),
    path('files/delete/', oss.delete_file, name='file-delete'),
    path('files/restore/', oss.restore_file, name='file-restore'),  # 新增：恢复文件
    path('files/sts-token/', oss.get_sts_token, name='file-sts-token'),
    
    # 包含ViewSet路由
    path('', include(router.urls)),
]

# 总路由
urlpatterns = [
    # API路由 - 所有API路由都以/api/前缀开始
    path('api/', include((api_urlpatterns, 'api'))),
]
