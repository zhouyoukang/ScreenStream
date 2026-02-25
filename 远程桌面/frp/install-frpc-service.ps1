# FRP Client Windows 开机自启安装脚本
# 以管理员身份运行

$frpDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$frpcExe = Join-Path $frpDir "frpc.exe"
$frpcToml = Join-Path $frpDir "frpc.toml"
$taskName = "FRP Client"

if (-not (Test-Path $frpcExe)) {
    Write-Host "错误: 未找到 frpc.exe" -ForegroundColor Red
    exit 1
}

# 创建计划任务（开机自启，以SYSTEM身份运行）
$action = New-ScheduledTaskAction -Execute $frpcExe -Argument "-c `"$frpcToml`"" -WorkingDirectory $frpDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# 删除旧任务
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# 注册新任务
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "FRP Client - 远程桌面穿透服务"

Write-Host "✓ 计划任务 '$taskName' 已创建" -ForegroundColor Green
Write-Host "  frpc路径: $frpcExe" -ForegroundColor Cyan
Write-Host "  配置文件: $frpcToml" -ForegroundColor Cyan

# 立即启动
Write-Host "`n启动FRP Client..." -ForegroundColor Yellow
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 3

# 验证
$task = Get-ScheduledTask -TaskName $taskName
$frpcProc = Get-Process frpc -ErrorAction SilentlyContinue
if ($frpcProc) {
    Write-Host "✓ FRP Client 运行中 (PID: $($frpcProc.Id))" -ForegroundColor Green
} else {
    Write-Host "⚠ FRP Client 可能启动失败，检查日志" -ForegroundColor Yellow
}

Write-Host "`n完成！远程访问地址:" -ForegroundColor Green
Write-Host "  remote_agent: http://60.205.171.100:19903" -ForegroundColor Cyan
Write-Host "  RDP: 60.205.171.100:13389" -ForegroundColor Cyan
Write-Host "  FRP控制台: http://60.205.171.100:7500" -ForegroundColor Cyan
