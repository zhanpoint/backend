from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.core.cache import cache
import logging

from apps.dream.serializers.user_serializers import VerificationCodeRequestSerializer
from apps.dream.utils.sms import SMSService
from config.env_config import FEATURE_FLAGS

# 获取日志记录器
logger = logging.getLogger(__name__)


class VerificationCodeAPIView(APIView):
    """
    短信验证码API
    """
    permission_classes = [AllowAny]

    def check_rate_limit(self, phone, limit_seconds=60):
        """
        检查发送频率限制
        
        Args:
            phone: 手机号
            limit_seconds: 限制时间间隔(秒)，默认60秒
            
        Returns:
            tuple: (是否允许发送, 剩余等待时间)
        """
        rate_limit_key = f"sms_rate_limit:{phone}"
        
        # 获取剩余的TTL
        ttl = cache.ttl(rate_limit_key)
        
        if ttl > 0:
            # 还在限制期内
            return False, ttl
            
        # 设置新的频率限制
        cache.set(rate_limit_key, True, timeout=limit_seconds)
        return True, 0

    def post(self, request):
        """
        发送短信验证码
        POST /api/verifications/sms/
        """
        # 检查短信服务是否启用
        if not FEATURE_FLAGS.get('SMS_SERVICE_ENABLED'):
            logger.warning("短信服务已被禁用，拒绝发送验证码请求")
            return Response({
                "code": 503,
                "message": "短信服务暂时不可用，请使用邮箱验证码",
                "errors": {"service": ["短信服务暂时不可用，请使用邮箱验证码"]}
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        serializer = VerificationCodeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                "code": 400,
                "message": "请求失败",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        phone = serializer.validated_data.get('phone')
        scene = serializer.validated_data['scene']

        if not phone:
            return Response({
                "code": 400,
                "message": "请求失败",
                "errors": {"phone": ["请提供手机号"]}
            }, status=status.HTTP_400_BAD_REQUEST)

        # 检查发送频率限制
        allowed, wait_time = self.check_rate_limit(phone)
        if not allowed:
            logger.warning(f"短信验证码发送过于频繁, 手机号: {phone}, 剩余等待时间: {wait_time}秒")
            return Response({
                "code": 429,
                "message": f"发送过于频繁，请{wait_time}秒后再试",
                "errors": {"phone": [f"发送过于频繁，请{wait_time}秒后再试"]}
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        try:
            result = SMSService.send_verification_code(phone, scene)
            if result:
                logger.info(f"短信验证码发送成功, 手机号: {phone}, 场景: {scene}")
                return Response({
                    "code": 200,
                    "message": "验证码发送成功"
                })
            else:
                logger.error(f"短信验证码发送失败, 手机号: {phone}, 场景: {scene}")
                return Response({
                    "code": 500,
                    "message": "验证码发送失败，请稍后重试"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.exception(f"发送短信验证码时发生异常: {str(e)}")
            return Response({
                "code": 500,
                "message": "服务器错误，验证码发送失败",
                "errors": {"detail": ["服务器内部错误，请稍后重试"]}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



