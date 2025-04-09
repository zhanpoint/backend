# WebSocket 图片处理通知功能

本文档说明了如何使用 WebSocket 来接收图片处理状态的实时通知。

## 功能概述

当用户创建梦境记录并上传图片时，我们采用以下流程处理图片：

1. 后端立即返回梦境创建成功的响应，但图片处理部分为异步处理
2. 前端立即显示梦境内容，但图片位置显示为"加载中"状态
3. 后端通过 Celery 任务异步处理图片（包括调整大小、上传到OSS等）
4. 处理完成后，后端通过 WebSocket 通知前端
5. 前端接收通知，更新图片 URL 并刷新显示

## 服务器端配置

### 1. 安装所需依赖

```bash
pip install channels==3.0.5 channels-redis==3.4.1 daphne
```

### 2. 在设置中配置 WebSocket

在 `settings.py` 中已添加必要的配置：

```python
INSTALLED_APPS = [
    # ... 其他应用
    'channels',  # 添加 Django Channels 支持
]

# 添加 ASGI 应用
ASGI_APPLICATION = 'backend.asgi.application'

# 添加 Channel Layers 配置
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [f'redis://:{redis_password}@127.0.0.1:6379/2'],
        },
    },
}
```

### 3. 启动服务器

使用 Daphne 代替 runserver 来支持 WebSocket：

```bash
daphne -b 0.0.0.0 -p 8000 backend.asgi:application
```

## WebSocket API 说明

### 连接 URL

```
ws://your-domain/ws/dream-images/{dream_id}/
```

其中 `{dream_id}` 是梦境记录的 ID。

### 认证

连接时需要在请求头中添加 JWT 认证令牌：

```javascript
const socket = new WebSocket(wsUrl);
socket.onopen = () => {
  socket.send(JSON.stringify({
    type: 'authenticate',
    token: 'Bearer your-jwt-token'
  }));
};
```

### 事件类型

1. **连接建立事件**：

```json
{
  "type": "connection_established",
  "dream_id": "123",
  "message": "连接已建立，等待图片处理状态更新"
}
```

2. **图片处理开始事件**：

```json
{
  "type": "image_update",
  "dream_id": "123",
  "status": "processing",
  "images": [],
  "timestamp": 1649154789.123
}
```

3. **图片处理完成事件**：

```json
{
  "type": "image_update",
  "dream_id": "123",
  "status": "completed",
  "images": [
    {
      "id": 1,
      "url": "https://example.com/image1.jpg",
      "position": 10
    },
    {
      "id": 2,
      "url": "https://example.com/image2.jpg",
      "position": 50
    }
  ],
  "timestamp": 1649154799.456
}
```

4. **图片处理失败事件**：

```json
{
  "type": "image_update",
  "dream_id": "123",
  "status": "failed",
  "images": [],
  "timestamp": 1649154799.789
}
```

### 心跳机制

为保持连接活跃，客户端应每 30 秒发送一次心跳:

```json
{
  "type": "ping",
  "timestamp": 1649154859.123
}
```

服务器会回复:

```json
{
  "type": "pong",
  "timestamp": 1649154859.123
}
```

## 前端集成示例

项目提供了 `frontend_example.js` 文件，其中包含完整的前端集成示例。关键部分：

```javascript
// 创建 WebSocket 客户端
const socket = new DreamImageWebSocketClient(
  dreamId, 
  authToken,
  handleImageUpdate
);
socket.connect();

// 处理图片更新事件
function handleImageUpdate(data) {
  if (data.status === 'completed') {
    // 更新界面显示图片
    updateImages(data.images);
  }
}
```

## 注意事项

1. WebSocket 连接依赖于 Redis，确保 Redis 服务已启动
2. WebSocket 服务需要使用 Daphne 或 uvicorn 启动，不能使用传统的 runserver
3. 前端应当实现重连逻辑，以应对网络波动
4. 为了安全，WebSocket 连接会验证用户是否有权访问该梦境记录 