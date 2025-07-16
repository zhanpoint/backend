from django.core.management.base import BaseCommand
from apps.dream.models import DreamCategory


class Command(BaseCommand):
    help = '创建默认的梦境分类'

    def handle(self, *args, **options):
        # 定义所有分类
        categories = [
            ('normal', '普通梦境', '#6366f1'),
            ('lucid', '清醒梦', '#8b5cf6'),
            ('nightmare', '噩梦', '#ef4444'),
            ('recurring', '重复梦', '#f59e0b'),
            ('prophetic', '预知梦', '#10b981'),
            ('healing', '治愈梦', '#06b6d4'),
            ('spiritual', '灵性梦境', '#ec4899'),
            ('creative', '创意梦境', '#f97316'),
            ('hypnagogic', '入睡幻觉', '#84cc16'),
            ('hypnopompic', '醒前幻觉', '#22d3ee'),
            ('sleep_paralysis', '睡眠瘫痪', '#a855f7'),
            ('false_awakening', '假醒', '#fb7185'),
            ('anxiety', '焦虑梦', '#f87171'),
            ('joyful', '快乐梦境', '#34d399'),
            ('melancholic', '忧郁梦境', '#64748b'),
            ('adventure', '冒险梦境', '#fbbf24'),
        ]

        created_count = 0
        for name, description, color in categories:
            category, created = DreamCategory.objects.get_or_create(
                name=name,
                defaults={
                    'description': description,
                    'color_code': color
                }
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'创建分类: {category.get_name_display()}')
                )

        if created_count == 0:
            self.stdout.write(
                self.style.WARNING('所有分类已存在，无需创建')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'成功创建 {created_count} 个分类')
            ) 