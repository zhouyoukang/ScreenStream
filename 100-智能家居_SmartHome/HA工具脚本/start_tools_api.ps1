# Home Assistant 工具库管理API启动脚本
# 此脚本现在调用Homeassistant工具库中的版本

$ErrorActionPreference = "Stop"
$toolsPath = Join-Path $PSScriptRoot "Homeassistant工具库\实用工具\api_server\start_tools_api.ps1"

if (Test-Path $toolsPath) {
    Write-Host "正在启动工具库API服务器..." -ForegroundColor Cyan
    & $toolsPath
} else {
    Write-Host "❌ 找不到工具库API启动脚本: $toolsPath" -ForegroundColor Red
    Write-Host "请确保已将文件移至Homeassistant工具库目录" -ForegroundColor Yellow
} 