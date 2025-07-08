import random
import string
import json
import hashlib
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.auth.credentials import StsTokenCredential
from aliyunsdkcore.request import CommonRequest
from aliyunsdksts.request.v20150401.AssumeRoleRequest import AssumeRoleRequest
from config.env_config import ALIYUN_CONFIG
from django.core.cache import cache
from datetime import datetime
from dateutil import parser
import logging


class SMSService:
    """
    短信服务工具类
    """

    def __init__(self):
        # 从Django配置中读取阿里云访问凭证
        self.access_key_id = ALIYUN_CONFIG.get('access_key_id')
        self.access_key_secret = ALIYUN_CONFIG.get('access_key_secret')
        self.sts_role_arn = ALIYUN_CONFIG.get('sts_role_sms_arn')
        self.region_id = ALIYUN_CONFIG.get('region_id', 'cn-wuhan-lr')
        # 缓存键名
        self.cache_key = 'aliyun_sts_credentials'  # 应该根据session ID来确定缓存键
        # 设置提前刷新阈值(秒)，凭证过期前5分钟就刷新
        self.refresh_threshold = 300

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
        # encode将字符串 code 转换为字节序列（bytes），因为加密算法不能直接处理字符串，必须是字节；通常默认使用 UTF-8 编码。
        # hexdigest将哈希对象的结果转换成十六进制字符串。    
        return hashlib.sha256(code.encode()).hexdigest()

    @staticmethod
    def store_code_in_redis(phone, code, expires=300):
        """
        将验证码存储到Redis，设置过期时间
        
        Args:
            phone: 手机号
            code: 验证码
            expires: 过期时间(秒)，默认300秒
            
        Returns:
            bool: 存储是否成功
        """
        cache_key = f"sms_code:{phone}"
        try:
            # 对验证码进行哈希处理后存储
            hashed_code = SMSService._hash_code(code)
            cache.set(cache_key, hashed_code, timeout=expires)
            stored_code = cache.get(cache_key)
            logging.info(f"验证码已存储到Redis，手机号: {phone}，过期时间: {expires}秒")
            return stored_code == hashed_code
        except Exception as e:
            logging.error(f"存储验证码到Redis出错: {str(e)}")
            if not hasattr(SMSService, '_code_cache'):
                # 如果_code_cache不存在，则创建一个空字典，充当“临时 Redis”，仅在 Redis 异常时使用
                SMSService._code_cache = {}

            import threading
            import time

            # 将验证码的哈希值保存到备用内存缓存 _code_cache 中
            SMSService._code_cache[cache_key] = SMSService._hash_code(code)

            # 定义一个清理函数：在指定时间（验证码的过期时间）后，删除内存中的验证码缓存。
            def cleanup():
                time.sleep(expires)
                if cache_key in SMSService._code_cache:
                    del SMSService._code_cache[cache_key]

            # 启动一个后台线程，异步执行 cleanup() 函数，确保验证码会在过期时间后自动清除，避免内存泄漏。
            threading.Thread(target=cleanup, daemon=True).start()

            return True

    def get_sts_token(self):
        """
        获取STS临时凭证, 优先从缓存读取，过期或即将过期时重新获取
        """
        cached_credentials = cache.get(self.cache_key)

        if cached_credentials:
            expiration = parser.parse(cached_credentials['expiration'])
            now = datetime.now(expiration.tzinfo)
            remaining_seconds = (expiration - now).total_seconds()

            if remaining_seconds > self.refresh_threshold:
                return cached_credentials

        client = AcsClient(self.access_key_id, self.access_key_secret, self.region_id)

        request = AssumeRoleRequest()
        request.set_accept_format('json')
        request.set_RoleArn(self.sts_role_arn)
        request.set_RoleSessionName('django-sms-session')
        request.set_DurationSeconds(3600)

        response = client.do_action_with_exception(request)
        response_dict = json.loads(response)

        credentials = response_dict['Credentials']
        sts_credentials = {
            'access_key_id': credentials['AccessKeyId'],
            'access_key_secret': credentials['AccessKeySecret'],
            'security_token': credentials['SecurityToken'],
            'expiration': credentials['Expiration']
        }

        expiration = parser.parse(credentials['Expiration'])
        now = datetime.now(expiration.tzinfo)
        cache_ttl = int((expiration - now).total_seconds() - self.refresh_threshold)
        cache.set(self.cache_key, sts_credentials, cache_ttl)

        return sts_credentials

    def send_sms(self, phone_numbers, template_code, template_param=None, retry_count=1):
        """
        使用STS临时凭证发送短信
        """
        try:
            sts_credentials = self.get_sts_token()

            credentials = StsTokenCredential(
                sts_credentials['access_key_id'],
                sts_credentials['access_key_secret'],
                sts_credentials['security_token']
            )

            client = AcsClient(region_id=self.region_id, credential=credentials)

            request = CommonRequest()
            request.set_accept_format('json')
            request.set_domain('dysmsapi.aliyuncs.com')
            request.set_method('POST')
            request.set_protocol_type('https')
            request.set_version('2017-05-25')
            request.set_action_name('SendSms')

            request.add_query_param('PhoneNumbers', phone_numbers)
            request.add_query_param('SignName', ALIYUN_CONFIG.get('sms_sign_name'))
            request.add_query_param('TemplateCode', template_code)

            if template_param:
                request.add_query_param('TemplateParam', template_param)

            response = client.do_action_with_exception(request)
            return json.loads(response)

        except Exception as e:
            logging.error(f"发送短信时出错: {str(e)}")

            error_msg = str(e).lower()
            if ('expired' in error_msg or 'invalid' in error_msg) and retry_count > 0:
                cache.delete(self.cache_key)
                return self.send_sms(phone_numbers, template_code, template_param, retry_count - 1)
            else:
                return {
                    'Code': 'Error',
                    'Message': f'SMS发送失败: {str(e)}'
                }

    @staticmethod
    def send_verification_code(phone, scene):
        """
        生成、存储并发送短信验证码
        """
        verification_code = SMSService.generate_verification_code()
        
        if not SMSService.store_code_in_redis(phone, verification_code, expires=300):
            logging.error(f"无法将短信验证码存储到Redis，手机号: {phone}")
            return False

        template_map = {
            'register': ALIYUN_CONFIG.get('sms_template_code_register'),
            'login': ALIYUN_CONFIG.get('sms_template_code_login'),
            'reset_password': ALIYUN_CONFIG.get('sms_template_code_resetpassword')
        }
        
        template_code = template_map.get(scene, template_map['register'])

        try:
            sms_service = SMSService()
            template_param = json.dumps({'code': verification_code})

            sent = sms_service.send_sms(
                phone_numbers=phone,
                template_code=template_code,
                template_param=template_param
            )

            if sent.get('Code') != 'OK':
                logging.error(f"短信发送失败，错误: {sent}")
                return False
            
            return True

        except Exception as e:
            logging.exception(f"发送短信验证码过程中发生异常: {str(e)}")
            return False

    @staticmethod
    def verify_code(phone, code):
        """
        验证短信验证码是否正确
        """
        cache_key = f"sms_code:{phone}"
        attempts_key = f"sms_verify_attempts:{phone}"

        try:
            # 检查验证尝试次数
            attempts = cache.get(attempts_key, 0)
            if attempts >= 5:
                logging.warning(f"短信验证码验证尝试次数过多，手机号: {phone}")
                # 删除验证码，防止继续尝试
                cache.delete(cache_key)
                if hasattr(SMSService, '_code_cache') and cache_key in SMSService._code_cache:
                    del SMSService._code_cache[cache_key]
                return False
            
            stored_code = cache.get(cache_key)

            if stored_code is None and hasattr(SMSService, '_code_cache'):
                stored_code = SMSService._code_cache.get(cache_key)

            if stored_code is not None:
                # 对用户输入的验证码进行哈希后比较
                hashed_input = SMSService._hash_code(code)
                if stored_code == hashed_input:
                    cache.delete(cache_key)
                    cache.delete(attempts_key)  # 验证成功，删除尝试次数
                    if hasattr(SMSService, '_code_cache') and cache_key in SMSService._code_cache:
                        del SMSService._code_cache[cache_key]
                    return True
                else:
                    # 验证失败，增加尝试次数
                    cache.set(attempts_key, attempts + 1, timeout=300)  # 5分钟内的尝试次数

            return False

        except Exception as e:
            logging.error(f"验证码验证过程中出错: {str(e)}")
            return False
