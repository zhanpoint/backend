#!/usr/bin/env python
"""
Celery Worker 启动脚本
支持命令行选项或使用默认配置启动 worker
"""

import os
import sys
from django import setup
from celery.__main__ import main

# 设置Django环境变量
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# 初始化Django
setup()

if __name__ == '__main__':
    # 默认的 Celery worker 参数
    default_args = [
        'celery',
        '-A', 'dream.celery',
        'worker',
        '--pool=threads',  # 继续使用线程池，因为worker主要处理I/O操作和任务分发
        '-Q', 'default,dream_image_processing',  # 同时处理默认队列和图像处理队列
        '--loglevel=info',  # 日志级别
        '--concurrency=4'  # 并发数，可根据 CPU 核心数调整
    ]
    
    # 使用命令行参数或默认参数
    sys.argv = ['celery', '-A', 'dream.celery'] + sys.argv[1:] if len(sys.argv) > 1 else default_args
    
    # 启动 Celery worker
    sys.exit(main()) 