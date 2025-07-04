import os

# 查看所有环境变量
for key, value in os.environ.items():
    print(f"{key} = {value}")
print('--------------------------------')
# 查看特定变量
print(os.environ.get('HTTPS_PROXY'))
