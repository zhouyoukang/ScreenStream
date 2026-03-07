# Quest 3 WebXR 开发环境一键配置
# 用法: .\setup.ps1

Write-Host "=== Quest 3 WebXR 开发环境配置 ===" -ForegroundColor Cyan

# 1. 检查Node.js
$nodeVersion = node --version 2>$null
if ($nodeVersion) {
    Write-Host "[OK] Node.js: $nodeVersion" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Node.js未安装，请先安装: https://nodejs.org/" -ForegroundColor Red
    exit 1
}

# 2. 检查ADB
$adbVersion = adb version 2>$null
if ($adbVersion) {
    Write-Host "[OK] ADB: 已安装" -ForegroundColor Green
} else {
    Write-Host "[WARN] ADB未安装，无法直接部署到Quest" -ForegroundColor Yellow
}

# 3. 检查Quest连接
$devices = adb devices 2>$null | Select-String "device$"
if ($devices) {
    Write-Host "[OK] Quest已连接: $($devices.Count)台设备" -ForegroundColor Green
} else {
    Write-Host "[INFO] 未检测到Quest设备(请确保USB连接+开发者模式)" -ForegroundColor Yellow
}

# 4. 生成自签HTTPS证书(WebXR必须)
$certPath = Join-Path $PSScriptRoot ".." "certs"
if (-not (Test-Path $certPath)) {
    New-Item -ItemType Directory -Path $certPath -Force | Out-Null
}

$certFile = Join-Path $certPath "cert.pem"
$keyFile = Join-Path $certPath "key.pem"

if (-not (Test-Path $certFile)) {
    Write-Host "生成自签HTTPS证书..." -ForegroundColor Yellow
    $opensslAvailable = Get-Command openssl -ErrorAction SilentlyContinue
    if ($opensslAvailable) {
        openssl req -x509 -newkey rsa:2048 -keyout $keyFile -out $certFile -days 365 -nodes -subj "/CN=localhost" 2>$null
        Write-Host "[OK] 证书已生成: $certPath" -ForegroundColor Green
    } else {
        Write-Host "[WARN] openssl未找到，请手动生成证书或使用mkcert" -ForegroundColor Yellow
    }
} else {
    Write-Host "[OK] 证书已存在: $certPath" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== 配置完成 ===" -ForegroundColor Cyan
Write-Host "下一步: 在webxr/目录中创建项目" -ForegroundColor White
