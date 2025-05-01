# Celery 任务队列系统

本项目使用 Celery 作为异步任务队列系统，处理图片上传、处理和定时清理等后台任务。

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

## 并发模式说明

本项目采用混合并发模式设计，充分发挥各种并发模型的优势：

1. **Celery Worker：线程池模式**
   - 使用 `--pool=threads` 配置
   - 适合处理任务队列和I/O操作
   - 配置轻量，启动快速，资源占用低

2. **图像处理：进程池模式**
   - 在任务内部使用 `ProcessPoolExecutor`
   - 绕过Python GIL限制，实现真正的并行处理
   - 充分利用多核CPU加速图像处理

3. **OSS上传：串行处理**
   - 在当前任务线程中串行执行
   - I/O密集型操作不会阻塞CPU
   - 避免创建过多的并发连接

### 优势

- **资源高效利用**：CPU密集型操作（图像处理）使用进程并行；I/O操作（网络请求）在线程中处理
- **横向扩展**：可增加Celery Worker实例数量处理更多任务
- **纵向扩展**：可调整进程池大小适应不同规模的任务

### 调优参数

- `PROCESS_COUNT`：进程池大小，默认为CPU核心数-1（最大8）
- `--concurrency`：Celery Worker线程数，默认为4

## 启动 Celery Worker

Celery Worker 负责处理异步任务。使用以下命令启动：

```bash
# 使用默认配置启动
python backend/dream/celery/worker.py

# 或者自定义参数
python backend/dream/celery/worker.py worker --loglevel=debug
```

默认配置包括：
- 使用线程池
- 处理默认队列和图像处理队列
- 日志级别：info
- 并发数：4

## 启动 Celery Beat (定时任务)

Celery Beat 负责调度定时任务，如清理过期的黑名单令牌。使用以下命令启动：

```bash
# 使用默认配置启动
python backend/dream/celery/beat.py

# 或者自定义参数
python backend/dream/celery/beat.py beat --loglevel=debug
```

## 定时任务列表

当前配置了以下定时任务：

1. **cleanup_expired_tokens**: 每天凌晨 3 点清理已过期的黑名单令牌

## 队列列表

1. **default**: 默认队列，处理一般任务
2. **dream_image_processing**: 图像处理队列，处理图片上传和处理任务 


## 生产版本建议（LInux）
1. 在生产环境中：配置系统服务管理器（如 systemd、supervisor 等）来管理 Celery worker 进程
2. 在开发环境中：可以使用工具如 honcho 或自定义脚本来同时启动 Django 和 Celery worker
 