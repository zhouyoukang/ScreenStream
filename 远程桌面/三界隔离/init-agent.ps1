# 三界隔离 — 地界环境初始化
# 在 windsurf-test 会话中首次运行, 配置开发环境
# Usage: .\init-agent.ps1

Write-Host ""
Write-Host "  地界环境初始化" -ForegroundColor Cyan
Write-Host "  当前用户: $env:USERNAME" -ForegroundColor DarkGray
Write-Host ""

if ($env:USERNAME -ne 'windsurf-test') {
    Write-Host "  [!] 此脚本应在 windsurf-test 会话中运行" -ForegroundColor Red
    Write-Host "  [!] 当前用户: $env:USERNAME" -ForegroundColor Red
    return
}

$checks = @()

# --- 1. Git ---
Write-Host "  [1/5] Git..." -NoNewline
$gitExe = Get-Command git -ErrorAction SilentlyContinue
if ($gitExe) {
    # Configure git for agent account
    $name = git config --global user.name 2>$null
    if (-not $name) {
        git config --global user.name "windsurf-agent"
        git config --global user.email "agent@localhost"
    }
    git config --global core.autocrlf true
    git config --global init.defaultBranch main
    Write-Host " OK ($(git --version))" -ForegroundColor Green
    $checks += @{Name='Git'; OK=$true}
} else {
    Write-Host " NOT FOUND (system-wide install needed)" -ForegroundColor Red
    $checks += @{Name='Git'; OK=$false}
}

# --- 2. Python ---
Write-Host "  [2/5] Python..." -NoNewline
$pyExe = Get-Command python -ErrorAction SilentlyContinue
if ($pyExe) {
    $pyVer = python --version 2>&1
    Write-Host " OK ($pyVer)" -ForegroundColor Green
    $checks += @{Name='Python'; OK=$true}
} else {
    Write-Host " NOT FOUND" -ForegroundColor Red
    $checks += @{Name='Python'; OK=$false}
}

# --- 3. ADB ---
Write-Host "  [3/5] ADB..." -NoNewline
$adbPaths = @(
    'E:\道\道生一\一生二\构建部署\android-sdk\platform-tools\adb.exe'
    (Get-Command adb -ErrorAction SilentlyContinue).Source
)
$adbExe = $adbPaths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if ($adbExe) {
    # Add to PATH if not already there
    if ($env:PATH -notmatch 'platform-tools') {
        $adbDir = Split-Path $adbExe
        [Environment]::SetEnvironmentVariable('PATH', "$env:PATH;$adbDir", 'User')
        $env:PATH += ";$adbDir"
    }
    Write-Host " OK ($adbExe)" -ForegroundColor Green
    $checks += @{Name='ADB'; OK=$true}
} else {
    Write-Host " NOT FOUND" -ForegroundColor Red
    $checks += @{Name='ADB'; OK=$false}
}

# --- 4. 共享数据访问 ---
Write-Host "  [4/5] 共享数据..." -NoNewline
$sharedOK = $true
@('E:\道\', 'E:\github\', 'E:\道\道生一\一生二\') | ForEach-Object {
    if (-not (Test-Path $_)) { $sharedOK = $false }
}
if ($sharedOK) {
    # Test write access
    $testFile = 'E:\道\道生一\一生二\.agent-test-write'
    try {
        'test' | Set-Content $testFile -ErrorAction Stop
        Remove-Item $testFile -ErrorAction SilentlyContinue
        Write-Host " OK (read+write)" -ForegroundColor Green
    } catch {
        Write-Host " OK (read-only)" -ForegroundColor Yellow
    }
    $checks += @{Name='SharedData'; OK=$true}
} else {
    Write-Host " FAILED (paths missing)" -ForegroundColor Red
    $checks += @{Name='SharedData'; OK=$false}
}

# --- 5. Windsurf CLI ---
Write-Host "  [5/5] Windsurf..." -NoNewline
$wsExe = Get-Command windsurf -ErrorAction SilentlyContinue
if (-not $wsExe) {
    $wsExe = Get-Command code -ErrorAction SilentlyContinue  # fallback
}
if ($wsExe) {
    Write-Host " OK ($($wsExe.Source))" -ForegroundColor Green
    $checks += @{Name='Windsurf'; OK=$true}
} else {
    Write-Host " NOT FOUND (install from https://windsurf.com)" -ForegroundColor Yellow
    $checks += @{Name='Windsurf'; OK=$false}
}

# --- Summary ---
$ok = ($checks | Where-Object { $_.OK }).Count
$total = $checks.Count
Write-Host ""
Write-Host "  === 初始化完成: $ok/$total ===" -ForegroundColor $(if($ok -eq $total){'Green'}else{'Yellow'})

if ($ok -eq $total) {
    Write-Host ""
    Write-Host "  地界就绪! 可以执行:" -ForegroundColor Green
    Write-Host "    windsurf E:\道\道生一\一生二   # 打开项目" -ForegroundColor DarkGray
    Write-Host "    cd E:\道\道生一\一生二         # 进入项目" -ForegroundColor DarkGray
} else {
    Write-Host ""
    Write-Host "  部分工具缺失, 但不影响基本功能" -ForegroundColor Yellow
}
