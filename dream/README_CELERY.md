# Celery 使用指南

## 架构概述

本项目使用以下组件进行异步任务处理：

- **Celery**：分布式任务队列
- **RabbitMQ**：消息代理，用于任务发送和接收
- **Redis**：结果后端，用于存储任务结果和状态

## 队列配置

系统配置了两个队列：

1. `default`：通用任务队列
2. `dream_image_processing`：专用于图片处理的队列

## 在Windows上启动Celery

由于Windows上存在事件循环和多进程的兼容性问题，我们使用线程池和专用的启动方式：

```bash
# 启动图片处理worker (推荐在Windows上使用)
celery -A dream.celery_worker worker --pool=threads -Q dream_image_processing --loglevel=info
```

注意事项：

- 使用 `dream.celery_worker` 模块替代 `dream`
- 指定 `--pool=threads` 选项使用线程池而非进程池
- `-Q dream_image_processing` 指定只处理图片任务队列

## 在Linux/Unix上启动Celery

在Linux/Unix系统上，可以使用标准启动方式：

```bash
# 启动所有队列的worker
celery -A dream worker --loglevel=info

# 或者只启动图片处理队列
celery -A dream worker -Q dream_image_processing --loglevel=info
```

## 启动Celery Beat (定时任务)

```bash
celery -A dream beat --loglevel=info
```

## 监控

使用Flower监控Celery任务：

```bash
pip install flower
celery -A dream flower --port=5555
```

然后访问 http://localhost:5555 查看任务执行状态。

## 常见问题排查

### Django应用未加载

如果遇到 `AppRegistryNotReady: Apps aren't loaded yet` 错误，请确保：

1. 使用 `dream.celery_worker` 模块启动worker
2. 使用 `--pool=threads` 选项

### 事件循环错误

如果遇到 `Task got Future attached to a different loop` 错误，说明存在事件循环冲突，请：

1. 确保使用线程池而非进程池
2. 在Windows上避免使用asyncio

### 队列积压

如果任务积压严重：

1. 增加worker数量，用 `-c` 参数设置并发数：`-c 4`
2. 监控RabbitMQ队列状态，确保消息未堆积

## 配置文件说明

- `dream/celery.py`：Celery应用配置
- `dream/celery_worker.py`：Worker启动模块
- `dream/tasks/`：包含所有Celery任务定义
- `dream/tasks/image_tasks.py`：图片处理任务

## 使用示例

```python
from dream.utils.queue_manager import send_image_processing_task

# 发送图片处理任务
task_id = send_image_processing_task(dream_id, image_files, positions)
``` 