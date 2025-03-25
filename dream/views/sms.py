from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import json
import logging

from backend import local_settings
from dream.serializers.user_serializers import PhoneSerializer
from dream.utils.sms import SMSService

# 获取日志记录器
logger = logging.getLogger(__name__)


class SendVerificationCodeAPIView(APIView):
    """
    发送短信验证码API视图
    """

    def post(self, request):
        # 1. 验证手机号
        serializer = PhoneSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(f"手机号验证失败: {serializer.errors}")
            return Response({
                "code": 400,
                "message": "请求参数错误",
                "errors": serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        phone = serializer.validated_data['phone']
        logger.info(f"请求发送验证码到手机: {phone}")

        # 2. 生成验证码
        verification_code = SMSService.generate_verification_code()
        logger.debug(f"为手机 {phone} 生成验证码: {verification_code}")

        # 3. 将验证码存入Redis
        stored = SMSService.store_code_in_redis(phone, verification_code)
        if not stored:
            logger.error(f"无法将验证码存储到Redis，手机号: {phone}")
            return Response({
                "code": 500,
                "message": "验证码存储失败，请稍后重试"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 4. 调用短信发送服务
        try:
            sms_services = SMSService()
            # 正确使用短信模板ID和传递验证码作为参数
            template_code = local_settings.ALIYUN_SMS_TEMPLATE.get('register')
            template_param = json.dumps({'code': verification_code})

            logger.info(f"发送短信，手机号: {phone}, 模板: {template_code}")
            sent = sms_services.send_sms(
                phone_numbers=phone,
                template_code=template_code,
                template_param=template_param
            )

            logger.info(f"短信发送结果: {sent}")

            if sent.get('Code') != 'OK':
                logger.error(f"短信发送失败，错误: {sent}")
                return Response({
                    "code": 500,
                    "message": "验证码发送失败，请稍后重试"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # 5. 返回成功响应
            logger.info(f"成功发送验证码到手机号: {phone}")
            return Response({
                "code": 200,
                "message": "验证码发送成功"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"发送验证码过程中发生异常: {str(e)}")
            return Response({
                "code": 500,
                "message": f"服务器错误: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



