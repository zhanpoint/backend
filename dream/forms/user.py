from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from dream.models import User


class UserRegistrationForm(UserCreationForm):
    """
    用户注册表单，基于 Django 的 UserCreationForm
    
    UserCreationForm 默认包含用户名、密码、确认密码字段，
    我们只需添加手机号字段即可
    """
    
    phone_number = forms.CharField(
        label='手机号',
        max_length=11,
        required=True,
        help_text='请输入11位中国大陆手机号码',
        error_messages={
            'required': '请输入手机号',
            'max_length': '手机号最多为11个字符',
        }
    )
    
    class Meta:
        model = User
        fields = ('username', 'phone_number', 'password1', 'password2')
    
    def clean_phone_number(self):
        """验证手机号格式"""
        phone_number = self.cleaned_data.get('phone_number')
        # 验证逻辑已经在模型中定义，这里可以添加额外的验证
        return phone_number


class UserLoginForm(AuthenticationForm):
    """
    用户登录表单，基于 Django 的 AuthenticationForm
    
    可以使用用户名或手机号登录
    """
    
    username = forms.CharField(
        label='用户名或手机号',
        max_length=150,
        required=True,
        error_messages={
            'required': '请输入用户名或手机号',
        }
    )
    
    def clean_username(self):
        """
        重写 clean_username 方法，支持使用手机号登录
        """
        username = self.cleaned_data.get('username')
        # 如果输入的是手机号格式，尝试查找对应的用户
        if username and username.isdigit() and len(username) == 11:
            try:
                user = User.objects.get(phone_number=username)
                return user.username  # 返回对应的用户名
            except User.DoesNotExist:
                pass
        return username 