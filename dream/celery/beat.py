#!/usr/bin/env python
"""
Celery Beat 启动脚本
用于运行定时任务(如清理过期令牌)
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
    # 默认参数
    default_args = [
        'celery',
        '-A', 'dream.celery',
        'beat',
        '--loglevel=info',
    ]
    
    # 使用命令行参数或默认参数
    sys.argv = ['celery', '-A', 'dream.celery'] + sys.argv[1:] if len(sys.argv) > 1 else default_args
    
    # 启动 Celery beat
    sys.exit(main()) 