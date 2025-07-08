from celery import shared_task
from apps.dream.utils.email import EmailService
import logging

logger = logging.getLogger(__name__)

# @shared_task 或 @app.task 装饰器在模块被加载时运行，会将该任务函数注册到 Celery 实例的任务注册表（registry）中。
@shared_task(bind=True, max_retries=3)
def send_verification_email_task(self, email, code, scene='register'):
    """
    异步发送邮箱验证码任务
    
    Args:
        email: 收件人邮箱
        code: 验证码
        scene: 场景类型 ('register', 'login', 'reset_password')
    
    Returns:
        dict: 发送结果
    """
    try:
        # 直接调用 EmailService 的内部发送方法
        success = EmailService._send_email(email, code, scene)
        
        if success:
            logger.info(f"邮箱验证码发送任务成功，邮箱: {email}, 场景: {scene}")
            return {'status': 'success', 'email': email}
        else:
            logger.error(f"邮箱验证码发送任务失败，邮箱: {email}, 场景: {scene}")
            # 如果发送失败，抛出异常以触发重试机制
            raise Exception(f"邮件发送失败")
            
    except Exception as e:
        logger.error(f"邮箱验证码发送任务异常，邮箱: {email}, 错误: {str(e)}")
        
        # 重试机制
        try:
            # 延迟重试：第一次重试30秒，第二次重试60秒，第三次重试120秒
            countdown = 30 * (2 ** self.request.retries)
            raise self.retry(exc=e, countdown=countdown)
        except self.MaxRetriesExceededError:
            logger.error(f"邮箱验证码发送任务重试次数超限，邮箱: {email}")
            return {
                'status': 'failed',
                'message': f'邮件发送失败，已达到最大重试次数: {str(e)}'
            }


@shared_task
def cleanup_expired_email_codes():
    """
    清理过期的邮箱验证码缓存
    注意：Redis会自动清理过期的键，这个任务主要用于清理内存缓存
    """
    try:
        if hasattr(EmailService, '_code_cache'):
            # 这里只是记录，实际的清理由各个键的过期机制自动处理
            cache_size = len(EmailService._code_cache)
            logger.info(f"当前内存中的邮箱验证码缓存数量: {cache_size}")
        return "清理任务执行完成"
    except Exception as e:
        logger.error(f"清理邮箱验证码缓存失败: {str(e)}")
        return f"清理任务失败: {str(e)}" 