# Command Router - Level 1 规则引擎
# 零模型成本解析用户指令，路由到正确的ADB/API执行路径
# 用法: .\command_router.ps1 -Command "查看电池" -Device "R5CW2221VGL"

param(
    [Parameter(Mandatory=$true)]
    [string]$Command,
    [string]$Device = "",
    [string]$AdbPath = "e:\github\AIOT\ScreenStream_v2\090-构建与部署_Build\android-sdk\platform-tools\adb.exe",
    [string]$ApiBase = ""
)

# Auto-detect device
if (-not $Device) {
    $Device = (& $AdbPath devices 2>$null | Select-String "device$" | Select-Object -First 1 | ForEach-Object { ($_ -split '\s+')[0] })
}

# === Level 1: Rule-based Command Parser ===
# Pattern matching - no AI model needed

$cmd = $Command.Trim().ToLower()
$result = @{ok=$false; action="unknown"; detail=""}

# --- Battery/Power ---
if ($cmd -match "电[池量]|battery|充电") {
    $bat = ((& $AdbPath -s $Device shell "dumpsys battery" 2>$null) | Select-String "level|status|plugged" | ForEach-Object { $_.ToString().Trim() }) -join " | "
    $result = @{ok=$true; action="battery"; detail=$bat}
}
# --- Memory ---
elseif ($cmd -match "内存|memory|ram") {
    $mem = & $AdbPath -s $Device shell cat /proc/meminfo 2>$null
    $total = [math]::Round([int](($mem | Select-String "MemTotal" | ForEach-Object { ($_ -split '\s+')[1] }))/1024)
    $avail = [math]::Round([int](($mem | Select-String "MemAvailable" | ForEach-Object { ($_ -split '\s+')[1] }))/1024)
    $result = @{ok=$true; action="memory"; detail="可用${avail}MB / 总${total}MB ($([math]::Round(($total-$avail)/$total*100))%已用)"}
}
# --- Storage ---
elseif ($cmd -match "存储|storage|空间|磁盘") {
    $stor = (& $AdbPath -s $Device shell "df -h /sdcard" 2>$null | Select-Object -Last 1).Trim()
    $result = @{ok=$true; action="storage"; detail=$stor}
}
# --- Temperature ---
elseif ($cmd -match "温度|temperature|发热|发烫") {
    $temp = [int](& $AdbPath -s $Device shell cat /sys/class/thermal/thermal_zone0/temp 2>$null)
    $result = @{ok=$true; action="temperature"; detail="CPU: $([math]::Round($temp/1000,1))°C"}
}
# --- WiFi ---
elseif ($cmd -match "wifi|wlan|网络|联网") {
    $wifi = (& $AdbPath -s $Device shell "dumpsys wifi" 2>$null | Select-String "mWifiInfo" | Select-Object -First 1).ToString().Trim()
    $result = @{ok=$true; action="wifi"; detail=$wifi.Substring(0, [Math]::Min(100, $wifi.Length))}
}
# --- Screenshot ---
elseif ($cmd -match "截图|screenshot|截屏|拍屏") {
    & $AdbPath -s $Device shell screencap -p /sdcard/agent_cmd_screenshot.png 2>$null
    & $AdbPath -s $Device pull /sdcard/agent_cmd_screenshot.png "$env:TEMP\agent_cmd_screenshot.png" 2>$null | Out-Null
    $result = @{ok=$true; action="screenshot"; detail="已保存到 $env:TEMP\agent_cmd_screenshot.png"}
}
# --- Open App ---
elseif ($cmd -match "打开|启动|open|launch") {
    $appName = $cmd -replace '打开|启动|open|launch|\s',''
    $knownApps = @{
        "微信"="com.tencent.mm"; "wechat"="com.tencent.mm"
        "设置"="com.android.settings"; "settings"="com.android.settings"
        "相机"="intent:android.media.action.IMAGE_CAPTURE"
        "浏览器"="intent:android.intent.action.VIEW:https://www.baidu.com"
        "电话"="intent:android.intent.action.DIAL"
    }
    $pkg = $knownApps[$appName]
    if ($pkg -and $pkg.StartsWith("intent:")) {
        $parts = $pkg.Substring(7) -split ':',2
        & $AdbPath -s $Device shell "am start -a $($parts[0]) -d '$($parts[1])' --activity-clear-task" 2>$null | Out-Null
        $result = @{ok=$true; action="open_intent"; detail="已通过Intent打开: $appName"}
    } elseif ($pkg) {
        & $AdbPath -s $Device shell "monkey -p $pkg -c android.intent.category.LAUNCHER 1" 2>$null | Out-Null
        $result = @{ok=$true; action="open_app"; detail="已打开: $appName ($pkg)"}
    } else {
        $result = @{ok=$false; action="open_app"; detail="未知APP: $appName (需要Level 2模型辅助)"}
    }
}
# --- Home/Back/Recents ---
elseif ($cmd -match "回.*家|主页|home|桌面") {
    & $AdbPath -s $Device shell input keyevent KEYCODE_HOME 2>$null
    $result = @{ok=$true; action="home"; detail="已返回桌面"}
}
elseif ($cmd -match "返回|back|后退") {
    & $AdbPath -s $Device shell input keyevent KEYCODE_BACK 2>$null
    $result = @{ok=$true; action="back"; detail="已返回"}
}
# --- Notification ---
elseif ($cmd -match "通知|消息|notification|message") {
    if ($ApiBase) {
        try {
            $n = (Invoke-WebRequest -Uri "$ApiBase/notifications/read?limit=5" -TimeoutSec 5 -UseBasicParsing).Content | ConvertFrom-Json
            $detail = "共$($n.total)条通知。最近5条:`n"
            foreach ($notif in $n.notifications) {
                $pkg = $notif.package -replace 'com\.',''
                $title = if($notif.title){$notif.title}else{$notif.text}
                $detail += "  - [$pkg] $($title.Substring(0, [Math]::Min(40, $title.Length)))`n"
            }
            $result = @{ok=$true; action="notifications"; detail=$detail}
        } catch {
            $result = @{ok=$false; action="notifications"; detail="需要ScreenStream API (未连接)"}
        }
    } else {
        $result = @{ok=$false; action="notifications"; detail="需要ScreenStream API连接 (指定-ApiBase参数)"}
    }
}
# --- Device Info ---
elseif ($cmd -match "设备|手机|信息|status|型号") {
    $model = (& $AdbPath -s $Device shell getprop ro.product.model 2>$null).Trim()
    $mfr = (& $AdbPath -s $Device shell getprop ro.product.manufacturer 2>$null).Trim()
    $ver = (& $AdbPath -s $Device shell getprop ro.build.version.release 2>$null).Trim()
    $result = @{ok=$true; action="device_info"; detail="$model ($mfr) Android $ver"}
}
# --- Unknown: Needs Level 2+ ---
else {
    $result = @{ok=$false; action="unknown"; detail="Level 1无法解析: '$Command' → 需要升级到Level 2(小模型)或Level 3(大模型)"}
}

# === Output ===
if ($result.ok) {
    Write-Host "✅ [$($result.action)] $($result.detail)" -ForegroundColor Green
} else {
    Write-Host "❌ [$($result.action)] $($result.detail)" -ForegroundColor Yellow
}

# Notify phone
if ($result.ok) {
    & $AdbPath -s $Device shell "cmd notification post -S bigtext -t 'Agent' 'cmd_result' '$($result.detail.Substring(0, [Math]::Min(150, $result.detail.Length)))'" 2>$null | Out-Null
}

return $result
