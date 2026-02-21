# Autonomous Phone Agent - Level 0 纯脚本层
# 无需AI模型，独立运行，零成本24小时监控+自动响应
# 用法: .\autonomous_agent.ps1 -Devices "R5CW2221VGL,192.168.10.122:5555"

param(
    [string]$Devices = "",
    [int]$Interval = 60,
    [string]$AdbPath = "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\android-sdk\platform-tools\adb.exe",
    [int]$BatteryAlert = 20,
    [int]$MemoryAlert = 90,
    [int]$TempAlert = 42
)

# Auto-detect devices if not specified
if (-not $Devices) {
    $detected = & $AdbPath devices 2>$null | Select-String "device$" | ForEach-Object { ($_ -split '\s+')[0] }
    $Devices = $detected -join ","
}
$deviceList = $Devices -split ','

Write-Host "=== Autonomous Phone Agent (Level 0) ===" -ForegroundColor Cyan
Write-Host "Devices: $($deviceList.Count) | Interval: ${Interval}s"
Write-Host "Alerts: Battery<${BatteryAlert}% | Memory>${MemoryAlert}% | Temp>${TempAlert}C"
Write-Host "Press Ctrl+C to stop`n"

$round = 0
$deviceProfiles = @{}

while ($true) {
    $round++
    $time = Get-Date -Format "HH:mm:ss"
    
    foreach ($dev in $deviceList) {
        if (-not $dev.Trim()) { continue }
        $dev = $dev.Trim()
        
        # Initialize profile
        if (-not $deviceProfiles.ContainsKey($dev)) {
            $model = (& $AdbPath -s $dev shell getprop ro.product.model 2>$null).Trim()
            $deviceProfiles[$dev] = @{model=$model; lastBat=-1; lastFg=""; alertCount=0}
            Write-Host "[$time] 新设备: $dev ($model)" -ForegroundColor Green
        }
        $profile = $deviceProfiles[$dev]
        
        # Level 0: Pure data collection (no AI needed)
        $bat = [int]((& $AdbPath -s $dev shell "dumpsys battery" 2>$null | Select-String "level" | Select-Object -First 1) -replace '[^\d]','')
        $memRaw = & $AdbPath -s $dev shell cat /proc/meminfo 2>$null
        $memTotal = [int](($memRaw | Select-String "MemTotal" | ForEach-Object { ($_ -split '\s+')[1] }))
        $memAvail = [int](($memRaw | Select-String "MemAvailable" | ForEach-Object { ($_ -split '\s+')[1] }))
        $memPct = if($memTotal -gt 0){[math]::Round(($memTotal-$memAvail)/$memTotal*100)}else{0}
        $temp = [int]((& $AdbPath -s $dev shell cat /sys/class/thermal/thermal_zone0/temp 2>$null))
        $tempC = [math]::Round($temp/1000,1)
        
        # Level 1: Rule-based alerts (no AI needed)
        $alerts = @()
        if ($bat -gt 0 -and $bat -lt $BatteryAlert) { $alerts += "电池低:${bat}%" }
        if ($memPct -gt $MemoryAlert) { $alerts += "内存高:${memPct}%" }
        if ($tempC -gt $TempAlert) { $alerts += "温度高:${tempC}C" }
        
        # Level 0: Auto-notify on alerts
        if ($alerts.Count -gt 0) {
            $alertMsg = $alerts -join " | "
            & $AdbPath -s $dev shell "cmd notification post -S bigtext -t 'Agent Alert' 'auto_alert' '$alertMsg'" 2>$null | Out-Null
            Write-Host "[$time] ⚠️ $($profile.model): $alertMsg" -ForegroundColor Red
            $profile.alertCount++
        }
        
        # Status line
        $status = "[$time] $($profile.model): 🔋${bat}% 💾${memPct}% 🌡${tempC}C"
        if ($alerts.Count -eq 0) {
            Write-Host $status -ForegroundColor Gray
        }
        
        $profile.lastBat = $bat
    }
    
    Start-Sleep -Seconds $Interval
}
