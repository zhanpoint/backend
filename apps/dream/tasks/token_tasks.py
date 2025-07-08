from celery import shared_task
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)

@shared_task
def cleanup_expired_tokens():
    """
    只要refresh token还没过期，理论上它都可能被恶意使用。
    如果你提前把黑名单记录删掉，系统就无法判断某个token是否已经被拉黑，会导致被拉黑的token重新变得可用，严重威胁安全。
    SimpleJWT官方推荐的做法就是只清理过期的黑名单token，保证在整个生命周期内都能拦截被拉黑的token。
    """
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