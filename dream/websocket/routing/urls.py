"""
WebSocket URL 路由配置
"""
from django.urls import re_path
from dream.websocket.consumers import DreamImagesConsumer

# WebSocket URL 路由配置
websocket_urlpatterns = [
    # 梦境图片上传通知: ws://example.com/ws/dream-images/<dream_id>/
    re_path(r'^ws/dream-images/(?P<dream_id>\d+)/$', DreamImagesConsumer.as_asgi()),
] 