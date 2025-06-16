# WebSocket 模块

本模块负责处理 WebSocket 连接和消息传递，用于提供实时图片处理状态更新功能。采用异步处理模式，确保高效的实时通信。

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

## 核心组件

### 1. WebSocket 消费者 (DreamImagesConsumer)

梦境图片处理状态的WebSocket消费者，负责:

- 处理客户端连接认证 (基于JWT)
- 管理WebSocket连接生命周期
- 处理客户端消息和请求
- 发送图片处理状态更新通知
- 维持心跳保持连接稳定

```python
# 消费者主要方法
async def connect()         # 处理连接请求与认证
async def disconnect()      # 处理连接断开
async def receive_json()    # 接收客户端JSON消息
async def image_update()    # 接收并转发图片更新事件
```

### 2. WebSocket 通知工具 (notifications.py)

封装了向WebSocket通道发送消息的功能，支持:

- 发送多种类型的状态更新
- 失败重试机制
- 异步到同步消息转换

```python
# 主要函数
send_image_update(dream_id, image_urls, status, message) 
```

## 完整通信流程与技术原理

### 1. 消息传递流程

#### 从 Celery 任务到 Channel Layer

```python
# 在 Celery 任务中调用
send_image_update(dream_id=123, image_urls=[...], status='completed')

# send_image_update 内部实现
channel_layer = get_channel_layer()
message_data = {
    'type': 'image_update',  # 关键字段，决定调用哪个方法
    'dream_id': dream_id,
    'status': status,
    'images': image_urls or [],
    'timestamp': time.time()
}
group_name = f'dream_images_{dream_id}'
async_to_sync(channel_layer.group_send)(group_name, message_data)
```

1. Celery 任务调用 `send_image_update`
2. 消息准备包含特殊的 `type` 字段
3. 使用 `async_to_sync` 在同步环境中调用异步方法
4. 通过 `group_send` 将消息发送到指定通道组

#### Channel Layer 内部消息路由

Channel Layer（通常基于Redis实现）处理消息分发：

1. 消息存储到 Redis 中
2. 查询指定通道组的所有成员通道
3. 将消息复制并发送到组内的每个通道队列

#### 从 Channel Layer 到 Consumer

```python
# 自动调用的处理方法
async def image_update(self, event):
    """处理图片更新事件并发送到客户端"""
    await self.send_json({
        'type': 'image_update',
        'dream_id': event['dream_id'],
        'status': event['status'],
        'images': event['images'],
        'timestamp': event['timestamp'],
        'message': event.get('message')
    })
```

1. ASGI 服务器从 Channel Layer 接收消息
2. **自动触发机制**：根据消息的 `type` 字段动态查找并调用对应的方法
3. Django Channels 内部通过 `getattr(self, event['type'])` 查找方法
4. 调用 `image_update` 方法并传入完整的消息数据

#### 从 Consumer 到 WebSocket 客户端

当 `image_update` 方法被调用后，数据通过以下流程传递到客户端：

```
image_update() 方法
    ↓
self.send_json() - 将字典序列化为JSON
    ↓
self.send() - 准备WebSocket消息
    ↓
self.base_send() - 传递给ASGI接口
    ↓
ASGI服务器 - 处理WebSocket消息
    ↓
WebSocket协议封装 - 创建帧
    ↓
TCP/IP网络传输
    ↓
客户端浏览器WebSocket API
    ↓
onmessage事件处理器
```

1. `send_json()` 将Python字典序列化为JSON字符串
2. `send()` 将数据包装为WebSocket消息格式
3. ASGI服务器（Daphne/Uvicorn）负责WebSocket协议处理
4. 数据通过TCP/IP传输到客户端浏览器
5. 客户端的WebSocket实例触发 `onmessage` 事件

### 2. 技术要点

#### 自动触发机制

* Django Channels 框架确保了从 Channel Layer 接收消息到调用对应的处理方法再到发送响应的整个流程是自动化的
* 开发者只需实现 image\_update 方法，剩下的由框架处理

```python
# Django Channels 内部实现（简化版）
async def dispatch(self, message):
    handler = getattr(self, message["type"], None)
    if handler:
        await handler(message)
```

1. 消息中的 `type` 字段必须与消费者中的方法名匹配
2. 框架自动查找并调用对应方法，无需手动分发
3. 整个流程从消息到方法调用完全自动化

#### 异步和同步环境的桥接

```python
# 在同步环境中调用异步函数
async_to_sync(channel_layer.group_send)(group_name, message_data)

# 在异步环境中
await channel_layer.group_send(group_name, message_data)
```

这种设计允许:

- Celery任务（同步环境）可以向异步WebSocket系统发送消息
- 各组件保持最自然的编程模型
- 无需手动处理线程同步问题

### 3. 工作流程图解

```
┌─────────────┐     ┌───────────┐     ┌────────────┐     ┌───────────┐
│             │     │           │     │            │     │           │
│ Celery任务  │     │ Channel   │     │ WebSocket  │     │ 浏览器    │
│ (同步环境)  │     │ Layer     │     │ 消费者     │     │ 客户端    │
│             │     │           │     │            │     │           │
└──────┬──────┘     └─────┬─────┘     └──────┬─────┘     └─────┬─────┘
       │                  │                  │                 │
       │ send_image_update│                  │                 │
       │─────────────────>│                  │                 │
       │                  │                  │                 │
       │                  │ 存储并分发消息   │                 │
       │                  │─────────────────>│                 │
       │                  │                  │                 │
       │                  │                  │ 根据type自动    │               
       │                  │                  │ 调用image_update│               
       │                  │                  │────────>│       │
       │                  │                  │                 │
       │                  │                  │ send_json()     │
       │                  │                  │───────────────────>
       │                  │                  │                 │
       │                  │                  │                 │ onmessage
       │                  │                  │                 │────────>
       │                  │                  │                 │
```

## 消息类型和状态定义

### 从服务器到客户端的消息类型


| 消息类型                 | 描述             | 示例                                                         |
| ------------------------ | ---------------- | ------------------------------------------------------------ |
| `connection_established` | 连接建立成功     | `{type: "connection_established", dream_id: 123}`            |
| `image_update`           | 图片处理状态更新 | `{type: "image_update", status: "completed", images: [...]}` |
| `ping`                   | 服务器心跳       | `{type: "ping", timestamp: 1627884800}`                      |
| `error`                  | 错误信息         | `{type: "error", message: "处理失败"}`                       |

### 从客户端到服务器的消息类型


| 消息类型         | 描述         | 示例                                      |
| ---------------- | ------------ | ----------------------------------------- |
| `ping`           | 客户端心跳   | `{type: "ping", timestamp: 1627884800}`   |
| `request_status` | 请求最新状态 | `{type: "request_status", dream_id: 123}` |

### 图片处理状态类型


| 状态                | 描述         |
| ------------------- | ------------ |
| `processing`        | 图片处理中   |
| `completed`         | 图片处理完成 |
| `failed`            | 图片处理失败 |
| `delete_processing` | 图片删除中   |
| `delete_completed`  | 图片删除完成 |
| `delete_failed`     | 图片删除失败 |
