"""
梦境图片 WebSocket 消费者

处理梦境图片上传状态的 WebSocket 连接和消息交换
"""
import json
import logging
import time
import asyncio
import urllib.parse
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.conf import settings
import jwt
from apps.dream.models import Dream, User, DreamImage

logger = logging.getLogger(__name__)


class DreamImagesConsumer(AsyncWebsocketConsumer):
    """
    梦境图片上传状态 WebSocket 消费者
    处理客户端与服务器之间的 WebSocket 连接，推送图片上传状态更新
    """

    async def connect(self):
        """
        建立 WebSocket 连接
        """
        self.dream_id = self.scope['url_route']['kwargs']['dream_id']
        self.room_group_name = f'dream_images_{self.dream_id}'
        self.authenticated = False
        self.ping_task = None

        # 从URL查询参数获取token
        query_string = self.scope.get('query_string', b'').decode()
        query_params = dict(urllib.parse.parse_qsl(query_string))
        token = query_params.get('token')

        # 认证检查
        if not token or not await self.verify_token(token):
            await self.close(code=4001)
            return

        # 客户端连接到 WebSocket 端点，将连接添加到特定通道组：self.room_group_name
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        
        # 认证成功
        self.authenticated = True
        
        # 发送连接成功消息并启动心跳任务
        await self.send_json({
            'type': 'connection_established',
            'dream_id': self.dream_id,
            'message': '连接已建立，等待图片处理状态更新'
        })
        
        self.ping_task = asyncio.create_task(self.server_ping())

    async def disconnect(self, close_code):
        """
        关闭 WebSocket 连接
        """
        # 停止心跳任务
        if self.ping_task:
            self.ping_task.cancel()
            self.ping_task = None

        # 将连接从通道组中移除
        try:
            await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        except Exception:
            pass

    async def receive_json(self, content):
        """
        接收并处理 WebSocket 消息
        """
        if not self.authenticated:
            return
            
        message_type = content.get('type')

        # 处理不同类型的消息
        try:
            if message_type == 'ping':
                await self.send_json({'type': 'pong', 'timestamp': time.time()})
            elif message_type == 'request_status':
                await self.handle_status_request()
            else:
                await self.send_json({'type': 'error', 'message': f'未知消息类型: {message_type}'})
        except Exception as e:
            if self.authenticated:
                await self.send_json({'type': 'error', 'message': f'处理消息失败: {str(e)}'})

    async def send_json(self, content):
        """
        向客户端发送 JSON 数据，带有错误处理
        """
        try:
            await self.send(text_data=json.dumps(content))
            return True
        except Exception:
            return False

    async def handle_status_request(self):
        """
        处理状态请求，返回梦境的最新图片处理状态
        """
        if not self.authenticated:
            return

        try:
            # 从数据库获取梦境图片
            dream_images = await self.get_dream_images()
            if not dream_images:
                return

            # 构建图片数据
            images_data = [{'id': img.id, 'url': img.image_url, 'position': img.position} 
                          for img in dream_images]

            # 发送状态响应
            await self.send_json({
                'type': 'image_update',
                'dream_id': self.dream_id,
                'images': images_data,
                'status': 'completed',
                'timestamp': time.time()
            })
        except Exception as e:
            await self.send_json({
                'type': 'error',
                'message': f'获取状态失败: {str(e)}'
            })

    async def verify_token(self, token):
        """
        验证JWT令牌
        """
        try:
            # 解码令牌
            payload = jwt.decode(
                token,
                settings.SIMPLE_JWT['SIGNING_KEY'],
                algorithms=[settings.SIMPLE_JWT['ALGORITHM']]
            )
            user_id = payload['user_id']

            # 验证用户和梦境
            user = await database_sync_to_async(lambda: User.objects.filter(id=user_id).first())()
            dream = await database_sync_to_async(lambda: Dream.objects.filter(id=self.dream_id).first())()
            
            return user and dream and dream.user_id == user_id
        except Exception:
            return False

    async def server_ping(self):
        """
        服务器发送定期心跳以保持连接活跃
        """
        try:
            while True:
                await asyncio.sleep(15)
                await self.send_json({'type': 'ping', 'timestamp': time.time()})
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    async def image_update(self, event):
        """
        接收图片更新事件并发送给客户端
        """
        if self.authenticated:
            await self.send_json(event)

    @database_sync_to_async
    def get_dream_images(self):
        """
        获取梦境图片列表
        """
        dream = Dream.objects.filter(id=self.dream_id).first()
        return list(DreamImage.objects.filter(dream=dream)) if dream else []
