"""
Django settings for backend project.

Generated by 'django-admin startproject' using Django 4.2.20.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/4.2/ref/settings/
"""

from pathlib import Path
from .local_settings import mysql_password, redis_password

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-fe1*#ihdw0+-9!-lt1-1mzj4rnby9=xia)*1!kmxi!8y=i+1pz'

# SECURITY WARNING: don't run with debug turned on in production!
# 开发模式
DEBUG = True

ALLOWED_HOSTS = []  # DEBUG=True，默认允许"localhost"和"127.0.0.1"访问，如果DEBUG=False，没有任何人能访问

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'dream.apps.DreamConfig',
    'rest_framework',  # 添加DRF
    'rest_framework_simplejwt',  # 添加SimpleJWT
    'rest_framework_simplejwt.token_blacklist',  # 添加JWT黑名单功能
    'coreapi',  # 添加coreapi用于API文档
    'corsheaders',  # 跨域支持
    'channels',  # 添加Django Channels支持WebSocket
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # 必须放在其他中间件前面
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# 只允许特定域名访问(生产环境)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",  # vite构建的React项目的默认端口
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
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# 允许暴露的响应头
CORS_EXPOSE_HEADERS = ['Content-Length', 'Content-Type']

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates']
        ,
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


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    # Django需要通过MySQLdb模块与MySQL数据库进行交互，而这个模块在Windows环境下通常由mysqlclient库提供(记得安装)
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'OPTIONS': {
            'charset': 'utf8mb4',  # 关键配置
            'init_command': 'SET NAMES utf8mb4 COLLATE utf8mb4_unicode_ci',
        },
        'HOST': 'localhost',
        'PORT': '3306',
        'NAME': 'dream',
        'USER': 'root',
        'PASSWORD': mysql_password,
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': 10},
            'PASSWORD': redis_password,
        },
        'TIMEOUT': 1209600,
    }
}

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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
    # 使用自定义复杂密码验证器，实现密码规则验证
    {
        'NAME': 'dream.validators.ComplexPasswordValidator',
        'OPTIONS': {
            'min_length': 8,
            'max_length': 32,
        }
    },
]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# 自定义用户模型配置
# 指定我们自定义的User模型，格式为 '应用名.模型名'
AUTH_USER_MODEL = 'dream.User'

# 密码哈希设置
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

# REST Framework 配置
REST_FRAMEWORK = {
    # 数据渲染器
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',  # 把数据转换成JSON格式返回
        'rest_framework.renderers.BrowsableAPIRenderer',  # 允许在浏览器中查看API文档
    ],
    # 数据解析器
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',  # 解析JSON格式的请求数据
        'rest_framework.parsers.FormParser',  # 解析表单数据
        'rest_framework.parsers.MultiPartParser',  # 解析文件上传数据
    ],
    # 认证方式
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',  # 方式二：DRF的官方JWT认证
    ],
    # 权限设置
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',  # 允许任何用户访问API
    ],
    # 异常处理
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',  # 默认的异常处理函数
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.coreapi.AutoSchema',  # 使用CoreAPI的AutoSchema生成API文档
}

# JWT设置
from datetime import timedelta
"""
- 只想返回JSON：删除 BrowsableAPIRenderer
- 需要更严格的访问控制：改用 IsAuthenticated
- 想添加token认证：加入 TokenAuthentication
"""
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,  # 是否允许刷新token
    'BLACKLIST_AFTER_ROTATION': True,  # 刷新token后，之前的token不再可用
    'UPDATE_LAST_LOGIN': True,  # 更新最后登录时间

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',  # 这是Django中HTTP头的特殊格式
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',

    'JTI_CLAIM': 'jti',
}


# RabbitMQ配置
RABBITMQ_HOST = '127.0.0.1'  # RabbitMQ服务器地址
RABBITMQ_PORT = 5672  # 端口号
RABBITMQ_USER = 'dream_admin'  # 用户名
RABBITMQ_PASSWORD = '333444lL'  # 密码
RABBITMQ_VHOST = '/'  # 虚拟主机路径

# Redis配置
REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
REDIS_PASSWORD = '333444'  # Redis密码
REDIS_DB = 0  # 使用的数据库编号

# Celery配置
# 使用RabbitMQ作为消息代理
CELERY_BROKER_URL = f'amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}/{RABBITMQ_VHOST}'
# Redis结果后端配置(带密码认证)
CELERY_RESULT_BACKEND = f'redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'
CELERY_REDIS_MAX_CONNECTIONS = 10  # Redis连接池最大连接数

# Celery序列化设置
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Shanghai'
CELERY_ENABLE_UTC = True

# Redis结果过期时间(秒)
CELERY_TASK_RESULT_EXPIRES = 60 * 60  # 1小时

# 任务执行设置
CELERY_TASK_ACKS_LATE = True  # 任务执行完成后再确认
CELERY_TASK_REJECT_ON_WORKER_LOST = True  # worker异常退出时拒绝任务

# 添加ASGI应用，替换WSGI配置
ASGI_APPLICATION = 'backend.asgi.application'

# 添加Channel Layers配置，使用Redis作为后端
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [f'redis://:{redis_password}@127.0.0.1:6379/2'],
        },
    },
}
