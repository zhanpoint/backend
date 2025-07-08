"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.schemas import get_schema_view
from django.conf import settings
from django.conf.urls.static import static

# API文档设置
schema_view = get_schema_view(
    title="Dream API",
    description="API Documentation for Dream Application",
    version="1.0.0"
)

urlpatterns = [
    # django自带的admin管理后台
    path('admin/', admin.site.urls),
    # dream应用路由
    path('', include('apps.dream.urls')),
    
    # API文档路径
    path('api/schema/', schema_view, name='api_schema'),
    # API认证路由
    path('api-auth/', include('rest_framework.urls')),  # DRF登录/登出视图
]

# 仅在开发模式下提供静态和媒体文件
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)