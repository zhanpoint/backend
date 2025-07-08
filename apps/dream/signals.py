from django.db.models.signals import post_save
from django.apps import apps
from .utils.oss import OSS
import logging

logger = logging.getLogger(__name__)

def create_user_bucket_handler(sender, instance, created, **kwargs):
    """
    当新用户注册时，为其创建OSS bucket的处理函数
    """
    if created:  # 只在用户首次创建时执行
        try:
            success = OSS.create_user_bucket(instance.username)
            if not success:
                logger.error(f"为用户{instance.username}创建bucket失败")
        except Exception as e:
            logger.error(f"处理用户{instance.username}的bucket创建时发生错误: {str(e)}")

def register_signals():
    """
    注册所有信号处理器
    """
    # 获取User模型
    User = apps.get_model('dream', 'User')
    
    # 注册用户创建后的bucket创建信号
    post_save.connect(
        create_user_bucket_handler,
        sender=User,
        dispatch_uid="create_user_bucket"  # 确保信号只被注册一次
    )
