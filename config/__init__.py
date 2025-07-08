import pymysql

# mysqlDB不支持python3.5之后版本。使用pymysql代替，
pymysql.install_as_MySQLdb()

# 确保在 Django 启动时，Celery 应用总能被导入，
from .celery import app as celery_app

# 显式声明当使用 from config import * 时，要导出的内容是 celery_app
__all__ = ('celery_app',)

"""
当你执行如下命令启动 Celery worker：celery -A config worker -l info

Celery 会尝试导入你指定的模块（此处是 config）：

进入 config/__init__.py

自动执行 from .celery import app as celery_app

成功获取 celery_app 实例

完成 Celery 的初始化和任务注册,所以以上配置是必须的
"""