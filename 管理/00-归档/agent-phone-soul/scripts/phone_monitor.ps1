# Phone Agent Monitor - 手机状态监控脚本
# 通过WiFi ADB + ScreenStream API持续监控手机，异常时推送通知
# 用法: .\phone_monitor.ps1 -PhoneIP "192.168.10.122" -Interval 30

param(
    [string]$PhoneIP = "192.168.10.122",
    [int]$AdbPort = 5555,
    [int]$ApiPort = 8087,
    [int]$Interval = 30,
    [int]$MaxRounds = 0,  # 0=无限
    [string]$AdbPath = "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\android-sdk\platform-tools\adb.exe"
)

$device = "${PhoneIP}:${AdbPort}"
$api = "http://127.0.0.1:${ApiPort}"

function Send-PhoneNotification {
    param([string]$Title, [string]$Text)
    & $AdbPath -s $device shell "cmd notification post -S bigtext -t '$Title' 'agent_monitor' '$Text'" 2>$null | Out-Null
}

function Get-DeviceInfo {
    try {
        $r = Invoke-WebRequest -Uri "$api/deviceinfo" -TimeoutSec 5 -UseBasicParsing
        return $r.Content | ConvertFrom-Json
    } catch { return $null }
}

function Get-Notifications {
    param([int]$Limit = 5)
    try {
        $r = Invoke-WebRequest -Uri "$api/notifications/read?limit=$Limit" -TimeoutSec 5 -UseBasicParsing
        return ($r.Content | ConvertFrom-Json).notifications
    } catch { return @() }
}

function Get-ForegroundApp {
    try {
        $r = Invoke-WebRequest -Uri "$api/foreground" -TimeoutSec 3 -UseBasicParsing
        return ($r.Content | ConvertFrom-Json).packageName
    } catch { return "unknown" }
}

# --- Main Loop ---
Write-Host "=== Phone Agent Monitor ===" -ForegroundColor Cyan
Write-Host "Device: $device | API: $api | Interval: ${Interval}s"
Write-Host "Press Ctrl+C to stop`n"

$round = 0
$lastBattery = -1
$lastFg = ""
$lastNotifTime = 0
$alerts = @()

while ($true) {
    $round++
    if ($MaxRounds -gt 0 -and $round -gt $MaxRounds) { break }
    
    $time = Get-Date -Format "HH:mm:ss"
    $info = Get-DeviceInfo
    
    if (-not $info) {
        Write-Host "[$time] ⚠️ 设备离线" -ForegroundColor Red
        $alerts += "设备离线"
        Start-Sleep -Seconds $Interval
        continue
    }
    
    # Battery monitoring
    $bat = $info.batteryLevel
    if ($lastBattery -gt 0 -and $bat -lt 20 -and $lastBattery -ge 20) {
        $msg = "电池低于20%: ${bat}%"
        Write-Host "[$time] 🔋 $msg" -ForegroundColor Yellow
        Send-PhoneNotification "Agent Alert" $msg
        $alerts += $msg
    }
    $lastBattery = $bat
    
    # Foreground app monitoring
    $fg = Get-ForegroundApp
    if ($fg -ne $lastFg -and $lastFg -ne "") {
        Write-Host "[$time] 📱 APP切换: $($lastFg -replace 'com\.','') → $($fg -replace 'com\.','')" -ForegroundColor DarkCyan
    }
    $lastFg = $fg
    
    # New notification monitoring
    $notifs = Get-Notifications -Limit 3
    if ($notifs.Count -gt 0 -and $notifs[0].time -ne $lastNotifTime) {
        $new = $notifs[0]
        $pkg = $new.package -replace 'com\.',''
        $title = if($new.title){$new.title}else{$new.text}
        if ($title -and $pkg -ne "android.shell") {
            Write-Host "[$time] 🔔 $pkg : $($title.Substring(0, [Math]::Min(50, $title.Length)))" -ForegroundColor Green
        }
        $lastNotifTime = $notifs[0].time
    }
    
    # Status line
    $status = "[$time] 🔋${bat}% | 📱$($fg -replace 'com\.microsoft\.','') | ⏱$($info.uptimeFormatted)"
    Write-Host $status
    
    Start-Sleep -Seconds $Interval
}

# Summary
Write-Host "`n=== Monitor Stopped ===" -ForegroundColor Cyan
Write-Host "Rounds: $round | Alerts: $($alerts.Count)"
if ($alerts.Count -gt 0) {
    Write-Host "Alerts:" -ForegroundColor Yellow
    $alerts | ForEach-Object { Write-Host "  - $_" }
}
