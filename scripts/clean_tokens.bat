@echo off
cd /d D:\python project\backend
call .venv\Scripts\activate
python manage.py clean_expired_tokens
echo 清理过期令牌完成 - %date% %time% >> logs\token_cleanup.log