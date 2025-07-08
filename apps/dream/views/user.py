from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login, logout
from django.core.cache import cache
from apps.dream.models import User
import logging
from apps.dream.serializers.user_serializers import (
    UserSerializer,
    UserLoginSerializer,
    UserRegistrationSerializer,
    PhoneLoginSerializer,
    EmailLoginSerializer,
    PasswordResetSerializer,
)
from apps.dream.utils.sms import SMSService
from apps.dream.utils.email import EmailService
from config.env_config import FEATURE_FLAGS

# 获取日志记录器
logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ModelViewSet):
    """
    用户资源ViewSet - 处理用户CRUD操作
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        """
        根据不同的操作返回不同的权限类
        - create（注册）: 允许匿名访问，注册操作应该是公开的，不需要认证。
        - 其他操作: 需要认证
        """
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        """
        只返回当前用户的数据
        """
        return [self.request.user] if self.request.user.is_authenticated else []

    def create(self, request, *args, **kwargs):
        """
        用户注册 - 支持手机号和邮箱注册
        POST /api/users/
        """
        # 根据请求数据中是否有phone_number或email来判断注册方式
        phone_number = request.data.get('phone_number')
        email = request.data.get('email')
        code = request.data.get('code')

        if phone_number:
            return self._register_with_phone(request)
        elif email:
            return self._register_with_email(request)
        else:
            return Response({
                "code": 400,
                "message": "注册失败",
                "errors": {"detail": ["请提供手机号或邮箱地址"]}
            }, status=status.HTTP_400_BAD_REQUEST)

    def _register_with_phone(self, request):
        """手机号验证码注册"""
        serializer = UserRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"用户注册数据验证失败: {serializer.errors}")
            return Response({
                "code": 400,
                "message": "注册失败",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        # 验证短信验证码
        phone = serializer.validated_data['phone_number']
        code = serializer.validated_data['code']

        logger.info(f"验证用户注册短信验证码, 手机号: {phone}")

        if not SMSService.verify_code(phone, code):
            logger.warning(f"用户注册验证码验证失败, 手机号: {phone}")
            return Response({
                "code": 400,
                "message": "验证码错误或已过期",
                "errors": {"code": ["验证码错误或已过期"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = serializer.save()
            login(request, user)
            refresh = RefreshToken.for_user(user)
            user_data = UserSerializer(user).data

            logger.info(f"用户注册成功, 用户名: {user.username}, 手机号: {phone}")

            return Response({
                "code": 201,
                "message": "注册成功",
                "data": user_data,
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception(f"用户注册过程中发生异常: {str(e)}")
            return self._handle_registration_error(e)

    def _register_with_email(self, request):
        """邮箱验证码注册"""
        serializer = UserRegistrationSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"邮箱注册数据验证失败: {serializer.errors}")
            return Response({
                "code": 400,
                "message": "注册失败",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        # 验证邮箱验证码
        email = serializer.validated_data['email']
        code = serializer.validated_data['code']

        logger.info(f"验证用户注册邮箱验证码, 邮箱: {email}")

        if not EmailService.verify_code(email, code):
            logger.warning(f"用户注册验证码验证失败, 邮箱: {email}")
            return Response({
                "code": 400,
                "message": "验证码错误或已过期",
                "errors": {"code": ["验证码错误或已过期"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = serializer.save()
            login(request, user)
            refresh = RefreshToken.for_user(user)
            user_data = UserSerializer(user).data

            logger.info(f"用户注册成功, 用户名: {user.username}, 邮箱: {email}")

            return Response({
                "code": 201,
                "message": "注册成功",
                "data": user_data,
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.exception(f"邮箱注册过程中发生异常: {str(e)}")
            return self._handle_registration_error(e)

    def _handle_registration_error(self, exception):
        """处理注册错误"""
        error_detail = str(exception)
        logger.error(f"注册错误详情: {error_detail}")  # 仅在日志中记录详细错误
        
        if "unique constraint" in error_detail.lower() or "duplicate" in error_detail.lower():
            if "username" in error_detail.lower():
                return Response({
                    "code": 400,
                    "message": "注册失败",
                    "errors": {"username": ["该用户名已被注册"]}
                }, status=status.HTTP_400_BAD_REQUEST)
            elif "phone_number" in error_detail.lower():
                return Response({
                    "code": 400,
                    "message": "注册失败",
                    "errors": {"phone_number": ["该手机号已被注册"]}
                }, status=status.HTTP_400_BAD_REQUEST)
        elif "email" in error_detail.lower():
            return Response({
                "code": 400,
                "message": "注册失败",
                "errors": {"email": ["该邮箱已被注册"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "code": 500,
        "message": "服务器错误，注册失败",
        "errors": {"detail": ["服务器内部错误，请稍后重试"]}  # 不暴露具体错误信息
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def retrieve(self, request, *args, **kwargs):
        """
        获取当前用户信息
        GET /api/users/{id}/
        """
        user_data = UserSerializer(request.user).data
        return Response({
            "code": 200,
            "message": "获取用户信息成功",
            "data": user_data
        })

    def update(self, request, *args, **kwargs):
        """
        更新用户信息
        PUT /api/users/{id}/
        """
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"用户信息更新成功, 用户ID: {request.user.id}")
            return Response({
                "code": 200,
                "message": "用户信息更新成功",
                "data": serializer.data
            })
        
        logger.warning(f"用户信息更新失败: {serializer.errors}")
        return Response({
            "code": 400,
            "message": "用户信息更新失败",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class AuthSessionAPIView(APIView):
    """
    认证会话API - 统一处理登录和登出
    """
    
    def get_permissions(self):
        """
        POST（登录）允许匿名，DELETE（登出）需要认证
        """
        if self.request.method == 'POST':
            return [AllowAny()]
        return [IsAuthenticated()]

    def check_login_attempts(self, identifier, max_attempts=5, lockout_time=900):
        """
        检查登录尝试次数
        
        Args:
            identifier: 用户标识（用户名、手机号或邮箱）
            max_attempts: 最大尝试次数，默认5次
            lockout_time: 锁定时间（秒），默认15分钟
            
        Returns:
            tuple: (是否允许登录, 剩余锁定时间)
        """
        attempts_key = f"login_attempts:{identifier}"
        lockout_key = f"login_lockout:{identifier}"
        
        # 检查是否被锁定
        lockout_ttl = cache.ttl(lockout_key)
        if lockout_ttl > 0:
            return False, lockout_ttl
        
        # 获取当前尝试次数
        attempts = cache.get(attempts_key, 0)
        
        if attempts >= max_attempts:
            # 设置锁定
            cache.set(lockout_key, True, timeout=lockout_time)
            cache.delete(attempts_key)
            return False, lockout_time
        
        return True, 0
    
    def increment_login_attempts(self, identifier):
        """
        增加登录尝试次数
        """
        attempts_key = f"login_attempts:{identifier}"
        attempts = cache.get(attempts_key, 0)
        cache.set(attempts_key, attempts + 1, timeout=3600)  # 1小时后重置计数
    
    def reset_login_attempts(self, identifier):
        """
        重置登录尝试次数（登录成功后调用）
        """
        attempts_key = f"login_attempts:{identifier}"
        lockout_key = f"login_lockout:{identifier}"
        cache.delete(attempts_key)
        cache.delete(lockout_key)

    def post(self, request):
        """
        用户登录 - 支持用户名密码、手机验证码、邮箱验证码登录
        POST /api/auth/sessions/
        """
        # 根据请求参数判断登录方式
        if 'phone_number' in request.data and 'code' in request.data:
            return self._login_with_phone_code(request)
        elif 'email' in request.data and 'code' in request.data:
            return self._login_with_email_code(request)
        else:
            return self._login_with_password(request)

    def _login_with_password(self, request):
        """用户名密码登录"""
        username = request.data.get('username', '')
        
        # 检查登录尝试次数
        allowed, lockout_time = self.check_login_attempts(username)
        if not allowed:
            logger.warning(f"用户登录被锁定: {username}, 剩余锁定时间: {lockout_time}秒")
            return Response({
                "code": 429,
                "message": f"登录失败次数过多，请{lockout_time}秒后再试",
                "errors": {"username": [f"账户已被锁定，请{lockout_time}秒后再试"]}
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        serializer = UserLoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            refresh = RefreshToken.for_user(user)

            # 登录成功，重置尝试次数
            self.reset_login_attempts(username)
            logger.info(f"用户登录成功, 用户名: {user.username}")

            return Response({
                "code": 200,
                "message": "登录成功",
                "data": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            })

        # 登录失败，增加尝试次数
        self.increment_login_attempts(username)
        logger.warning(f"用户登录失败: {serializer.errors}")

        return Response({
            "code": 400,
            "message": "登录失败",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    def _login_with_phone_code(self, request):
        """手机验证码登录"""
        serializer = PhoneLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "code": 400,
                "message": "登录失败",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        phone_number = serializer.validated_data['phone_number']
        code = serializer.validated_data['code']

        if not SMSService.verify_code(phone_number, code):
            logger.warning(f"手机验证码登录失败, 手机号: {phone_number}")
            return Response({
                "code": 400,
                "message": "验证码错误或已过期",
                "errors": {"code": ["验证码错误或已过期"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data['user']
        login(request, user)
        refresh = RefreshToken.for_user(user)
        
        logger.info(f"手机验证码登录成功, 用户名: {user.username}")
        
        return Response({
            "code": 200,
            "message": "登录成功",
            "data": UserSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        })

    def _login_with_email_code(self, request):
        """邮箱验证码登录"""
        serializer = EmailLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "code": 400,
                "message": "登录失败",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']
        code = serializer.validated_data['code']

        if not EmailService.verify_code(email, code):
            logger.warning(f"邮箱验证码登录失败, 邮箱: {email}")
            return Response({
                "code": 400,
                "message": "验证码错误或已过期",
                "errors": {"code": ["验证码错误或已过期"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data['user']
        login(request, user)
        refresh = RefreshToken.for_user(user)

        logger.info(f"邮箱验证码登录成功, 用户名: {user.username}")

        return Response({
            "code": 200,
            "message": "登录成功",
            "data": UserSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        })

    def delete(self, request):
        """
        用户登出
        DELETE /api/auth/sessions/
        """
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            logout(request)
            logger.info(f"用户登出成功, 用户ID: {request.user.id}")

            return Response({
                "code": 200,
                "message": "登出成功"
            })
        except Exception as e:
            logger.exception(f"用户登出过程中发生异常: {str(e)}")
            return Response({
                "code": 500,
                "message": "登出失败",
                "errors": {"detail": ["服务器内部错误，请稍后重试"]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UserPasswordAPIView(APIView):
    """
    用户密码管理API
    """
    permission_classes = [AllowAny]

    def put(self, request):
        """
        重置密码 - 支持手机号和邮箱重置
        PUT /api/users/password/
        """
        # 根据请求数据判断重置方式
        if 'phone' in request.data:
            return self._reset_password_with_phone(request)
        elif 'email' in request.data:
            return self._reset_password_with_email(request)
        else:
            return Response({
                "code": 400,
                "message": "重置失败",
                "errors": {"detail": ["请提供手机号或邮箱地址"]}
            }, status=status.HTTP_400_BAD_REQUEST)

    def _reset_password_with_phone(self, request):
        """手机号重置密码"""
        serializer = PasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "code": 400,
                "message": "重置失败",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        phone = serializer.validated_data['phone']
        code = serializer.validated_data['code']
        new_password = serializer.validated_data['newPassword']

        if not SMSService.verify_code(phone, code):
            logger.warning(f"密码重置验证码验证失败, 手机号: {phone}")
            return Response({
                "code": 400,
                "message": "验证码错误或已过期",
                "errors": {"code": ["验证码错误或已过期"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(phone_number=phone)
            user.set_password(new_password)
            user.save()

            logger.info(f"密码重置成功, 手机号: {phone}")

            return Response({
                "code": 200,
                "message": "密码重置成功"
            })
        except User.DoesNotExist:
            return Response({
                "code": 400,
                "message": "该手机号未注册",
                "errors": {"phone": ["该手机号未注册"]}
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"密码重置过程中发生异常: {str(e)}")
            return Response({
                "code": 500,
                "message": "服务器错误，密码重置失败",
                "errors": {"detail": ["服务器内部错误，请稍后重试"]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _reset_password_with_email(self, request):
        """邮箱重置密码"""
        serializer = PasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "code": 400,
                "message": "重置失败",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data.get('email')
        code = serializer.validated_data['code']
        new_password = serializer.validated_data['newPassword']

        if not EmailService.verify_code(email, code):
            logger.warning(f"密码重置验证码验证失败, 邮箱: {email}")
            return Response({
                "code": 400,
                "message": "验证码错误或已过期",
                "errors": {"code": ["验证码错误或已过期"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            user.set_password(new_password)
            user.save()

            logger.info(f"密码重置成功, 邮箱: {email}")

            return Response({
                "code": 200,
                "message": "密码重置成功"
            })
        except User.DoesNotExist:
            return Response({
                "code": 400,
                "message": "该邮箱未注册",
                "errors": {"email": ["该邮箱未注册"]}
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.exception(f"密码重置过程中发生异常: {str(e)}")
            return Response({
                "code": 500,
                "message": "服务器错误，密码重置失败",
                "errors": {"detail": ["服务器内部错误，请稍后重试"]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FeatureFlagsAPIView(APIView):
    """
    获取功能开关状态API
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """
        获取前端需要的功能开关状态
        """
        try:
            # 只返回前端需要的功能开关
            frontend_flags = {
                'SMS_SERVICE_ENABLED': FEATURE_FLAGS.get('SMS_SERVICE_ENABLED', False),
                'EMAIL_SERVICE_ENABLED': FEATURE_FLAGS.get('EMAIL_SERVICE_ENABLED', True),
                'PASSWORD_LOGIN_ENABLED': True,  # 密码登录始终启用
            }
            
            return Response({
                'code': 200,
                'message': '获取功能开关状态成功',
                'data': frontend_flags
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"获取功能开关状态失败: {str(e)}")
            return Response({
                'code': 500,
                'message': '获取功能开关状态失败'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
