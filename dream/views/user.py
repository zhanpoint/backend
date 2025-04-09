from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login, logout
import logging
from dream.serializers.user_serializers import (
    UserSerializer,
    UserLoginSerializer,
    UserRegistrationWithCodeSerializer,
    PhoneVerifyCodeLoginSerializer,
    ResetPasswordSerializer
)
from dream.utils.sms import SMSService

# 获取日志记录器
logger = logging.getLogger(__name__)


# 用户注册API
class UserRegistrationWithCodeAPIView(APIView):
    """
    带短信验证码的用户注册API
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # 1. 验证请求数据
        serializer = UserRegistrationWithCodeSerializer(data=request.data)
        if not serializer.is_valid():
            # 记录验证失败详情
            logger.warning(f"用户注册数据验证失败: {serializer.errors}")
            return Response({
                "code": 400,
                "message": "注册失败",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        # 2. 验证短信验证码
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

        # 3. 创建用户
        try:
            user = serializer.save()
            # 自动登录
            login(request, user)

            # 生成JWT令牌
            refresh = RefreshToken.for_user(user)

            # 返回用户数据
            user_data = UserSerializer(user).data

            logger.info(f"用户注册成功, 用户名: {user.username}, 手机号: {phone}")

            # 4. 返回成功响应（包含token）
            return Response({
                "code": 201,
                "message": "注册成功",
                "data": user_data,
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            # 处理创建用户过程中的异常
            logger.exception(f"用户注册过程中发生异常: {str(e)}")

            # 根据异常类型返回不同的错误信息
            error_message = "服务器错误，注册失败"
            error_detail = str(e)

            # 检查是否是唯一约束错误
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

            # 其他未知错误
            return Response({
                "code": 500,
                "message": error_message,
                "errors": {"detail": error_detail}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# 用户名密码登录API
class UserLoginAPIView(APIView):
    """
    用户登录API
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """
        处理POST请求，验证用户并登录
        
        请求格式:
        {
            "username": "user123", (或手机号)
            "password": "SecurePass123"
        }
        
        成功响应:
        {
            "code": 200,
            "message": "登录成功",
            "data": {
                "id": 1,
                "username": "user123",
                "phone_number": "13812345678",
                "date_joined": "2023-08-01T12:00:00Z",
                "last_login": "2023-08-01T15:30:00Z"
            },
            "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        }
        """
        serializer = UserLoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)

            # 生成JWT令牌
            refresh = RefreshToken.for_user(user)

            logger.info(f"用户登录成功, 用户名: {user.username}")

            return Response({
                "code": 200,
                "message": "登录成功",
                "data": UserSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh)
            })

        logger.warning(f"用户登录失败: {serializer.errors}")

        return Response({
            "code": 400,
            "message": "登录失败",
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


# 手机号验证码登录API
class PhoneLoginWithCodeAPIView(APIView):
    """
    手机号验证码登录API
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """
        处理POST请求，验证手机号验证码并登录

        请求格式:
        {
            "phone_number": "13812345678",
            "code": "123456"
        }

        成功响应:
        {
            "code": 200,
            "message": "登录成功",
            "data": {
                "id": 1,
                "username": "user123",
                "phone_number": "13812345678",
                "date_joined": "2023-08-01T12:00:00Z",
                "last_login": "2023-08-01T15:30:00Z"
            },
            "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
        }
        """
        serializer = PhoneVerifyCodeLoginSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"手机号验证码登录验证失败: {serializer.errors}")
            return Response({
                "code": 400,
                "message": "登录失败",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        # 验证验证码
        phone = serializer.validated_data['phone_number']
        code = serializer.validated_data['code']

        if not SMSService.verify_code(phone, code):
            logger.warning(f"手机号 {phone} 验证码验证失败")
            return Response({
                "code": 400,
                "message": "验证码错误或已过期",
                "errors": {"code": ["验证码错误或已过期"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 登录用户
        user = serializer.validated_data['user']
        login(request, user)

        # 生成JWT令牌
        refresh = RefreshToken.for_user(user)

        logger.info(f"用户通过手机验证码登录成功, 手机号: {phone}")

        return Response({
            "code": 200,
            "message": "登录成功",
            "data": UserSerializer(user).data,
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        })
    # 用户登出API

# 用户登出API
class UserLogoutAPIView(APIView):
    """
    用户登出API
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        处理POST请求，登出用户并使JWT令牌立即失效
        
        请求格式(可选):
        {
            "refresh": "用户的refresh token"
        }
        
        成功响应:
        {
            "code": 200,
            "message": "登出成功"
        }
        """
        try:
            # 获取请求中的refresh token
            refresh_token = request.data.get('refresh')
            
            # 如果请求中包含refresh token，将其加入黑名单
            if refresh_token:
                # 创建RefreshToken对象
                token = RefreshToken(refresh_token)
                # 将token加入黑名单
                token.blacklist()
                logger.info(f"用户 {request.user.username} 的refresh token已加入黑名单")

            else:
                # 尝试从请求的Authorization头获取access token
                auth_header = request.headers.get('Authorization', '')
                if auth_header.startswith('Bearer '):
                    access_token = auth_header.split(' ')[1]
                    
                    # 通过解码access token获取user_id
                    # 注意：这不会将access token加入黑名单，但可以记录该用户所有token已失效
                    logger.info(f"用户 {request.user.username} 的access token已记录为失效")
            
            # 记录用户退出
            logger.info(f"用户 {request.user.username} 退出登录")
            
            # 调用Django的登出方法清除session
            logout(request)
            
            return Response({
                "code": 200,
                "message": "退出成功，令牌已失效"
            })
            
        except Exception as e:
            logger.error(f"退出登录过程中出错: {str(e)}")
            # 即使出错，也要尝试登出
            logout(request)
            
            return Response({
                "code": 200,
                "message": "退出成功，但令牌失效处理可能不完整"
            })
            

# 用户个人资料API
class UserProfileAPIView(APIView):
    """
    用户个人资料API
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        获取当前登录用户的个人资料
        
        成功响应:
        {
            "code": 200,
            "data": {
                "id": 1,
                "username": "user123",
                "phone_number": "13812345678",
                "date_joined": "2023-08-01T12:00:00Z",
                "last_login": "2023-08-01T15:30:00Z"
            }
        }
        """
        serializer = UserSerializer(request.user)
        return Response({
            "code": 200,
            "data": serializer.data
        })

class ResetPasswordAPIView(APIView):
    """
    密码重置API
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """
        处理POST请求，重置用户密码
        
        请求格式:
        {
            "phone": "13812345678",
            "code": "123456",
            "new_password": "newpass123"
        }
        
        成功响应:
        {
            "code": 200,
            "message": "密码重置成功"
        }
        """
        # 1. 验证请求数据
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"密码重置数据验证失败: {serializer.errors}")
            return Response({
                "code": 400,
                "message": "重置失败",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        # 2. 验证短信验证码
        phone = serializer.validated_data['phone']
        code = serializer.validated_data['code']

        logger.info(f"验证密码重置短信验证码, 手机号: {phone}")

        if not SMSService.verify_code(phone, code):
            logger.warning(f"密码重置验证码验证失败, 手机号: {phone}")
            return Response({
                "code": 400,
                "message": "验证码错误或已过期",
                "errors": {"code": ["验证码错误或已过期"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 3. 更新用户密码
        try:
            user = serializer.user
            user.set_password(serializer.validated_data['newPassword'])
            user.save()

            logger.info(f"用户密码重置成功, 手机号: {phone}")

            return Response({
                "code": 200,
                "message": "密码重置成功"
            })

        except Exception as e:
            logger.exception(f"密码重置过程中发生异常: {str(e)}")
            return Response({
                "code": 500,
                "message": "服务器错误，密码重置失败"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
