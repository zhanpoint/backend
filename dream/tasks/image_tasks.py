import logging
import io
import base64
from dream.utils.oss import OSS
from typing import List, Dict
from django.db import transaction
from dream.websocket.utils.notifications import send_image_update
from django.core.exceptions import ObjectDoesNotExist
from celery import shared_task

logger = logging.getLogger(__name__)


# 任务执行
@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def celery_upload_images(self, dream_id: int, encoded_files: List[Dict], positions: List[int]) -> List[str]:
    """
    直接上传多个图片的Celery任务，不进行处理。
    此任务被设计为幂等的，以确保在重试时不会创建重复数据。
    """
    # 在函数内部导入 Django 模型
    from dream.models import DreamImage, Dream

    # 参数验证
    if not isinstance(dream_id, int) or dream_id <= 0 or not encoded_files or len(encoded_files) != len(positions):
        send_image_update(dream_id, [], status='failed', message='无效的参数')
        return []

    try:
        # 获取梦境记录
        dream = Dream.objects.get(id=dream_id)

        # 创建OSS实例并确保存储桶存在
        oss = OSS(username=dream.user.username)
        oss.ensure_bucket_exists()

        # 解码图片数据并通知处理开始
        image_data_list = [(base64.b64decode(file['data']), file['name'], position) 
                           for file, position in zip(encoded_files, positions)]
        send_image_update(dream_id, [], status='processing')

        # 直接上传图片
        uploaded_images = []
        for image_data, filename, position in image_data_list:
            # 准备上传 - 使用确定性文件名以保证幂等性
            # 格式: {dream_id}_{position}_{original_filename}
            unique_filename = f"{dream_id}_{position}_{filename}"
            file_obj = io.BytesIO(image_data)
            file_obj.name = unique_filename
            
            # 上传到OSS（如果文件已存在，会被覆盖，这是幂等行为）
            image_url = oss.upload_file(file_obj)
            uploaded_images.append((image_url, position))

        # 创建数据库记录并发送通知
        created_images_info = []
        with transaction.atomic():
            for url, position in uploaded_images:
                # 使用 get_or_create 保证幂等性
                # 如果记录已存在，则不会创建新的，避免了重复
                # 注意: 这假设 (dream, position) 组合在数据库中是唯一的
                image, created = DreamImage.objects.get_or_create(
                    dream=dream,
                    position=position,
                    defaults={'image_url': url}
                )
                
                # 如果不是新创建的，可能URL因某种原因需要更新
                if not created and image.image_url != url:
                    image.image_url = url
                    image.save()

                created_images_info.append({
                    "id": image.id,
                    "url": image.image_url,
                    "position": image.position
                })

        # 发送完成通知
        send_image_update(dream_id, created_images_info, status='completed')
        
        # 返回所有图片URL
        return [url for url, _ in uploaded_images]

    except Exception as e:
        # 捕获上传过程中的其他异常（如网络问题），并进行重试
        logger.error(f"处理梦境(ID={dream_id})的图片时发生未知错误: {e}")
        send_image_update(dream_id, [], status='failed', message=str(e))
        raise self.retry(exc=e)


@shared_task(bind=True, max_retries=5, retry_backoff=True, retry_backoff_max=600, time_limit=300)
def celery_delete_images(self, dream_id: int, image_urls: List[Dict], username: str) -> List[bool]:
    """删除梦境相关的所有图片"""
    
    if not image_urls:
        send_image_update(dream_id, [], status='delete_completed', message='没有图片需要删除')
        return []

    # 发送删除开始通知
    send_image_update(dream_id, image_urls, status='delete_processing',
                      message=f'开始删除{len(image_urls)}张图片')

    try:
        # 创建OSS实例
        oss = OSS(username=username)
        results = []
        deleted_images = []

        # 处理每个图片
        for image_info in image_urls:
            image_url = image_info.get('url')
            if not image_url:
                continue
                
            # 从URL中提取文件路径
            file_path = image_url.split('/', 3)[-1] if '/' in image_url else image_url
            
            # 删除OSS中的文件
            if file_path.startswith('dreams/'):
                success = oss.delete_file(file_path)
                results.append(success)
                
                if success:
                    deleted_images.append(image_info)

        # 发送删除完成通知
        send_image_update(dream_id, deleted_images, status='delete_completed',
                          message=f'成功删除{len(deleted_images)}张图片')

        return results
    except Exception as e:
        send_image_update(dream_id, [], status='delete_failed', message=str(e))
        raise self.retry(exc=e, countdown=60)


# celery任务数据预处理
def upload_images(dream_id: int, image_files: List[Dict], positions: List[int]) -> str:
    """发送图片处理任务到Celery队列"""
    try:
        # 编码图片数据
        encoded_files = [{
            'name': file['name'],
            'data': base64.b64encode(file['data']).decode('utf-8')
        } for file in image_files]

        # 发送Celery任务
        result = celery_upload_images.delay(dream_id, encoded_files, positions)
        return result.id
    except Exception as e:
        logger.error(f"发送图片处理任务失败: {str(e)}")
        raise


def delete_images(dream_id: int, image_urls: List[Dict], username: str) -> str:
    """发送图片删除任务到Celery队列"""
    try:
        result = celery_delete_images.delay(dream_id, image_urls, username)
        return result.id
    except Exception as e:
        logger.error(f"发送图片删除任务失败: {str(e)}")
        raise
