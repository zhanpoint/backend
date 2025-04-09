import os
from celery import Celery
from kombu import Exchange, Queue
import logging

logger = logging.getLogger(__name__)

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# 创建Celery应用实例
app = Celery('dream')

# 从Django配置加载Celery配置
app.config_from_object('django.conf:settings', namespace='CELERY')

# 声明交换机
default_exchange = Exchange('default', type='direct', durable=True)
image_exchange = Exchange('dream_images', type='direct', durable=True)

# 声明队列
default_queue = Queue('default', exchange=default_exchange, routing_key='default', durable=True)
image_queue = Queue('dream_image_processing', exchange=image_exchange, routing_key='image_processing', durable=True)

# 配置队列到Celery
app.conf.task_queues = (default_queue, image_queue)

# 设置默认队列
app.conf.task_default_queue = 'default'
app.conf.task_default_exchange = 'default'
app.conf.task_default_routing_key = 'default'

# 配置任务路由
app.conf.task_routes = {
    'dream.tasks.image_tasks.process_and_upload_images': {
        'queue': 'dream_image_processing',
        'exchange': 'dream_images',
        'routing_key': 'image_processing',
    },
    'dream.tasks.image_tasks.delete_dream_images': {
        'queue': 'dream_image_processing',
        'exchange': 'dream_images',
        'routing_key': 'image_processing',
    },
}

# 自动发现任务
app.autodiscover_tasks(['dream.tasks'])