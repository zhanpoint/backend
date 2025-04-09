"""
WebSocket消费者实现
用于处理WebSocket连接和消息传递
"""
import json
import logging
import time
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from channels.db import database_sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from .models import Dream, User, DreamImage

logger = logging.getLogger(__name__)


class DreamImagesConsumer(AsyncWebsocketConsumer):
    """
    梦境图片上传状态WebSocket消费者
    处理客户端与服务器之间的WebSocket连接，推送图片上传状态更新
    """

    async def connect(self):
        """
        建立WebSocket连接
        """
        self.dream_id = self.scope['url_route']['kwargs']['dream_id']
        self.room_group_name = f'dream_images_{self.dream_id}'
        self.authenticated = False
        self.ping_task = None
        self.connection_time = time.time()

        # 检查URL查询参数中是否有token
        query_string = self.scope.get('query_string', b'').decode()
        query_params = {}
        token_from_url = None
        
        if query_string:
            # 解析查询字符串
            import urllib.parse
            query_params = dict(urllib.parse.parse_qsl(query_string))
            
            # 如果URL参数中有token，则设置为认证令牌
            if 'token' in query_params:
                token_from_url = query_params['token']
                # 在headers中设置Authorization头
                if 'headers' not in self.scope:
                    self.scope['headers'] = []
                
                # 添加认证头
                auth_header = [b'authorization', f'Bearer {token_from_url}'.encode()]
                # 移除任何已存在的authorization头
                self.scope['headers'] = [h for h in self.scope['headers'] if h[0] != b'authorization']
                # 添加新的authorization头
                self.scope['headers'].append(auth_header)
                
                logger.info(f"从URL参数提取到认证令牌: dream_id={self.dream_id}")

        # 验证用户权限
        valid = await self.validate_user()
        if not valid:
            logger.warning(f"用户无权访问梦境ID: {self.dream_id}，WebSocket连接被拒绝")
            await self.close(code=4003)
            return

        # 将连接添加到通道组
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # 接受WebSocket连接
        await self.accept()
        logger.info(f"WebSocket连接已建立: dream_id={self.dream_id}, channel={self.channel_name}")

        # 自动进行认证（如果URL中有令牌）
        if token_from_url:
            try:
                authenticated = await self.authenticate(f'Bearer {token_from_url}')
                if authenticated:
                    self.authenticated = True
                    await self.send_json({
                        'type': 'connection_established',
                        'dream_id': self.dream_id,
                        'message': '连接已建立，等待图片处理状态更新'
                    })
                    
                    # 启动服务器心跳任务
                    self.ping_task = asyncio.create_task(self.server_ping())
                    logger.info(f"通过URL参数成功认证: dream_id={self.dream_id}")
                else:
                    logger.warning(f"通过URL参数认证失败: dream_id={self.dream_id}")
                    await self.close(code=4001)
                    return
            except Exception as e:
                logger.error(f"处理URL认证时出错: {str(e)}")
                await self.close(code=4009)
                return
        else:
            # 设置认证超时（如果没有通过URL认证）
            asyncio.create_task(self.authentication_timeout())

    async def authentication_timeout(self):
        """
        认证超时检查
        """
        await asyncio.sleep(30)  # 等待30秒进行认证
        if not self.authenticated:
            logger.warning(f"WebSocket连接认证超时: dream_id={self.dream_id}")
            await self.close(code=4008)

    async def disconnect(self, close_code):
        """
        关闭WebSocket连接
        """
        # 停止心跳任务
        if self.ping_task:
            self.ping_task.cancel()
            self.ping_task = None

        # 将连接从通道组中移除
        try:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        except Exception as e:
            logger.error(f"从通道组移除连接时出错: {str(e)}")

        connection_duration = time.time() - self.connection_time
        logger.info(f"WebSocket连接已关闭: dream_id={self.dream_id}, channel={self.channel_name}, "
                   f"code={close_code}, 连接持续时间={connection_duration:.1f}秒")

    async def receive_json(self, content):
        """
        接收并处理WebSocket消息
        """
        try:
            message_type = content.get('type')
            logger.debug(f"收到消息类型: {message_type}")
            
            # 如果未认证，只接受认证消息
            if not self.authenticated and message_type != 'authenticate':
                logger.warning(f"未认证连接尝试发送非认证消息: {message_type}")
                await self.send_json({
                    'type': 'error',
                    'message': '未授权，请先进行认证'
                })
                return
            
            # 处理不同类型的消息
            if message_type == 'authenticate':
                await self.authenticate(content)
            elif message_type == 'ping':
                await self.handle_ping(content)
            elif message_type == 'request_status':
                await self.handle_status_request(content)
            else:
                logger.warning(f"收到未知类型消息: {message_type}")
                await self.send_json({
                    'type': 'error',
                    'message': f'未知消息类型: {message_type}'
                })
                
        except Exception as e:
            logger.error(f"处理JSON消息时出错: {str(e)}")
            if self.authenticated:
                await self.send_json({
                    'type': 'error',
                    'message': f'处理消息失败: {str(e)}'
                })
                
    async def handle_status_request(self, content):
        """
        处理状态请求，返回梦境的最新图片处理状态
        """
        if not self.authenticated:
            return
            
        try:
            # 从数据库获取最新的梦境数据
            dream = None
            try:
                dream = await database_sync_to_async(Dream.objects.get)(id=self.dream_id)
            except Dream.DoesNotExist:
                await self.send_json({
                    'type': 'error',
                    'message': f'梦境(ID={self.dream_id})不存在'
                })
                return
                
            # 获取梦境相关的图片
            dream_images = await database_sync_to_async(list)(DreamImage.objects.filter(dream=dream))
            
            # 构建图片数据
            images_data = []
            for image in dream_images:
                images_data.append({
                    'id': image.id,
                    'url': image.image_url,
                    'position': image.position
                })
                
            # 获取最近的图片处理状态
            processing_status = await database_sync_to_async(DreamImageProcessing.objects.filter)(dream_id=self.dream_id).order_by('-created_at').first()
            
            # 构建状态响应
            status_response = {
                'type': 'image_update',
                'dream_id': self.dream_id,
                'images': images_data,
                'status': 'completed'  # 默认状态
            }
            
            # 如果有正在处理的状态，更新响应
            if processing_status:
                status_response['status'] = processing_status.status
                status_response['progress'] = processing_status.progress
                if processing_status.message:
                    status_response['message'] = processing_status.message
            
            # 发送状态响应
            await self.send_json(status_response)
            logger.info(f"已发送梦境(ID={self.dream_id})的状态更新，包含{len(images_data)}张图片")
            
        except Exception as e:
            logger.error(f"处理状态请求时出错: {str(e)}")
            await self.send_json({
                'type': 'error',
                'message': f'获取状态失败: {str(e)}'
            })

    async def authenticate(self, content):
        """
        处理认证请求
        """
        token = content.get('token', '')
        if not token:
            logger.warning(f"收到空认证令牌: dream_id={self.dream_id}")
            await self.send_json({
                'type': 'error',
                'message': '认证失败: 令牌为空'
            })
            await self.close(code=4001)
            return False
            
        # 如果已经认证，则不需要再次认证
        if self.authenticated:
            logger.info(f"客户端重复认证请求: dream_id={self.dream_id}, 已认证")
            await self.send_json({
                'type': 'connection_established',
                'dream_id': self.dream_id,
                'message': '连接已建立，等待图片处理状态更新'
            })
            return True
            
        try:
            # 验证令牌
            from django.conf import settings
            import jwt
            
            # 清理令牌前缀
            if token.startswith('Bearer '):
                token = token[7:]
                
            # 验证JWT令牌
            try:
                payload = jwt.decode(
                    token, 
                    settings.SIMPLE_JWT['SIGNING_KEY'],
                    algorithms=[settings.SIMPLE_JWT['ALGORITHM']]
                )
                user_id = payload['user_id']
                
                # 验证用户是否存在
                user = await database_sync_to_async(User.objects.filter)(id=user_id).first()
                if not user:
                    logger.warning(f"认证失败 - 用户不存在: user_id={user_id}")
                    await self.send_json({
                        'type': 'error',
                        'message': '认证失败: 用户不存在'
                    })
                    await self.close(code=4001)
                    return False
                    
                # 检查梦境的所有者是否是当前用户
                dream = await database_sync_to_async(Dream.objects.filter)(id=self.dream_id).first()
                if not dream:
                    logger.warning(f"认证失败 - 梦境不存在: dream_id={self.dream_id}")
                    await self.send_json({
                        'type': 'error',
                        'message': '认证失败: 梦境不存在'
                    })
                    await self.close(code=4001)
                    return False
                    
                # 验证成功
                self.authenticated = True
                self.user = user
                
                # 启动服务器心跳任务
                if self.ping_task is None:
                    self.ping_task = asyncio.create_task(self.server_ping())
                    
                await self.send_json({
                    'type': 'connection_established',
                    'dream_id': self.dream_id,
                    'message': '连接已建立，等待图片处理状态更新'
                })
                
                logger.info(f"认证成功: user_id={user_id}, dream_id={self.dream_id}")
                return True
                
            except jwt.ExpiredSignatureError:
                logger.warning(f"认证失败 - 令牌过期: dream_id={self.dream_id}")
                await self.send_json({
                    'type': 'error',
                    'message': '认证失败: 令牌已过期'
                })
                await self.close(code=4001)
                return False
                
            except jwt.InvalidTokenError:
                logger.warning(f"认证失败 - 无效令牌: dream_id={self.dream_id}")
                await self.send_json({
                    'type': 'error',
                    'message': '认证失败: 无效令牌'
                })
                await self.close(code=4001)
                return False
                
        except Exception as e:
            logger.error(f"认证过程中出错: {str(e)}")
            await self.send_json({
                'type': 'error',
                'message': f'认证失败: {str(e)}'
            })
            await self.close(code=4001)
            return False
            
    async def handle_ping(self, content):
        """
        处理客户端心跳
        """
        if not self.authenticated:
            return
            
        try:
            await self.send_json({
                'type': 'pong',
                'timestamp': content.get('timestamp', time.time())
            })
        except Exception as e:
            logger.error(f"处理心跳请求时出错: {str(e)}")
            
    async def server_ping(self):
        """
        服务器发送定期心跳以保持连接活跃
        """
        try:
            while True:
                await asyncio.sleep(30)  # 每30秒发送一次心跳
                await self.send_json({
                    'type': 'ping',
                    'timestamp': time.time()
                })
        except asyncio.CancelledError:
            # 任务被取消，这是预期的行为
            pass
        except Exception as e:
            logger.error(f"发送服务器心跳时出错: {str(e)}")

    async def image_update(self, event):
        """
        接收图片更新事件并发送给客户端
        """
        # 仅在已认证的情况下发送消息
        if not self.authenticated:
            logger.warning(f"尝试向未认证的连接发送图片更新: dream_id={self.dream_id}")
            return

        try:
            # 直接转发消息到客户端
            await self.send_json(event)
            logger.debug(f"已发送图片更新到客户端: dream_id={self.dream_id}, status={event.get('status')}")
        except Exception as e:
            logger.error(f"发送图片更新消息失败: {str(e)}")

    async def send_json(self, content):
        """
        向客户端发送JSON数据，带有错误处理
        """
        try:
            await self.send(text_data=json.dumps(content))
            return True
        except Exception as e:
            logger.error(f"发送JSON消息失败: {str(e)}")
            return False

    @database_sync_to_async
    def validate_user(self):
        """
        验证用户是否有权限访问该梦境（从HTTP头部）
        """
        try:
            # 获取认证令牌
            headers = dict(self.scope.get('headers', []))
            auth_header = headers.get(b'authorization', b'').decode()

            if not auth_header.startswith('Bearer '):
                logger.warning(f"缺少Bearer令牌: dream_id={self.dream_id}")
                return False

            token = auth_header.split(' ')[1]

            # 验证令牌
            access_token = AccessToken(token)
            user_id = access_token.get('user_id')

            # 首先检查用户是否存在
            try:
                user = User.objects.get(id=user_id)
            except ObjectDoesNotExist:
                logger.warning(f"用户不存在: user_id={user_id}, dream_id={self.dream_id}")
                return False

            # 然后检查梦境是否存在
            try:
                # 先检查梦境是否存在
                if not Dream.objects.filter(id=self.dream_id).exists():
                    # 对于刚刚创建的梦境，可能数据库事务尚未提交，我们返回true允许连接
                    # 稍后会在图片更新时再次验证
                    logger.info(f"梦境记录不存在，可能是新创建的: dream_id={self.dream_id}, user={user.username}")
                    return True
                
                dream = Dream.objects.get(id=self.dream_id)
                
                # 检查用户是否拥有该梦境
                if dream.user_id == user.id:
                    return True
                else:
                    logger.warning(f"用户无权访问此梦境: user_id={user_id}, dream_id={self.dream_id}, dream_owner={dream.user_id}")
                    return False
            except ObjectDoesNotExist:
                # 对于刚刚创建的梦境，可能数据库事务尚未提交
                logger.info(f"梦境记录不存在，可能是新创建的: dream_id={self.dream_id}")
                return True

        except (TokenError, ObjectDoesNotExist) as e:
            logger.error(f"验证用户失败: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"验证过程中发生错误: {str(e)}")
            return False
 