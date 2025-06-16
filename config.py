"""
配置管理模块
负责加载和管理环境变量配置
"""

from pathlib import Path
from datetime import timedelta
import environ

# 对需要进行类型转换的环境变量中进行初始化，
env = environ.Env(
    DEBUG=(bool, True),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1', '120.216.67.22']),
    DB_PORT=(int, 3306),
    REDIS_PORT=(int, 6379),
    REDIS_DB=(int, 0),
    RABBITMQ_PORT=(int, 5672),
    JWT_ACCESS_TOKEN_LIFETIME_MINUTES=(int, 60),
    JWT_REFRESH_TOKEN_LIFETIME_DAYS=(int, 7),
)

# 读取项目最外层的.env文件
# 获取当前文件的路径，向上两级到达项目根目录
project_root = Path(__file__).resolve().parent
env_path = project_root / '.env'

# 加载.env文件
environ.Env.read_env(env_path)

# Django基础配置
DEBUG = env('DEBUG')
DJANGO_SECRET_KEY = env('DJANGO_SECRET_KEY')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# 数据库配置
DATABASE = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('DB_NAME', default='dream'),
        'USER': env('DB_USER', default='root'),
        'PASSWORD': env('DB_PASSWORD', default=''),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': 'SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci',
        }
    }
}

# Redis配置(缓存0，celery1，websocket2)
REDIS_CONFIG = {
    'host': env('REDIS_HOST', default='127.0.0.1'),
    'port': env('REDIS_PORT'),
    'password': env('REDIS_PASSWORD', default=''),
    'db': env('REDIS_DB'),
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
    'host': env('RABBITMQ_HOST', default='127.0.0.1'),
    'port': env('RABBITMQ_PORT'),
    'user': env('RABBITMQ_DEFAULT_USER', default='guest'),
    'password': env('RABBITMQ_DEFAULT_PASS', default='guest'),
    'vhost': env('RABBITMQ_VHOST', default='/'),
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
    'access_key_id': env('ALIYUN_ACCESS_KEY_ID', default=None),
    'access_key_secret': env('ALIYUN_ACCESS_KEY_SECRET', default=None),
    'oss_endpoint': env('ALIYUN_OSS_ENDPOINT', default=None),
    'sts_role_oss_arn': env('ALIYUN_STS_ROLE_OSS_ARN', default=None),
    'sts_role_sms_arn': env('ALIYUN_STS_ROLE_SMS_ARN', default=None),
    'region_id': env('ALIYUN_REGION_ID', default='cn-wuhan-lr'),
    'sms_sign_name': env('ALIYUN_SMS_SIGN1', default=None),
    'sms_template_code_register': env('ALIYUN_SMS_TEMPLATE_REGISTER', default=None),
    'sms_template_code_login': env('ALIYUN_SMS_TEMPLATE_LOGIN', default=None),
    'sms_template_code_resetpassword': env('ALIYUN_SMS_TEMPLATE_RESETPASSWORD', default=None),
}

# JWT配置
# DRF SimpleJWT内部使用的是UTC时间来处理token的过期时间,OutstandingToken模型直接使用了JWT中的原始时间信息(UTC时间)
JWT_CONFIG = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=env('JWT_ACCESS_TOKEN_LIFETIME_MINUTES')),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=env('JWT_REFRESH_TOKEN_LIFETIME_DAYS')),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': DJANGO_SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}
