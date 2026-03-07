#!/usr/bin/env pwsh
# Home Assistant 脚本启动器 (修复版)
# 此脚本用于启动其他脚本，带有超时保护

# 超时保护
$scriptTimeout = 600 # 10分钟超时
$scriptStartTime = Get-Date

# 导入超时函数
try {
    . "Homeassistant工具库/timeout_functions.ps1"
} catch {
    Write-Host "无法加载超时保护函数，继续执行..." -ForegroundColor Yellow
}

# 创建日志目录
if (-not (Test-Path "脚本/日志")) {
    New-Item -Path "脚本/日志" -ItemType Directory -Force | Out-Null
}

# 执行脚本索引
try {
    & "Homeassistant工具库/脚本索引.ps1"
} catch {
    Write-Host "脚本执行出错: $_" -ForegroundColor Red
    
    # 尝试修复
    Write-Host "`n尝试修复脚本执行问题..." -ForegroundColor Yellow
    & "Homeassistant工具库/系统维护/脚本执行修复_自动.ps1"
    
    Write-Host "`n修复完成，请重新运行脚本启动器" -ForegroundColor Green
}
