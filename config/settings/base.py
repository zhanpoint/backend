"""
Django base settings for backend project.
基础配置文件，包含所有环境共享的配置
"""

from pathlib import Path
import os
from kombu import Queue, Exchange

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'channels',  # 使Django识别WebSocket功能
    
    # 本地应用
    'apps.dream',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'zh-CN'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = False  # 这个设置为True时，Django内部使用UTC，只在展示时转换

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 自定义用户模型配置
AUTH_USER_MODEL = 'dream.User'

# 密码哈希设置
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

# REST Framework 配置
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',  # 把数据转换成JSON格式返回
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',  # 解析JSON格式的请求数据
        'rest_framework.parsers.MultiPartParser',  # 解析文件上传数据
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',  # JWT认证
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',  # 允许任何用户访问API
    ],
}

# 由于WSGI只支持HTTP协议，而asgi模块支持WebSocket协议
ASGI_APPLICATION = 'config.asgi.application'

# 静态文件配置
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles_collected')

# Media files (User uploaded content)
MEDIA_URL = 'media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Celery序列化设置
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Shanghai'
CELERY_ENABLE_UTC = True

# Redis结果过期时间(秒)
CELERY_TASK_RESULT_EXPIRES = 3600  # 1小时

# 任务执行设置
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# -- Celery 路由配置 --
# 1. 定义一个所有任务通用的交换机
task_exchange = Exchange('tasks', type='direct')

# 2. 定义队列，并明确地将它们全部绑定到上面定义的同一个交换机
CELERY_TASK_QUEUES = (
    Queue('default', task_exchange, routing_key='task.default'),
    Queue('image_tasks', task_exchange, routing_key='task.image'),
)

# 3. 设置默认队列、交换机和路由键
CELERY_TASK_DEFAULT_QUEUE = 'default'
CELERY_TASK_DEFAULT_EXCHANGE = 'tasks'
CELERY_TASK_DEFAULT_ROUTING_KEY = 'task.default'

# 4. 定义精确的任务路由规则，将特定任务发送到指定队列
CELERY_TASK_ROUTES = {
    'apps.dream.tasks.image_tasks.celery_upload_images': {
        'queue': 'image_tasks',
        'routing_key': 'task.image',
    },
    'apps.dream.tasks.image_tasks.celery_delete_images': {
        'queue': 'image_tasks',
        'routing_key': 'task.image',
    },
    # 其他未明确指定的任务 (如 token_tasks) 将使用默认路由进入 'default' 队列
}