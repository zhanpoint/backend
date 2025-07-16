"""
图片软删除管理服务
"""

import re
import logging
from typing import List, Set, Dict, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from django.utils import timezone
from django.db import transaction
from django.conf import settings

from ..models import UploadedImage, Dream, User
from .oss import OSS

logger = logging.getLogger(__name__)


class ImageLifecycleManager:
    """图片生命周期管理器 - 简化版"""
    
    def __init__(self, user: User):
        self.user = user
        self.oss_client = OSS(user_id=user.id)
    
    def extract_image_urls_from_html(self, html_content: str) -> Set[str]:
        """从HTML内容中提取所有图片URL"""
        if not html_content:
            return set()
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            img_tags = soup.find_all('img')
            
            urls = set()
            for img in img_tags:
                src = img.get('src')
                if src and self._is_valid_image_url(src):
                    urls.add(src.strip())
            
            return urls
            
        except Exception as e:
            logger.error(f"解析HTML内容失败: {e}")
            return set()
    
    def _is_valid_image_url(self, url: str) -> bool:
        """检查是否为有效的图片URL"""
        if not url or not url.strip():
            return False
        
        # 检查是否为本项目的图片URL
        return any(domain in url for domain in [
            'dream-log', 'oss-cn-', 'aliyuncs.com'
        ])
    
    def calculate_image_differences(self, old_content: str, new_content: str) -> tuple:
        """计算新旧内容的图片差异"""
        old_urls = self.extract_image_urls_from_html(old_content or '')
        new_urls = self.extract_image_urls_from_html(new_content or '')
        
        deleted_urls = old_urls - new_urls  # 在旧内容中但不在新内容中
        added_urls = new_urls - old_urls    # 在新内容中但不在旧内容中
        kept_urls = old_urls & new_urls     # 在新旧内容中都存在
        
        return deleted_urls, added_urls, kept_urls
    
    @transaction.atomic
    def process_dream_image_changes(self, dream: Dream, old_content: str = None, new_content: str = None) -> Dict[str, int]:
        """处理梦境图片变化，执行软删除逻辑"""
        if new_content is None:
            new_content = dream.content
        
        stats = {
            'marked_for_delete': 0,
            'restored_active': 0,
            'newly_registered': 0,
        }
        
        if old_content is not None:
            # 编辑模式：比较新旧内容
            deleted_urls, added_urls, kept_urls = self.calculate_image_differences(old_content, new_content)
            
            # 标记删除的图片
            for url in deleted_urls:
                if self._mark_image_for_deletion(url):
                    stats['marked_for_delete'] += 1
            
            # 恢复重新使用的图片
            for url in kept_urls:
                if self._restore_image_if_needed(url, dream):
                    stats['restored_active'] += 1
            
            # 注册新增的图片
            for url in added_urls:
                if self._register_new_image(url, dream):
                    stats['newly_registered'] += 1
        else:
            # 创建模式：注册所有图片
            image_urls = self.extract_image_urls_from_html(new_content)
            for url in image_urls:
                if self._register_new_image(url, dream):
                    stats['newly_registered'] += 1
        
        logger.info(f"梦境 {dream.id} 图片处理完成: {stats}")
        return stats
    
    def _mark_image_for_deletion(self, url: str) -> bool:
        """标记图片为待删除状态"""
        try:
            image = UploadedImage.objects.get(url=url, user=self.user, status='active')
            image.mark_for_deletion()
            logger.info(f"图片已标记为待删除: {url}")
            return True
        except UploadedImage.DoesNotExist:
            logger.warning(f"尝试删除不存在的图片: {url}")
            return False
        except Exception as e:
            logger.error(f"标记图片删除失败: {url}, 错误: {e}")
            return False
    
    def _restore_image_if_needed(self, url: str, dream: Dream) -> bool:
        """如果图片处于待删除状态，则恢复为活跃状态"""
        try:
            image = UploadedImage.objects.get(url=url, user=self.user, status='pending_delete')
            image.restore_active()
            # 更新关联的梦境
            if image.dream != dream:
                image.dream = dream
                image.save(update_fields=['dream'])
            logger.info(f"图片已恢复为活跃状态: {url}")
            return True
        except UploadedImage.DoesNotExist:
            # 图片可能已经是活跃状态，更新关联关系
            try:
                image = UploadedImage.objects.get(url=url, user=self.user, status='active')
                if image.dream != dream:
                    image.dream = dream
                    image.last_referenced_time = timezone.now()
                    image.save(update_fields=['dream', 'last_referenced_time'])
                return False
            except UploadedImage.DoesNotExist:
                logger.warning(f"图片不存在于数据库中: {url}")
                return False
        except Exception as e:
            logger.error(f"恢复图片失败: {url}, 错误: {e}")
            return False
    
    def _register_new_image(self, url: str, dream: Dream) -> bool:
        """注册新的图片到数据库"""
        try:
            # 检查图片是否已存在
            existing_image = UploadedImage.objects.filter(url=url, user=self.user).first()
            
            if existing_image:
                # 如果图片已存在，更新关联和状态
                if existing_image.status == 'pending_delete':
                    existing_image.restore_active()
                
                if existing_image.dream != dream:
                    existing_image.dream = dream
                    existing_image.last_referenced_time = timezone.now()
                    existing_image.save(update_fields=['dream', 'last_referenced_time'])
                
                return False
            
            # 从URL提取文件信息
            file_key = self._extract_file_key_from_url(url)
            
            # 创建新的图片记录
            UploadedImage.objects.create(
                url=url,
                file_key=file_key or '',
                user=self.user,
                dream=dream,
                status='active',
                last_referenced_time=timezone.now()
            )
            
            logger.info(f"新图片已注册: {url}")
            return True
            
        except Exception as e:
            logger.error(f"注册新图片失败: {url}, 错误: {e}")
            return False
    
    def _extract_file_key_from_url(self, url: str) -> Optional[str]:
        """从URL中提取OSS文件key"""
        try:
            if '/users/' in url:
                return url.split('/users/', 1)[1]
            return None
        except Exception:
            return None
    
    def cleanup_user_images(self, hours_threshold: int = 24) -> Dict[str, int]:
        """清理用户的过期待删除图片"""
        threshold_time = timezone.now() - timezone.timedelta(hours=hours_threshold)
        
        pending_images = UploadedImage.objects.filter(
            user=self.user,
            status='pending_delete',
            marked_for_delete_time__lte=threshold_time
        ).order_by('marked_for_delete_time')
        
        stats = {
            'total_pending': len(pending_images),
            'success': 0,
            'failed': 0
        }
        
        for image in pending_images:
            try:
                # 尝试从OSS删除
                oss_success = True
                if image.file_key:
                    oss_success = self.oss_client.delete_file(image.file_key)
                
                if oss_success:
                    # 从数据库删除记录
                    image.delete()
                    stats['success'] += 1
                    logger.info(f"图片清理成功: {image.url}")
                else:
                    stats['failed'] += 1
                    logger.error(f"OSS删除失败: {image.url}")
                    
            except Exception as e:
                stats['failed'] += 1
                logger.error(f"图片清理异常: {image.url}, 错误: {e}")
        
        logger.info(f"用户 {self.user.id} 图片清理完成: {stats}")
        return stats


class GlobalImageCleanupManager:
    """全局图片清理管理器"""
    
    @staticmethod
    def cleanup_all_expired_images(hours_threshold: int = 24) -> Dict[str, int]:
        """清理所有用户的过期图片"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        threshold_time = timezone.now() - timezone.timedelta(hours=hours_threshold)
        
        # 获取有待删除图片的用户
        users_with_pending_images = User.objects.filter(
            uploadedimage__status='pending_delete',
            uploadedimage__marked_for_delete_time__lte=threshold_time
        ).distinct()
        
        total_stats = {
            'processed_users': 0,
            'total_pending': 0,
            'success': 0,
            'failed': 0
        }
        
        for user in users_with_pending_images:
            try:
                manager = ImageLifecycleManager(user)
                user_stats = manager.cleanup_user_images(hours_threshold)
                
                total_stats['processed_users'] += 1
                total_stats['total_pending'] += user_stats['total_pending']
                total_stats['success'] += user_stats['success']
                total_stats['failed'] += user_stats['failed']
                    
            except Exception as e:
                logger.error(f"用户 {user.id} 图片清理失败: {e}")
        
        logger.info(f"全局图片清理完成: {total_stats}")
        return total_stats 