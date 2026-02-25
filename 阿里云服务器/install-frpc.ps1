# FRP Client Windows 开机自启安装脚本
# 以管理员身份运行
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File install-frpc.ps1
#   powershell -ExecutionPolicy Bypass -File install-frpc.ps1 -FrpDir "D:\frp"

param(
    [string]$FrpDir = ""
)

$ErrorActionPreference = "Stop"

# 自动检测 frpc.exe 位置
if (-not $FrpDir) {
    $FrpDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}

$frpcExe = Join-Path $FrpDir "frpc.exe"
$frpcToml = Join-Path $FrpDir "frpc.toml"
$taskName = "FRP Client"

# ── 检查文件 ──
if (-not (Test-Path $frpcExe)) {
    Write-Host "错误: 未找到 frpc.exe" -ForegroundColor Red
    Write-Host "  请下载: https://github.com/fatedier/frp/releases" -ForegroundColor Yellow
    Write-Host "  解压到: $FrpDir" -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path $frpcToml)) {
    $exampleToml = Join-Path $FrpDir "frpc.example.toml"
    if (Test-Path $exampleToml) {
        Write-Host "错误: 未找到 frpc.toml" -ForegroundColor Red
        Write-Host "  请先: cp frpc.example.toml frpc.toml 并填入真实密码" -ForegroundColor Yellow
    } else {
        Write-Host "错误: 未找到 frpc.toml 配置文件" -ForegroundColor Red
    }
    exit 1
}

# ── 检查配置中是否有占位符 ──
$configContent = Get-Content $frpcToml -Raw
if ($configContent -match "YOUR_") {
    Write-Host "错误: frpc.toml 中仍有 YOUR_xxx 占位符，请替换为真实值" -ForegroundColor Red
    exit 1
}

# ── 创建计划任务（开机自启，SYSTEM身份） ──
$action = New-ScheduledTaskAction -Execute $frpcExe -Argument "-c `"$frpcToml`"" -WorkingDirectory $FrpDir
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# 删除旧任务
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# 注册新任务
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "FRP Client - 阿里云穿透服务"

Write-Host "`n[OK] 计划任务 '$taskName' 已创建" -ForegroundColor Green
Write-Host "  frpc路径: $frpcExe" -ForegroundColor Cyan
Write-Host "  配置文件: $frpcToml" -ForegroundColor Cyan

# ── 立即启动 ──
Write-Host "`n启动FRP Client..." -ForegroundColor Yellow
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 3

# ── 验证 ──
$frpcProc = Get-Process frpc -ErrorAction SilentlyContinue
if ($frpcProc) {
    Write-Host "[OK] FRP Client 运行中 (PID: $($frpcProc.Id))" -ForegroundColor Green
} else {
    Write-Host "[!] FRP Client 可能启动失败，检查日志" -ForegroundColor Yellow
}

# ── 读取配置显示连接信息 ──
$serverAddr = if ($configContent -match 'serverAddr\s*=\s*"([^"]+)"') { $Matches[1] } else { "未知" }
Write-Host "`n远程访问地址:" -ForegroundColor Green
Write-Host "  remote_agent: http://${serverAddr}:19903" -ForegroundColor Cyan
Write-Host "  RDP:          ${serverAddr}:13389" -ForegroundColor Cyan
Write-Host "  FRP控制台:    http://${serverAddr}:7500" -ForegroundColor Cyan
