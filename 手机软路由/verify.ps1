# Phone Soft Router Verify
# Usage: powershell -File verify.ps1 [-serial <device>]
# Default: OPPO Reno4 SE (WK555X5DF65PPR4L)

param([string]$serial = "WK555X5DF65PPR4L")

$ADB = "D:\platform-tools\adb.exe"
$SERIAL = $serial
$ErrorCount = 0

Write-Host "`n=== Phone Router Verify ===" -ForegroundColor Cyan

# 1. 设备连接
Write-Host "`n[1/6] Device connection..." -ForegroundColor Yellow
$devices = & $ADB devices 2>&1 | Select-String $SERIAL
if ($devices) {
    $model = (& $ADB -s $SERIAL shell "getprop ro.product.model" 2>&1).Trim()
    Write-Host "  OK: $model connected ($SERIAL)" -ForegroundColor Green
} else {
    Write-Host "  FAIL: Device not connected" -ForegroundColor Red
    $ErrorCount++
}

# 2. V2rayNG运行状态
Write-Host "`n[2/6] V2rayNG status..." -ForegroundColor Yellow
$v2ray = & $ADB -s $SERIAL shell "ps -A | grep v2ray" 2>&1
if ($v2ray -match "v2ray") {
    Write-Host "  OK: V2rayNG running" -ForegroundColor Green
} else {
    Write-Host "  FAIL: V2rayNG not running" -ForegroundColor Red
    $ErrorCount++
}

# 3. SOCKS5端口
Write-Host "`n[3/6] SOCKS5 port (10808)..." -ForegroundColor Yellow
$socks = & $ADB -s $SERIAL shell "netstat -tlnp 2>/dev/null | grep 10808" 2>&1
if ($socks -match "10808") {
    Write-Host "  OK: SOCKS5 :10808 LISTEN" -ForegroundColor Green
} else {
    Write-Host "  FAIL: SOCKS5 port not listening" -ForegroundColor Red
    $ErrorCount++
}

# 4. HTTP端口
Write-Host "`n[4/6] HTTP port (10809)..." -ForegroundColor Yellow
$http = & $ADB -s $SERIAL shell "netstat -tlnp 2>/dev/null | grep 10809" 2>&1
if ($http -match "10809") {
    Write-Host "  OK: HTTP :10809 LISTEN" -ForegroundColor Green
} else {
    Write-Host "  WARN: HTTP port not open (optional, enable in V2rayNG settings)" -ForegroundColor DarkYellow
}

# 5. 手机IP
Write-Host "`n[5/6] Network interfaces..." -ForegroundColor Yellow
$wlan = & $ADB -s $SERIAL shell "ip addr show wlan0 2>/dev/null | grep 'inet '" 2>&1
if ($wlan -match "inet\s+([\d.]+)") {
    $ip = $Matches[1]
    Write-Host "  OK: WiFi: $ip" -ForegroundColor Green
}
$tun = & $ADB -s $SERIAL shell "ip addr show tun0 2>/dev/null | grep 'inet '" 2>&1
if ($tun -match "tun0") {
    Write-Host "  OK: VPN tunnel (tun0) established" -ForegroundColor Green
} else {
    Write-Host "  FAIL: VPN tunnel not established" -ForegroundColor Red
    $ErrorCount++
}

# 6. 代理测试
Write-Host "`n[6/6] Proxy connectivity test..." -ForegroundColor Yellow
if ($ip) {
    try {
        $result = & curl.exe -s -o NUL -w "%{http_code}" -x "socks5://${ip}:10808" "https://www.google.com" -m 10 2>&1
        if ($result -eq "200") {
            Write-Host "  OK: Google reachable (HTTP 200)" -ForegroundColor Green
        } else {
            Write-Host "  FAIL: Google unreachable (HTTP $result)" -ForegroundColor Red
            $ErrorCount++
        }
    } catch {
        Write-Host "  FAIL: Proxy test error: $_" -ForegroundColor Red
        $ErrorCount++
    }
} else {
    Write-Host "  SKIP: Cannot get phone IP" -ForegroundColor DarkYellow
}

# 总结
Write-Host "`n=== Result ===" -ForegroundColor Cyan
if ($ErrorCount -eq 0) {
    Write-Host "ALL PASS! Proxy: socks5://${ip}:10808" -ForegroundColor Green
} else {
    Write-Host "$ErrorCount FAILED - check details above" -ForegroundColor Red
}
Write-Host ""
