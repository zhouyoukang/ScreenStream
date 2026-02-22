#!/usr/bin/env pwsh
<#
.SYNOPSIS
    ScreenStream Vivo一键部署脚本 — 从零到远程操控全链路
.DESCRIPTION
    Phase 1: ADB授权检测 + 设备识别
    Phase 2: APK安装 + 权限授予
    Phase 3: 无障碍服务激活 + 端口转发
    Phase 4: WiFi ADB配置（断USB后仍可连）
    Phase 5: API全量验证（五感代入）
    Phase 6: 远程穿透方案部署
#>

$ErrorActionPreference = "Continue"
$adb = "e:\道\道生一\一生二\构建部署\android-sdk\platform-tools\adb.exe"
$apk = "e:\道\道生一\一生二\用户界面\build\outputs\apk\FDroid\debug\app-FDroid-debug.apk"
$pkg = "info.dvkr.screenstream"
$pkgDev = "info.dvkr.screenstream.dev"
$serial = ""
$port = 0

function Write-Phase($phase, $msg) {
    Write-Host "`n[$phase] $msg" -ForegroundColor Cyan
}
function Write-Ok($msg) { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "  ✗ $msg" -ForegroundColor Red }
function Write-Info($msg) { Write-Host "  → $msg" -ForegroundColor Yellow }

# ============================================================
# Phase 1: ADB 授权检测
# ============================================================
Write-Phase "Phase 1" "ADB 授权检测"

# 检测设备
$maxWait = 60
$waited = 0
while ($waited -lt $maxWait) {
    $raw = & $adb devices 2>&1 | Out-String
    # 查找已授权设备
    if ($raw -match "(\S+)\s+device\s") {
        $serial = $Matches[1]
        Write-Ok "设备已授权: $serial"
        break
    }
    # 查找未授权设备
    if ($raw -match "(\S+)\s+unauthorized") {
        $unauth = $Matches[1]
        if ($waited -eq 0) {
            Write-Info "设备 $unauth 未授权 — 请在手机屏幕上点击'允许USB调试'"
            Write-Info "等待授权中（最多${maxWait}秒）..."
        }
        if ($waited % 10 -eq 0 -and $waited -gt 0) {
            Write-Info "仍在等待... (${waited}s) 如果没有弹窗请拔插USB线"
        }
    } elseif ($waited -eq 0) {
        Write-Info "未检测到设备，请确认USB连接..."
    }
    Start-Sleep 3
    $waited += 3
}

if (-not $serial) {
    Write-Fail "超时：未检测到已授权设备"
    Write-Host "解决方案:" -ForegroundColor Yellow
    Write-Host "  1. 手机设置 → 开发者选项 → 开启USB调试"
    Write-Host "  2. 拔掉USB线重新插入"
    Write-Host "  3. 手机屏幕弹窗点击'允许'"
    exit 1
}

# 获取设备信息
Write-Info "获取设备信息..."
$model = (& $adb -s $serial shell getprop ro.product.model 2>$null).Trim()
$brand = (& $adb -s $serial shell getprop ro.product.brand 2>$null).Trim()
$android = (& $adb -s $serial shell getprop ro.build.version.release 2>$null).Trim()
$sdk = (& $adb -s $serial shell getprop ro.build.version.sdk 2>$null).Trim()
Write-Ok "设备: $brand $model | Android $android (API $sdk)"

# ============================================================
# Phase 2: APK 安装
# ============================================================
Write-Phase "Phase 2" "APK 安装"

# 检查APK是否存在
if (-not (Test-Path $apk)) {
    Write-Info "APK不存在，需要构建..."
    Write-Info "正在执行 Gradle 构建（可能需要2-5分钟）..."
    Push-Location "e:\道\道生一\一生二"
    & .\gradlew.bat :app:assembleFDroidDebug 2>&1 | Select-Object -Last 5
    Pop-Location
    if (-not (Test-Path $apk)) {
        Write-Fail "构建失败，请检查 Gradle 配置"
        exit 1
    }
}

$apkSize = [math]::Round((Get-Item $apk).Length / 1MB, 1)
$apkDate = (Get-Item $apk).LastWriteTime.ToString("yyyy-MM-dd HH:mm")
Write-Info "APK: $apkSize MB (构建于 $apkDate)"

# 检查是否已安装
$installed = & $adb -s $serial shell pm list packages 2>$null | Out-String
$targetPkg = if ($installed -match $pkgDev) { $pkgDev } elseif ($installed -match $pkg) { $pkg } else { $null }

if ($targetPkg) {
    Write-Info "已安装 $targetPkg，执行覆盖安装..."
} else {
    Write-Info "首次安装..."
}

# 安装APK
& $adb -s $serial install -r -g $apk 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Ok "APK 安装成功"
} else {
    # Vivo可能需要允许USB安装
    Write-Fail "安装失败 — Vivo可能拦截了USB安装"
    Write-Info "请在手机上查看是否有安装确认弹窗并点击'继续安装'"
    Start-Sleep 10
    & $adb -s $serial install -r -g $apk 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "APK 安装成功（第二次尝试）"
    } else {
        Write-Fail "安装仍然失败。请手动在手机上允许USB安装应用"
        Write-Info "设置 → 安全 → 允许通过USB安装应用"
    }
}

# 重新检测包名
$installed = & $adb -s $serial shell pm list packages 2>$null | Out-String
$targetPkg = if ($installed -match "info.dvkr.screenstream.dev") { "info.dvkr.screenstream.dev" } 
             elseif ($installed -match "info.dvkr.screenstream") { "info.dvkr.screenstream" } 
             else { "info.dvkr.screenstream" }
Write-Info "目标包名: $targetPkg"

# ============================================================
# Phase 3: 权限授予 + 无障碍服务
# ============================================================
Write-Phase "Phase 3" "权限授予 + 无障碍服务"

# 授予运行时权限
$permissions = @(
    "android.permission.POST_NOTIFICATIONS",
    "android.permission.RECORD_AUDIO",
    "android.permission.CAMERA",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE"
)
foreach ($perm in $permissions) {
    $r = & $adb -s $serial shell pm grant $targetPkg $perm 2>&1
    $shortPerm = $perm.Split(".")[-1]
    if ($r -notmatch "Exception|Unknown") {
        Write-Ok "权限: $shortPerm"
    } else {
        Write-Info "权限 $shortPerm 可能不适用于此API级别（跳过）"
    }
}

# 禁用电池优化（防止后台被杀）
& $adb -s $serial shell dumpsys deviceidle whitelist +$targetPkg 2>$null | Out-Null
Write-Ok "电池优化白名单已添加"

# 禁用Vivo自启限制
& $adb -s $serial shell cmd appops set $targetPkg AUTO_START allow 2>$null | Out-Null
& $adb -s $serial shell cmd appops set $targetPkg RUN_IN_BACKGROUND allow 2>$null | Out-Null
& $adb -s $serial shell cmd appops set $targetPkg RUN_ANY_IN_BACKGROUND allow 2>$null | Out-Null
Write-Ok "Vivo后台限制已解除"

# 检查无障碍服务状态
$a11y = & $adb -s $serial shell settings get secure enabled_accessibility_services 2>$null
$a11yTarget = "$targetPkg/info.dvkr.screenstream.input.InputService"
if ($a11y -match "screenstream") {
    Write-Ok "无障碍服务已启用"
} else {
    Write-Info "正在启用无障碍服务..."
    # 尝试直接启用（需要设备支持）
    if ($a11y -and $a11y -ne "null") {
        $newA11y = "$a11y`:$a11yTarget"
    } else {
        $newA11y = $a11yTarget
    }
    & $adb -s $serial shell settings put secure enabled_accessibility_services $newA11y 2>$null
    & $adb -s $serial shell settings put secure accessibility_enabled 1 2>$null
    Start-Sleep 1
    $check = & $adb -s $serial shell settings get secure enabled_accessibility_services 2>$null
    if ($check -match "screenstream") {
        Write-Ok "无障碍服务已通过ADB启用"
    } else {
        Write-Fail "无法通过ADB启用无障碍服务（Vivo安全限制）"
        Write-Info "请手动操作：设置 → 无障碍 → ScreenStream → 开启"
        # 自动跳转到无障碍设置页
        & $adb -s $serial shell am start -a android.settings.ACCESSIBILITY_SETTINGS 2>$null | Out-Null
        Write-Info "已打开手机无障碍设置页面，请找到ScreenStream并启用"
        Read-Host "启用后按Enter继续"
    }
}

# ============================================================
# Phase 4: 启动APP + 端口探测 + 转发
# ============================================================
Write-Phase "Phase 4" "启动APP + 端口探测"

# 启动APP
& $adb -s $serial shell monkey -p $targetPkg -c android.intent.category.LAUNCHER 1 2>$null | Out-Null
Write-Info "APP已启动，等待HTTP服务就绪..."
Start-Sleep 5

# 探测端口（8080-8099）
$port = 0
for ($p = 8080; $p -le 8099; $p++) {
    & $adb -s $serial forward tcp:$p tcp:$p 2>$null | Out-Null
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:$p/status" -TimeoutSec 2 -ErrorAction Stop
        if ($resp.connected -ne $null) {
            $port = $p
            Write-Ok "ScreenStream HTTP 端口: $port"
            break
        }
    } catch {
        & $adb -s $serial forward --remove tcp:$p 2>$null | Out-Null
    }
}

if ($port -eq 0) {
    Write-Fail "未找到ScreenStream HTTP服务"
    Write-Info "可能原因：1.APP未开启投屏 2.无障碍服务未启用"
    Write-Info "请在手机上打开ScreenStream并点击'开始流'"
    
    # 等待用户操作后重试
    for ($retry = 0; $retry -lt 6; $retry++) {
        Start-Sleep 5
        for ($p = 8080; $p -le 8099; $p++) {
            & $adb -s $serial forward tcp:$p tcp:$p 2>$null | Out-Null
            try {
                $resp = Invoke-RestMethod -Uri "http://127.0.0.1:$p/status" -TimeoutSec 2 -ErrorAction Stop
                if ($resp.connected -ne $null) {
                    $port = $p
                    break
                }
            } catch {
                & $adb -s $serial forward --remove tcp:$p 2>$null | Out-Null
            }
        }
        if ($port -gt 0) { break }
        Write-Info "重试 $($retry+1)/6..."
    }
    
    if ($port -gt 0) {
        Write-Ok "ScreenStream HTTP 端口: $port"
    } else {
        Write-Fail "无法连接到ScreenStream HTTP服务，请手动检查"
        exit 1
    }
}

# 转发所有相关端口
& $adb -s $serial forward tcp:$port tcp:$port 2>$null | Out-Null
Write-Ok "端口转发 tcp:$port → 手机:$port"

# ============================================================
# Phase 5: 五感验证
# ============================================================
Write-Phase "Phase 5" "五感代入验证"
$base = "http://127.0.0.1:$port"
$passed = 0
$total = 0

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
        Write-Fail "$name - $($_.Exception.Message)"
        return $null
    }
}

Write-Host "`n  --- 👁 视觉(Vision) ---" -ForegroundColor Magenta
Test-API "连接状态" "GET" "/status"
Test-API "设备信息" "GET" "/deviceinfo"
$screenText = Test-API "屏幕文本" "GET" "/screen/text"
if ($screenText) {
    Write-Info "  屏幕文字数: $($screenText.textCount), 可点击: $($screenText.clickableCount)"
}

Write-Host "`n  --- 👂 听觉(Hearing) ---" -ForegroundColor Magenta
Test-API "通知列表" "GET" "/notifications/read?limit=5"
Test-API "音量控制" "POST" "/volume" @{stream="music";level=5}

Write-Host "`n  --- 🖐 触觉(Touch) ---" -ForegroundColor Magenta
Test-API "语义查找" "POST" "/findnodes" @{text="设置"}
Test-API "前台APP" "GET" "/foreground"

Write-Host "`n  --- 🧠 认知(Cognition) ---" -ForegroundColor Magenta
Test-API "View树" "GET" "/viewtree?depth=3"
Test-API "窗口信息" "GET" "/windowinfo"
Test-API "剪贴板读" "GET" "/clipboard"
Test-API "APP列表" "GET" "/apps"

Write-Host "`n  --- 🎮 控制(Control) ---" -ForegroundColor Magenta
Test-API "亮度查询" "GET" "/brightness"
Test-API "自动旋转" "GET" "/autorotate"
Test-API "勿扰模式" "GET" "/dnd"
Test-API "常亮状态" "GET" "/stayawake"
Test-API "文件存储" "GET" "/files/storage"

Write-Host "`n  结果: $passed/$total 通过" -ForegroundColor $(if ($passed -eq $total) { "Green" } else { "Yellow" })

# ============================================================
# Phase 6: WiFi ADB（断USB后仍可连）
# ============================================================
Write-Phase "Phase 6" "WiFi ADB 配置"

$wifiIP = (& $adb -s $serial shell ip route 2>$null | Select-String "src (\d+\.\d+\.\d+\.\d+)" | ForEach-Object { $_.Matches[0].Groups[1].Value })
if ($wifiIP) {
    & $adb -s $serial tcpip 5555 2>$null | Out-Null
    Start-Sleep 2
    Write-Ok "WiFi ADB 已开启: $wifiIP`:5555"
    Write-Info "断开USB后可用: & `$adb connect $wifiIP`:5555"
} else {
    Write-Info "未检测到WiFi，跳过WiFi ADB"
}

# ============================================================
# 汇总
# ============================================================
Write-Host "`n" + "="*60 -ForegroundColor Cyan
Write-Host "  部署完成！" -ForegroundColor Green
Write-Host "="*60 -ForegroundColor Cyan
Write-Host ""
Write-Host "  设备: $brand $model (Android $android)" -ForegroundColor White
Write-Host "  包名: $targetPkg" -ForegroundColor White
Write-Host "  端口: $port" -ForegroundColor White
Write-Host "  API:  $passed/$total 通过" -ForegroundColor $(if ($passed -eq $total) { "Green" } else { "Yellow" })
Write-Host ""
Write-Host "  本地访问:" -ForegroundColor Yellow
Write-Host "    浏览器: http://127.0.0.1:$port" -ForegroundColor White
Write-Host "    API:    Invoke-RestMethod http://127.0.0.1:$port/status" -ForegroundColor White
Write-Host "    Python: from phone_lib import Phone; p=Phone($port)" -ForegroundColor White
if ($wifiIP) {
    Write-Host ""
    Write-Host "  WiFi访问（同局域网）:" -ForegroundColor Yellow
    Write-Host "    浏览器: http://$wifiIP`:$port" -ForegroundColor White
    Write-Host "    连接:   & `$adb connect $wifiIP`:5555" -ForegroundColor White
}
Write-Host ""
Write-Host "  远程穿透（任意网络）:" -ForegroundColor Yellow
Write-Host "    方案A - Tailscale（推荐）:" -ForegroundColor White
Write-Host "      手机装Tailscale → 登录 → 自动获得100.x.x.x IP" -ForegroundColor DarkGray
Write-Host "      PC装Tailscale → 直接访问 http://100.x.x.x:$port" -ForegroundColor DarkGray
Write-Host "    方案B - Cloudflare Tunnel:" -ForegroundColor White
Write-Host "      cloudflared tunnel --url http://127.0.0.1:$port" -ForegroundColor DarkGray
Write-Host "      获得公网HTTPS地址，任何浏览器可访问" -ForegroundColor DarkGray
Write-Host ""
