# PowerShell script for setting up Windows Task Scheduler
# For JWT token cleanup task

# Set output encoding to UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8

# PowerShell脚本 - 设置Windows任务计划程序
# 用于在Windows系统上设置JWT令牌清理任务

# 设置任务路径
$taskName = "JWT Token Cleanup"
$projectPath = "D:\python project\backend"
$scriptPath = "$projectPath\scripts\clean_tokens.bat"

# 检查批处理文件是否存在，如果不存在则创建
if (-not (Test-Path $scriptPath)) {
    Write-Host "Creating batch file..."
    $batchContent = @"
@echo off
cd /d $projectPath
call .venv\Scripts\activate
python manage.py clean_expired_tokens
echo Cleanup completed - %date% %time% >> logs\token_cleanup.log
"@
    $batchContent | Out-File -FilePath $scriptPath -Encoding ASCII
    Write-Host "Batch file created: $scriptPath"
}

# 删除现有任务（如果存在）
try {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed existing task: $taskName"
}
catch {
    Write-Host "No existing task found: $taskName"
}

# 创建触发器 - 每天下午3点运行
$trigger = New-ScheduledTaskTrigger -Daily -At 3pm

# 创建操作 - 运行批处理脚本
$action = New-ScheduledTaskAction -Execute $scriptPath

# 创建设置 - 即使用户未登录也运行，出错后重试最多3次
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)

# 注册任务
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Run JWT token cleanup daily at 3 AM"

Write-Host "Task created successfully: $taskName"
Write-Host "Script path: $scriptPath"
Write-Host "Run time: Daily at 3 AM"
