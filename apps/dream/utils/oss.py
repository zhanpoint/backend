import oss2
from aliyunsdkcore import client
from aliyunsdksts.request.v20150401 import AssumeRoleRequest
import json
import time
import uuid
from config.env_config import ALIYUN_CONFIG
import re
import os


class OSS:
    SHARED_BUCKET_NAME = 'dreamlog-shared'
    
    def __init__(self, user_id):
        if not user_id:
            raise ValueError("用户ID不能为空")
                
        self.user_id = str(user_id)
        self.access_key_id = ALIYUN_CONFIG.get('access_key_id')
        self.access_key_secret = ALIYUN_CONFIG.get('access_key_secret')
        self.role_arn = ALIYUN_CONFIG.get('sts_role_oss_arn')
        
        self.endpoint = str(ALIYUN_CONFIG.get('oss_endpoint')).strip()
        if not self.endpoint.startswith(('http://', 'https://')):
            self.endpoint = f'https://{self.endpoint}'
                
        self.bucket_name = self.SHARED_BUCKET_NAME
        self.user_prefix = f'users/{self.user_id}/'
        self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
    
    def _clear_proxy_env(self):
        original_proxies = {}
        for proxy_var in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY']:
            if proxy_var in os.environ:
                original_proxies[proxy_var] = os.environ[proxy_var]
                del os.environ[proxy_var]
        return original_proxies
    
    def _restore_proxy_env(self, original_proxies):
        for proxy_var, proxy_value in original_proxies.items():
            os.environ[proxy_var] = proxy_value
    
    def get_user_upload_path(self, filename=''):
        date_path = time.strftime("%Y/%m/%d")
        
        if filename:
            safe_filename = self._sanitize_filename(filename)
            unique_filename = f"{uuid.uuid4().hex[:8]}_{safe_filename}"
        else:
            unique_filename = f"{uuid.uuid4().hex}.jpg"
            
        return f"{self.user_prefix}dreams/{date_path}/{unique_filename}"
    
    def _sanitize_filename(self, filename):
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', name)
        safe_name = safe_name[:50]
        return f"{safe_name}.{ext}" if ext else safe_name
    
    def _get_sts_token(self):
        original_proxies = self._clear_proxy_env()
        
        try:
            clt = client.AcsClient(
                self.access_key_id,
                self.access_key_secret,
                'cn-wuhan-lr'
            )
            
            request = AssumeRoleRequest.AssumeRoleRequest()
            request.set_accept_format('json')
            request.set_RoleArn(self.role_arn)
            request.set_RoleSessionName(f'user_{self.user_id}_{int(time.time())}')
            request.set_DurationSeconds(3600)
            
            policy = {
                "Version": "1",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "oss:PutObject",
                            "oss:GetObject",
                            "oss:DeleteObject"
                        ],
                        "Resource": [
                            f"acs:oss:*:*:{self.bucket_name}/{self.user_prefix}*"
                        ]
                    }
                ]
            }
            
            request.set_Policy(json.dumps(policy))
            response = clt.do_action_with_exception(request)
            credentials = json.loads(response).get('Credentials')
            
            return {
                'access_key_id': credentials.get('AccessKeyId'),
                'access_key_secret': credentials.get('AccessKeySecret'),
                'security_token': credentials.get('SecurityToken')
            }
        finally:
            self._restore_proxy_env(original_proxies)
    
    def ensure_bucket_exists(self):
        original_proxies = self._clear_proxy_env()
        
        try:
            bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)
            
            try:
                bucket.get_bucket_info()
                self._ensure_cors_config(bucket)
                return True
            except oss2.exceptions.NoSuchBucket:
                bucket.create_bucket(
                    oss2.models.BUCKET_ACL_PRIVATE,
                    oss2.models.BucketCreateConfig(oss2.BUCKET_STORAGE_CLASS_STANDARD)
                )
                self._ensure_cors_config(bucket)
                return True
                
        except Exception:
            return False
        finally:
            self._restore_proxy_env(original_proxies)
    
    def _ensure_cors_config(self, bucket):
        try:
            cors_rule = oss2.models.CorsRule(
                allowed_origins=['*'],
                allowed_methods=['GET', 'PUT', 'POST', 'DELETE', 'HEAD'],
                allowed_headers=['*'],
                expose_headers=['ETag', 'x-oss-request-id'],
                max_age_seconds=3600
            )
            
            cors_config = oss2.models.BucketCors([cors_rule])
            bucket.put_bucket_cors(cors_config)
        except Exception:
            pass
    
    def generate_presigned_url(self, filename, content_type='image/jpeg', expires=3600):
        original_proxies = self._clear_proxy_env()
        
        try:
            file_key = self.get_user_upload_path(filename)
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            bucket = oss2.Bucket(auth, self.endpoint, self.bucket_name)
            
            upload_url = bucket.sign_url('PUT', file_key, expires, headers={
                'Content-Type': content_type
            })
            
            access_url = bucket.sign_url('GET', file_key, expires)
            
            return {
                'upload_url': upload_url,
                'access_url': access_url,
                'file_key': file_key,
                'expires_in': expires
            }
        finally:
            self._restore_proxy_env(original_proxies)
    
    def delete_file(self, file_key):
        try:
            if not file_key.startswith(self.user_prefix):
                return False
            
            original_proxies = self._clear_proxy_env()
            
            try:
                bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)
                bucket.delete_object(file_key)
                return True
            finally:
                self._restore_proxy_env(original_proxies)
                
        except Exception:
            return False
    
    def list_user_files(self, prefix='', max_keys=100):
        original_proxies = self._clear_proxy_env()
        
        try:
            bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)
            full_prefix = self.user_prefix + prefix
            
            files = []
            for obj in oss2.ObjectIterator(bucket, prefix=full_prefix, max_keys=max_keys):
                files.append({
                    'key': obj.key,
                    'size': obj.size,
                    'last_modified': obj.last_modified,
                    'etag': obj.etag
                })
                
            return files
        except Exception:
            return []
        finally:
            self._restore_proxy_env(original_proxies)
    
    @classmethod
    def initialize_shared_bucket(cls):
        try:
            oss = cls(user_id='system')
            return oss.ensure_bucket_exists()
        except Exception:
            return False
