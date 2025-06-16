import logging
from PIL import Image
import io
import base64
from dream.utils.oss import OSS
from dream.models import DreamImage, Dream
import multiprocessing
from typing import List, Dict
from django.db import transaction
from dataclasses import dataclass
from concurrent.futures import ProcessPoolExecutor
from dream.websocket.utils.notifications import send_image_update
import time
from django.core.exceptions import ObjectDoesNotExist
from celery import shared_task

logger = logging.getLogger(__name__)

# 进程池核心数，根据CPU数量自动设置
CPU_COUNT = multiprocessing.cpu_count()
PROCESS_COUNT = max(2, min(CPU_COUNT - 1, 8))  # 留一个核心给系统，最多使用8个核心


@dataclass
class ImageTask:
    """图片任务数据类"""
    data: bytes
    filename: str
    position: int
    processed_data: bytes = None
    image_url: str = None


def process_image(image_data: bytes, filename: str, max_size: int = 1024 * 1024) -> bytes:
    """处理单个图片（在进程池中执行）"""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # 转换RGBA到RGB
            if img.mode == 'RGBA':
                img = img.convert('RGB')

            # 调整图片大小
            current_size = len(image_data)
            if current_size > max_size:
                ratio = (max_size / current_size) ** 0.5
                width, height = img.size
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # 保存图片
            output = io.BytesIO()
            quality = 85 if current_size <= max_size else int(85 * (max_size / current_size))
            img.save(output, format='JPEG', quality=quality, optimize=True)
            return output.getvalue()
    except Exception as e:
        logger.error(f"处理图片失败: {str(e)}")
        raise


# 任务执行
@shared_task(bind=True, max_retries=5, retry_backoff=True, retry_backoff_max=600, time_limit=300)
def celery_upload_images(self, dream_id: int, encoded_files: List[Dict], positions: List[int]) -> List[str]:
    """处理并上传多个图片的Celery任务"""
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

        # 并行处理图片
        process_count = min(PROCESS_COUNT, len(image_data_list))
        processed_images = []
        
        with ProcessPoolExecutor(max_workers=process_count) as executor:
            futures = [executor.submit(process_image, data, filename) for data, filename, _ in image_data_list]
            processed_data_list = [future.result() for future in futures]

        # 上传处理后的图片
        for i, processed_data in enumerate(processed_data_list):
            _, filename, position = image_data_list[i]
            
            # 准备上传
            unique_filename = f"{int(time.time())}_{filename}"
            file_obj = io.BytesIO(processed_data)
            file_obj.name = unique_filename
            
            # 上传到OSS
            image_url = oss.upload_file(file_obj)
            processed_images.append((image_url, position))

        # 创建数据库记录并发送通知
        created_images = []
        with transaction.atomic():
            for url, position in processed_images:
                image = DreamImage.objects.create(
                    dream=dream,
                    image_url=url,
                    position=position
                )
                created_images.append({
                    "id": image.id,
                    "url": url,
                    "position": position
                })

        # 发送完成通知
        send_image_update(dream_id, created_images, status='completed')
        
        # 返回所有图片URL
        return [url for url, _ in processed_images]

    except ObjectDoesNotExist as e:
        send_image_update(dream_id, [], status='failed', message=f'无法找到梦境记录(ID={dream_id})')
        raise self.retry(exc=e, countdown=60)
    except Exception as e:
        send_image_update(dream_id, [], status='failed', message=str(e))
        raise self.retry(exc=e, countdown=60)


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
