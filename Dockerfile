# 使用官方的Python 3.9 slim版本作为基础镜像
FROM python:3.9-slim

# 设置环境变量，防止生成.pyc文件并使输出直接可见
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装（不保留缓存文件以减小镜像体积。）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目所有文件到工作目录
COPY . . 