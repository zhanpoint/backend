import random
import string
import logging
import hashlib
from django.core.mail import send_mail
from django.core.cache import cache
from django.conf import settings
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


class EmailService:
    """
    邮件服务工具类
    - 生成、存储、发送和验证邮箱验证码
    - 提供邮件发送频率限制
    """

    def __init__(self):
        # 缓存键名前缀
        self.cache_prefix = 'email_code:'
        
    @staticmethod
    def generate_verification_code(length=6):
        """
        生成指定长度的数字验证码
        """
        return ''.join(random.choices(string.digits, k=length))

    @staticmethod
    def _hash_code(code):
        """
        对验证码进行哈希处理
        """
        return hashlib.sha256(code.encode()).hexdigest()

    @staticmethod
    def store_code_in_redis(email, code, expires=300):
        """
        将验证码存储到Redis，设置过期时间
        
        Args:
            email: 邮箱地址
            code: 验证码
            expires: 过期时间(秒)，默认300秒(5分钟)
            
        Returns:
            bool: 存储是否成功
        """
        cache_key = f"email_code:{email}"
        try:
            # 对验证码进行哈希处理后存储
            hashed_code = EmailService._hash_code(code)
            cache.set(cache_key, hashed_code, timeout=expires)
            # 验证存储是否成功
            stored_code = cache.get(cache_key)
            logging.info(f"邮箱验证码已存储到Redis，邮箱: {email}，过期时间: {expires}秒")
            return stored_code == hashed_code
        except Exception as e:
            # 记录详细错误
            logging.error(f"存储验证码到Redis出错: {str(e)}")
            # 如果Redis不可用，临时使用内存字典存储
            if not hasattr(EmailService, '_code_cache'):
                EmailService._code_cache = {}

            import threading
            import time

            # 备用存储也使用哈希值
            EmailService._code_cache[cache_key] = EmailService._hash_code(code)

            # 创建线程在指定时间后清除验证码
            def cleanup():
                time.sleep(expires)
                if cache_key in EmailService._code_cache:
                    del EmailService._code_cache[cache_key]

            # 启动清理线程
            threading.Thread(target=cleanup, daemon=True).start()

            return True

    def check_rate_limit(self, email, limit_seconds=60):
        """
        检查发送频率限制
        
        Args:
            email: 邮箱地址
            limit_seconds: 限制时间间隔(秒)，默认60秒
            
        Returns:
            tuple: (是否允许发送, 剩余等待时间)
        """
        rate_limit_key = f"email_rate_limit:{email}"
        
        # 获取剩余的TTL
        ttl = cache.ttl(rate_limit_key)
        
        if ttl > 0:
            # 还在限制期内
            return False, ttl
            
        # 设置新的频率限制
        cache.set(rate_limit_key, True, timeout=limit_seconds)
        return True, 0

    @staticmethod
    def _send_email(email, code, scene):
        """
        内部方法：渲染并发送邮件
        """
        # 1. 场景与模板映射
        template_map = {
            'register': {
                'subject': '欢迎注册DreamLog - 您的验证码',
                'html': 'email/user_register.html',
                'text': 'email/user_register.txt',
            },
            'login': {
                'subject': 'DreamLog 登录验证',
                'html': 'email/user_login.html',
                'text': 'email/user_login.txt',
            },
            'reset_password': {
                'subject': 'DreamLog 密码重置',
                'html': 'email/user_reset_password.html',
                'text': 'email/user_reset_password.txt',
            }
        }
        
        # 2. 获取当前场景的配置
        config = template_map.get(scene)
        if not config:
            logger.error(f"无效的邮件场景: {scene}")
            return False

        # 3. 准备邮件内容
        context = {'code': code}
        subject = config['subject']
        html_message = render_to_string(config['html'], context)
        plain_message = render_to_string(config['text'], context)
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [email]

        # 4. 发送邮件
        try:
            send_mail(
                subject,
                plain_message,
                from_email,
                recipient_list,
                html_message=html_message
            )
            logger.info(f"邮件成功发送至 {email}, 场景: {scene}")
            return True
        except Exception as e:
            logger.error(f"发送邮件至 {email} 失败: {str(e)}")
            return False

    @staticmethod
    def send_verification_code(email, scene):
        """
        生成、存储并通过异步任务发送邮件验证码

        Args:
            email (str): 目标邮箱地址
            scene (str): 使用场景 ('register', 'login', 'reset_password')

        Returns:
            bool: 任务是否成功提交
        """
        try:
            # 1. 生成验证码
            code = EmailService.generate_verification_code()
            logger.info(f"为邮箱 {email} 生成验证码: {code}, 场景: {scene}")

            # 2. 存储验证码到Redis
            if not EmailService.store_code_in_redis(email, code, expires=300):
                logger.error(f"存储邮箱验证码到Redis失败: {email}")
                return False

            # 3. 异步发送邮件 - 使用延迟导入避免循环依赖，避免模块加载时的死锁
            from dream.tasks.email_tasks import send_verification_email_task
            send_verification_email_task.delay(email, code, scene)
            logger.info(f"成功提交邮箱验证码发送任务: {email}, 场景: {scene}")

            return True

        except Exception as e:
            logger.error(f"发送邮箱验证码任务失败: {str(e)}")
            return False

    @staticmethod
    def verify_code(email, code):
        """
        验证邮箱验证码是否正确
        
        Args:
            email: 邮箱地址
            code: 用户提交的验证码
            
        Returns:
            bool: 验证是否成功
        """
        # 构建缓存键
        cache_key = f"email_code:{email}"
        attempts_key = f"email_verify_attempts:{email}"

        try:
            # 检查验证尝试次数
            attempts = cache.get(attempts_key, 0)
            if attempts >= 5:
                logging.warning(f"邮箱验证码验证尝试次数过多，邮箱: {email}")
                # 删除验证码，防止继续尝试
                cache.delete(cache_key)
                if hasattr(EmailService, '_code_cache') and cache_key in EmailService._code_cache:
                    del EmailService._code_cache[cache_key]
                return False
            
            # 尝试从Redis获取验证码
            stored_code = cache.get(cache_key)

            # 如果Redis中没有，尝试从内存缓存获取
            if stored_code is None and hasattr(EmailService, '_code_cache'):
                stored_code = EmailService._code_cache.get(cache_key)

            # 验证码比较
            if stored_code is not None:
                # 对用户输入的验证码进行哈希后比较
                hashed_input = EmailService._hash_code(code)
                if stored_code == hashed_input:
                    # 验证成功后删除验证码，防止重复使用
                    cache.delete(cache_key)
                    cache.delete(attempts_key)  # 验证成功，删除尝试次数
                    if hasattr(EmailService, '_code_cache') and cache_key in EmailService._code_cache:
                        del EmailService._code_cache[cache_key]
                    logging.info(f"邮箱验证码验证成功: {email}")
                    return True
                else:
                    # 验证失败，增加尝试次数
                    cache.set(attempts_key, attempts + 1, timeout=300)  # 5分钟内的尝试次数

            # 验证码不存在或不匹配
            logging.warning(f"邮箱验证码验证失败: {email}")
            return False

        except Exception as e:
            logger.error(f"验证邮箱验证码时发生错误: {str(e)}")
            return False 