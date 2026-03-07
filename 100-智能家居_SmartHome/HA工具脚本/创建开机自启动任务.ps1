# 创建 Windows 任务计划程序任务 - 开机自动启动语音唤醒服务
# 以管理员权限运行此脚本

$taskName = "HomeAssistant语音唤醒服务"
$taskPath = "\HomeAssistant\"
$scriptPath = "D:\homeassistant\🔧_工具脚本\启动语音唤醒服务.bat"

# 检查是否以管理员权限运行
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "⚠️ 请以管理员权限运行此脚本！" -ForegroundColor Red
    Write-Host "右键点击 PowerShell → 以管理员身份运行" -ForegroundColor Yellow
    pause
    exit
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  创建开机自启动任务" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 删除已存在的任务
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "发现已存在的任务，正在删除..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# 创建任务
Write-Host "创建新的计划任务..." -ForegroundColor Green

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$scriptPath`""
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "开机自动启动 Home Assistant 语音唤醒相关的 Docker 容器（Whisper、OpenWakeWord、Piper）"

Register-ScheduledTask -TaskName $taskName -InputObject $task

Write-Host ""
Write-Host "✅ 任务创建成功！" -ForegroundColor Green
Write-Host ""
Write-Host "任务详情:" -ForegroundColor Cyan
Write-Host "  名称: $taskName"
Write-Host "  触发: 用户登录时"
Write-Host "  脚本: $scriptPath"
Write-Host ""
Write-Host "下次登录 Windows 时将自动启动语音唤醒服务。" -ForegroundColor Yellow
Write-Host ""
pause
