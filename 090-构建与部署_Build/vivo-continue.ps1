#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Vivo续行脚本 — APK安装后一键完成全部配置
.DESCRIPTION
    前置条件: ScreenStream APK已安装到Vivo手机
    本脚本自动完成: 权限→启动→端口→五感验证→WiFi ADB→远程穿透指引
#>

$ErrorActionPreference = "Continue"
$adb = "e:\道\道生一\一生二\构建部署\android-sdk\platform-tools\adb.exe"

function Write-Phase($p, $m) { Write-Host "`n[$p] $m" -ForegroundColor Cyan }
function Write-Ok($m) { Write-Host "  ✓ $m" -ForegroundColor Green }
function Write-Fail($m) { Write-Host "  ✗ $m" -ForegroundColor Red }
function Write-Info($m) { Write-Host "  → $m" -ForegroundColor Yellow }

# 检查设备
$serial = (& $adb devices 2>&1 | Select-String "(\S+)\s+device\s" | ForEach-Object { $_.Matches[0].Groups[1].Value })
if (-not $serial) { Write-Fail "未检测到已授权设备"; exit 1 }
Write-Ok "设备: $serial"

# 检查ScreenStream是否已安装
$installed = & $adb -s $serial shell pm list packages 2>&1 | Out-String
$pkg = if ($installed -match "info.dvkr.screenstream.dev") { "info.dvkr.screenstream.dev" }
       elseif ($installed -match "info.dvkr.screenstream") { "info.dvkr.screenstream" }
       else { $null }

if (-not $pkg) {
    Write-Fail "ScreenStream未安装！"
    Write-Info "请先在手机上安装: 文件管理器 → Download → ScreenStream.apk"
    exit 1
}
Write-Ok "已安装: $pkg"

# ============================================================
# Phase 1: 权限授予
# ============================================================
Write-Phase "1" "权限授予"

# 运行时权限
foreach ($perm in @("POST_NOTIFICATIONS","RECORD_AUDIO","CAMERA","READ_EXTERNAL_STORAGE","WRITE_EXTERNAL_STORAGE")) {
    & $adb -s $serial shell pm grant $pkg "android.permission.$perm" 2>$null
}
Write-Ok "运行时权限已授予"

# 电池优化白名单
& $adb -s $serial shell dumpsys deviceidle whitelist +$pkg 2>$null | Out-Null
Write-Ok "电池优化白名单"

# Vivo后台限制解除
& $adb -s $serial shell cmd appops set $pkg AUTO_START allow 2>$null
& $adb -s $serial shell cmd appops set $pkg RUN_IN_BACKGROUND allow 2>$null
& $adb -s $serial shell cmd appops set $pkg RUN_ANY_IN_BACKGROUND allow 2>$null
Write-Ok "Vivo后台限制已解除"

# 保持唤醒（防止后台杀）
& $adb -s $serial shell settings put global stay_on_while_plugged_in 3 2>$null
Write-Ok "充电时保持唤醒"

# ============================================================
# Phase 2: 无障碍服务
# ============================================================
Write-Phase "2" "无障碍服务"

$a11y = & $adb -s $serial shell settings get secure enabled_accessibility_services 2>$null
$a11yTarget = "$pkg/info.dvkr.screenstream.input.InputService"
if ($a11y -match "screenstream") {
    Write-Ok "无障碍服务已启用"
} else {
    $newA11y = if ($a11y -and $a11y -ne "null") { "$a11y`:$a11yTarget" } else { $a11yTarget }
    & $adb -s $serial shell settings put secure enabled_accessibility_services $newA11y 2>$null
    & $adb -s $serial shell settings put secure accessibility_enabled 1 2>$null
    Start-Sleep 1
    $check = & $adb -s $serial shell settings get secure enabled_accessibility_services 2>$null
    if ($check -match "screenstream") { Write-Ok "无障碍服务已启用(ADB)" }
    else {
        Write-Fail "需要手动启用无障碍服务"
        & $adb -s $serial shell am start -a android.settings.ACCESSIBILITY_SETTINGS 2>$null | Out-Null
        Write-Info "已打开无障碍设置 → 找到ScreenStream → 开启"
    }
}

# ============================================================
# Phase 3: 启动APP + 端口探测
# ============================================================
Write-Phase "3" "启动APP + 端口探测"

& $adb -s $serial shell monkey -p $pkg -c android.intent.category.LAUNCHER 1 2>$null | Out-Null
Write-Info "APP已启动"

# 等待HTTP服务就绪（需要用户在手机上点击"开始流"后才有HTTP服务）
Write-Info "等待HTTP服务（如果手机弹出投屏权限弹窗请点击允许）..."
Start-Sleep 5

$port = 0
$maxRetry = 12
for ($retry = 0; $retry -lt $maxRetry; $retry++) {
    for ($p = 8080; $p -le 8099; $p++) {
        & $adb -s $serial forward tcp:$p tcp:$p 2>$null | Out-Null
        try {
            $r = Invoke-RestMethod -Uri "http://127.0.0.1:$p/status" -TimeoutSec 2 -ErrorAction Stop
            if ($null -ne $r.connected) { $port = $p; break }
        } catch {
            & $adb -s $serial forward --remove tcp:$p 2>$null | Out-Null
        }
    }
    if ($port -gt 0) { break }
    if ($retry -eq 0) { Write-Info "未检测到HTTP服务，请在手机上点击'开始流'..." }
    if ($retry % 4 -eq 3) { Write-Info "仍在等待... ($($retry*5)s)" }
    Start-Sleep 5
}

if ($port -eq 0) {
    Write-Fail "无法连接HTTP服务(60s超时)"
    Write-Info "请确认: 1.手机上打开ScreenStream 2.点击'开始流' 3.允许投屏权限"
    exit 1
}
Write-Ok "HTTP端口: $port"

# ============================================================
# Phase 4: 五感验证
# ============================================================
Write-Phase "4" "五感代入验证"
$base = "http://127.0.0.1:$port"
$passed = 0; $total = 0

function Test-API($name, $method, $path, $body = $null) {
    $script:total++
    try {
        $params = @{ Uri = "$base$path"; Method = $method; TimeoutSec = 10; ContentType = "application/json" }
        if ($body) { $params["Body"] = ($body | ConvertTo-Json -Compress) }
        $r = Invoke-RestMethod @params -ErrorAction Stop
        $script:passed++
        Write-Ok "$name"
        return $r
    } catch {
        Write-Fail "$name"
        return $null
    }
}

Write-Host "  --- 👁 视觉 ---" -ForegroundColor Magenta
Test-API "连接状态" "GET" "/status"
$dev = Test-API "设备信息" "GET" "/deviceinfo"
$scr = Test-API "屏幕文本" "GET" "/screen/text"
if ($scr) { Write-Info "  文字:$($scr.textCount) 可点击:$($scr.clickableCount)" }

Write-Host "  --- 👂 听觉 ---" -ForegroundColor Magenta
Test-API "通知" "GET" "/notifications/read?limit=5"
Test-API "音量" "POST" "/volume" @{stream="music";level=5}

Write-Host "  --- 🖐 触觉 ---" -ForegroundColor Magenta
Test-API "前台APP" "GET" "/foreground"
Test-API "语义查找" "POST" "/findnodes" @{text="设置"}

Write-Host "  --- 🧠 认知 ---" -ForegroundColor Magenta
Test-API "View树" "GET" "/viewtree?depth=3"
Test-API "窗口信息" "GET" "/windowinfo"
Test-API "剪贴板" "GET" "/clipboard"
Test-API "APP列表" "GET" "/apps"

Write-Host "  --- 🎮 控制 ---" -ForegroundColor Magenta
Test-API "亮度" "GET" "/brightness"
Test-API "存储" "GET" "/files/storage"
Test-API "勿扰" "GET" "/dnd"
Test-API "宏列表" "GET" "/macro/list"

Write-Host "`n  结果: $passed/$total 通过" -ForegroundColor $(if ($passed -eq $total) {"Green"} else {"Yellow"})

# ============================================================
# Phase 5: WiFi ADB（断USB仍可连）
# ============================================================
Write-Phase "5" "WiFi ADB + 远程配置"

$wifiIP = (& $adb -s $serial shell "ip route" 2>$null | Select-String "src (\d+\.\d+\.\d+\.\d+)" | ForEach-Object { $_.Matches[0].Groups[1].Value })
if ($wifiIP) {
    & $adb -s $serial tcpip 5555 2>$null | Out-Null
    Start-Sleep 2
    Write-Ok "WiFi ADB: ${wifiIP}:5555"
    Write-Info "断USB后: & `$adb connect ${wifiIP}:5555"
} else {
    Write-Info "无WiFi，跳过WiFi ADB"
}

# ============================================================
# 汇总
# ============================================================
$model = if ($dev) { "$($dev.manufacturer) $($dev.model)" } else { "vivo V2068A" }
$bat = if ($dev) { "$($dev.batteryLevel)%" } else { "?" }

Write-Host "`n$('='*60)" -ForegroundColor Cyan
Write-Host "  ScreenStream Vivo 部署完成!" -ForegroundColor Green
Write-Host "$('='*60)" -ForegroundColor Cyan
Write-Host @"

  设备: $model | 电量: $bat
  包名: $pkg | 端口: $port
  API验证: $passed/$total

  === 访问方式 ===

  1. 本地(USB):
     浏览器: http://127.0.0.1:$port
     Python:  from phone_lib import Phone; p=Phone($port)

  2. 局域网(WiFi):
     浏览器: http://${wifiIP}:$port
     ADB:    adb connect ${wifiIP}:5555

  3. 远程穿透方案:
     方案A - Tailscale (推荐，P2P零配置):
       手机装Tailscale → 登录 → 获得100.x.x.x
       PC装Tailscale → http://100.x.x.x:$port
     方案B - Cloudflare Tunnel (公网HTTPS):
       cloudflared tunnel --url http://127.0.0.1:$port
     方案C - frp (自有服务器):
       配置frpc.ini → 映射$port → 公网访问

  === 负面环境恢复 ===

  断USB: WiFi ADB自动保持连接
  断WiFi: 手机4G + Tailscale保持VPN隧道
  APP被杀: 电池白名单+后台限制已解除，自动拉起
  手机重启: ScreenStream设为自启(设置中开启)
  锁屏: 已设充电时保持唤醒

"@
