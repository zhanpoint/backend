import oss2
from aliyunsdkcore import client
from aliyunsdksts.request.v20150401 import AssumeRoleRequest
import json
import time
import uuid
from backend import local_settings
import re
import logging

logger = logging.getLogger(__name__)

class OSS:
    def __init__(self, username=None):
        """初始化OSS配置"""
        try:
            if not username:
                raise ValueError("用户名不能为空")
                
            # 强制类型转换和清理
            if isinstance(username, (tuple, list)):
                username = username[0] if len(username) > 0 else 'unknown'
            self.username = str(username).strip()
            
            self.access_key_id = local_settings.ALIBABA_CLOUD_ACCESS_RAM_USER_KEY_ID
            self.access_key_secret = local_settings.ALIBABA_CLOUD_ACCESS_RAM_USER_KEY_SECRET
            self.role_arn = local_settings.ALIYUN_STS_ROLE_OSS_ARN
            
            # 处理endpoint配置
            self.endpoint = str(local_settings.ALIYUN_OSS_ENDPOINT).strip()  # 强制转换为字符串
            if not self.endpoint.startswith(('http://', 'https://')):
                self.endpoint = f'https://{self.endpoint}'
                
            self.sts_endpoint = 'sts.aliyuncs.com'
            self.bucket_name = self._generate_bucket_name(self.username)
            
            # 创建服务连接
            self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            self.service = oss2.Service(self.auth, self.endpoint)  # 使用处理后的endpoint
            
            logger.debug(f"OSS配置初始化完成 | endpoint: {self.endpoint} | bucket: {self.bucket_name}")
            
        except Exception as e:
            logger.error(f"OSS初始化失败: {str(e)}")
            raise

    def _generate_bucket_name(self, username):
        """生成规范的bucket名称"""
        try:
            base_name = "dreamlog"
            
            # 深度类型检查和处理
            if isinstance(username, (list, tuple)):
                username = username[0] if len(username) > 0 else 'unknown'
            username = str(username or 'unknown').strip().lower()
            
            # 添加调试日志
            logger.debug(f"生成bucket名称，原始username: {username} 类型: {type(username)}")
            
            # 清理非法字符（保留连字符）
            username = re.sub(r'[^a-z0-9-]', '', username)
            
            # 生成基础名称
            bucket_name = f"{base_name}-{username}"
            
            # 长度处理（确保符合OSS命名规范）
            bucket_name = bucket_name[:63].ljust(3, '0')  # 截断至63字符且至少3字符
            
            logger.debug(f"最终生成的bucket名称: {bucket_name}")
            return bucket_name
            
        except Exception as e:
            logger.error(f"生成bucket名称时发生错误: {str(e)} | 原始username: {username} | 类型: {type(username)}")
            return f"dreamlog-default-{uuid.uuid4().hex[:8]}"

    def _get_sts_token(self):
        """获取STS临时凭证"""
        try:
            clt = client.AcsClient(
                self.access_key_id,
                self.access_key_secret,
                'cn-wuhan-lr'
            )
            
            request = AssumeRoleRequest.AssumeRoleRequest()
            request.set_accept_format('json')
            request.set_RoleArn(self.role_arn)
            request.set_RoleSessionName(f'dream_upload_{int(time.time())}')
            request.set_DurationSeconds(3600)
            
            response = clt.do_action_with_exception(request)
            credentials = json.loads(response).get('Credentials')
            
            return {
                'access_key_id': credentials.get('AccessKeyId'),
                'access_key_secret': credentials.get('AccessKeySecret'),
                'security_token': credentials.get('SecurityToken')
            }
        except Exception as e:
            logger.error(f"获取STS Token失败: {str(e)}")
            raise

    def ensure_bucket_exists(self):
        """确保bucket存在，不存在则创建"""
        try:
            logger.debug(f"创建Bucket实例参数检查: "
                        f"auth_type={type(self.auth)}, "
                        f"endpoint_type={type(self.endpoint)}, "
                        f"bucket_name_type={type(self.bucket_name)}")
            
            # 显式转换为字符串
            endpoint = str(self.endpoint)
            bucket_name = str(self.bucket_name)
            
            bucket = oss2.Bucket(self.auth, endpoint, bucket_name)
            
            try:
                bucket.get_bucket_info()
                logger.info(f"Bucket {bucket_name} 已存在")
                return True
            except oss2.exceptions.NoSuchBucket:
                logger.info(f"正在创建新Bucket: {bucket_name}")
                bucket.create_bucket(
                    oss2.models.BUCKET_ACL_PRIVATE,
                    oss2.models.BucketCreateConfig(oss2.BUCKET_STORAGE_CLASS_STANDARD)
                )
                return True
                
        except Exception as e:
            logger.error(f"确保bucket存在时发生错误: {str(e)}\n"
                        f"详细参数: auth={self.auth}, "
                        f"endpoint={self.endpoint}, "
                        f"bucket_name={self.bucket_name}")
            return False

    def upload_file(self, file_obj):
        """上传文件到OSS"""
        try:
            # 获取STS凭证
            sts_token = self._get_sts_token()
            
            # 创建Bucket实例 - 使用StsAuth
            auth = oss2.StsAuth(
                sts_token['access_key_id'],
                sts_token['access_key_secret'],
                sts_token['security_token']

            )
            bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)
            
            # 生成文件路径
            file_ext = file_obj.name.split('.')[-1]
            file_path = f'dreams/{time.strftime("%Y%m%d")}/{uuid.uuid4().hex}.{file_ext}'
            
            # 上传文件
            result = bucket.put_object(file_path, file_obj)
            
            if result.status == 200:
                return f'https://{self.bucket_name}.{self.endpoint}/{file_path}'
            else:
                raise Exception("文件上传失败")
                
        except Exception as e:
            logger.error(f"文件上传失败: {str(e)}")
            raise

    @classmethod
    def create_user_bucket(cls, username):
        """
        为新用户创建bucket的类方法
        可在用户注册时调用
        """
        try:
            oss = cls(username=username)
            return oss.ensure_bucket_exists()
        except Exception as e:
            logger.error(f"为用户{username}创建bucket失败: {str(e)}")
            return False 