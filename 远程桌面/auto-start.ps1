# Remote Desktop Agent — 开机自动启动配置
# 在目标Windows账号中运行此脚本，Agent会在该账号登录时自动启动
# 需要以目标账号身份运行

param(
    [int]$Port = 9903,
    [string]$Token = "",
    [switch]$Remove
)

$TaskName = "RemoteDesktopAgent_$Port"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AgentPath = Join-Path $ScriptDir "remote_agent.py"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task: $TaskName" -ForegroundColor Yellow
    exit 0
}

# Build arguments
$AgentArgs = "`"$AgentPath`" --port $Port"
if ($Token) { $AgentArgs += " --token $Token" }

# Find python
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) {
    Write-Host "ERROR: Python not found in PATH" -ForegroundColor Red
    exit 1
}

# Create scheduled task that runs at user logon
$Action = New-ScheduledTaskAction -Execute $Python -Argument $AgentArgs -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force | Out-Null

Write-Host "=== Auto-Start Configured ===" -ForegroundColor Green
Write-Host "  Task: $TaskName" -ForegroundColor White
Write-Host "  Port: $Port" -ForegroundColor White
Write-Host "  Python: $Python" -ForegroundColor White
if ($Token) { Write-Host "  Auth: token enabled" -ForegroundColor White }
Write-Host "`nThe agent will auto-start when this user logs in." -ForegroundColor Gray
Write-Host "To remove: .\auto-start.ps1 -Remove -Port $Port" -ForegroundColor Gray

# Also start it now
Write-Host "`nStarting agent now..." -ForegroundColor Cyan
Start-Process -FilePath $Python -ArgumentList $Args -WorkingDirectory $ScriptDir -WindowStyle Hidden
Write-Host "Agent running on port $Port" -ForegroundColor Green
