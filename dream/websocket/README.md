# WebSocket 模块

本模块负责处理 WebSocket 连接和消息传递，主要用于提供实时图片处理状态更新功能。

## 目录结构

```
websocket/
├── __init__.py             # 包初始化文件
├── consumers/              # WebSocket 消费者
│   ├── __init__.py         # 消费者包初始化文件，导出 DreamImagesConsumer
│   └── dream_images.py     # 梦境图片处理状态 WebSocket 消费者
├── routing/                # WebSocket 路由
│   ├── __init__.py         # 路由包初始化文件，导出 websocket_urlpatterns
│   └── urls.py             # WebSocket URL 路由配置
└── utils/                  # WebSocket 工具函数
    ├── __init__.py         # 工具包初始化文件，导出通知函数
    └── notifications.py    # 发送 WebSocket 通知的工具函数
```

## 使用方法

### 前端连接 WebSocket

前端可以通过以下 URL 格式连接 WebSocket：

```
ws://example.com/ws/dream-images/<dream_id>/?token=<jwt_token>
```

其中：

- `<dream_id>` 是梦境记录的 ID
- `<jwt_token>` 是用户的 JWT 认证令牌

### 在后端发送通知

在异步任务或其他地方发送 WebSocket 通知：

```python
from dream.websocket.utils import send_image_update

# 发送图片处理状态更新
send_image_update(
    dream_id=123,
    image_urls=[{'id': 1, 'url': 'https://example.com/img1.jpg', 'position': 0}],
    status='completed',
    progress=100,
    message='图片处理完成'

```

### WebSocket 消息类型

#### 从服务器到客户端：

1. `connection_established` - 连接建立成功
2. `image_update` - 图片处理状态更新
3. `ping` - 服务器心跳
4. `pong` - 客户端心跳响应
5. `error` - 错误消息

#### 从客户端到服务器：

1. `authenticate` - 客户端认证
2. `ping` - 客户端心跳
3. `request_status` - 请求最新状态
