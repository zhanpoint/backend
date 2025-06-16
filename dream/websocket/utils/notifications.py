"""
WebSocket 通知工具函数

提供发送 WebSocket 消息的功能，主要用于异步任务完成后通知前端
"""
import logging
import time
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings

logger = logging.getLogger(__name__)

def send_image_update(dream_id, image_urls=None, status='completed', message=None):
    """
    发送图片处理状态更新到 WebSocket 通道
    
    Args:
        dream_id: 梦境ID
        image_urls: 处理完成的图片URL列表 [{"url": "http://...", "position": 0}, ...]
        status: 处理状态 (processing, completed, failed, delete_processing, delete_completed, delete_failed)
        message: 状态消息
        
    Returns:
        bool: 发送是否成功
    """
    if not dream_id:
        return False
        
    try:
        # 获取 Django Channels 的通道层实例。通道层是 Channels 的核心组件，负责消息的路由和传递。
        channel_layer = get_channel_layer()
        if not channel_layer:
            return False
        
        # 准备消息数据
        message_data = {
            'type': 'image_update',  # 消息类型与 consumer 方法名匹配
            'dream_id': dream_id,
            'status': status,
            'images': image_urls or [],
            'timestamp': time.time()
        }
        
        # 如果提供了消息文本，添加到数据中
        if message:
            message_data['message'] = message
            
        # 重试逻辑
        max_retries = getattr(settings, 'WEBSOCKET_MAX_RETRIES', 3)
        retry_delay = getattr(settings, 'WEBSOCKET_RETRY_DELAY', 1)
        
        # 发送消息到指定的通道组
        group_name = f'dream_images_{dream_id}'
        
        for attempt in range(max_retries):
            try:
                # 消息通过 channel_layer.group_send 发送到通道组
                # 由于 send_image_update 函数在同步环境（如 Celery 任务或视图函数）中调用，而 Channels 的通道层操作是异步的，所以需要这个转换器将异步函数转换为同步函数
                async_to_sync(channel_layer.group_send)(group_name, message_data)
                return True
            except Exception:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        return False
    
    except Exception:
        return False
