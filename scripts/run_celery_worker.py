import os
import sys
from celery.__main__ import main

if __name__ == '__main__':
    # 设置Django的settings模块
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    
    # 构建Celery worker的启动参数
    sys.argv = [
        'celery',
        '-A',
        'dream.celery_worker',  # 指定Celery worker的入口文件
        'worker',
        '--pool=threads',  # 使用线程池
        '-Q',  # 指定队列名称
        'dream_image_processing',  # 队列名称
        '--loglevel=info'  # 日志级别
    ]
    
    # 启动Celery worker
    sys.exit(main())