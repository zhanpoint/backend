"""
Celery Worker启动文件
注意：这个文件应该被用来启动Celery worker
命令：celery -A dream.celery_worker worker --pool=threads -Q dream_image_processing --loglevel=info
"""

import os
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# 初始化Django应用
django.setup()

# 导入Celery实例 (必须在django.setup()之后)
from dream.celery import app as celery_app  # noqa 