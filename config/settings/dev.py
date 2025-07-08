"""
开发环境配置
"""
from .base import *
from ..env_config import (
    DEBUG, DJANGO_SECRET_KEY, ALLOWED_HOSTS,
    DATABASE, CACHES_CONFIG, REDIS_CONFIG,
    RABBITMQ_CONFIG, CELERY_CONFIG, 
    JWT_CONFIG, EMAIL_CONFIG
)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = DJANGO_SECRET_KEY

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = DEBUG

ALLOWED_HOSTS = ALLOWED_HOSTS

# 开发环境CORS配置
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# 允许携带认证信息（cookies等）
CORS_ALLOW_CREDENTIALS = True

# 允许的请求方法
CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# 允许的请求头
CORS_ALLOW_HEADERS = [
    'authorization',  # 用于JWT认证
    'content-type',  # 用于指定请求体的格式
]

# 允许暴露的响应头
CORS_EXPOSE_HEADERS = [
    'Content-Type',  # 用于指定响应内容的类型
    'Authorization',  # 用于JWT token的传递
]

# Database
DATABASES = DATABASE

# Cache
CACHES = CACHES_CONFIG

# RabbitMQ配置
RABBITMQ_HOST = RABBITMQ_CONFIG['host']
RABBITMQ_PORT = RABBITMQ_CONFIG['port']
RABBITMQ_USER = RABBITMQ_CONFIG['user']
RABBITMQ_PASSWORD = RABBITMQ_CONFIG['password']
RABBITMQ_VHOST = RABBITMQ_CONFIG['vhost']

# Redis配置
REDIS_HOST = REDIS_CONFIG['host']
REDIS_PORT = REDIS_CONFIG['port']
REDIS_PASSWORD = REDIS_CONFIG['password']
REDIS_DB = 0  # 使用的数据库编号

# Celery配置
CELERY_BROKER_URL = CELERY_CONFIG['broker_url']
CELERY_RESULT_BACKEND = CELERY_CONFIG['result_backend']
CELERY_REDIS_MAX_CONNECTIONS = CELERY_CONFIG['redis_max_connections']
CELERY_INCLUDE = CELERY_CONFIG['include']

# - 配置消息层，用于处理WebSocket连接之间的通信
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/2'],
        },
    },
}

# JWT设置
SIMPLE_JWT = JWT_CONFIG

# Email配置
EMAIL_BACKEND = EMAIL_CONFIG['backend']
EMAIL_HOST = EMAIL_CONFIG['host']
EMAIL_PORT = EMAIL_CONFIG['port']
EMAIL_USE_SSL = EMAIL_CONFIG['use_ssl']
EMAIL_USE_TLS = EMAIL_CONFIG['use_tls']
EMAIL_HOST_USER = EMAIL_CONFIG['username']
EMAIL_HOST_PASSWORD = EMAIL_CONFIG['password']
DEFAULT_FROM_EMAIL = EMAIL_CONFIG['default_from_email'] or EMAIL_HOST_USER

# 开发环境日志配置
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}