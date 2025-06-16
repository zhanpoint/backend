# Celery 任务队列系统

本项目使用 Celery 作为异步任务队列系统，专注于处理图片上传、处理和定时清理等后台任务。整个系统设计为高效、可扩展、容错的架构。

## 目录结构

```
dream/celery/
├── __init__.py     # 包初始化文件，导出 celery_app
├── app.py          # Celery 应用配置文件
├── worker.py       # Worker 启动脚本
├── beat.py         # Beat 定时任务启动脚本
└── tasks/          # 任务定义目录
    ├── __init__.py     # 任务包初始化文件
    ├── image_tasks.py  # 图片处理相关任务
    └── token_tasks.py  # 令牌清理相关任务
```

## 核心组件

### 1. Celery 应用配置 (app.py)

定义了 Celery 应用及其配置，包括：

- 队列和交换机设置
- 路由规则
- 定时任务调度
- 任务自动发现

### 2. 图片处理任务 (image_tasks.py)

实现图片处理、上传和删除功能：

- **process_and_upload_images**: 处理和上传图片
- **delete_dream_images**: 从OSS删除图片
- **process_image**: 图片处理工具函数
- **upload_images**: 发送图片处理任务
- **delete_images**: 发送图片删除任务

### 3. 令牌清理任务 (token_tasks.py)

实现JWT黑名单令牌的清理：

- **cleanup_expired_tokens**: 清理过期的黑名单令牌

### 4. 工作进程启动脚本 (worker.py)

用于启动Celery工作进程，支持自定义参数。

### 5. 定时任务调度器 (beat.py)

用于启动Celery Beat定时任务调度器。

## 任务执行流程

### 图片处理流程

1. 视图层接收用户上传的图片
2. 调用`upload_images`函数，编码图片数据并发送到Celery队列
3. Celery Worker接收任务并执行`process_and_upload_images`：
   - 发送处理开始通知
   - 使用进程池并行处理图片
   - 上传处理后的图片到OSS
   - 创建数据库记录
   - 发送处理完成通知
4. WebSocket将处理结果推送给前端

```
客户端 → 视图层 → upload_images → Celery队列 → process_and_upload_images
                                                      ↓
                  WebSocket ← 通知工具 ← 处理结果返回
                      ↓
                   客户端UI更新
```

### 图片删除流程

1. 视图层接收删除请求
2. 调用`delete_images`函数，将图片信息发送到Celery队列
3. Celery Worker执行`delete_dream_images`：
   - 发送删除开始通知
   - 从OSS中删除图片文件
   - 发送删除完成通知
4. WebSocket将删除结果推送给前端

### 令牌清理流程

1. Celery Beat根据调度计划触发`cleanup_expired_tokens`任务
2. 任务删除数据库中过期的黑名单令牌
3. 记录清理结果日志

## 并发模式详解

本项目采用了三层并发模型设计：

### 1. Celery Worker 线程池

- 使用`--pool=threads`配置
- 适合任务队列管理和I/O操作
- 每个worker默认支持4个并发线程

### 2. 图像处理进程池

- 使用`ProcessPoolExecutor`
- 绕过Python GIL限制，实现真正的CPU并行计算
- 动态调整大小，根据CPU核心数和任务量自适应

### 3. OSS上传单线程

- 在任务线程中串行执行
- 避免创建过多并发连接
- I/O等待不阻塞CPU

## 队列详解

系统定义了两个主要队列，用于任务分发和负载均衡：

### 1. default

- 用途：一般任务和定时任务
- 交换机类型：direct
- 持久化：是
- 示例任务：`cleanup_expired_tokens`

### 2. dream_image_processing

- 用途：图片处理和上传任务
- 交换机类型：direct
- 持久化：是
- 示例任务：`process_and_upload_images`, `delete_dream_images`

## 定时任务配置


| 任务名称               | 函数                   | 调度        | 描述                    |
| ---------------------- | ---------------------- | ----------- | ----------------------- |
| cleanup-expired-tokens | cleanup_expired_tokens | 每天凌晨3点 | 清理过期的JWT黑名单令牌 |

## 错误处理和重试策略

所有任务都配置了以下错误处理策略：

- 最大重试次数：5次
- 重试间隔：指数退避（第一次60秒，后续次数按1.5倍增加）
- 最大重试间隔：600秒
- 任务超时：300秒

## 性能优化

### CPU优化

- 自动检测CPU核心数并动态配置进程池大小
- 图片大小自适应压缩，减少处理和传输开销
- 批量处理，减少数据库操作次数

### 内存优化

- 图片流式处理，避免将整个图片加载到内存
- 使用链接而非直接复制大数据结构

### I/O优化

- 使用线程池处理I/O操作
- 针对网络操作实现重试机制
- 使用批量数据库事务

## 部署建议

### 开发环境

使用以下命令启动开发环境：

```bash
# 启动Celery Worker
python backend/dream/celery/worker.py

# 启动Celery Beat
python backend/dream/celery/beat.py
```

### 生产环境 (Linux)

#### 使用 Systemd 部署

1. 创建 Celery Worker 服务文件 `/etc/systemd/system/dream-celery-worker.service`：

```ini
[Unit]
Description=Dream Celery Worker
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/python backend/dream/celery/worker.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

2. 创建 Celery Beat 服务文件 `/etc/systemd/system/dream-celery-beat.service`：

```ini
[Unit]
Description=Dream Celery Beat
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/python backend/dream/celery/beat.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

3. 启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl start dream-celery-worker
sudo systemctl start dream-celery-beat
sudo systemctl enable dream-celery-worker
sudo systemctl enable dream-celery-beat
```

#### 使用 Supervisor 部署

1. 安装 supervisor：`pip install supervisor`
2. 创建配置文件 `/etc/supervisor/conf.d/dream-celery.conf`：

```ini
[program:dream-celery-worker]
command=/path/to/venv/bin/python backend/dream/celery/worker.py
directory=/path/to/project
user=www-data
numprocs=1
stdout_logfile=/var/log/dream-celery-worker.log
stderr_logfile=/var/log/dream-celery-worker-error.log
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600

[program:dream-celery-beat]
command=/path/to/venv/bin/python backend/dream/celery/beat.py
directory=/path/to/project
user=www-data
numprocs=1
stdout_logfile=/var/log/dream-celery-beat.log
stderr_logfile=/var/log/dream-celery-beat-error.log
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
```

3. 启动服务：

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start dream-celery-worker
sudo supervisorctl start dream-celery-beat
```
