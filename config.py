"""
配置管理模块
负责加载和管理环境变量配置
"""

import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv

# 加载.env文件
#   获取当前文件的路径，解析所有符号链接，将路径转换为完整的绝对路径，并获取绝对路径的父目录，Path对象重载了 / 运算符，用于路径拼接
env_path = Path(__file__).resolve().parent / '.env'
#   加载指定路径的.env文件到环境变量
load_dotenv(env_path)


def get_env_value(key: str, default: any = None, cast_type: type = str) -> any:
    """
    获取环境变量值，支持类型转换和默认值

    参数:
        key: 环境变量名
        default: 当环境变量不存在或转换失败时返回的默认值
        cast_type: 目标类型 (默认为str)

    返回:
        转换后的环境变量值或默认值
    """
    value = os.getenv(key, default)
    if value is None:
        return default

    if cast_type == bool:
        return str(value).lower() in ('true', '1', 'yes')
    if cast_type == list:
        return [x.strip() for x in str(value).split(',') if x.strip()]
    try:
        return cast_type(value)
    except (ValueError, TypeError):
        return default


# Django基础配置
DEBUG = get_env_value('DEBUG', True, bool)
SECRET_KEY = get_env_value('SECRET_KEY', 'django-insecure-default-key-change-me')
ALLOWED_HOSTS = get_env_value('ALLOWED_HOSTS', 'localhost,127.0.0.1', list)

# 数据库配置
DATABASE = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': get_env_value('DB_NAME', 'dream'),
        'USER': get_env_value('DB_USER', 'root'),
        'PASSWORD': get_env_value('DB_PASSWORD', ''),
        'HOST': get_env_value('DB_HOST', 'localhost'),
        'PORT': get_env_value('DB_PORT', 3306, int),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': 'SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci',
        }
    }
}

# Redis配置(缓存0，celery1，websocket2)
REDIS_CONFIG = {
    'host': get_env_value('REDIS_HOST', '127.0.0.1'),
    'port': get_env_value('REDIS_PORT', 6379, int),
    'password': get_env_value('REDIS_PASSWORD', ''),
    'db': get_env_value('REDIS_DB', 0, int),
}

# Redis缓存配置
CACHES_CONFIG = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://:{REDIS_CONFIG['password']}@{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}/0",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': 10},
            'PASSWORD': REDIS_CONFIG['password'],
        },
        'TIMEOUT': 1209600,  # 14天
    }
}

# RabbitMQ配置
RABBITMQ_CONFIG = {
    'host': get_env_value('RABBITMQ_HOST', '127.0.0.1'),
    'port': get_env_value('RABBITMQ_PORT', 5672, int),
    'user': get_env_value('RABBITMQ_USER', 'guest'),
    'password': get_env_value('RABBITMQ_PASSWORD', 'guest'),
    'vhost': get_env_value('RABBITMQ_VHOST', '/'),
}

# Celery配置
CELERY_CONFIG = {
    'broker_url': f"amqp://{RABBITMQ_CONFIG['user']}:{RABBITMQ_CONFIG['password']}@{RABBITMQ_CONFIG['host']}:{RABBITMQ_CONFIG['port']}/{RABBITMQ_CONFIG['vhost']}",
    'result_backend': f"redis://:{REDIS_CONFIG['password']}@{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}/1",
    'redis_max_connections': 10,
    'task_serializer': 'json',
    'result_serializer': 'json',
    'accept_content': ['json'],
    'timezone': 'Asia/Shanghai',
    'enable_utc': True,
    'task_result_expires': 3600,  # 1小时
    'task_acks_late': True,
    'task_reject_on_worker_lost': True,
}

# 阿里云配置
ALIYUN_CONFIG = {
    'access_key_id': get_env_value('ALIYUN_ACCESS_KEY_ID'),
    'access_key_secret': get_env_value('ALIYUN_ACCESS_KEY_SECRET'),
    'oss_endpoint': get_env_value('ALIYUN_OSS_ENDPOINT'),
    'sts_role_oss_arn': get_env_value('ALIYUN_STS_ROLE_OSS_ARN'),
    'sts_role_sms_arn': get_env_value('ALIYUN_STS_ROLE_SMS_ARN'),
    'region_id': get_env_value('ALIYUN_REGION_ID', 'cn-wuhan-lr'),
    'sms_sign_name': get_env_value('ALIYUN_SMS_SIGN1'),
    'sms_template_code_register': get_env_value('ALIYUN_SMS_TEMPLATE_REGISTER'),
    'sms_template_code_login': get_env_value('ALIYUN_SMS_TEMPLATE_LOGIN'),
    'sms_template_code_resetpassword': get_env_value('ALIYUN_SMS_TEMPLATE_RESETPASSWORD'),
}

# JWT配置
# DRF SimpleJWT内部使用的是UTC时间来处理token的过期时间,OutstandingToken模型直接使用了JWT中的原始时间信息(UTC时间)
JWT_CONFIG = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=get_env_value('JWT_ACCESS_TOKEN_LIFETIME_MINUTES', 60, int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=get_env_value('JWT_REFRESH_TOKEN_LIFETIME_DAYS', 7, int)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}
