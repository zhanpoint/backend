from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _


class User(AbstractUser):
    """
    自定义用户模型，继承自Django的AbstractUser
    
    AbstractUser已经包含了用户名(username)和密码(password)字段，
    因此我们只需要添加手机号字段，并自定义这些字段的验证规则
    """
    
    # 自定义用户名验证规则：只能包含字母、数字，长度为4-16个字符
    username = models.CharField(
        _('用户名'),
        max_length=16,
        unique=True,
        help_text=_('必填。只能包含字母、数字，长度为4-16个字符。'),
        validators=[RegexValidator(
            regex=r'^[a-zA-Z0-9]{4,16}$',
            message='用户名只能包含字母和数字，长度在4-16个字符之间'
        )],
        error_messages={
            'unique': _("该用户名已存在"),
        },
    )
    
    # 添加手机号字段，使用正则验证中国大陆手机号格式
    phone_number = models.CharField(
        _('手机号'),
        max_length=11,
        unique=True,
        validators=[RegexValidator(
            regex=r'^1[3-9]\d{9}$',
            message='请输入有效的中国大陆手机号+86'
        )],
        help_text=_('请输入11位中国大陆手机号码+86')
    )
    
    # 将密码验证逻辑从模型层移到了系统配置和专门的验证器中
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
    
    def __str__(self):
        """返回用户的用户名作为字符串表示"""
        return self.username
    
    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'
        swappable = 'AUTH_USER_MODEL'  # 允许此模型可被settings.AUTH_USER_MODEL设置替换
