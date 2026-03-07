<#
.SYNOPSIS
    台式机 Windsurf 首次启动初始化 + 健康检查
.DESCRIPTION
    在台式机交互式会话中执行（RDP或本地登录），一键完成：
    1. 环境检查（Node/npm/Git/Clash代理）
    2. MCP服务预热（npx首次下载需联网）
    3. Windsurf VIP状态检查
    4. C盘空间监控
    5. 打开Windsurf项目
.EXAMPLE
    .\windsurf-desktop-init.ps1          # 完整初始化+打开Windsurf
    .\windsurf-desktop-init.ps1 -Check   # 仅健康检查，不打开
    .\windsurf-desktop-init.ps1 -Sync    # 先从GitHub拉最新代码再打开
#>
param(
    [switch]$Check,
    [switch]$Sync
)

$ErrorActionPreference = 'Continue'
$projectPath = 'D:\道\道生一\一生二'
$pass = 0; $warn = 0; $fail = 0

function Test-Item($name, $test, $fixHint) {
    $ok = & $test
    if ($ok) {
        Write-Host "  [OK] $name" -ForegroundColor Green
        $script:pass++
    } else {
        Write-Host "  [!!] $name — $fixHint" -ForegroundColor Red
        $script:fail++
    }
    return $ok
}

function Warn-Item($name, $msg) {
    Write-Host "  [~~] $name — $msg" -ForegroundColor Yellow
    $script:warn++
}

Write-Host "`n========== 台式机 Windsurf 健康检查 ==========" -ForegroundColor Cyan
Write-Host "  时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "  主机: $env:COMPUTERNAME"

# === 1. 系统资源 ===
Write-Host "`n[1/7] 系统资源" -ForegroundColor Yellow
$memPct = [math]::Round((Get-CimInstance Win32_OperatingSystem | ForEach-Object { ($_.TotalVisibleMemorySize-$_.FreePhysicalMemory)/$_.TotalVisibleMemorySize*100 }),0)
$cFree = [math]::Round((Get-Volume C).SizeRemaining/1GB,1)
$dFree = [math]::Round((Get-Volume D).SizeRemaining/1GB,1)

Test-Item "内存 (${memPct}%)" { $memPct -lt 90 } "内存>90%，关闭不必要程序"
Test-Item "C盘 (${cFree}GB)" { $cFree -gt 10 } "C盘<10GB危险！清理Temp/npm缓存"
Test-Item "D盘 (${dFree}GB)" { $dFree -gt 20 } "D盘空间不足"

if ($cFree -lt 20) {
    Warn-Item "C盘紧张" "建议清理: Remove-Item $env:TEMP\* -Recurse -Force"
}

# === 2. 依赖工具 ===
Write-Host "`n[2/7] 依赖工具" -ForegroundColor Yellow
Test-Item "Node.js" { Get-Command node -ErrorAction SilentlyContinue } "安装 Node.js"
Test-Item "npm" { Get-Command npm -ErrorAction SilentlyContinue } "npm未找到"
Test-Item "npx" { Get-Command npx -ErrorAction SilentlyContinue } "npx未找到"
Test-Item "Git" { Get-Command git -ErrorAction SilentlyContinue } "安装 Git"
Test-Item "Python" { Get-Command python -ErrorAction SilentlyContinue } "安装 Python"
Test-Item "Windsurf" { Get-Command windsurf -ErrorAction SilentlyContinue } "Windsurf不在PATH"

# npm缓存位置检查
$npmCache = npm config get cache 2>$null
if ($npmCache -and $npmCache -like "C:*") {
    Warn-Item "npm缓存在C盘" "运行: npm config set cache D:\npm-cache --global"
}

# === 3. 网络代理 ===
Write-Host "`n[3/7] 网络代理（GitHub访问）" -ForegroundColor Yellow
$clashRunning = Get-Process "clash*","Clash*" -ErrorAction SilentlyContinue
if ($clashRunning) {
    Write-Host "  [OK] Clash进程运行中" -ForegroundColor Green; $pass++
} else {
    Warn-Item "Clash未运行" "启动Clash Verge以访问GitHub"
}

# 测试代理连通性
try {
    $null = Invoke-WebRequest "https://github.com" -Proxy "http://127.0.0.1:7890" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    Write-Host "  [OK] GitHub via Clash可达" -ForegroundColor Green; $pass++
} catch {
    try {
        $null = Invoke-WebRequest "https://github.com" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        Write-Host "  [OK] GitHub直连可达" -ForegroundColor Green; $pass++
    } catch {
        Warn-Item "GitHub不可达" "检查Clash配置或网络连接"
    }
}

# Git代理
$gitProxy = git config --global --get http.proxy 2>$null
Test-Item "Git代理 ($gitProxy)" { $gitProxy } "运行: git config --global http.proxy http://127.0.0.1:7890"

# === 4. 项目工作区 ===
Write-Host "`n[4/7] 项目工作区" -ForegroundColor Yellow
Test-Item "项目目录" { Test-Path $projectPath } "运行 sync-to-desktop.ps1 从笔记本同步"
Test-Item ".git" { Test-Path "$projectPath\.git" } "项目未初始化git"
Test-Item ".windsurf/" { Test-Path "$projectPath\.windsurf" } ".windsurf/配置缺失"
Test-Item ".windsurfrules" { Test-Path "$projectPath\.windsurfrules" } "项目根规则文件缺失"

if (Test-Path "$projectPath\.windsurf") {
    $rules = (Get-ChildItem "$projectPath\.windsurf\rules" -File -ErrorAction SilentlyContinue).Count
    $skills = (Get-ChildItem "$projectPath\.windsurf\skills" -Directory -ErrorAction SilentlyContinue).Count
    $workflows = (Get-ChildItem "$projectPath\.windsurf\workflows" -File -ErrorAction SilentlyContinue).Count
    Test-Item "Rules ($rules/6)" { $rules -ge 6 } "规则文件不完整"
    Test-Item "Skills ($skills/13)" { $skills -ge 13 } "技能文件不完整"
    Test-Item "Workflows ($workflows/10)" { $workflows -ge 10 } "工作流不完整"
}

# === 5. Windsurf配置 ===
Write-Host "`n[5/7] Windsurf配置" -ForegroundColor Yellow
$mcpPath = "$env:USERPROFILE\.codeium\windsurf\mcp_config.json"
$grPath = "$env:USERPROFILE\.codeium\windsurf\memories\global_rules.md"
$settingsPath = "$env:APPDATA\Windsurf\User\settings.json"

Test-Item "MCP配置" { Test-Path $mcpPath } "从笔记本同步: sync-to-desktop.ps1 -ConfigOnly"
Test-Item "全局规则 ($([math]::Round((Get-Item $grPath -ErrorAction SilentlyContinue).Length/1KB,1))KB)" { (Get-Item $grPath -ErrorAction SilentlyContinue).Length -gt 1000 } "global_rules.md过小或缺失"
Test-Item "IDE设置" { Test-Path $settingsPath } "settings.json缺失"

# VIP扩展
$vipExt = Get-ChildItem "$env:USERPROFILE\.windsurf\extensions" -Directory -Filter "*vip*" -ErrorAction SilentlyContinue
if ($vipExt) {
    Write-Host "  [OK] VIP扩展已安装: $($vipExt.Name)" -ForegroundColor Green; $pass++
} else {
    Warn-Item "VIP扩展" "安装续杯插件以获取Pro功能"
}

# === 6. MCP预热 ===
Write-Host "`n[6/7] MCP服务预热" -ForegroundColor Yellow
if (-not $Check) {
    $mcpPackages = @(
        @{Name='chrome-devtools-mcp'; Cmd='npx -y chrome-devtools-mcp@latest --help'},
        @{Name='@upstash/context7-mcp'; Cmd='npx -y @upstash/context7-mcp@latest --help'},
        @{Name='@playwright/mcp'; Cmd='npx -y @playwright/mcp --help'}
    )
    foreach ($pkg in $mcpPackages) {
        Write-Host "  预热 $($pkg.Name)..." -NoNewline
        try {
            $job = Start-Job -ScriptBlock { param($c) Invoke-Expression $c 2>&1 | Out-Null } -ArgumentList $pkg.Cmd
            $done = Wait-Job $job -Timeout 30
            if ($done) {
                Write-Host " OK" -ForegroundColor Green; $pass++
            } else {
                Stop-Job $job; Remove-Job $job -Force
                Warn-Item $pkg.Name "下载超时，检查网络代理"
            }
        } catch {
            Warn-Item $pkg.Name "预热失败: $_"
        }
    }
} else {
    Write-Host "  跳过（Check模式）" -ForegroundColor Gray
}

# === 7. Git同步 ===
Write-Host "`n[7/7] Git状态" -ForegroundColor Yellow
if (Test-Path "$projectPath\.git") {
    Push-Location $projectPath
    $branch = git branch --show-current 2>$null
    $remote = git remote get-url origin 2>$null
    $status = git status --porcelain 2>$null
    Write-Host "  分支: $branch"
    Write-Host "  远程: $remote"
    if ($status) {
        Warn-Item "未提交变更" "$($status.Count) 个文件有修改"
    } else {
        Write-Host "  [OK] 工作区干净" -ForegroundColor Green; $pass++
    }

    if ($Sync) {
        Write-Host "  拉取最新代码..." -NoNewline
        $pullResult = git pull origin $branch 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host " OK" -ForegroundColor Green
        } else {
            Warn-Item "git pull" "$pullResult"
        }
    }
    Pop-Location
}

# === 汇总 ===
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  通过: $pass | 警告: $warn | 失败: $fail" -ForegroundColor $(if($fail -eq 0){'Green'}elseif($fail -le 2){'Yellow'}else{'Red'})
Write-Host "========================================" -ForegroundColor Cyan

# === 打开Windsurf ===
if (-not $Check -and $fail -eq 0) {
    Write-Host "`n正在打开 Windsurf..." -ForegroundColor Cyan
    Start-Process "windsurf" -ArgumentList $projectPath
    Write-Host "Windsurf 已启动，项目: $projectPath" -ForegroundColor Green
} elseif ($fail -gt 0) {
    Write-Host "`n有 $fail 项检查失败，请先修复后再打开Windsurf" -ForegroundColor Red
}
