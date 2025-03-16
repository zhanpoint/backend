from django.core.management.base import BaseCommand
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
import logging
import os
from django.conf import settings
from datetime import timedelta

# 获取日志记录器
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    清理过期的黑名单令牌命令
    
    用法:
    python manage.py clean_expired_tokens
    
    可选参数:
    --days: 清理多少天前的令牌 (默认: 3)
    --dry-run: 仅显示将被删除的令牌数量，但不实际删除
    --batch-size: 批处理大小，每批处理的令牌数量 (默认: 1000)
    """
    help = '清理过期的JWT黑名单令牌'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=3,
            help='清理多少天前的令牌'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='仅显示将被删除的令牌数量，但不实际删除'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=1000,
            help='批处理大小，每批处理的令牌数量'
        )
        parser.add_argument(
            '--log-file',
            type=str,
            help='自定义日志文件路径'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        log_file = options.get('log_file')
        
        # 设置自定义日志文件
        if log_file:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        
        # 记录开始执行
        start_time = timezone.now()
        logger.info(f"开始清理过期JWT令牌 (过期天数: {days}天)")
        self.stdout.write(f"开始清理过期JWT令牌 (过期天数: {days}天)")
        
        # 计算清理日期
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # 统计过期令牌
        expired_count = OutstandingToken.objects.filter(expires_at__lt=cutoff_date).count()
        blacklisted_count = BlacklistedToken.objects.filter(token__expires_at__lt=cutoff_date).count()

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f'将删除的过期令牌: {expired_count} (其中黑名单令牌: {blacklisted_count})'
                )
            )
            logger.info(f'[干运行] 将删除的过期令牌: {expired_count} (其中黑名单令牌: {blacklisted_count})')
            return

        # 使用批处理方式删除，避免一次性加载太多数据
        total_deleted = 0
        total_blacklisted_deleted = 0
        
        # 先删除黑名单中的记录
        self.stdout.write("正在清理黑名单令牌...")
        
        # 每次处理一批黑名单令牌
        while True:
            blacklisted_batch = BlacklistedToken.objects.filter(
                token__expires_at__lt=cutoff_date
            )[:batch_size]
            
            if not blacklisted_batch.exists():
                break
                
            batch_count = blacklisted_batch.count()
            blacklisted_batch.delete()
            total_blacklisted_deleted += batch_count
            self.stdout.write(f"已删除 {total_blacklisted_deleted}/{blacklisted_count} 个黑名单令牌")
        
        # 然后删除过期的令牌
        self.stdout.write("正在清理过期令牌...")
        
        # 每次处理一批过期令牌
        while True:
            expired_batch = OutstandingToken.objects.filter(
                expires_at__lt=cutoff_date
            )[:batch_size]
            
            if not expired_batch.exists():
                break
                
            batch_count = expired_batch.count()
            expired_batch.delete()
            total_deleted += batch_count
            self.stdout.write(f"已删除 {total_deleted}/{expired_count} 个过期令牌")
        
        # 计算执行时间
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()
        
        success_message = (
            f'成功删除 {total_deleted} 个过期令牌 '
            f'(其中黑名单令牌: {total_blacklisted_deleted}), '
            f'用时: {duration:.2f}秒'
        )
        
        self.stdout.write(self.style.SUCCESS(success_message))
        logger.info(success_message)
        
        # 尝试写入日志文件
        try:
            log_dir = os.path.join(settings.BASE_DIR, 'logs')
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            with open(os.path.join(log_dir, 'token_cleanup.log'), 'a') as f:
                f.write(f'{timezone.now().strftime("%Y-%m-%d %H:%M:%S")} - {success_message}\n')
        except Exception as e:
            logger.error(f"写入日志文件失败: {str(e)}")
            self.stderr.write(f"写入日志文件失败: {str(e)}") 