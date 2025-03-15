from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import login, logout
import logging
from dream.serializers import (
    UserSerializer,
    UserLoginSerializer,
    UserRegistrationWithCodeSerializer
)
from dream.utils.sms import SMSService

# 获取日志记录器
logger = logging.getLogger(__name__)


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


class UserLogoutAPIView(APIView):
    """
    用户登出API
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        处理POST请求，登出用户
        
        成功响应:
        {
            "code": 200,
            "message": "登出成功"
        }
        """
        logout(request)
        return Response({
            "code": 200,
            "message": "登出成功"
        })


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