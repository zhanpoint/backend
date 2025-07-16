from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.utils import timezone
import uuid


# 用户的注册方式
class RegistrationMethod(models.TextChoices):
    EMAIL = 'email', _('邮箱')
    PHONE = 'phone', _('手机')


class User(AbstractUser):
    """自定义用户模型"""
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

    email = models.EmailField(_('邮箱地址'), unique=True, null=True, blank=True, default=None)

    phone_number = models.CharField(
        _('手机号'),
        max_length=11,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(r'^1[3-9]\d{9}$', '请输入正确的手机号')],
        default=None
    )

    registration_method = models.CharField(
        max_length=10,
        choices=RegistrationMethod.choices,
        default=RegistrationMethod.EMAIL,
        verbose_name=_('注册方式')
    )

    # 用户偏好设置
    timezone = models.CharField(max_length=50, default='Asia/Shanghai', verbose_name='时区')
    dream_privacy_default = models.CharField(
        max_length=10,
        choices=[('private', '私人'), ('public', '公开'), ('friends', '好友可见')],
        default='private',
        verbose_name='梦境默认隐私设置'
    )

    class Meta:
        verbose_name = _('用户')
        verbose_name_plural = verbose_name

    def clean(self):
        super().clean()
        if not self.phone_number and not self.email:
            raise ValidationError('必须提供手机号或邮箱地址其中一个')

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
    """梦境分类模型 - 扩展更多类型"""
    CATEGORY_CHOICES = [
        # 基础分类
        ('normal', '普通梦境'),
        ('lucid', '清醒梦'),
        ('nightmare', '噩梦'),
        ('recurring', '重复梦'),
        
        # 特殊体验
        ('prophetic', '预知梦'),
        ('healing', '治愈梦'),
        ('spiritual', '灵性梦境'),
        ('creative', '创意梦境'),
        
        # 睡眠相关
        ('hypnagogic', '入睡幻觉'),
        ('hypnopompic', '醒前幻觉'),
        ('sleep_paralysis', '睡眠瘫痪'),
        ('false_awakening', '假醒'),
        
        # 情感类型
        ('anxiety', '焦虑梦'),
        ('joyful', '快乐梦境'),
        ('melancholic', '忧郁梦境'),
        ('adventure', '冒险梦境'),
    ]

    name = models.CharField(
        max_length=50,
        unique=True,
        choices=CATEGORY_CHOICES,
        verbose_name="分类名称"
    )
    description = models.TextField(blank=True, verbose_name="分类描述")
    color_code = models.CharField(max_length=7, default='#6366f1', verbose_name="颜色代码")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "梦境分类"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.get_name_display()


class Tag(models.Model):
    """标签模型 - 支持层级结构"""
    TAG_TYPE_CHOICES = [
        ('emotion', '情感'),
        ('character', '角色'),
        ('location', '地点'),
        ('object', '物体'),
        ('action', '行为'),
        ('symbol', '符号'),
        ('color', '颜色'),
        ('sound', '声音'),
        ('weather', '天气'),
        ('time', '时间'),
        ('custom', '自定义'),
    ]

    name = models.CharField(max_length=50, verbose_name="标签名称")
    tag_type = models.CharField(
        max_length=20,
        choices=TAG_TYPE_CHOICES,
        verbose_name="标签类型"
    )

    created_by = models.ForeignKey(
        User, 
        null=True, 
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="创建者"
    )
    is_public = models.BooleanField(default=False, verbose_name="是否公共标签")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "标签"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=['tag_type']),
            models.Index(fields=['is_public']),
        ]

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_tag_type_display()}:{self.name}"


class Dream(models.Model):
    """梦境记录模型 - 完整重构"""
    LUCIDITY_CHOICES = [
        (0, '完全无意识'),
        (1, '轻微意识'),
        (2, '部分清醒'),
        (3, '较为清醒'),
        (4, '完全清醒'),
        (5, '超清醒状态'),
    ]

    MOOD_CHOICES = [
        ('very_negative', '非常消极'),
        ('negative', '消极'),
        ('neutral', '中性'),
        ('positive', '积极'),
        ('very_positive', '非常积极'),
    ]

    SLEEP_QUALITY_CHOICES = [
        (1, '很差'),
        (2, '较差'),
        (3, '一般'),
        (4, '良好'),
        (5, '很好'),
    ]

    PRIVACY_CHOICES = [
        ('private', '私人'),
        ('public', '公开'),
        ('friends', '好友可见'),
    ]

    # 基础信息
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    title = models.CharField(max_length=200, verbose_name="梦境标题")
    
    # 梦境内容
    content = models.TextField(verbose_name="梦境内容")
    interpretation = models.TextField(blank=True, verbose_name="梦境解析")
    personal_notes = models.TextField(blank=True, verbose_name="个人笔记")
    
    # 梦境特征
    dream_date = models.DateField(verbose_name="梦境日期")
    lucidity_level = models.IntegerField(
        choices=LUCIDITY_CHOICES,
        default=0,
        verbose_name="清醒度等级"
    )
    mood_before_sleep = models.CharField(
        max_length=20,
        choices=MOOD_CHOICES,
        blank=True,
        verbose_name="睡前情绪"
    )
    mood_in_dream = models.CharField(
        max_length=20,
        choices=MOOD_CHOICES,
        blank=True,
        verbose_name="梦中情绪"
    )
    mood_after_waking = models.CharField(
        max_length=20,
        choices=MOOD_CHOICES,
        blank=True,
        verbose_name="醒后情绪"
    )
    
    # 睡眠相关
    sleep_quality = models.IntegerField(
        choices=SLEEP_QUALITY_CHOICES,
        null=True,
        blank=True,
        verbose_name="睡眠质量"
    )
    sleep_duration = models.DurationField(null=True, blank=True, verbose_name="睡眠时长")
    bedtime = models.TimeField(null=True, blank=True, verbose_name="就寝时间")
    wake_time = models.TimeField(null=True, blank=True, verbose_name="醒来时间")
    
    # 梦境特性
    is_recurring = models.BooleanField(default=False, verbose_name="是否重复梦")
    recurring_elements = models.TextField(blank=True, verbose_name="重复元素")
    vividness = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)],
        null=True,
        blank=True,
        verbose_name="清晰度(1-5)"
    )
    
    # 关联关系
    categories = models.ManyToManyField(
        DreamCategory,
        blank=True,
        verbose_name="梦境分类"
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        verbose_name="标签"
    )
    related_dreams = models.ManyToManyField(
        'self',
        blank=True,
        symmetrical=True,
        verbose_name="相关梦境"
    )
    
    # 隐私和分享
    privacy = models.CharField(
        max_length=10,
        choices=PRIVACY_CHOICES,
        default='private',
        verbose_name="隐私设置"
    )
    is_favorite = models.BooleanField(default=False, verbose_name="是否收藏")
    
    # 元数据
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "梦境"
        verbose_name_plural = verbose_name
        ordering = ['-dream_date', '-created_at']
        indexes = [
            models.Index(fields=['user', '-dream_date']),
            models.Index(fields=['privacy', '-created_at']),
            models.Index(fields=['is_favorite', '-created_at']),
            models.Index(fields=['lucidity_level']),
        ]

    def clean(self):
        super().clean()
        # 仅保留关键验证
        if self.dream_date and self.dream_date > timezone.now().date():
            raise ValidationError({'dream_date': '梦境日期不能是未来日期'})

    def __str__(self):
        return f"{self.title} - {self.dream_date}"

    @property
    def word_count(self):
        """计算内容字数"""
        return len(self.content.replace(' ', ''))

    @property
    def reading_time(self):
        """估算阅读时间（分钟）"""
        return max(1, self.word_count // 200)


class DreamJournal(models.Model):
    """梦境日记本模型"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    name = models.CharField(max_length=100, verbose_name="日记本名称")
    description = models.TextField(blank=True, verbose_name="日记本描述")
    color_theme = models.CharField(max_length=7, default='#6366f1', verbose_name="主题颜色")
    is_default = models.BooleanField(default=False, verbose_name="是否默认日记本")
    dreams = models.ManyToManyField(Dream, blank=True, verbose_name="包含的梦境")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "梦境日记本"
        verbose_name_plural = verbose_name
        unique_together = ('user', 'name')

    def __str__(self):
        return f"{self.user.username} - {self.name}"


class SleepPattern(models.Model):
    """睡眠模式记录"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="用户")
    date = models.DateField(verbose_name="日期")
    bedtime = models.TimeField(verbose_name="就寝时间")
    sleep_time = models.TimeField(null=True, blank=True, verbose_name="入睡时间")
    wake_time = models.TimeField(verbose_name="醒来时间")
    sleep_quality = models.IntegerField(
        choices=Dream.SLEEP_QUALITY_CHOICES,
        verbose_name="睡眠质量"
    )
    total_sleep_time = models.DurationField(null=True, blank=True, verbose_name="总睡眠时间")
    awakenings = models.PositiveIntegerField(default=0, verbose_name="夜间醒来次数")
    notes = models.TextField(blank=True, verbose_name="备注")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        verbose_name = "睡眠模式"
        verbose_name_plural = verbose_name
        unique_together = ('user', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.username} - {self.date}"


class UploadedImage(models.Model):
    """图片软删除管理模型"""
    
    STATUS_CHOICES = [
        ('active', '活跃'),
        ('pending_delete', '待删除'),
    ]
    
    # 基础信息
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField(max_length=500, unique=True, verbose_name="图片URL")
    file_key = models.CharField(max_length=500, verbose_name="OSS文件Key")
    
    # 关联信息
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="上传用户")
    dream = models.ForeignKey(
        Dream, 
        null=True, 
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="关联梦境"
    )
    
    # 状态管理
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name="状态"
    )
    marked_for_delete_time = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name="标记删除时间"
    )
    
    # 元数据
    upload_time = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")
    last_referenced_time = models.DateTimeField(auto_now=True, verbose_name="最后引用时间")
    
    class Meta:
        verbose_name = "上传图片"
        verbose_name_plural = verbose_name
        ordering = ['-upload_time']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'marked_for_delete_time']),
            models.Index(fields=['dream', 'status']),
            models.Index(fields=['url']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.url} ({self.status})"
    
    def mark_for_deletion(self):
        """标记图片为待删除状态"""
        if self.status == 'active':
            self.status = 'pending_delete'
            self.marked_for_delete_time = timezone.now()
            self.save(update_fields=['status', 'marked_for_delete_time'])
    
    def restore_active(self):
        """恢复图片为活跃状态"""
        if self.status == 'pending_delete':
            self.status = 'active'
            self.marked_for_delete_time = None
            self.last_referenced_time = timezone.now()
            self.save(update_fields=['status', 'marked_for_delete_time', 'last_referenced_time'])
    
    @property
    def is_pending_delete(self):
        """检查是否处于待删除状态"""
        return self.status == 'pending_delete'
    
    def is_ready_for_deletion(self, hours_threshold=24):
        """检查是否可以被物理删除（默认24小时后）"""
        if not self.is_pending_delete or not self.marked_for_delete_time:
            return False
        
        threshold_time = timezone.now() - timezone.timedelta(hours=hours_threshold)
        return self.marked_for_delete_time <= threshold_time
    
    def get_file_key_from_url(self):
        """从URL中提取文件key"""
        if not self.url:
            return None
        
        # 假设URL格式: https://domain.com/bucket/users/123/dreams/2024/01/01/filename.jpg
        # 提取: users/123/dreams/2024/01/01/filename.jpg
        if '/users/' in self.url:
            return self.url.split('/users/', 1)[1]
        return None
