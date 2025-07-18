"""
生产环境配置
"""
from .base import *
from ..env_config import (
    DJANGO_SECRET_KEY, ALLOWED_HOSTS,
    DATABASE, CACHES_CONFIG, REDIS_CONFIG,
    RABBITMQ_CONFIG, CELERY_CONFIG, 
    JWT_CONFIG, EMAIL_CONFIG
)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = DJANGO_SECRET_KEY

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = ALLOWED_HOSTS

# 生产环境CORS配置 - 根据实际部署域名修改
CORS_ALLOWED_ORIGINS = [
    "https://dreamlog.xyz",
    "https://www.dreamlog.xyz",
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
    'authorization',
    'content-type',
]

# 允许暴露的响应头
CORS_EXPOSE_HEADERS = [
    'Content-Type',
    'Authorization',
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
REDIS_DB = 0

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

# 生产环境安全设置
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# 生产环境日志配置
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
            'maxBytes': 1024 * 1024 * 15,  # 15MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file', 'console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}