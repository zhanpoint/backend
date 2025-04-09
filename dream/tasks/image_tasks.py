import os
import logging
from PIL import Image
import io
import base64
from dream.utils.oss import OSS
from dream.models import DreamImage, Dream
from django.core.files.uploadedfile import InMemoryUploadedFile
import multiprocessing
from typing import List, Tuple, Dict
from django.db import transaction
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
from dream.utils.websocket import send_image_update
import time
from django.core.exceptions import ObjectDoesNotExist

# 获取Celery实例
from dream import celery_app

logger = logging.getLogger(__name__)

# 在Windows上使用线程池而非进程池，避免事件循环问题
MAX_WORKERS = max(4, multiprocessing.cpu_count())
THREAD_POOL = ThreadPoolExecutor(max_workers=MAX_WORKERS)

@dataclass
class ImageTask:
    """图片任务数据类"""
    data: bytes
    filename: str
    position: int
    processed_data: bytes = None
    image_url: str = None

def process_image(image_task: ImageTask, max_size: int = 1024 * 1024) -> ImageTask:
    """处理单个图片（在线程池中执行）"""
    try:
        with Image.open(io.BytesIO(image_task.data)) as img:
            if img.mode == 'RGBA':
                img = img.convert('RGB')

            current_size = len(image_task.data)
            if current_size > max_size:
                ratio = (max_size / current_size) ** 0.5
                width, height = img.size
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            output = io.BytesIO()
            quality = 85 if current_size <= max_size else int(85 * (max_size / current_size))
            img.save(output, format='JPEG', quality=quality, optimize=True)
            image_task.processed_data = output.getvalue()

        return image_task
    except Exception as e:
        logger.error(f"处理图片失败: {str(e)}")
        raise

def upload_image(image_task: ImageTask, oss) -> Tuple[str, int]:
    """上传单个图片到OSS（在线程池中执行）"""
    try:
        # 生成唯一文件名，防止覆盖
        filename = f"{int(time.time())}_{image_task.filename}"
        
        # 创建一个类似文件对象的BytesIO，用于传递给upload_file
        file_obj = io.BytesIO(image_task.processed_data)
        file_obj.name = filename  # 设置文件名属性
        
        # 使用OSS的upload_file方法而不是不存在的upload_bytes
        url = oss.upload_file(file_obj)
        
        return url, image_task.position
    except Exception as e:
        logger.error(f"上传图片失败: {str(e)}")
        raise

@celery_app.task(bind=True, max_retries=5, retry_backoff=True, retry_backoff_max=600, time_limit=300)
def process_and_upload_images(self, dream_id: int, encoded_files: List[Dict], positions: List[int]) -> List[str]:
    """处理并上传多个图片的Celery任务"""
    
    # 任务参数验证
    if not isinstance(dream_id, int) or dream_id <= 0:
        logger.error(f"无效的梦境ID: {dream_id}")
        send_image_update(dream_id, [], status='failed', message='无效的梦境ID')
        return []
        
    if not encoded_files or not positions or len(encoded_files) != len(positions):
        logger.error(f"无效的图片数据: 文件数量={len(encoded_files) if encoded_files else 0}, 位置数量={len(positions) if positions else 0}")
        send_image_update(dream_id, [], status='failed', message='无效的图片数据')
        return []
    
    # 记录详细信息用于调试
    logger.info(f"开始处理梦境ID={dream_id}的图片, 文件数量={len(encoded_files)}")
    
    MAX_RETRIES_FOR_DREAM_FETCH = 8  # 增加重试次数
    RETRY_DELAY_FOR_DREAM_FETCH = 2  # 秒
    
    # 尝试获取Dream实例，允许多次重试
    dream = None
    retry_count = 0
    last_error = None

    while retry_count < MAX_RETRIES_FOR_DREAM_FETCH:
        try:
            # 尝试直接查询梦境记录是否存在
            exists = Dream.objects.filter(id=dream_id).exists()
            if not exists:
                retry_count += 1
                logger.warning(f"梦境记录(ID={dream_id})不存在, 重试次数 {retry_count}/{MAX_RETRIES_FOR_DREAM_FETCH}")
                if retry_count >= MAX_RETRIES_FOR_DREAM_FETCH:
                    logger.error(f"梦境记录(ID={dream_id})不存在，已达到最大重试次数")
                    send_image_update(dream_id, [], status='failed', message=f'梦境记录(ID={dream_id})不存在')
                    raise self.retry(
                        exc=ObjectDoesNotExist(f"梦境记录(ID={dream_id})不存在"), 
                        countdown=60*min(retry_count, 10)
                    )
                time.sleep(RETRY_DELAY_FOR_DREAM_FETCH)
                continue
                
        # 获取Dream实例
        dream = Dream.objects.get(id=dream_id)
            # 成功获取，跳出循环
            logger.info(f"成功获取梦境记录: ID={dream_id}, 用户={dream.user.username}")
            break
        except ObjectDoesNotExist as e:
            retry_count += 1
            last_error = e
            logger.warning(f"梦境记录(ID={dream_id})尚未可用，可能是事务尚未提交。重试次数 {retry_count}/{MAX_RETRIES_FOR_DREAM_FETCH}")
            # 最后一次重试失败，抛出异常
            if retry_count >= MAX_RETRIES_FOR_DREAM_FETCH:
                logger.error(f"无法找到梦境记录(ID={dream_id})，已达到最大重试次数")
                send_image_update(dream_id, [], status='failed', message=f'无法找到梦境记录(ID={dream_id})')
                raise self.retry(
                    exc=e, 
                    countdown=60*min(retry_count, 10)
                )
            # 等待一段时间再重试，递增等待时间
            time.sleep(RETRY_DELAY_FOR_DREAM_FETCH * min(retry_count, 5))
    
    if not dream:
        logger.error(f"无法获取梦境记录(ID={dream_id}): {last_error}")
        send_image_update(dream_id, [], status='failed', message=f'无法找到梦境记录(ID={dream_id})')
        raise self.retry(
            exc=last_error or ObjectDoesNotExist(f"梦境记录(ID={dream_id})不存在"), 
            countdown=60
        )
    
    try:
        # 创建OSS实例
        oss = OSS(username=dream.user.username)
        oss.ensure_bucket_exists()
        
        # 解码图片数据并创建任务
        image_tasks = []
        for file, position in zip(encoded_files, positions):
            image_tasks.append(ImageTask(
                data=base64.b64decode(file['data']),
                filename=file['name'],
                position=position
            ))
        
        # 发送处理开始通知
        send_image_update(dream_id, [], status='processing')
        
        # 使用线程池并行处理图片
        logger.info(f"开始处理 {len(image_tasks)} 张图片")
        processed_tasks = []
        futures = []
        
        # 提交所有处理任务到线程池
        for task in image_tasks:
            future = THREAD_POOL.submit(process_image, task)
            futures.append(future)
        
        # 收集处理结果
        for future in futures:
            processed_task = future.result()
            processed_tasks.append(processed_task)
        
        # 使用线程池并行上传图片
        logger.info(f"开始上传 {len(processed_tasks)} 张图片")
        upload_futures = []
        
        # 提交所有上传任务到线程池
        for task in processed_tasks:
            future = THREAD_POOL.submit(upload_image, task, oss)
            upload_futures.append(future)
        
        # 收集上传结果
        processed_images = []
        for future in upload_futures:
            image_url, position = future.result()
            processed_images.append((image_url, position))
        
        # 批量创建数据库记录
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
        
        # 发送WebSocket通知
        send_image_update(dream_id, created_images, status='completed')
        
        # 返回所有图片URL
        return [url for url, _ in processed_images]
        
    except Exception as e:
        logger.error(f"批量处理图片失败: {str(e)}")
        # 发送处理失败通知
        send_image_update(dream_id, [], status='failed', message=str(e))
        # 如果失败，重试任务
        raise self.retry(exc=e, countdown=60)

@celery_app.task(bind=True, max_retries=5, retry_backoff=True, retry_backoff_max=600, time_limit=300)
def delete_dream_images(self, dream_id: int, image_urls: List[Dict], username: str) -> List[bool]:
    """
    删除梦境相关的所有图片的Celery任务
    
    Args:
        dream_id: 梦境记录ID
        image_urls: 图片URL列表 [{"id": 1, "url": "https://..."}]
        username: 用户名，用于获取OSS实例
    
    Returns:
        List[bool]: 每个图片的删除结果
    """
    if not image_urls:
        logger.info(f"没有图片需要删除: dream_id={dream_id}")
        send_image_update(dream_id, [], status='delete_completed', message='没有图片需要删除')
        return []
    
    logger.info(f"开始删除梦境(ID={dream_id})的图片, 总数: {len(image_urls)}")
    
    # 发送删除开始通知
    send_image_update(dream_id, image_urls, status='delete_processing', 
                     message=f'开始删除{len(image_urls)}张图片')
    
    try:
        # 创建OSS实例
        oss = OSS(username=username)
        
        # 提取文件路径
        results = []
        success_count = 0
        
        # 从URL中提取文件路径
        for image in image_urls:
            try:
                url = image['url']
                # 从URL中提取文件路径，例如 https://bucket.endpoint/dreams/date/uuid.jpg
                # 提取 dreams/date/uuid.jpg 部分作为file_key
                file_key = url.split('/', 3)[-1] if '/' in url else url
                
                # 使用线程池删除文件
                result = oss.delete_file(file_key)
                results.append({
                    'id': image.get('id'),
                    'url': url,
                    'deleted': result
                })
                
                if result:
                    success_count += 1
                    logger.info(f"成功删除图片: {file_key}")
                else:
                    logger.warning(f"删除图片失败: {file_key}")
                
                # 每删除一定数量的图片就更新一次进度
                if len(results) % 5 == 0 or len(results) == len(image_urls):
                    progress = int((len(results) / len(image_urls)) * 100)
                    send_image_update(
                        dream_id, 
                        results, 
                        status='delete_processing',
                        progress=progress, 
                        message=f'已删除 {len(results)}/{len(image_urls)} 张图片'
                    )
            except Exception as e:
                logger.error(f"删除图片时出错: {str(e)}, 图片URL: {image.get('url')}")
                results.append({
                    'id': image.get('id'),
                    'url': image.get('url'),
                    'deleted': False,
                    'error': str(e)
                })
        
        # 发送完成通知
        if success_count == len(image_urls):
            send_image_update(
                dream_id, 
                results, 
                status='delete_completed',
                message=f'已成功删除全部 {len(image_urls)} 张图片'
            )
        else:
            send_image_update(
                dream_id, 
                results, 
                status='delete_completed',
                message=f'已删除 {success_count}/{len(image_urls)} 张图片，部分删除失败'
            )
        
        return results
    
    except Exception as e:
        logger.error(f"批量删除图片失败: {str(e)}")
        # 发送处理失败通知
        send_image_update(dream_id, [], status='delete_failed', message=str(e))
        # 如果失败，重试任务
        raise self.retry(exc=e, countdown=60) 