# Generated by Django 4.2.20 on 2025-03-19 04:34

from django.conf import settings
import django.contrib.auth.validators
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('dream', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Dream',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=30, validators=[django.core.validators.MinLengthValidator(5)], verbose_name='标题')),
                ('content', models.TextField(validators=[django.core.validators.MinLengthValidator(30), django.core.validators.MaxLengthValidator(2000)], verbose_name='内容')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
            ],
            options={
                'verbose_name': '梦境',
                'verbose_name_plural': '梦境',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='DreamCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(choices=[('normal', '普通梦境'), ('memorable', '难忘梦境'), ('indicate', '预示梦境'), ('archetypal', '原型梦境'), ('lucid', '清醒梦'), ('nightmare', '噩梦'), ('repeating', '重复梦'), ('sleep_paralysis', '睡眠瘫痪')], max_length=50, unique=True, verbose_name='分类名称')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
            ],
            options={
                'verbose_name': '梦境分类',
                'verbose_name_plural': '梦境分类',
            },
        ),
        migrations.AlterField(
            model_name='user',
            name='phone_number',
            field=models.CharField(max_length=11, unique=True, validators=[django.core.validators.RegexValidator('^1[3-9]\\d{9}$', '请输入正确的手机号')], verbose_name='手机号'),
        ),
        migrations.AlterField(
            model_name='user',
            name='username',
            field=models.CharField(error_messages={'unique': 'A user with that username already exists.'}, help_text='Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.', max_length=150, unique=True, validators=[django.contrib.auth.validators.UnicodeUsernameValidator()], verbose_name='username'),
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=20, verbose_name='标签名称')),
                ('tag_type', models.CharField(choices=[('theme', '主题'), ('character', '角色'), ('location', '地点')], max_length=20, verbose_name='标签类型')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='创建者')),
            ],
            options={
                'verbose_name': '标签',
                'verbose_name_plural': '标签',
                'unique_together': {('name', 'tag_type', 'created_by')},
            },
        ),
        migrations.CreateModel(
            name='DreamImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image_url', models.URLField(max_length=255, verbose_name='图片URL')),
                ('position', models.PositiveIntegerField(default=0, verbose_name='图片位置')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('dream', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='dream.dream', verbose_name='所属梦境')),
            ],
            options={
                'verbose_name': '梦境图片',
                'verbose_name_plural': '梦境图片',
                'ordering': ['position'],
            },
        ),
        migrations.AddField(
            model_name='dream',
            name='categories',
            field=models.ManyToManyField(to='dream.dreamcategory', verbose_name='梦境分类'),
        ),
        migrations.AddField(
            model_name='dream',
            name='character_tags',
            field=models.ManyToManyField(related_name='dream_characters', to='dream.tag', verbose_name='角色标签'),
        ),
        migrations.AddField(
            model_name='dream',
            name='location_tags',
            field=models.ManyToManyField(related_name='dream_locations', to='dream.tag', verbose_name='地点标签'),
        ),
        migrations.AddField(
            model_name='dream',
            name='theme_tags',
            field=models.ManyToManyField(related_name='dream_themes', to='dream.tag', verbose_name='主题标签'),
        ),
        migrations.AddField(
            model_name='dream',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='用户'),
        ),
    ]
