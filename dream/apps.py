from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class DreamConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dream'

    def ready(self):
        """
        应用准备就绪时，注册信号处理器
        """
        try:
            from . import signals
            signals.register_signals()
            logger.info("成功注册Dream应用的信号处理器")
        except Exception as e:
            logger.error(f"注册信号处理器时发生错误: {str(e)}")