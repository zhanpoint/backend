from celery import shared_task
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

@shared_task
def cleanup_expired_tokens():
    """清理已过期的黑名单令牌"""
    try:
        with transaction.atomic():
            # 删除所有过期的令牌
            now = timezone.now()
            deleted_count = BlacklistedToken.objects.filter(
                token__expires_at__lt=now
            ).delete()[0]
            
            if deleted_count > 0:
                logger.info(f"成功清理 {deleted_count} 个过期的黑名单令牌")
            return deleted_count
    except Exception as e:
        logger.error(f"清理过期令牌失败: {str(e)}")
        return 0 