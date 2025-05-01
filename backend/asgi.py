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
from dream.websocket.routing import websocket_urlpatterns  # 更新为新的导入路径


application = ProtocolTypeRouter({  # - 根据不同的协议类型（HTTP/WebSocket）路由到不同的处理器
    "http": django_asgi_app,  # Django视图处理HTTP请求
    "websocket": AllowedHostsOriginValidator(  # 验证WebSocket请求来源
        AuthMiddlewareStack(  # 提供认证中间件
            URLRouter(  # 处理WebSocket的URL路由
                websocket_urlpatterns  # 自定义的WebSocket路由配置
            )
        )
    ),
})
