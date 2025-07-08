import os
from celery import Celery

# 在命令中设置环境变量（pycharm中配置的环境变量只在pycharm中生效）
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

# 注释掉这里的django.setup()，因为在Django启动时会造成循环导入
# django.setup() 应该只在独立脚本中调用，而不是在Django项目的模块中

# 创建一个 Celery 实例，名字为 'config'(推荐与 Django 项目同名)
app = Celery('config')

# 告诉 Celery 从 Django 的配置文件中加载配置（django.conf.settings中以 CELERY_ 开头的配置项）
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动从所有已注册的 Django app 中查找并加载 tasks.py 文件中的任务函数
app.autodiscover_tasks()

# Celery Beat 任务调度器
app.conf.beat_schedule = {

} 