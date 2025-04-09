"""
WebSocket通知辅助函数

这个模块提供了发送WebSocket通知的功能，主要用于异步任务完成后通知前端
"""
import json
import logging
import time
import asyncio
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings

logger = logging.getLogger(__name__)

def send_image_update(dream_id, image_urls, status='completed', progress=100, message=None):
    """
    发送图片处理状态更新到WebSocket通道
    
    Args:
        dream_id: 梦境ID
        image_urls: 处理完成的图片URL列表 [{"url": "http://...", "position": 0}, ...]
        status: 处理状态 (processing, completed, failed)
        progress: 进度百分比 (0-100)
        message: 状态消息
    """
    if not dream_id:
        logger.error("发送WebSocket通知失败: 缺少梦境ID")
        return False
        
    try:
        # 获取通道层
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.error(f"无法获取通道层，WebSocket消息未发送: dream_id={dream_id}")
            return False
        
        # 确保image_urls是列表
        if image_urls is None:
            image_urls = []
        
        # 准备消息数据
        message_data = {
            'type': 'image_update',  # 消息类型与consumer方法名匹配
            'dream_id': dream_id,
            'status': status,
            'images': image_urls,
            'progress': progress,
            'timestamp': time.time()
        }
        
        # 如果提供了消息文本，添加到数据中
        if message:
            message_data['message'] = message
            
        # 重试逻辑
        max_retries = getattr(settings, 'WEBSOCKET_MAX_RETRIES', 3)
        retry_delay = getattr(settings, 'WEBSOCKET_RETRY_DELAY', 1)
        
        # 发送消息到通道组
        group_name = f'dream_images_{dream_id}'
        
        for attempt in range(max_retries):
            try:
                async_to_sync(channel_layer.group_send)(group_name, message_data)
                logger.info(f"已发送图片更新通知: dream_id={dream_id}, status={status}, "
                           f"images={len(image_urls)}, attempt={attempt+1}")
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"发送WebSocket通知失败，将重试: attempt={attempt+1}, error={str(e)}")
                    time.sleep(retry_delay)
                else:
                    logger.error(f"发送WebSocket通知失败，已达到最大重试次数: {str(e)}")
        
        return False
    
    except Exception as e:
        logger.error(f"发送WebSocket通知失败: {str(e)}")
        return False

def send_processing_status(dream_id, progress, images=None, message=None):
    """
    发送图片处理进度更新
    
    Args:
        dream_id: 梦境ID
        progress: 处理进度 (0-100)
        images: 处理中图片的位置信息 [{"position": 0}, ...]
        message: 状态消息
    """
    return send_image_update(
        dream_id=dream_id,
        image_urls=images or [],
        status='processing',
        progress=progress,
        message=message or f'图片处理中 ({progress}%)'
    ) 