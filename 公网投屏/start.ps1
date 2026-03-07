# ScreenStream 公网投屏 一键启动
# 自动发现手机ADB → 启动中继 → 启动桥接 → 输出公网地址
# 用法: powershell -File 公网投屏\start.ps1

$ErrorActionPreference = "SilentlyContinue"
$root = Split-Path $PSScriptRoot -Parent
$relayDir = Join-Path $PSScriptRoot "relay-server"
$bridgeScript = Join-Path $PSScriptRoot "ss-bridge.py"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ScreenStream 公网投屏 一键启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. 发现手机ADB
Write-Host "`n[1/4] 搜索手机..." -ForegroundColor Yellow
$mdns = adb mdns services 2>&1 | Select-String "_adb-tls-connect"
if (-not $mdns) {
    Write-Host "  未发现手机无线调试，尝试已知连接..." -ForegroundColor Red
    $devices = adb devices -l 2>&1 | Select-String "device " | Select-Object -First 1
    if ($devices) {
        $adbDevice = ($devices -split "\s+")[0]
    } else {
        Write-Host "  错误: 无ADB设备。请开启手机无线调试。" -ForegroundColor Red
        exit 1
    }
} else {
    # 取最新的端口
    $line = ($mdns | Select-Object -Last 1).ToString()
    if ($line -match "(\d+\.\d+\.\d+\.\d+):(\d+)") {
        $phoneIP = $Matches[1]
        $phonePort = $Matches[2]
        $adbDevice = "${phoneIP}:${phonePort}"
        adb connect $adbDevice 2>&1 | Out-Null
        Start-Sleep -Seconds 2
    }
}
Write-Host "  手机: $adbDevice" -ForegroundColor Green

# 2. 检查ScreenStream投屏
Write-Host "`n[2/4] 检查ScreenStream..." -ForegroundColor Yellow
$ssPort = adb -s $adbDevice shell "netstat -tlnp 2>/dev/null | grep 8086" 2>&1
if ($ssPort -match "LISTEN") {
    Write-Host "  ScreenStream已在投屏 (端口8086)" -ForegroundColor Green
} else {
    Write-Host "  ScreenStream未投屏，尝试启动..." -ForegroundColor Yellow
    adb -s $adbDevice shell "am start -n info.dvkr.screenstream.dev/info.dvkr.screenstream.SingleActivity" 2>&1 | Out-Null
    Start-Sleep -Seconds 3
    adb -s $adbDevice shell "input tap 540 1944" 2>&1 | Out-Null
    Start-Sleep -Seconds 3
    $ssPort2 = adb -s $adbDevice shell "netstat -tlnp 2>/dev/null | grep 8086" 2>&1
    if ($ssPort2 -match "LISTEN") {
        Write-Host "  ScreenStream已启动" -ForegroundColor Green
    } else {
        Write-Host "  警告: ScreenStream可能未启动，请手动检查" -ForegroundColor Red
    }
}

# 3. 启动中继服务器
Write-Host "`n[3/4] 启动中继服务器..." -ForegroundColor Yellow
$existingRelay = Get-Process -Name node -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "server\.js" }
if ($existingRelay) {
    Write-Host "  中继已在运行 (PID: $($existingRelay.Id))" -ForegroundColor Green
} else {
    Start-Process -FilePath "node" -ArgumentList "server.js","--dev" -WorkingDirectory $relayDir -WindowStyle Hidden
    Start-Sleep -Seconds 2
    Write-Host "  中继已启动 (端口9800)" -ForegroundColor Green
}

# 4. 启动桥接
Write-Host "`n[4/4] 启动桥接..." -ForegroundColor Yellow
$existingBridge = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "ss-bridge" }
if ($existingBridge) {
    $existingBridge | Stop-Process -Force
    Start-Sleep -Seconds 1
}

$phoneWifiIP = ($adbDevice -split ":")[0]
Start-Process -FilePath "python" -ArgumentList "$bridgeScript","--phone","${phoneWifiIP}:8086","--relay","ws://localhost:9800","--room","phone","--token","screenstream_2026","--device",$adbDevice -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
Start-Sleep -Seconds 3
Write-Host "  桥接已启动" -ForegroundColor Green

# 完成
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  公网投屏已就绪!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  公网地址 (HTTPS):" -ForegroundColor White
Write-Host "  https://aiotvr.xyz/relay/?room=phone&token=screenstream_2026" -ForegroundColor Yellow
Write-Host ""
Write-Host "  本地地址:" -ForegroundColor White
Write-Host "  http://localhost:9800/?room=phone&token=screenstream_2026" -ForegroundColor Yellow
Write-Host ""
Write-Host "  手机: $adbDevice | 分辨率: 270p | 编码: H264" -ForegroundColor DarkGray
Write-Host ""
