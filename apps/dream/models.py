from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator, MinLengthValidator, MaxLengthValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.validators import UnicodeUsernameValidator


# 用户的注册方式
class RegistrationMethod(models.TextChoices):
    EMAIL = 'email', _('邮箱')
    PHONE = 'phone', _('手机')


class User(AbstractUser):
    """自定义用户模型"""
    # 用户名: 保持不变
    username = models.CharField(
        _('username'),
        max_length=150,
        unique=True,
        help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'),
        validators=[UnicodeUsernameValidator()],
        error_messages={
            'unique': _("A user with that username already exists."),
        },
    )

    # 邮箱地址
    email = models.EmailField(_('邮箱地址'), unique=True, null=True, blank=True, default=None)

    # 手机号
    phone_number = models.CharField(
        _('手机号'),
        max_length=11,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(r'^1[3-9]\d{9}$', '请输入正确的手机号')],
        default=None
    )

    # 新增注册方式字段
    registration_method = models.CharField(
        max_length=10,
        choices=RegistrationMethod.choices,
        default=RegistrationMethod.EMAIL,
        verbose_name=_('注册方式')
    )

    class Meta:
        verbose_name = _('用户')
        verbose_name_plural = verbose_name

    def clean(self):
        """确保用户至少提供手机号或邮箱其中一个"""
        super().clean()
        if not self.phone_number and not self.email:
            raise ValidationError('必须提供手机号或邮箱地址其中一个')

        # 确保唯一性约束
        if self.phone_number:
            existing_user = User.objects.filter(phone_number=self.phone_number).exclude(pk=self.pk).first()
            if existing_user:
                raise ValidationError({'phone_number': '该手机号已被注册'})

        if self.email:
            existing_user = User.objects.filter(email=self.email).exclude(pk=self.pk).first()
            if existing_user:
                raise ValidationError({'email': '该邮箱地址已被注册'})

    def __str__(self):
        return self.username or self.phone_number or self.email


class DreamCategory(models.Model):
    """梦境分类模型"""
    CATEGORY_CHOICES = [
        ('normal', '普通梦境'),
        ('memorable', '难忘梦境'),
        ('indicate', '预示梦境'),
        ('archetypal', '原型梦境'),
        ('lucid', '清醒梦'),
        ('nightmare', '噩梦'),
        ('repeating', '重复梦'),
        ('sleep_paralysis', '睡眠瘫痪')
    ]

    name = models.CharField(
        max_length=50,
        unique=True,
        choices=CATEGORY_CHOICES,
        verbose_name="分类名称"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "梦境分类"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.get_name_display()


class Tag(models.Model):
    """标签基类模型"""
    name = models.CharField(
        max_length=20,
        verbose_name="标签名称"
    )
    tag_type = models.CharField(
        max_length=20,
        choices=[
            ('theme', '主题'),
            ('character', '角色'),
            ('location', '地点')
        ],
        verbose_name="标签类型"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        unique_together = ('name', 'tag_type')
        verbose_name = "标签"
        verbose_name_plural = verbose_name

    def clean(self):
        if self.name:
            self.name = self.name.strip()

        if not self.name:
            raise ValidationError('标签名称不能为空')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tag_type_display()}:{self.name}"


def validate_image_size(value):
    if value.size > 2 * 1024 * 1024:  # 2MB
        raise ValidationError('图片大小不能超过2MB')


class DreamImage(models.Model):
    """梦境图片模型"""
    dream = models.ForeignKey(
        'Dream',
        on_delete=models.CASCADE,
        related_name='images',
        verbose_name="所属梦境"
    )
    image_url = models.URLField(
        max_length=255,
        verbose_name="图片URL"
    )
    position = models.PositiveIntegerField(
        default=0,
        verbose_name="图片在梦境内容的位置"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="创建时间"
    )

    class Meta:
        verbose_name = "梦境图片"
        verbose_name_plural = verbose_name
        ordering = ['position']

    def __str__(self):
        return f"{self.dream.title}的图片{self.id}"


class Dream(models.Model):
    """梦境记录模型"""
    title = models.CharField(
        max_length=30,
        validators=[MinLengthValidator(5)],
        verbose_name="标题"
    )
    content = models.TextField(
        validators=[
            MinLengthValidator(30),
            MaxLengthValidator(2000)
        ],
        verbose_name="内容"
    )
    user = models.ForeignKey('User', on_delete=models.CASCADE, verbose_name="用户")
    categories = models.ManyToManyField(
        DreamCategory,
        verbose_name="梦境分类",

    )
    theme_tags = models.ManyToManyField(
        Tag,
        related_name="dream_themes",
        verbose_name="主题标签"
    )
    character_tags = models.ManyToManyField(
        Tag,
        related_name="dream_characters",
        verbose_name="角色标签"
    )
    location_tags = models.ManyToManyField(
        Tag,
        related_name="dream_locations",
        verbose_name="地点标签"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "梦境"
        verbose_name_plural = verbose_name
        ordering = ['-created_at']

    def clean(self):
        # 验证标题
        if self.title:
            self.title = self.title.strip()

        # 只有在已保存的对象上才验证关系
        if self.id:
            # 验证分类数量（在保存后进行）
            if hasattr(self, 'categories'):
                categories_count = self.categories.count()
                if categories_count < 1 or categories_count > 3:
                    raise ValidationError('梦境分类数量必须在1-3个之间')

            # 验证图片数量和总大小
            if hasattr(self, 'images'):
                images = self.images.all()
                if images.count() > 3:
                    raise ValidationError('最多只能上传3张图片')

                try:
                    total_size = sum(img.image.size for img in images if hasattr(img, 'image') and img.image)
                    if total_size > 10 * 1024 * 1024:  # 10MB
                        raise ValidationError('所有图片总大小不能超过10MB')
                except:
                    pass

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
