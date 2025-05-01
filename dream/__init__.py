"""
Dream应用初始化文件
"""

# 导入Celery应用
# 当你导入dream包时，实际上是通过两个__init__.py文件的链式导入，最终获取到dream.celery.app模块中的app实例（不过在 dream 包中它被重命名为 current_app）
from dream.celery import celery_app as current_app

__all__ = ['current_app']
