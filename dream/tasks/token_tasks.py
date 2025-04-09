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
            # 获取当前时间
            now = timezone.now()
            # 删除所有过期的令牌而不是删除所有黑名单令牌:
            #   安全考虑：如果我们删除了还未过期的黑名单令牌，那么这些令牌可能被恶意用户重新使用，因为系统会认为它们是有效的（不在黑名单中且未过期）。
            deleted_count = BlacklistedToken.objects.filter(
                token__expires_at__lt=now
            ).delete()[0]
            
            logger.info(f"成功清理 {deleted_count} 个过期的黑名单令牌")
            return deleted_count
    except Exception as e:
        logger.error(f"清理过期令牌时发生错误: {str(e)}")
        return 0 