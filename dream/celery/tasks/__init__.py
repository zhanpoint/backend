"""
Celery 任务模块

包含以下任务类型：
- 图像处理任务 (image_tasks.py)
- 令牌清理任务 (token_tasks.py)
"""

# 导入并注册所有可用的任务
from dream.celery.tasks.image_tasks import *
from dream.celery.tasks.token_tasks import * 