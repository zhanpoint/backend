from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import time

from ..utils.oss import OSS
from ..models import UploadedImage


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_signature(request):
    """获取上传签名 - 支持图片生命周期管理"""
    try:
        user = request.user
        filename = request.data.get('filename', '')
        content_type = request.data.get('content_type', 'image/jpeg')
        file_size = request.data.get('file_size')  # 新增：文件大小
        
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
        if content_type not in allowed_types:
            return Response(
                {'error': '不支持的文件类型'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 检查文件大小限制
        max_size = 10 * 1024 * 1024  # 10MB
        if file_size and int(file_size) > max_size:
            return Response(
                {'error': f'文件大小不能超过{max_size // (1024*1024)}MB'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        oss_client = OSS(user_id=user.id)
        oss_client.ensure_bucket_exists()
        
        result = oss_client.generate_presigned_url(
            filename=filename,
            content_type=content_type,
            expires=3600
        )
        
        # 预注册图片到数据库（状态为active，但可能还未实际上传）
        try:
            # 检查是否已经存在同样的URL
            existing_image = UploadedImage.objects.filter(
                url=result['access_url'],
                user=user
            ).first()
            
            if not existing_image:
                UploadedImage.objects.create(
                    url=result['access_url'],
                    file_key=result['file_key'],
                    user=user,
                    status='active',
                    file_size=int(file_size) if file_size else None,
                    file_name=filename,
                    content_type=content_type
                )
        except Exception as e:
            # 预注册失败不影响上传流程
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"预注册图片失败: {e}")
        
        return Response(result, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': '获取上传签名失败', 'detail': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_file(request):
    """删除文件 - 支持软删除"""
    try:
        user = request.user
        file_key = request.data.get('file_key')
        url = request.data.get('url')  # 新增：支持通过URL删除
        force_delete = request.data.get('force_delete', False)  # 新增：是否强制物理删除
        
        if not file_key and not url:
            return Response(
                {'error': '缺少file_key或url参数'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 查找图片记录
        try:
            if url:
                image = UploadedImage.objects.get(url=url, user=user)
            else:
                image = UploadedImage.objects.get(file_key=file_key, user=user)
        except UploadedImage.DoesNotExist:
            # 如果数据库中没有记录，但有file_key，尝试直接从OSS删除
            if file_key and force_delete:
                oss_client = OSS(user_id=user.id)
                success = oss_client.delete_file(file_key)
                if success:
                    return Response(
                        {'message': '文件删除成功（仅OSS）'}, 
                        status=status.HTTP_200_OK
                    )
                
                return Response(
                    {'error': '文件不存在或无权限'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            return Response(
                {'error': '文件不存在或无权限'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if force_delete:
            # 强制物理删除
            oss_client = OSS(user_id=user.id)
            oss_success = True
            
            if image.file_key:
                oss_success = oss_client.delete_file(image.file_key)
            
            # 删除数据库记录
            image.delete()
            
            return Response(
                {
                    'message': '文件强制删除成功',
                    'oss_deleted': oss_success,
                    'db_deleted': True
                }, 
                status=status.HTTP_200_OK
            )
        else:
            # 软删除（标记为待删除）
            image.mark_for_deletion()
            
            return Response(
                {
                    'message': '文件已标记为待删除',
                    'image_id': str(image.id),
                    'marked_time': image.marked_for_delete_time,
                    'will_be_deleted_after': '24小时后自动清理'
                }, 
                status=status.HTTP_200_OK
            )
        
    except Exception as e:
        return Response(
            {'error': '删除文件失败', 'detail': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_files(request):
    """列出用户文件 - 从数据库获取"""
    try:
        user = request.user
        status_filter = request.GET.get('status', 'active')  # active, pending_delete, all
        max_keys = int(request.GET.get('max_keys', 100))
        
        max_keys = min(max_keys, 1000)
        
        # 从数据库查询而不是OSS
        queryset = UploadedImage.objects.filter(user=user)
        
        if status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        
        queryset = queryset.order_by('-upload_time')[:max_keys]
        
        files = []
        for image in queryset:
            files.append({
                'id': str(image.id),
                'url': image.url,
                'file_key': image.file_key,

                'status': image.status,
                'upload_time': image.upload_time,
                'last_referenced_time': image.last_referenced_time,
                'marked_for_delete_time': image.marked_for_delete_time,
                'dream_title': image.dream.title if image.dream else None
            })
        
        return Response({
            'files': files,
            'count': len(files),
            'status_filter': status_filter
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': '列出文件失败', 'detail': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def restore_file(request):
    """恢复被标记为删除的文件"""
    try:
        user = request.user
        image_id = request.data.get('image_id')
        url = request.data.get('url')
        
        if not image_id and not url:
            return Response(
                {'error': '缺少image_id或url参数'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 查找图片记录
        try:
            if image_id:
                image = UploadedImage.objects.get(id=image_id, user=user)
            else:
                image = UploadedImage.objects.get(url=url, user=user)
        except UploadedImage.DoesNotExist:
            return Response(
                {'error': '文件不存在或无权限'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if image.status != 'pending_delete':
            return Response(
                {'error': '文件未处于待删除状态'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 恢复文件
        image.restore_active()
        
        return Response(
            {
                'message': '文件已恢复',
                'image_id': str(image.id),
                'url': image.url,
                'restored_time': image.last_referenced_time
            }, 
            status=status.HTTP_200_OK
        )
        
    except Exception as e:
        return Response(
            {'error': '恢复文件失败', 'detail': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_sts_token(request):
    """获取STS令牌 - 保持原有功能"""
    try:
        user = request.user
        
        oss_client = OSS(user_id=user.id)
        sts_token = oss_client._get_sts_token()
        
        response_data = {
            'credentials': {
                'access_key_id': sts_token['access_key_id'],
                'access_key_secret': sts_token['access_key_secret'],
                'security_token': sts_token['security_token'],
                'expiration': int(time.time()) + 3600
            },
            'bucket': oss_client.bucket_name,
            'region': 'oss-cn-wuhan-lr',
            'endpoint': oss_client.endpoint,
            'user_prefix': oss_client.user_prefix
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': '获取STS凭证失败', 'detail': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )