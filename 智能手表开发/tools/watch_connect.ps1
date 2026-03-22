# Samsung Galaxy Watch4 Classic - WiFi ADB连接助手
# 用法: .\watch_connect.ps1 [-IP <手表IP>] [-Pair]

param(
    [string]$IP,
    [switch]$Pair,
    [int]$Port = 5555
)

$ADB = "D:\platform-tools\adb.exe"

function Find-Watch {
    $devices = & $ADB devices -l 2>&1
    foreach ($line in $devices) {
        if ($line -match "(\S+)\s+device\s+.*model:SM-R8") {
            return $Matches[1]
        }
    }
    # 扫描已知LAN段
    Write-Host "Scanning LAN for Galaxy Watch..." -ForegroundColor Yellow
    $subnet = "192.168.31"
    1..254 | ForEach-Object {
        $testIP = "$subnet.$_"
        $r = Test-Connection $testIP -Count 1 -TimeoutSeconds 1 -ErrorAction SilentlyContinue
        if ($r) {
            $model = & $ADB connect "${testIP}:5555" 2>&1
            if ($model -match "connected") {
                $m = & $ADB -s "${testIP}:5555" shell getprop ro.product.model 2>&1
                if ($m -match "SM-R8") {
                    Write-Host "Found Galaxy Watch at $testIP (Model: $m)" -ForegroundColor Green
                    return "${testIP}:5555"
                } else {
                    & $ADB disconnect "${testIP}:5555" 2>$null
                }
            }
        }
    }
    return $null
}

Write-Host "=== Galaxy Watch4 Classic Connection Helper ===" -ForegroundColor Cyan

if ($Pair) {
    Write-Host "`nPairing mode - Enter watch IP and pairing port:" -ForegroundColor Yellow
    if (-not $IP) { $IP = Read-Host "Watch IP" }
    $pairPort = Read-Host "Pairing Port (shown on watch)"
    Write-Host "Pairing with ${IP}:${pairPort}..."
    & $ADB pair "${IP}:${pairPort}"
    Write-Host "`nNow connecting..."
    & $ADB connect "${IP}:${Port}"
} elseif ($IP) {
    Write-Host "Connecting to ${IP}:${Port}..."
    & $ADB connect "${IP}:${Port}"
} else {
    $watch = Find-Watch
    if ($watch) {
        Write-Host "`nWatch connected: $watch" -ForegroundColor Green
    } else {
        Write-Host "`nNo Galaxy Watch found!" -ForegroundColor Red
        Write-Host @"

Steps to enable WiFi ADB:
1. On watch: Settings > About Watch > Software > Tap 'Software Version' 7 times
2. Settings > Developer Options > ADB Debugging > ON
3. Settings > Developer Options > Debug over WiFi > ON
4. Note the IP:Port shown
5. Run: .\watch_connect.ps1 -Pair -IP <watch_ip>
"@
        exit 1
    }
}

# 验证连接
$model = & $ADB shell getprop ro.product.model 2>&1
$android = & $ADB shell getprop ro.build.version.release 2>&1
$battery = & $ADB shell dumpsys battery 2>&1 | Select-String "level:" | ForEach-Object { ($_ -split ":")[1].Trim() }

Write-Host "`n--- Watch Status ---" -ForegroundColor Green
Write-Host "Model:   $model"
Write-Host "Android: $android"
Write-Host "Battery: ${battery}%"
Write-Host "Ready for development!" -ForegroundColor Green
