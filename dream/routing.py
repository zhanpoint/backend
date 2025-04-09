"""
WebSocket路由配置
"""
from django.urls import re_path
from . import consumers

# WebSocket URL路由配置
websocket_urlpatterns = [
    # 梦境图片上传通知WebSocket路由
    # 格式: ws://example.com/ws/dream-images/<dream_id>/
    re_path(r'ws/dream-images/(?P<dream_id>\d+)/$', consumers.DreamImagesConsumer.as_asgi()),
] 