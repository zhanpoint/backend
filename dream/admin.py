from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

# Register your models here.

# 注册自定义User模型
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    自定义User模型的Admin配置
    """
    # 列表页显示的字段
    list_display = ('username', 'phone_number', 'email', 'is_active', 'is_staff', 'date_joined')
    # 搜索字段
    search_fields = ('username', 'phone_number', 'email')
    # 过滤器
    list_filter = ('is_active', 'is_staff', 'date_joined')
    
    # 添加和编辑页面的字段集
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('个人信息', {'fields': ('phone_number', 'email')}),
        ('权限', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('重要日期', {'fields': ('last_login', 'date_joined')}),
    )
    # 添加用户页面的字段集
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'phone_number', 'password1', 'password2'),
        }),
    )
