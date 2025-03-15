# 示例配置文件，使用前请重命名为local_settings.py并填入实际值

# 阿里云RAM用户秘钥（请从环境变量或安全存储获取）
ALIBABA_CLOUD_ACCESS_RAM_USER_KEY_ID = 'YOUR_ALIYUN_KEY_ID'
ALIBABA_CLOUD_ACCESS_RAM_USER_KEY_SECRET = 'YOUR_ALIYUN_KEY_SECRET'

# 阿里云region
ALIYUN_REGION_ID = 'cn-wuhan-lr'

# 短信服务RAM角色ARN
ALIYUN_STS_ROLE_SMS_ARN = 'acs:ram::YOUR_ACCOUNT_ID:role/smsrole'
# 对象存储服务RAM角色ARN
ALIYUN_STS_ROLE_OSS_ARN = 'acs:ram::YOUR_ACCOUNT_ID:role/oss-upload-role'

# 发送短信的签名和模版ID
ALIYUN_SMS_SIGN1 = "应用名称"
ALIYUN_SMS_SIGN2 = "应用名称2"
ALIYUN_SMS_TEMPLATE = {
    "register": "SMS_TEMPLATE_ID1",
    "login": "SMS_TEMPLATE_ID2",
    "reset_password": "SMS_TEMPLATE_ID3"
}

# 数据库密码
mysql_password = "YOUR_MYSQL_PASSWORD"
redis_password = "YOUR_REDIS_PASSWORD" 