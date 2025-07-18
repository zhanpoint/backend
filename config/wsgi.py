"""
WSGI config for backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application

# 设置Django的环境变量，指定设置模块
app_env = os.environ.get('APP_ENV', 'dev')
settings_module = f'config.settings.{app_env}'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

# 获取Django的WSGI应用程序
application = get_wsgi_application()
