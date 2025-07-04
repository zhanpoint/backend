from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
import logging
from dream.serializers.user_serializers import VerificationCodeRequestSerializer
from dream.utils.email import EmailService
from dream.models import User

# 获取日志记录器
logger = logging.getLogger(__name__)


class EmailVerificationCodeAPIView(APIView):
    """
    邮箱验证码API
    """
    permission_classes = [AllowAny]

    def post(self, request):
        """
        发送邮箱验证码
        POST /api/verifications/email/
        """
        serializer = VerificationCodeRequestSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"邮箱验证码请求数据验证失败: {serializer.errors}")
            return Response({
                "code": 400,
                "message": "请求参数错误",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data.get('email')
        scene = serializer.validated_data['scene']

        if not email:
            return Response({"code": 400, "message": "邮箱地址不能为空"}, status=status.HTTP_400_BAD_REQUEST)

        # 检查发送频率
        email_service = EmailService()
        allowed, wait_time = email_service.check_rate_limit(email)
        if not allowed:
            logger.warning(f"邮箱验证码发送频率过快: {email}, 剩余等待时间: {wait_time}秒")
            return Response({
                "code": 429,
                "message": f"发送频率过快，请{wait_time}秒后再试",
                "errors": {"email": [f"发送频率过快，请{wait_time}秒后再试"]}
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        # 根据场景进行用户存在性检查
        user_exists = User.objects.filter(email=email).exists()

        if scene == 'register' and user_exists:
            return Response({"code": 400, "message": "该邮箱已被注册"}, status=status.HTTP_400_BAD_REQUEST)
        if scene in ['login', 'reset_password'] and not user_exists:
            return Response({"code": 400, "message": "该邮箱未注册"}, status=status.HTTP_400_BAD_REQUEST)

        # 调用服务发送验证码
        if EmailService.send_verification_code(email, scene):
            logger.info(f"成功提交邮箱验证码发送任务: {email}, 场景: {scene}")
            return Response({
                "code": 200,
                "message": "验证码发送成功",
                "data": {"expires_in": 300}
            })
        else:
            logger.error(f"提交邮箱验证码发送任务失败: {email}")
            return Response({
                "code": 500,
                "message": "验证码发送失败，请稍后重试"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 