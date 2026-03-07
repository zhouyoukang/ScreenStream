# 三界隔离 — 状态面板
# Usage: .\status.ps1

$AgentUser = 'windsurf-test'
$MainUser = 'zhouyoukang'

Write-Host ""
Write-Host "  +===================================+" -ForegroundColor Cyan
Write-Host "  |    道 之 隔 离 — 三界状态面板     |" -ForegroundColor Cyan
Write-Host "  +===================================+" -ForegroundColor Cyan

# --- 会话状态 ---
$raw = query session 2>$null
Write-Host ""
Write-Host "  [ 天界 · 用户区 ]" -ForegroundColor White

$mainLine = $raw | Where-Object { $_ -match $MainUser }
if ($mainLine) {
    $state = if ($mainLine -match '运行中|Active') { '运行中' } elseif ($mainLine -match '断开|Disc') { '断开(后台)' } else { '未知' }
    $color = if ($state -eq '运行中') { 'Green' } elseif ($state -match '断开') { 'Yellow' } else { 'DarkGray' }
    Write-Host "    $MainUser : $state" -ForegroundColor $color
} else {
    Write-Host "    $MainUser : 未登录" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "  [ 地界 · Agent区 ]" -ForegroundColor White

$agentLine = $raw | Where-Object { $_ -match $AgentUser }
if ($agentLine) {
    $state = if ($agentLine -match '运行中|Active') { '运行中' } elseif ($agentLine -match '断开|Disc') { '断开(后台)' } else { '未知' }
    $color = if ($state -eq '运行中') { 'Green' } elseif ($state -match '断开') { 'Yellow' } else { 'DarkGray' }
    $sid = if ($agentLine -match '\s+(\d+)\s+') { " [Session $($matches[1])]" } else { '' }
    Write-Host "    $AgentUser : $state$sid" -ForegroundColor $color
} else {
    Write-Host "    $AgentUser : 未启动" -ForegroundColor DarkGray
}

# --- 人界 · 共享数据 ---
Write-Host ""
Write-Host "  [ 人界 · 共享数据层 ]" -ForegroundColor White

$paths = [ordered]@{
    'E:\道\'              = '项目文件 (两账号共享)'
    'E:\github\'          = '代码仓库'
    'E:\道\道生一\一生二\' = 'ScreenStream 工作区'
}
foreach ($kv in $paths.GetEnumerator()) {
    $ok = Test-Path $kv.Key
    $icon = if ($ok) { '+' } else { 'x' }
    $color = if ($ok) { 'Green' } else { 'Red' }
    Write-Host "    [$icon] $($kv.Key) — $($kv.Value)" -ForegroundColor $color
}

# Git
$gitRoot = 'E:\道\道生一\一生二'
if (Test-Path "$gitRoot\.git") {
    $branch = git -C $gitRoot branch --show-current 2>$null
    $dirty = git -C $gitRoot status --porcelain 2>$null | Measure-Object | Select-Object -ExpandProperty Count
    $gitInfo = "branch=$branch"
    if ($dirty -gt 0) { $gitInfo += ", $dirty 未提交" }
    Write-Host "    [G] Git: $gitInfo" -ForegroundColor Green
}

# --- 连接方式 ---
Write-Host ""
Write-Host "  [ 连接通道 ]" -ForegroundColor White

# RDP
$rdpEnabled = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' -Name fDenyTSConnections -EA SilentlyContinue).fDenyTSConnections -eq 0
$rdpIcon = if ($rdpEnabled) { '+' } else { 'x' }
Write-Host "    [$rdpIcon] RDP本地连接 (127.0.0.1)" -ForegroundColor $(if($rdpEnabled){'Green'}else{'Red'})

# SMB
$smbShares = (Get-SmbShare | Where-Object { $_.Name -in @('C','D','E') }).Count
Write-Host "    [+] SMB共享 ($smbShares 个驱动器)" -ForegroundColor Green

# Fast switch
Write-Host "    [+] 快速用户切换 (tscon)" -ForegroundColor Green

# --- 系统资源 ---
Write-Host ""
Write-Host "  [ 系统资源 ]" -ForegroundColor White
$os = Get-CimInstance Win32_OperatingSystem
$memPct = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize * 100, 0)
$memFreeGB = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
$memColor = if ($memPct -gt 90) { 'Red' } elseif ($memPct -gt 80) { 'Yellow' } else { 'Green' }
Write-Host "    RAM: ${memPct}% (${memFreeGB}GB free)" -ForegroundColor $memColor

$cFree = [math]::Round((Get-Volume C).SizeRemaining / 1GB, 0)
$eFree = [math]::Round((Get-Volume E).SizeRemaining / 1GB, 0)
Write-Host "    C: ${cFree}GB free | E: ${eFree}GB free" -ForegroundColor Green

Write-Host ""
Write-Host "  +===================================+" -ForegroundColor Cyan
Write-Host "  | enter.ps1  — 进入地界             |" -ForegroundColor DarkGray
Write-Host "  | return.ps1 — 返回天界             |" -ForegroundColor DarkGray
Write-Host "  +===================================+" -ForegroundColor Cyan
Write-Host ""
