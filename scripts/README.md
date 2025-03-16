# JWT令牌黑名单清理

本目录包含用于定期清理过期JWT黑名单令牌的脚本。

## 安装说明

### Windows系统

我们提供了两种方式在Windows系统上设置定时清理任务：

#### 方法1：使用PowerShell设置Windows任务计划程序（推荐）

1. 以管理员身份运行PowerShell
2. 执行以下命令：
   ```powershell
   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
   cd "D:\python project\backend\scripts"
   .\setup_windows_scheduler.ps1
   ```
3. 脚本将自动创建一个每天凌晨3点运行的Windows计划任务

#### 方法2：手动设置Windows任务计划程序

1. 打开Windows任务计划程序（在搜索框中输入"任务计划程序"）
2. 点击右侧的"创建基本任务"
3. 输入名称（如"JWT令牌清理"）和描述
4. 选择触发器为"每天"，设置开始时间为凌晨3:00
5. 选择操作为"启动程序"
6. 浏览并选择脚本文件：`D:\python project\backend\scripts\clean_tokens.bat`
7. 完成向导并保存

### Linux/Unix系统

在Linux/Unix系统上，可以使用django-crontab扩展（仅适用于生产环境）：

1. 确保django-crontab已安装：`pip install django-crontab`
2. 添加crontab任务：`python manage.py crontab add`
3. 查看添加的任务：`python manage.py crontab show`
4. 如需删除任务：`python manage.py crontab remove`

或者手动设置crontab：

1. 编辑crontab文件：`crontab -e`
2. 添加如下定时任务（每天凌晨3点执行）：
   ```
   0 3 * * * /path/to/your/project/scripts/clean_tokens.sh
   ```
3. 确保脚本具有执行权限：`chmod +x /path/to/your/project/scripts/clean_tokens.sh`

## 手动执行

你也可以手动执行清理命令：

```bash
# 使用默认设置（清理3天前的过期令牌）
python manage.py clean_expired_tokens

# 清理7天前的令牌
python manage.py clean_expired_tokens --days=7

# 仅显示将被删除的令牌数量，但不实际删除
python manage.py clean_expired_tokens --dry-run

# 设置每批处理的令牌数量为500（优化性能）
python manage.py clean_expired_tokens --batch-size=500
```

## 日志

清理操作日志存储在 `logs/token_cleanup.log` 文件中。

## 故障排除

### Windows系统

1. 检查任务计划程序中的任务状态和历史记录
2. 检查日志文件：`logs/token_cleanup.log`
3. 确保批处理文件（`.bat`）的路径正确
4. 确保用户具有运行脚本的权限

### Linux系统

1. 检查crontab是否包含任务：`crontab -l`
2. 检查系统日志：`/var/log/syslog`或`/var/log/cron`
3. 检查日志文件：`logs/token_cleanup.log`
4. 确保脚本具有执行权限：`chmod +x clean_tokens.sh`
5. 确保路径设置正确 