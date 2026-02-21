# ScreenStream 开发环境一键部署脚本（Root 设备）
# 用法: .\dev-deploy.ps1 [-SkipBuild] [-SkipInstall]
param(
    [switch]$SkipBuild,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$ADB = "$PSScriptRoot\android-sdk\platform-tools\adb.exe"
$APK = "$ProjectRoot\010-用户界面与交互_UI\build\outputs\apk\FDroid\debug\app-FDroid-debug.apk"
$PKG = "info.dvkr.screenstream.dev"
$SVC = "$PKG/info.dvkr.screenstream.input.InputService"
$ACTIVITY = "$PKG/info.dvkr.screenstream.SingleActivity"

function Log($msg) { Write-Host "[Deploy] $msg" -ForegroundColor Cyan }
function Ok($msg) { Write-Host "[  OK  ] $msg" -ForegroundColor Green }
function Err($msg) { Write-Host "[ FAIL ] $msg" -ForegroundColor Red }

# 1. 检查 ADB 设备
Log "检查 ADB 设备..."
$devices = & $ADB devices 2>&1 | Select-String "device$"
if (-not $devices) { Err "未检测到 ADB 设备"; exit 1 }
Ok "设备已连接: $($devices.Line.Split("`t")[0])"

# 2. 编译（可跳过）
if (-not $SkipBuild) {
    Log "编译 APK..."
    $env:JAVA_HOME = "C:\Program Files\Processing\app\resources\jdk"
    $env:ANDROID_SDK_ROOT = "$PSScriptRoot\android-sdk"
    & "$ProjectRoot\gradlew.bat" assembleFDroidDebug --no-configuration-cache 2>&1 | Select-Object -Last 5
    if ($LASTEXITCODE -ne 0) { Err "编译失败"; exit 1 }
    Ok "编译成功"
}
else { Log "跳过编译" }

# 3. 推送安装（可跳过）
if (-not $SkipInstall) {
    Log "推送 APK..."
    & $ADB push $APK /data/local/tmp/ss.apk 2>&1 | Select-Object -Last 1
    $size = (Get-Item $APK).Length
    Log "安装 APK ($size bytes)..."
    & $ADB shell "cat /data/local/tmp/ss.apk | pm install -t -r -S $size" 2>&1
    if ($LASTEXITCODE -ne 0) { Err "安装失败"; exit 1 }
    Ok "安装成功"
}
else { Log "跳过安装" }

# 4. 启用 AccessibilityService（Root 方式，无需手动操作）
Log "启用 AccessibilityService..."
$current = & $ADB shell "settings get secure enabled_accessibility_services" 2>&1
if ($current -notlike "*$SVC*") {
    if ($current -eq "null" -or [string]::IsNullOrWhiteSpace($current)) {
        & $ADB shell "settings put secure enabled_accessibility_services $SVC" 2>&1
    }
    else {
        & $ADB shell "settings put secure enabled_accessibility_services `"$current`:$SVC`"" 2>&1
    }
    & $ADB shell "settings put secure accessibility_enabled 1" 2>&1
    Ok "AccessibilityService 已自动启用"
}
else {
    Ok "AccessibilityService 已处于启用状态"
}

# 4.5. 授权 UsageStats 权限（需 Magisk root，用于微信等阻止 AccessibilityService 的APP前台检测）
Log "授权 UsageStats 权限..."
$suResult = & $ADB shell "su -c `"appops set $PKG android:get_usage_stats allow`"" 2>&1
if ($LASTEXITCODE -eq 0) {
    Ok "UsageStats 权限已授权（via Magisk root）"
}
else {
    Log "UsageStats 授权失败（需 Magisk root），微信前台检测可能不可用"
}

# 5. 唤醒屏幕 + 配置端口 + 启动应用（全自动，无需手动操作）
$TARGET_PORT = 8086
Log "唤醒屏幕..."
& $ADB shell "input keyevent KEYCODE_WAKEUP" 2>&1 | Out-Null
Start-Sleep -Seconds 1

Log "发送 DEV_CONTROL 广播（端口=$TARGET_PORT）..."
& $ADB shell "am broadcast -a com.screenstream.DEV_CONTROL --ei port $TARGET_PORT -n $PKG/info.dvkr.screenstream.DevControlReceiver" 2>&1 | Out-Null
Start-Sleep -Seconds 4
Ok "DEV_CONTROL 广播已发送"

# 6. 端口转发（固定端口 + 探测补充）
Log "设置端口转发..."
& $ADB forward tcp:$TARGET_PORT tcp:$TARGET_PORT 2>&1 | Out-Null

$ssOutput = & $ADB shell "ss -tlnp 2>/dev/null" 2>$null
$ports = @($TARGET_PORT)
foreach ($line in $ssOutput) {
    if ($line -match '\*:(\d+)\s' -and [int]$Matches[1] -ge 8080 -and [int]$Matches[1] -le 8099) {
        if ($Matches[1] -ne $TARGET_PORT.ToString()) {
            $ports += $Matches[1]
            & $ADB forward tcp:$($Matches[1]) tcp:$($Matches[1]) 2>&1 | Out-Null
        }
    }
}
$ports = $ports | Sort-Object -Unique
Ok "端口转发完成: $($ports -join '/')"

# 7. 等待 Input API 就绪（优先检测目标端口）
Log "等待 Input API 就绪..."
$ready = $false
$apiPort = $null
for ($i = 0; $i -lt 15; $i++) {
    foreach ($p in $ports) {
        try {
            $resp = curl.exe -s --connect-timeout 2 http://127.0.0.1:${p}/status 2>$null
            if ($resp -like '*"connected":true*') {
                $ready = $true
                $apiPort = $p
                break
            }
        }
        catch {}
    }
    if ($ready) { break }
    Start-Sleep -Seconds 2
}

if ($ready) {
    Ok "Input API 就绪 (端口 $apiPort)"

    # 8. 全面 API 验证
    Log "运行 API 验证..."
    $pass = 0; $fail = 0

    # 基础
    foreach ($ep in @("/status", "/deviceinfo")) {
        $r = curl.exe -s --connect-timeout 2 "http://127.0.0.1:${apiPort}${ep}" 2>$null
        if ($r -and $r.Length -gt 5) { $pass++; Ok "  GET $ep" } else { $fail++; Err "  GET $ep" }
    }

    # 宏系统
    $r = curl.exe -s --connect-timeout 2 "http://127.0.0.1:${apiPort}/macro/list" 2>$null
    if ($r) { $pass++; Ok "  GET /macro/list" } else { $fail++; Err "  GET /macro/list" }

    $r = curl.exe -s --connect-timeout 2 "http://127.0.0.1:${apiPort}/macro/running" 2>$null
    if ($r) { $pass++; Ok "  GET /macro/running" } else { $fail++; Err "  GET /macro/running" }

    # AI Brain
    $r = curl.exe -s --connect-timeout 2 "http://127.0.0.1:${apiPort}/viewtree?depth=3" 2>$null
    if ($r -and $r.Length -gt 10) { $pass++; Ok "  GET /viewtree" } else { $fail++; Err "  GET /viewtree" }

    $r = curl.exe -s --connect-timeout 2 "http://127.0.0.1:${apiPort}/windowinfo" 2>$null
    if ($r) { $pass++; Ok "  GET /windowinfo" } else { $fail++; Err "  GET /windowinfo" }

    Ok "API 验证完成: $pass 通过, $fail 失败"
}
else {
    Err "Input API 未就绪（请在手机上解锁并点击'开始投屏'）"
    Log "提示: 手机需要解锁 + 开始投屏后 API 才可用"
    Log "解锁后可用 -SkipBuild -SkipInstall 参数重试验证"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "  ScreenStream v32+ 部署完成！" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
if ($apiPort) {
    Write-Host "  API 端口: $apiPort" -ForegroundColor Green
    Write-Host ""
    Write-Host "  快捷链接:" -ForegroundColor White
    Write-Host "  投屏页面  http://127.0.0.1:${apiPort}/" -ForegroundColor Cyan
    Write-Host "  状态查询  http://127.0.0.1:${apiPort}/status" -ForegroundColor Cyan
    Write-Host "  设备信息  http://127.0.0.1:${apiPort}/deviceinfo" -ForegroundColor Cyan
    Write-Host "  View树    http://127.0.0.1:${apiPort}/viewtree" -ForegroundColor Cyan
    Write-Host "  宏列表    http://127.0.0.1:${apiPort}/macro/list" -ForegroundColor Cyan
}
else {
    Write-Host "  已转发端口: $($ports -join '/')" -ForegroundColor White
    Write-Host "  请在手机上解锁并开始投屏后重试:" -ForegroundColor Yellow
    Write-Host "  .\dev-deploy.ps1 -SkipBuild -SkipInstall" -ForegroundColor Cyan
}
Write-Host "========================================" -ForegroundColor Yellow
