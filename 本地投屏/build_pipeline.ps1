# ScreenStream 本地投屏 · 渐进式构建管线
# 用法:
#   .\build_pipeline.ps1                    # 全链路: 构建→部署→验证
#   .\build_pipeline.ps1 -Phase build       # 仅构建
#   .\build_pipeline.ps1 -Phase deploy      # 仅部署(跳过构建)
#   .\build_pipeline.ps1 -Phase verify      # 仅验证(跳过构建+部署)
#   .\build_pipeline.ps1 -Phase e2e         # 端到端完整测试
#   .\build_pipeline.ps1 -Device OnePlus    # 指定设备
#   .\build_pipeline.ps1 -Clean             # 清理后重建
param(
    [ValidateSet("all", "build", "deploy", "verify", "e2e")]
    [string]$Phase = "all",
    [string]$Device = "",
    [switch]$Clean,
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$script:StartTime = Get-Date
$script:ProjectRoot = Split-Path $PSScriptRoot -Parent
$script:ADB = "D:\platform-tools\adb.exe"
$script:AndroidSdk = "E:\Android\Sdk"
$script:JavaHome = "E:\CacheMigration\.gradle\jdks\eclipse_adoptium-17-amd64-windows.2"
$script:PKG = "info.dvkr.screenstream.dev"
$script:SVC = "$script:PKG/info.dvkr.screenstream.input.InputService"
$script:APK_PATH = "$script:ProjectRoot\010-用户界面与交互_UI\build\outputs\apk\FDroid\debug\app-FDroid-debug.apk"
$script:PassCount = 0
$script:FailCount = 0
$script:WarnCount = 0
$script:PhaseResults = @{}

# ═══════════════════════════════════════════════
# 日志系统
# ═══════════════════════════════════════════════
function Log($msg) { Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $msg" -ForegroundColor Cyan }
function Ok($msg) { $script:PassCount++; Write-Host "[  OK  ] $msg" -ForegroundColor Green }
function Warn($msg) { $script:WarnCount++; Write-Host "[ WARN ] $msg" -ForegroundColor Yellow }
function Err($msg) { $script:FailCount++; Write-Host "[ FAIL ] $msg" -ForegroundColor Red }
function Step($n, $msg) { Write-Host "`n═══ Phase $n: $msg ═══" -ForegroundColor Magenta }

# ═══════════════════════════════════════════════
# Phase 0: 环境检查
# ═══════════════════════════════════════════════
function Test-Environment {
    Step 0 "环境检查"
    
    # ADB
    if (Test-Path $script:ADB) { Ok "ADB: $script:ADB" }
    else { Err "ADB not found: $script:ADB"; return $false }
    
    # Android SDK
    if (Test-Path $script:AndroidSdk) { Ok "Android SDK: $script:AndroidSdk" }
    else { Err "Android SDK not found: $script:AndroidSdk"; return $false }
    
    # Gradle wrapper
    $gradlew = "$script:ProjectRoot\gradlew.bat"
    if (Test-Path $gradlew) { Ok "Gradle wrapper: $gradlew" }
    else { Err "gradlew.bat not found"; return $false }
    
    # Debug key
    $debugKey = "$script:ProjectRoot\gradle\debug-key.jks"
    if (Test-Path $debugKey) { Ok "Debug key: $debugKey" }
    else { Warn "Debug key not found (will use default)" }
    
    # 设备
    $devices = & $script:ADB devices -l 2>&1 | Where-Object { $_ -match "device\s" -and $_ -notmatch "^List" }
    if ($devices) {
        foreach ($d in $devices) {
            if ($d -match "^(\S+)\s+device.*model:(\S+)") {
                Ok "Device: $($Matches[2]) [$($Matches[1])]"
            }
        }
    }
    else {
        Warn "No ADB devices connected"
    }
    
    # Java
    try {
        $javaVer = & java -version 2>&1 | Select-Object -First 1
        Ok "Java: $javaVer"
    }
    catch {
        Warn "Java not in PATH (Gradle will use its own)"
    }
    
    # Git状态
    $branch = & git -C $script:ProjectRoot rev-parse --abbrev-ref HEAD 2>$null
    $commit = & git -C $script:ProjectRoot rev-parse --short HEAD 2>$null
    Ok "Git: $branch @ $commit"
    
    $script:PhaseResults["environment"] = "PASS"
    return $true
}

# ═══════════════════════════════════════════════
# Phase 1: 从源码构建 APK
# ═══════════════════════════════════════════════
function Invoke-Build {
    Step 1 "从源码构建 APK (assembleFDroidDebug)"
    
    $env:ANDROID_SDK_ROOT = $script:AndroidSdk
    $env:JAVA_HOME = $script:JavaHome
    $gradlew = "$script:ProjectRoot\gradlew.bat"
    
    if ($Clean) {
        Log "清理旧构建..."
        & $gradlew clean --no-configuration-cache 2>&1 | Select-Object -Last 3
        Ok "清理完成"
    }
    
    Log "开始编译 (这可能需要几分钟)..."
    $buildStart = Get-Date
    
    $buildOutput = & $gradlew assembleFDroidDebug --no-configuration-cache 2>&1
    $buildExit = $LASTEXITCODE
    $buildDuration = (Get-Date) - $buildStart
    
    if ($Verbose) {
        $buildOutput | Select-Object -Last 20
    }
    else {
        $buildOutput | Select-Object -Last 5
    }
    
    if ($buildExit -ne 0) {
        Err "构建失败 (exit=$buildExit, 耗时=$([math]::Round($buildDuration.TotalSeconds))s)"
        # 输出错误行
        $buildOutput | Where-Object { $_ -match "error|Error|ERROR" } | Select-Object -Last 10
        $script:PhaseResults["build"] = "FAIL"
        return $false
    }
    
    if (Test-Path $script:APK_PATH) {
        $apkSize = [math]::Round((Get-Item $script:APK_PATH).Length / 1MB, 2)
        $apkTime = (Get-Item $script:APK_PATH).LastWriteTime
        Ok "构建成功: ${apkSize}MB ($([math]::Round($buildDuration.TotalSeconds))s)"
        Ok "APK: $script:APK_PATH"
        Ok "时间: $apkTime"
    }
    else {
        Err "APK文件未生成"
        $script:PhaseResults["build"] = "FAIL"
        return $false
    }
    
    $script:PhaseResults["build"] = "PASS"
    return $true
}

# ═══════════════════════════════════════════════
# Phase 2: 部署到手机
# ═══════════════════════════════════════════════
function Invoke-Deploy {
    Step 2 "部署到手机"
    
    # 选择设备
    $targetSerial = Get-TargetDevice
    if (-not $targetSerial) {
        Err "无可用设备"
        $script:PhaseResults["deploy"] = "FAIL"
        return $false
    }
    
    Log "目标设备: $targetSerial"
    
    # 唤醒屏幕
    Log "唤醒屏幕..."
    & $script:ADB -s $targetSerial shell "input keyevent KEYCODE_WAKEUP" 2>&1 | Out-Null
    Start-Sleep -Seconds 1
    
    # 卸载旧版(如存在)
    Log "检查旧版本..."
    $oldPkg = & $script:ADB -s $targetSerial shell "pm list packages $script:PKG" 2>&1
    if ($oldPkg -match $script:PKG) {
        Log "卸载旧版本..."
        & $script:ADB -s $targetSerial uninstall $script:PKG 2>&1 | Out-Null
        Ok "旧版本已卸载"
    }
    
    # 安装新版
    Log "安装APK..."
    $installResult = & $script:ADB -s $targetSerial install -r -t $script:APK_PATH 2>&1
    if ($installResult -match "Success") {
        Ok "安装成功"
    }
    else {
        Err "安装失败: $installResult"
        $script:PhaseResults["deploy"] = "FAIL"
        return $false
    }
    
    # 启用 AccessibilityService (Root方式)
    Log "启用 AccessibilityService..."
    $current = & $script:ADB -s $targetSerial shell "settings get secure enabled_accessibility_services" 2>&1
    if ($current -notlike "*$script:SVC*") {
        if ($current -eq "null" -or [string]::IsNullOrWhiteSpace($current)) {
            & $script:ADB -s $targetSerial shell "settings put secure enabled_accessibility_services $script:SVC" 2>&1 | Out-Null
        }
        else {
            & $script:ADB -s $targetSerial shell "settings put secure enabled_accessibility_services `"$current`:$script:SVC`"" 2>&1 | Out-Null
        }
        & $script:ADB -s $targetSerial shell "settings put secure accessibility_enabled 1" 2>&1 | Out-Null
        Ok "AccessibilityService 已启用"
    }
    else {
        Ok "AccessibilityService 已处于启用状态"
    }
    
    # 授权 UsageStats (需Root)
    Log "授权 UsageStats..."
    $suResult = & $script:ADB -s $targetSerial shell "su -c `"appops set $script:PKG android:get_usage_stats allow`"" 2>&1
    if ($LASTEXITCODE -eq 0) { Ok "UsageStats 已授权" }
    else { Warn "UsageStats 授权失败(需Root)" }
    
    # 启动APP
    Log "启动 ScreenStream..."
    & $script:ADB -s $targetSerial shell "am start -n $script:PKG/info.dvkr.screenstream.SingleActivity" 2>&1 | Out-Null
    Start-Sleep -Seconds 3
    Ok "APP已启动"
    
    # 端口转发
    Log "设置端口转发..."
    $ports = @()
    $ssOutput = & $script:ADB -s $targetSerial shell "ss -tlnp 2>/dev/null" 2>$null
    foreach ($line in $ssOutput) {
        if ($line -match '\*:(\d+)\s' -and [int]$Matches[1] -ge 8080 -and [int]$Matches[1] -le 8099) {
            $port = $Matches[1]
            & $script:ADB -s $targetSerial forward "tcp:$port" "tcp:$port" 2>&1 | Out-Null
            $ports += $port
        }
    }
    if ($ports.Count -gt 0) {
        Ok "端口转发: $($ports -join ', ')"
    }
    else {
        Warn "未检测到SS监听端口(APP可能尚未开始投屏)"
        # 转发默认端口
        foreach ($p in @(8080, 8081, 8084)) {
            & $script:ADB -s $targetSerial forward "tcp:$p" "tcp:$p" 2>&1 | Out-Null
        }
        Ok "已转发默认端口: 8080, 8081, 8084"
    }
    
    $script:PhaseResults["deploy"] = "PASS"
    return $true
}

# ═══════════════════════════════════════════════
# Phase 3: API验证
# ═══════════════════════════════════════════════
function Invoke-Verify {
    Step 3 "API验证"
    
    # 探测可用端口
    $apiPort = $null
    Log "探测API端口..."
    foreach ($p in @(8080, 8081, 8082, 8083, 8084, 8085, 8086, 8087, 8088, 8089)) {
        try {
            $resp = curl.exe -s --connect-timeout 2 "http://127.0.0.1:${p}/status" 2>$null
            if ($resp -and $resp.Length -gt 5) {
                $apiPort = $p
                Ok "API端口: $p"
                break
            }
        }
        catch {}
    }
    
    if (-not $apiPort) {
        Warn "未找到API端口(请确保手机已开始投屏)"
        $script:PhaseResults["verify"] = "SKIP"
        return $false
    }
    
    # 基础API测试
    $endpoints = @(
        @{ Path = "/status"; Name = "状态查询" },
        @{ Path = "/deviceinfo"; Name = "设备信息" },
        @{ Path = "/apps"; Name = "应用列表" },
        @{ Path = "/viewtree?depth=2"; Name = "View树" },
        @{ Path = "/macro/list"; Name = "宏列表" },
        @{ Path = "/screen/text"; Name = "屏幕文本(AI)" },
        @{ Path = "/windowinfo"; Name = "窗口信息" },
        @{ Path = "/foreground"; Name = "前台应用" }
    )
    
    $verifyPass = 0; $verifyFail = 0
    foreach ($ep in $endpoints) {
        try {
            $resp = curl.exe -s --connect-timeout 3 "http://127.0.0.1:${apiPort}$($ep.Path)" 2>$null
            if ($resp -and $resp.Length -gt 2) {
                $len = $resp.Length
                Ok "  $($ep.Name): ${len}B"
                $verifyPass++
            }
            else {
                Err "  $($ep.Name): 空响应"
                $verifyFail++
            }
        }
        catch {
            Err "  $($ep.Name): 连接失败"
            $verifyFail++
        }
    }
    
    # 触控测试 (tap屏幕中心)
    Log "触控API测试..."
    try {
        $tapResp = curl.exe -s --connect-timeout 3 -X POST "http://127.0.0.1:${apiPort}/tap" -H "Content-Type: application/json" -d '{\"x\":540,\"y\":1200}' 2>$null
        if ($tapResp) { Ok "  触控API: 响应OK"; $verifyPass++ }
        else { Warn "  触控API: 无响应"; $verifyFail++ }
    }
    catch { Warn "  触控API: $($_.Exception.Message)" }
    
    Log "API验证: $verifyPass 通过, $verifyFail 失败"
    $script:PhaseResults["verify"] = if ($verifyFail -eq 0) { "PASS" } else { "PARTIAL ($verifyPass/$($verifyPass+$verifyFail))" }
    
    # 保存API端口供后续使用
    $script:DetectedPort = $apiPort
    return ($verifyFail -eq 0)
}

# ═══════════════════════════════════════════════
# Phase 4: 端到端测试
# ═══════════════════════════════════════════════
function Invoke-E2E {
    Step 4 "端到端测试"
    
    $port = $script:DetectedPort
    if (-not $port) {
        # 重新探测
        foreach ($p in 8080..8089) {
            try {
                $r = curl.exe -s --connect-timeout 2 "http://127.0.0.1:${p}/status" 2>$null
                if ($r -and $r.Length -gt 5) { $port = $p; break }
            }
            catch {}
        }
    }
    
    if (-not $port) {
        Warn "无API端口，跳过E2E"
        $script:PhaseResults["e2e"] = "SKIP"
        return $false
    }
    
    $e2ePass = 0; $e2eFail = 0
    
    # E2E-1: 投屏页面可访问
    Log "E2E-1: 投屏页面..."
    try {
        $page = curl.exe -s --connect-timeout 5 "http://127.0.0.1:${port}/" 2>$null
        if ($page -and $page.Length -gt 1000) {
            Ok "  投屏页面: $($page.Length)B (index.html)"
            $e2ePass++
        }
        else { Err "  投屏页面: 内容不足"; $e2eFail++ }
    }
    catch { Err "  投屏页面: $($_.Exception.Message)"; $e2eFail++ }
    
    # E2E-2: MJPEG流
    Log "E2E-2: MJPEG视频流..."
    try {
        $mjpegPort = $port  # MJPEG通常和Gateway同端口或+1
        $streamResp = curl.exe -s --connect-timeout 3 --max-time 3 -o NUL -w "%{http_code},%{size_download}" "http://127.0.0.1:${mjpegPort}/stream.mjpeg" 2>$null
        if ($streamResp -match "200,(\d+)" -and [int]$Matches[1] -gt 0) {
            Ok "  MJPEG流: $($Matches[1])B received"
            $e2ePass++
        }
        else {
            Warn "  MJPEG流: $streamResp"
            $e2eFail++
        }
    }
    catch { Warn "  MJPEG流: timeout/error"; $e2eFail++ }
    
    # E2E-3: 导航命令
    Log "E2E-3: 导航命令..."
    foreach ($nav in @("home", "back")) {
        try {
            $r = curl.exe -s --connect-timeout 3 -X POST "http://127.0.0.1:${port}/$nav" 2>$null
            if ($r -ne $null) { Ok "  /$nav : OK"; $e2ePass++ }
            else { Warn "  /$nav : no response"; $e2eFail++ }
        }
        catch { Err "  /$nav : error"; $e2eFail++ }
        Start-Sleep -Milliseconds 500
    }
    
    # E2E-4: 文件管理API
    Log "E2E-4: 文件管理..."
    try {
        $files = curl.exe -s --connect-timeout 3 "http://127.0.0.1:${port}/files/list?path=/sdcard" 2>$null
        if ($files -and $files.Length -gt 10) {
            Ok "  文件列表: $($files.Length)B"
            $e2ePass++
        }
        else { Warn "  文件列表: 空或无响应"; $e2eFail++ }
    }
    catch { Warn "  文件列表: error"; $e2eFail++ }
    
    # E2E-5: AI Brain (viewtree + screen/text)
    Log "E2E-5: AI Brain..."
    try {
        $vt = curl.exe -s --connect-timeout 3 "http://127.0.0.1:${port}/viewtree?depth=3" 2>$null
        if ($vt -and $vt.Length -gt 50) {
            Ok "  ViewTree: $($vt.Length)B"
            $e2ePass++
        }
        else { Warn "  ViewTree: 内容不足"; $e2eFail++ }
    }
    catch { Warn "  ViewTree: error"; $e2eFail++ }
    
    try {
        $st = curl.exe -s --connect-timeout 3 "http://127.0.0.1:${port}/screen/text" 2>$null
        if ($st -and $st.Length -gt 10) {
            Ok "  Screen/Text: $($st.Length)B"
            $e2ePass++
        }
        else { Warn "  Screen/Text: 内容不足"; $e2eFail++ }
    }
    catch { Warn "  Screen/Text: error"; $e2eFail++ }
    
    # E2E-6: 宏系统
    Log "E2E-6: 宏系统..."
    try {
        $macros = curl.exe -s --connect-timeout 3 "http://127.0.0.1:${port}/macro/list" 2>$null
        if ($macros -ne $null) { Ok "  宏列表: $($macros.Length)B"; $e2ePass++ }
        else { Warn "  宏列表: null"; $e2eFail++ }
    }
    catch { Warn "  宏列表: error"; $e2eFail++ }
    
    Log "E2E结果: $e2ePass 通过, $e2eFail 失败"
    $script:PhaseResults["e2e"] = if ($e2eFail -eq 0) { "PASS ($e2ePass/$e2ePass)" } else { "PARTIAL ($e2ePass/$($e2ePass+$e2eFail))" }
    return ($e2eFail -eq 0)
}

# ═══════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════
function Get-TargetDevice {
    $deviceLines = & $script:ADB devices -l 2>&1 | Where-Object { $_ -match "^\S+\s+device\s" }
    if (-not $deviceLines) { return $null }
    
    foreach ($line in $deviceLines) {
        if ($line -match "^(\S+)\s+device.*model:(\S+)") {
            $serial = $Matches[1]
            $model = $Matches[2]
            
            # 如果指定了设备名，匹配
            if ($Device -and $model -notlike "*$Device*" -and $serial -notlike "*$Device*") { continue }
            
            # 优先选手机(排除Quest)
            if (-not $Device -and $model -like "*Quest*") { continue }
            
            return $serial
        }
    }
    
    # 没匹配到，返回第一个
    if ($deviceLines[0] -match "^(\S+)\s+device") { return $Matches[1] }
    return $null
}

# ═══════════════════════════════════════════════
# 最终报告
# ═══════════════════════════════════════════════
function Show-Report {
    $duration = (Get-Date) - $script:StartTime
    
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "║  ScreenStream 本地投屏 · 构建管线报告       ║" -ForegroundColor Yellow
    Write-Host "╠══════════════════════════════════════════════╣" -ForegroundColor Yellow
    
    foreach ($key in @("environment", "build", "deploy", "verify", "e2e")) {
        if ($script:PhaseResults.ContainsKey($key)) {
            $result = $script:PhaseResults[$key]
            $color = switch -Wildcard ($result) {
                "PASS*" { "Green" }
                "PARTIAL*" { "Yellow" }
                "SKIP*" { "DarkGray" }
                default { "Red" }
            }
            $padded = $key.PadRight(12)
            Write-Host "║  $padded : $result" -ForegroundColor $color
        }
    }
    
    Write-Host "╠══════════════════════════════════════════════╣" -ForegroundColor Yellow
    Write-Host "║  总计: $($script:PassCount) 通过 / $($script:WarnCount) 警告 / $($script:FailCount) 失败" -ForegroundColor $(if ($script:FailCount -eq 0) { "Green" } else { "Red" })
    Write-Host "║  耗时: $([math]::Round($duration.TotalSeconds))s" -ForegroundColor White
    Write-Host "║  时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor White
    
    if ($script:DetectedPort) {
        Write-Host "╠══════════════════════════════════════════════╣" -ForegroundColor Yellow
        Write-Host "║  投屏: http://127.0.0.1:$($script:DetectedPort)/" -ForegroundColor Cyan
        Write-Host "║  状态: http://127.0.0.1:$($script:DetectedPort)/status" -ForegroundColor Cyan
        Write-Host "║  AI:   http://127.0.0.1:$($script:DetectedPort)/viewtree" -ForegroundColor Cyan
    }
    
    Write-Host "╚══════════════════════════════════════════════╝" -ForegroundColor Yellow
}

# ═══════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════
Write-Host ""
Write-Host "  ScreenStream 本地投屏 · 渐进式构建管线" -ForegroundColor White
Write-Host "  Phase: $Phase | Clean: $Clean | Device: $(if($Device){$Device}else{'auto'})" -ForegroundColor DarkGray
Write-Host ""

# 环境检查 (总是执行)
$envOk = Test-Environment
if (-not $envOk -and $Phase -ne "verify") {
    Err "环境检查失败，中止"
    Show-Report
    exit 1
}

# 按Phase执行
switch ($Phase) {
    "build" {
        Invoke-Build
    }
    "deploy" {
        if (Test-Path $script:APK_PATH) { Invoke-Deploy }
        else { Err "APK不存在，请先构建: .\build_pipeline.ps1 -Phase build" }
    }
    "verify" {
        Invoke-Verify
    }
    "e2e" {
        Invoke-Verify
        Invoke-E2E
    }
    "all" {
        $buildOk = Invoke-Build
        if ($buildOk) {
            $deployOk = Invoke-Deploy
            if ($deployOk) {
                Start-Sleep -Seconds 5  # 等待APP完全启动
                $verifyOk = Invoke-Verify
                if ($verifyOk) {
                    Invoke-E2E
                }
            }
        }
    }
}

Show-Report
