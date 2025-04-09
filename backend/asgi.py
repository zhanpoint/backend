"""
ASGI config for backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator


# 设置Django的环境变量，指定设置模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# 初始化Django ASGI应用
django_asgi_app = get_asgi_application()

# 初始化Django
django.setup()

# 导入WebSocket路由
import dream.routing  # websocket路由

# 配置ASGI应用，支持HTTP和WebSocket协议
application = ProtocolTypeRouter({
    "http": django_asgi_app,  # Django视图处理HTTP请求
    "websocket": AllowedHostsOriginValidator(  # 验证WebSocket请求来源
        AuthMiddlewareStack(  # 提供认证功能
            URLRouter(
                dream.routing.websocket_urlpatterns  # WebSocket路由配置
            )
        )
    ),
})
