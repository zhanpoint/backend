import random
import string
import json
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.auth.credentials import StsTokenCredential
from aliyunsdkcore.request import CommonRequest
from aliyunsdksts.request.v20150401.AssumeRoleRequest import AssumeRoleRequest
from backend import local_settings
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
        self.access_key_id = local_settings.ALIBABA_CLOUD_ACCESS_RAM_USER_KEY_ID
        self.access_key_secret = local_settings.ALIBABA_CLOUD_ACCESS_RAM_USER_KEY_SECRET
        self.sts_role_arn = local_settings.ALIYUN_STS_ROLE_SMS_ARN
        self.region_id = local_settings.ALIYUN_REGION_ID
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
    def store_code_in_redis(phone, code, expires=60):
        """
        将验证码存储到Redis，设置过期时间
        
        Args:
            phone: 手机号
            code: 验证码
            expires: 过期时间(秒)，默认60秒
            
        Returns:
            bool: 存储是否成功
        """
        cache_key = f"sms_code:{phone}"
        try:
            # 使用Django的cache (Redis后端) 存储验证码
            cache.set(cache_key, code, timeout=expires)
            # 验证存储是否成功
            stored_code = cache.get(cache_key)
            return stored_code == code
        except Exception as e:
            # 记录详细错误
            logging.error(f"存储验证码到Redis出错: {str(e)}")
            # 如果Redis不可用，临时使用内存字典存储
            if not hasattr(SMSService, '_code_cache'):
                SMSService._code_cache = {}
            
            import threading
            import time
            
            # 存储验证码到内存
            SMSService._code_cache[cache_key] = code
            
            # 创建线程在指定时间后清除验证码
            def cleanup():
                time.sleep(expires)
                if cache_key in SMSService._code_cache:
                    del SMSService._code_cache[cache_key]
            
            # 启动清理线程
            threading.Thread(target=cleanup, daemon=True).start()
            
            return True

    def get_sts_token(self):
        """
        获取STS临时凭证, 优先从缓存读取，过期或即将过期时重新获取
        """
        # 尝试从缓存获取凭证
        cached_credentials = cache.get(self.cache_key)

        # 如果缓存中有凭证，检查是否即将过期
        if cached_credentials:
            # 检查凭证是否即将过期
            expiration = parser.parse(cached_credentials['expiration'])  # 将时间字符串转换为可操作的时间对象
            now = datetime.now(expiration.tzinfo)  # 使用相同的时区创建now对象
            # 计算剩余有效期(秒)
            remaining_seconds = (expiration - now).total_seconds()

            # 如果凭证仍然有效且未达到刷新阈值，直接返回缓存的凭证
            if remaining_seconds > self.refresh_threshold:
                return cached_credentials

        """没有凭证或凭证已过期"""
        # 创建ACS客户端
        client = AcsClient(self.access_key_id, self.access_key_secret, self.region_id)

        # 创建AssumeRole请求
        request = AssumeRoleRequest()
        request.set_accept_format('json')

        # 指定角色ARN
        request.set_RoleArn(self.sts_role_arn)
        # 指定临时凭证的会话名称，用于区分不同的临时凭证
        request.set_RoleSessionName('django-sms-session')
        # 设置临时凭证的有效期，单位为秒，最小为900，最大为3600
        request.set_DurationSeconds(3600)  # 建议在Token过期前5-10分钟就开始更新

        # 发送请求，获取响应
        response = client.do_action_with_exception(request)
        response_dict = json.loads(response)

        # 从响应中提取临时凭证
        credentials = response_dict['Credentials']
        sts_credentials = {
            'access_key_id': credentials['AccessKeyId'],
            'access_key_secret': credentials['AccessKeySecret'],
            'security_token': credentials['SecurityToken'],
            'expiration': credentials['Expiration']
        }

        # 计算缓存过期时间(凭证有效期减去刷新阈值)
        expiration = parser.parse(credentials['Expiration'])
        now = datetime.now(expiration.tzinfo)  # 使用相同的时区创建now对象
        cache_ttl = int((expiration - now).total_seconds() - self.refresh_threshold)

        # 将凭证保存到缓存
        cache.set(self.cache_key, sts_credentials, cache_ttl)

        return sts_credentials

    def send_sms(self, phone_numbers, template_code, template_param=None, retry_count=1):
        """
        使用STS临时凭证发送短信，自动处理凭证过期问题

        参数:
        - phone_numbers: 手机号码，多个号码用逗号分隔
        - template_code: 短信模板ID
        - template_param: 短信模板参数，JSON格式的字符串

        返回:
        - 发送结果
        """
        try:
            # 获取STS临时凭证
            sts_credentials = self.get_sts_token()

            # 使用STS临时凭证创建认证对象
            credentials = StsTokenCredential(
                sts_credentials['access_key_id'],
                sts_credentials['access_key_secret'],
                sts_credentials['security_token']
            )

            # 使用临时凭证创建ACS客户端
            client = AcsClient(region_id=self.region_id, credential=credentials)

            # 创建短信发送请求
            request = CommonRequest()
            request.set_accept_format('json')
            request.set_domain('dysmsapi.aliyuncs.com')
            request.set_method('POST')
            request.set_protocol_type('https')
            request.set_version('2017-05-25')
            request.set_action_name('SendSms')

            # 设置短信API的请求参数
            request.add_query_param('PhoneNumbers', phone_numbers)
            request.add_query_param('SignName', local_settings.ALIYUN_SMS_SIGN1)  # 签名id
            request.add_query_param('TemplateCode', template_code)  # 模版id

            if template_param:
                request.add_query_param('TemplateParam', template_param)

            # 发送短信请求
            response = client.do_action_with_exception(request)
            return json.loads(response)

        except Exception as e:
            # 记录详细错误信息
            logging.error(f"发送短信时出错: {str(e)}")
            
            # 检查是否是凭证过期错误
            error_msg = str(e).lower()
            if ('expired' in error_msg or 'invalid' in error_msg) and retry_count > 0:
                # 清除缓存中的过期凭证
                cache.delete(self.cache_key)
                # 递归调用自身重试，减少重试计数
                return self.send_sms(phone_numbers, template_code, template_param, retry_count - 1)
            else:
                # 如果不是凭证过期或已重试达到上限，返回错误信息而不是抛出异常
                return {
                    'Code': 'Error',
                    'Message': f'SMS发送失败: {str(e)}'
                }

    @staticmethod
    def verify_code(phone, code):
        """
        验证短信验证码是否正确
        
        Args:
            phone: 手机号
            code: 用户提交的验证码
            
        Returns:
            bool: 验证是否成功
        """
        # 构建缓存键
        cache_key = f"sms_code:{phone}"
        
        try:
            # 尝试从Redis获取验证码
            stored_code = cache.get(cache_key)
            
            # 如果Redis中没有，尝试从内存缓存获取
            if stored_code is None and hasattr(SMSService, '_code_cache'):
                stored_code = SMSService._code_cache.get(cache_key)
            
            # 验证码比较
            if stored_code is not None:
                # 验证成功后删除验证码，防止重复使用
                if stored_code == code:
                    cache.delete(cache_key)
                    if hasattr(SMSService, '_code_cache') and cache_key in SMSService._code_cache:
                        del SMSService._code_cache[cache_key]
                    return True
            
            # 验证码不存在或不匹配
            return False
            
        except Exception as e:
            logging.error(f"验证码验证过程中出错: {str(e)}")
            return False
