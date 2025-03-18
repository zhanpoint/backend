from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, parser_classes, authentication_classes, permission_classes
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
from ..utils.oss import OSS
import logging
import traceback
import jwt
from django.conf import settings

logger = logging.getLogger(__name__)

@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser])
def upload_image(request):
    """
    上传图片到OSS
    1. 检查用户bucket是否存在，不存在则创建
    2. 验证并上传图片
    """
    # 详细记录认证头和令牌解析过程，帮助调试
    auth_header = request.META.get('HTTP_AUTHORIZATION', '')
    logger.info(f"认证头: {auth_header}")

    try:
        # 手动解析JWT令牌进行调试
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            try:
                # 尝试解码JWT令牌进行检查
                decoded = jwt.decode(
                    token, 
                    settings.SIMPLE_JWT['SIGNING_KEY'],
                    algorithms=[settings.SIMPLE_JWT['ALGORITHM']]
                )
                logger.info(f"JWT解码成功: {decoded}")
                user_id = decoded.get('user_id')
                logger.info(f"用户ID: {user_id}")
            except jwt.ExpiredSignatureError:
                logger.error("JWT令牌已过期")
                return Response({'error': '认证令牌已过期'}, status=status.HTTP_401_UNAUTHORIZED)
            except jwt.InvalidTokenError as e:
                logger.error(f"JWT令牌无效: {str(e)}")
                return Response({'error': '无效的认证令牌'}, status=status.HTTP_401_UNAUTHORIZED)
            except Exception as e:
                logger.error(f"JWT解码错误: {str(e)}")
                return Response({'error': '认证令牌处理错误'}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            logger.error("请求中没有包含有效的Bearer令牌")
            return Response({'error': '缺少认证令牌'}, status=status.HTTP_401_UNAUTHORIZED)

        logger.info(f"认证用户: {request.user}")
        
        # 获取上传的文件
        file = request.FILES.get('file')
        if not file:
            return Response({'error': '请选择要上传的图片'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 验证文件大小
        if file.size > 2 * 1024 * 1024:  # 2MB
            return Response({'error': '图片大小不能超过2MB'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 验证文件类型
        validator = FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'gif'])
        try:
            validator(file)
        except ValidationError:
            return Response({'error': '不支持的图片格式'}, status=status.HTTP_400_BAD_REQUEST)
        
        # 初始化OSS助手
        logger.debug(f"接收上传请求，用户信息: {request.user} | 类型: {type(request.user)}")
        logger.debug(f"用户名字段详情: {dir(request.user)}")
        oss = OSS(username=request.user.username)
        logger.info(f"为用户 {request.user.username} 初始化OSS助手")
        
        # 确保bucket存在
        if not oss.ensure_bucket_exists():
            return Response({'error': '创建存储空间失败'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # 上传文件
        file_url = oss.upload_file(file)
        logger.info(f"文件上传成功: {file_url}")
        
        return Response({
            'url': file_url,
            'message': '上传成功'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"上传文件失败: {str(e)}")
        logger.error(traceback.format_exc())
        return Response({
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


