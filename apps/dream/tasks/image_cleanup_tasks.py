"""
图片清理定时任务 - 简化版
"""

import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from typing import Dict

from ..utils.image_manager import GlobalImageCleanupManager
from ..models import UploadedImage

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, retry_backoff=True)
def cleanup_expired_images(self, hours_threshold: int = 24) -> Dict[str, int]:
    """清理过期的待删除图片（主要定时任务）"""
    task_id = self.request.id
    logger.info(f"[Task {task_id}] 开始清理过期图片，阈值: {hours_threshold}小时")
    
    try:
        stats = GlobalImageCleanupManager.cleanup_all_expired_images(hours_threshold=hours_threshold)
        logger.info(f"[Task {task_id}] 图片清理完成: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"[Task {task_id}] 图片清理失败: {e}")
        raise self.retry(exc=e, countdown=60) 