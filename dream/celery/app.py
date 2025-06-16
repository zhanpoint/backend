"""定义和配置 Celery 应用"""

import os
from celery import Celery
from kombu import Exchange, Queue
from celery.schedules import crontab
import logging

logger = logging.getLogger(__name__)

# 1.设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# 2.创建Celery应用实例创建
app = Celery('dream')

# 3.从Django配置加载Celery配置
app.config_from_object('django.conf:settings', namespace='CELERY')

# 4.队列和交换机配置
default_exchange = Exchange('default', type='direct', durable=True)
image_exchange = Exchange('dream_images', type='direct', durable=True)
app.conf.task_queues = (
    Queue('default', default_exchange, routing_key='default', durable=True),
    Queue('dream_image_processing', image_exchange, routing_key='image_processing', durable=True)
)

# 5.配置队列到Celery
app.conf.task_default_queue = 'default'
app.conf.task_default_exchange = 'default'
app.conf.task_default_routing_key = 'default'

# 7.配置任务路由
app.conf.task_routes = {
    'dream.celery.tasks.image_tasks.celery_upload_images': {
        'queue': 'dream_image_processing',
        'exchange': 'dream_images',
        'routing_key': 'image_processing',
    },
    'dream.celery.tasks.image_tasks.celery_delete_images': {
        'queue': 'dream_image_processing',
        'exchange': 'dream_images',
        'routing_key': 'image_processing',
    },
}

# 8.配置定时任务
app.conf.beat_schedule = {
    'cleanup-expired-tokens': {
        'task': 'dream.celery.tasks.token_tasks.cleanup_expired_tokens',
        'schedule': crontab(hour=3, minute=0),  # 每天凌晨3点执行
    },
}

# 9.自动发现任务
app.autodiscover_tasks(['dream.celery.tasks']) 