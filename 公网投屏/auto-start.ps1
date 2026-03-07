#!/usr/bin/env pwsh
# 公网投屏 自动启动脚本
# 开机自启 或 手动运行均可
# 用法: powershell -File 公网投屏\auto-start.ps1

$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path $PSScriptRoot -Parent
$relayDir = Join-Path $PSScriptRoot "relay-server"
$bridgeScript = Join-Path $PSScriptRoot "ss-bridge.py"
$adb = Join-Path $root "构建部署\android-sdk\platform-tools\adb.exe"

# 手机WiFi IP (固定分配)
$PHONE_IP = "192.168.31.40"
$SS_PORT = 8086

Write-Host "[公网投屏] 启动中..." -ForegroundColor Cyan

# 1. 启动中继服务器
$relay = Get-Process -Name node -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "server\.js" }
if (-not $relay) {
    Start-Process -FilePath "node" -ArgumentList "server.js" -WorkingDirectory $relayDir -WindowStyle Hidden
    Start-Sleep 2
    Write-Host "  [1] 中继服务器 :9800 已启动" -ForegroundColor Green
} else {
    Write-Host "  [1] 中继服务器已在运行 (PID: $($relay.Id))" -ForegroundColor Green
}

# 2. 检查手机ScreenStream是否可达
$ssOk = $false
try {
    $r = Invoke-WebRequest -Uri "http://${PHONE_IP}:${SS_PORT}/" -TimeoutSec 3 -UseBasicParsing
    if ($r.StatusCode -eq 200) { $ssOk = $true }
} catch {}

if (-not $ssOk) {
    # 尝试ADB forward
    $devices = & $adb devices 2>&1 | Select-String "device$"
    if ($devices) {
        $serial = ($devices -split "\s+")[0]
        & $adb -s $serial forward tcp:$SS_PORT tcp:$SS_PORT 2>&1 | Out-Null
        try {
            $r = Invoke-WebRequest -Uri "http://localhost:${SS_PORT}/" -TimeoutSec 3 -UseBasicParsing
            if ($r.StatusCode -eq 200) {
                $ssOk = $true
                $PHONE_IP = "localhost"
            }
        } catch {}
    }
}

if ($ssOk) {
    Write-Host "  [2] ScreenStream可达: ${PHONE_IP}:${SS_PORT}" -ForegroundColor Green
} else {
    Write-Host "  [2] ScreenStream不可达，请确认手机已开始投屏" -ForegroundColor Red
    Write-Host "      等待手机连接后再运行此脚本" -ForegroundColor Yellow
    exit 1
}

# 3. 启动桥接
$bridge = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "ss-bridge" }
if ($bridge) { $bridge | Stop-Process -Force; Start-Sleep 1 }

# 找ADB设备用于反控
$adbDevice = "none"
$devices = & $adb devices -l 2>&1 | Select-String "device " | Select-Object -First 1
if ($devices) { $adbDevice = ($devices -split "\s+")[0] }

Start-Process -FilePath "python" -ArgumentList "$bridgeScript","--phone","${PHONE_IP}:${SS_PORT}","--relay","ws://localhost:9800","--room","phone","--token","screenstream_2026","--device",$adbDevice -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
Start-Sleep 3
Write-Host "  [3] 桥接已启动 (${PHONE_IP}:${SS_PORT} → relay)" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  公网投屏已就绪!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  公网地址:" -ForegroundColor White
Write-Host "  https://aiotvr.xyz/relay/?room=phone&token=screenstream_2026" -ForegroundColor Yellow
Write-Host ""
Write-Host "  本地地址:" -ForegroundColor White
Write-Host "  http://localhost:9800/?room=phone&token=screenstream_2026" -ForegroundColor Yellow
Write-Host ""
