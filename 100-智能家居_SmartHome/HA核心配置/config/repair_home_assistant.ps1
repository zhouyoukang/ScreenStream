#!/usr/bin/env pwsh
# Home Assistant 修复脚本
# 此脚本用于修复数据库问题并重启 Home Assistant

Write-Host "Home Assistant 修复工具" -ForegroundColor Green
Write-Host "======================" -ForegroundColor Green

# 创建新的最小数据库
try {
    Write-Host "创建新的最小数据库文件..." -ForegroundColor Cyan
    $sqlite_cmd = "CREATE DATABASE 'home-assistant_v2.minimal.db'"
    # 简单创建一个空文件
    New-Item -Path "home-assistant_v2.minimal.db" -ItemType File -Force | Out-Null
    Write-Host "已创建新的最小数据库文件" -ForegroundColor Green
} catch {
    Write-Host "创建数据库文件失败: $_" -ForegroundColor Red
}

# 准备配置文件
Write-Host "`n准备使用最小化配置文件启动 Home Assistant..." -ForegroundColor Cyan
Write-Host "备份原始配置文件..." -ForegroundColor Cyan
Copy-Item -Path "configuration.yaml" -Destination "configuration.yaml.backup" -Force
Write-Host "备份完成: configuration.yaml.backup" -ForegroundColor Green

# 提示用户
Write-Host "`n请执行以下操作:" -ForegroundColor Yellow
Write-Host "1. 重命名 minimal_configuration.yaml 为 configuration.yaml:" -ForegroundColor Yellow
Write-Host "   rename-item -path minimal_configuration.yaml -newname configuration.yaml -force" -ForegroundColor Gray
Write-Host "2. 重启 Home Assistant" -ForegroundColor Yellow
Write-Host "3. 如果成功启动，请使用 UI 禁用不必要的集成" -ForegroundColor Yellow
Write-Host "4. 如果需要恢复原始配置，请执行:" -ForegroundColor Yellow
Write-Host "   rename-item -path configuration.yaml.backup -newname configuration.yaml -force" -ForegroundColor Gray

Write-Host "`n注意: 此脚本不会自动重启 Home Assistant，请手动执行重启操作" -ForegroundColor Magenta 