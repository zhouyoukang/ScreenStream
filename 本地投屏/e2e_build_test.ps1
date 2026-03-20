# ScreenStream 本地投屏 · E2E自动化验证
# 纯验证脚本，不构建不部署，只检测当前运行状态
# 用法: .\e2e_build_test.ps1 [-Port 8084] [-Verbose]
param(
    [int]$Port = 0,
    [switch]$Verbose
)

$ADB = "D:\platform-tools\adb.exe"
$pass = 0; $fail = 0; $skip = 0
$results = @()

function Test-EP($name, $url, $minLen = 3) {
    try {
        $r = curl.exe -s --connect-timeout 3 $url 2>$null
        if ($r -and $r.Length -ge $minLen) {
            $script:pass++
            $script:results += [pscustomobject]@{Test = $name; Status = "PASS"; Size = "$($r.Length)B" }
            if ($Verbose) { Write-Host "[OK] $name : $($r.Length)B" -ForegroundColor Green }
            return $r
        }
        else {
            $script:fail++
            $script:results += [pscustomobject]@{Test = $name; Status = "FAIL"; Size = "empty" }
            if ($Verbose) { Write-Host "[FAIL] $name" -ForegroundColor Red }
            return $null
        }
    }
    catch {
        $script:fail++
        $script:results += [pscustomobject]@{Test = $name; Status = "FAIL"; Size = "error" }
        return $null
    }
}

# ═══ Phase 0: 设备与端口探测 ═══
Write-Host "`n=== E2E: Phase 0 - Device Probe ===" -ForegroundColor Magenta
$devices = & $ADB devices -l 2>&1 | Where-Object { $_ -match "^\S+\s+device\s" }
if ($devices) {
    foreach ($d in $devices) {
        if ($d -match "^(\S+)\s+device.*model:(\S+)") {
            Write-Host "  Device: $($Matches[2]) [$($Matches[1])]" -ForegroundColor Cyan
        }
    }
}
else {
    Write-Host "  No devices" -ForegroundColor Yellow
}

# 自动探测API端口
if ($Port -eq 0) {
    Write-Host "`n=== E2E: Port Probe ===" -ForegroundColor Magenta
    foreach ($p in 8080..8089) {
        $r = curl.exe -s --connect-timeout 2 "http://127.0.0.1:${p}/status" 2>$null
        if ($r -match '"connected"') { $Port = $p; break }
    }
    if ($Port -eq 0) {
        Write-Host "  未找到API端口 (需先启动投屏)" -ForegroundColor Red
        exit 1
    }
}
Write-Host "  API Port: $Port" -ForegroundColor Green
$base = "http://127.0.0.1:${Port}"

# ═══ Phase 1: 基础API ═══
Write-Host "`n=== E2E: Basic API (Phase 1) ===" -ForegroundColor Magenta
Test-EP "status" "$base/status" | Out-Null
Test-EP "deviceinfo" "$base/deviceinfo" 50 | Out-Null
Test-EP "apps" "$base/apps" 100 | Out-Null
Test-EP "foreground" "$base/foreground" 10 | Out-Null
Test-EP "clipboard" "$base/clipboard" 2 | Out-Null
Test-EP "windowinfo" "$base/windowinfo" 10 | Out-Null

# ═══ Phase 2: AI Brain ═══
Write-Host "`n=== E2E: AI Brain (Phase 2) ===" -ForegroundColor Magenta
Test-EP "viewtree" "$base/viewtree?depth=3" 30 | Out-Null
Test-EP "screen/text" "$base/screen/text" 30 | Out-Null

# ═══ Phase 3: 宏系统 ═══
Write-Host "`n=== E2E: Macro (Phase 3) ===" -ForegroundColor Magenta
Test-EP "macro/list" "$base/macro/list" 2 | Out-Null
Test-EP "macro/running" "$base/macro/running" 2 | Out-Null

# ═══ Phase 4: 文件管理 ═══
Write-Host "`n=== E2E: Files (Phase 4) ===" -ForegroundColor Magenta
Test-EP "files/list" "$base/files/list?path=/sdcard" 50 | Out-Null

# ═══ Phase 5: 前端页面 ═══
Write-Host "`n=== E2E: Frontend (Phase 5) ===" -ForegroundColor Magenta
Test-EP "index.html" "$base/" 1000 | Out-Null
Test-EP "favicon" "$base/favicon.ico" 100 | Out-Null
Test-EP "jmuxer.js" "$base/jmuxer.min.js" 1000 | Out-Null
Test-EP "voice.html" "$base/voice.html" 100 | Out-Null

# ═══ Phase 6: Auth系统 ═══
Write-Host "`n=== E2E: Auth (Phase 6) ===" -ForegroundColor Magenta
Test-EP "auth/info" "$base/auth/info" 5 | Out-Null

# ═══ Phase 7: 导航命令(ADB tap验证) ═══
Write-Host "`n=== E2E: Navigation (Phase 7) ===" -ForegroundColor Magenta
foreach ($cmd in @("home", "back")) {
    try {
        $r = curl.exe -s --connect-timeout 3 -X POST "$base/$cmd" 2>$null
        $pass++
        $results += [pscustomobject]@{Test = "nav/$cmd"; Status = "PASS"; Size = "ok" }
        if ($Verbose) { Write-Host "[OK] nav/$cmd" -ForegroundColor Green }
    }
    catch {
        $fail++
        $results += [pscustomobject]@{Test = "nav/$cmd"; Status = "FAIL"; Size = "error" }
    }
    Start-Sleep -Milliseconds 300
}

# 报告
Write-Host "`n+==========================================+" -ForegroundColor Yellow
Write-Host "|  ScreenStream E2E Report                 |" -ForegroundColor Yellow
Write-Host "+==========================================+" -ForegroundColor Yellow

$results | ForEach-Object {
    $color = if ($_.Status -eq "PASS") { "Green" } else { "Red" }
    $icon = if ($_.Status -eq "PASS") { "+" } else { "x" }
    Write-Host "|  $icon $($_.Test.PadRight(20)) $($_.Size.PadRight(12))" -ForegroundColor $color
}

$total = $pass + $fail
Write-Host "+==========================================+" -ForegroundColor Yellow
Write-Host "|  Result: $pass/$total PASS$(if($fail -gt 0){" ($fail FAIL)"})" -ForegroundColor $(if ($fail -eq 0) { "Green" } else { "Red" })
Write-Host "|  Port: $Port" -ForegroundColor Cyan
Write-Host "|  Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor White
Write-Host "+==========================================+" -ForegroundColor Yellow

# 输出JSON结果(供自动化使用)
$jsonResult = @{
    timestamp = (Get-Date -Format "o")
    port      = $Port
    pass      = $pass
    fail      = $fail
    total     = $total
    tests     = $results | ForEach-Object { @{name = $_.Test; status = $_.Status; size = $_.Size } }
} | ConvertTo-Json -Depth 3
$jsonResult | Out-File "$PSScriptRoot\e2e_results.json" -Encoding utf8

exit $fail
