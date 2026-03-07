#!/usr/bin/env pwsh
# 简单的Home Assistant重启脚本

$ErrorActionPreference = "Stop"
$baseUrl = "http://localhost:8123"

Write-Host "===== Home Assistant 重启工具 =====" -ForegroundColor Cyan
Write-Host "时间: $(Get-Date)" -ForegroundColor Yellow
Write-Host ""

# 读取令牌
if (Test-Path "ha_token.txt") {
    $token = Get-Content "ha_token.txt" -Raw
    $token = $token.Trim()
    Write-Host "已读取访问令牌" -ForegroundColor Green
} else {
    Write-Host "未找到令牌文件，请输入长期访问令牌" -ForegroundColor Yellow
    Write-Host "可从Home Assistant的个人资料->长期访问令牌中创建" -ForegroundColor Yellow
    $token = Read-Host "请输入令牌"
    $token | Out-File "ha_token.txt"
}

# 设置API头
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

# 确认重启
$confirm = Read-Host "是否确定要重启Home Assistant? (y/n)"

if ($confirm -eq "y") {
    # 重启Home Assistant
    try {
        Write-Host "正在发送重启命令..." -ForegroundColor Yellow
        $response = Invoke-RestMethod -Uri "$baseUrl/api/services/homeassistant/restart" -Headers $headers -Method Post
        Write-Host "重启命令已发送，请等待Home Assistant重新启动（通常需要30-60秒）" -ForegroundColor Green
    }
    catch {
        Write-Host "重启Home Assistant失败: $_" -ForegroundColor Red
    }
} else {
    Write-Host "已取消重启操作" -ForegroundColor Yellow
}

# 重启Home Assistant
# 调用备份目录中的重启脚本

$restartScriptPath = ".\HA备份\重启HA.ps1"

if (Test-Path $restartScriptPath) {
    & $restartScriptPath
} else {
    Write-Host "❌ 找不到重启脚本文件: $restartScriptPath" -ForegroundColor Red
    Start-Sleep -Seconds 3
} 