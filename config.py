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
    JWT_ACCESS_TOKEN_LIFETIME_MINUTES=(int, 1440),  # 24小时
    JWT_REFRESH_TOKEN_LIFETIME_DAYS=(int, 30),      # 30天
    EMAIL_PORT=(int, 465),
    EMAIL_USE_SSL=(bool, True),
    EMAIL_USE_TLS=(bool, False),
    SMS_SERVICE_ENABLED=(bool, False),
    EMAIL_SERVICE_ENABLED=(bool, True),
)

# 读取项目最外层的.env文件
# 获取当前文件的路径，向上两级到达项目根目录
project_root = Path(__file__).resolve().parent
env_path = project_root / '.env'

# # 加载.env文件
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
    # 使用 RabbitMQ 作为消息代理（Broker），负责接收和分发任务消息。
    'broker_url': f"amqp://{RABBITMQ_CONFIG['user']}:{RABBITMQ_CONFIG['password']}@{RABBITMQ_CONFIG['host']}:{RABBITMQ_CONFIG['port']}/{RABBITMQ_CONFIG['vhost']}",
    # 使用 Redis (db 1) 作为结果后端，用于存储任务的执行状态和返回值。
    'result_backend': f"redis://:{REDIS_CONFIG['password']}@{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}/1",
    # 这个配置项明确指定了Celery worker需要加载的任务模块，这是一种良好的实践，可以避免autodiscover_tasks可能带来的不确定性。
    'include': ['dream.tasks.image_tasks', 'dream.tasks.token_tasks', 'dream.tasks.email_tasks'],
    'redis_max_connections': 10,
    # 确保了任务和结果都使用JSON格式进行序列化，具有良好的通用性和可读性。
    'task_serializer': 'json',
    'result_serializer': 'json',
    'accept_content': ['json'],
    # 与Django配置保持一致，确保定时任务和时间记录的准确性。
    'timezone': 'Asia/Shanghai',
    'enable_utc': True,
    # 任务结果在Redis中会保存1小时，之后自动清除，有助于节省内存
    'task_result_expires': 3600,  # 1小时
    # 只有在任务执行成功后，消息才会从队列中被"确认"（删除）。如果worker在执行任务时崩溃，该任务会被重新分发给另一个worker。
    'task_acks_late': True,
    #  与上一条配合使用,即使worker进程被强制杀死，任务也会被拒绝并重新入队。
    'task_reject_on_worker_lost': True,
    # Celery的worker_prefetch_multiplier默认值是4,如果第一个任务是长耗时任务，那么其它3个任务会闲置在worker的内存中等待，而此时其他空闲的worker也无法获取这些任务，导致任务处理的并行度下降，队列阻塞
    # 设置为1对于长耗时任务是最佳实践，能确保任务被更均匀地分配给所有可用的worker。
    'worker_prefetch_multiplier': 1,
    
}


# 阿里云配置
ALIYUN_CONFIG = {
    'access_key_id': env('ALIYUN_ACCESS_KEY_ID', default=None),
    'access_key_secret': env('ALIYUN_ACCESS_KEY_SECRET', default=None),
    'oss_endpoint': env('ALIYUN_OSS_ENDPOINT', default=None),
    'sts_role_oss_arn': env('ALIYUN_STS_ROLE_OSS_ARN', default=None),
    'sts_role_sms_arn': env('ALIYUN_STS_ROLE_SMS_ARN', default=None),
    'region_id': env('ALIYUN_REGION_ID', default='cn-wuhan-lr'),
    'sms_sign_name': env('ALIYUN_SMS_SIGN', default=None),
    'sms_template_code_register': env('ALIYUN_SMS_TEMPLATE_REGISTER', default=None),
    'sms_template_code_login': env('ALIYUN_SMS_TEMPLATE_LOGIN', default=None),
    'sms_template_code_resetpassword': env('ALIYUN_SMS_TEMPLATE_RESETPASSWORD', default=None),
}

# 功能开关配置
FEATURE_FLAGS = {
    # 短信服务开关 - 设置为False时禁用短信功能
    'SMS_SERVICE_ENABLED': env('SMS_SERVICE_ENABLED', default=False),
    'EMAIL_SERVICE_ENABLED': env('EMAIL_SERVICE_ENABLED', default=True),
}

# 邮件配置
EMAIL_CONFIG = {
    'backend': 'django.core.mail.backends.smtp.EmailBackend',
    # 阿里云邮件推送SMTP服务器
    'host': env('EMAIL_HOST', default='smtpdm.aliyun.com'),
    # 阿里云邮件推送SMTP端口，465 是 SSL 加密连接的标准端口
    'port': env('EMAIL_PORT', default=465),
    # 使用SSL加密连接
    'use_ssl': env('EMAIL_USE_SSL', default=True),
    # 使用TLS，默认不使用
    'use_tls': env('EMAIL_USE_TLS', default=False),
    # 阿里云邮件推送发信地址，如 （noreply@your-domain.com）。
    'username': env('EMAIL_HOST_USER', default=None),
    # 阿里云邮件推送SMTP密码
    'password': env('EMAIL_HOST_PASSWORD', default=None),
    # 默认发信地址，用于发送邮件时显示的发件人信息
    'default_from_email': env('DEFAULT_FROM_EMAIL', default=None),
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
