<#
.SYNOPSIS
    三盘健康监控脚本 - Agent嗅觉层
.DESCRIPTION
    定期扫描C/D/E三盘，检测异常增长、空间告警、冗余文件
    可由Agent在每次新对话时调用，或手动运行
.PARAMETER Action
    diagnose = 快速诊断 | deep = 深度扫描 | watch = 持续监控
#>
param(
    [ValidateSet('diagnose', 'deep', 'watch')]
    [string]$Action = 'diagnose'
)

$ErrorActionPreference = 'SilentlyContinue'

function Write-Status($msg, $level = 'INFO') {
    $color = switch ($level) { 'OK' { 'Green' } 'WARN' { 'Yellow' } 'CRIT' { 'Red' } default { 'White' } }
    $icon = switch ($level) { 'OK' { '[OK]' } 'WARN' { '[!!]' } 'CRIT' { '[XX]' } default { '[--]' } }
    Write-Host "$icon $msg" -ForegroundColor $color
}

function Get-DiskHealth {
    $results = @()
    foreach ($d in @('C', 'D', 'E')) {
        $v = Get-Volume -DriveLetter $d -EA SilentlyContinue
        if (!$v) { continue }
        $pct = [math]::Round($v.SizeRemaining / $v.Size * 100, 1)
        $freeGB = [math]::Round($v.SizeRemaining / 1GB, 1)
        $level = if ($pct -lt 15) { 'CRIT' }elseif ($pct -lt 30) { 'WARN' }else { 'OK' }
        Write-Status "$($d): ${freeGB}GB free ($pct%)" $level
        $results += [PSCustomObject]@{Drive = $d; FreeGB = $freeGB; FreePct = $pct; Level = $level }
    }
    return $results
}

function Get-MemoryHealth {
    $os = Get-CimInstance Win32_OperatingSystem
    $pct = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize * 100, 0)
    $level = if ($pct -gt 95) { 'CRIT' }elseif ($pct -gt 90) { 'WARN' }else { 'OK' }
    Write-Status "Memory: ${pct}% used" $level
    return $pct
}

function Find-LargeNewFiles {
    param([int]$DaysBack = 7, [int]$MinMB = 500)
    Write-Host "`n--- New large files (>${MinMB}MB, last ${DaysBack}d) ---"
    $cutoff = (Get-Date).AddDays(-$DaysBack)
    $found = 0
    foreach ($root in @("C:\Users\zhouyoukang", "D:\", "E:\")) {
        Get-ChildItem $root -File -Force -EA SilentlyContinue | Where-Object {
            $_.Length -gt ($MinMB * 1MB) -and $_.LastWriteTime -gt $cutoff
        } | ForEach-Object {
            Write-Status "$([math]::Round($_.Length/1MB,0))MB $($_.FullName)" 'WARN'
            $found++
        }
    }
    if ($found -eq 0) { Write-Status "No new large files" 'OK' }
}

function Find-DuplicatePatterns {
    Write-Host "`n--- Known duplicate patterns ---"

    # CrossDevice still on C?
    $cd = Get-Item "C:\Users\zhouyoukang\CrossDevice" -Force -EA SilentlyContinue
    if ($cd -and !($cd.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        $sz = [math]::Round((Get-ChildItem $cd.FullName -Recurse -File -Force -EA SilentlyContinue | Measure-Object Length -Sum).Sum / 1GB, 1)
        Write-Status "CrossDevice still on C: (${sz}GB) - run crossdevice-migrate.ps1" 'CRIT'
    }
    else {
        Write-Status "CrossDevice: migrated or junction" 'OK'
    }

    # Download dir bloat
    $dlDir = "E:\浏览器下载位置"
    if (Test-Path $dlDir) {
        $pkgs = Get-ChildItem $dlDir -File -Force -EA SilentlyContinue | Where-Object { $_.Extension -match '\.(exe|msi|zip|rar|7z)$' -and $_.Length -gt 50MB }
        $pkgSum = ($pkgs | Measure-Object Length -Sum).Sum
        $pkgGB = [math]::Round($pkgSum / 1GB, 1)
        if ($pkgGB -gt 1) {
            Write-Status "Download dir has ${pkgGB}GB install packages" 'WARN'
        }
        else {
            Write-Status "Download dir clean" 'OK'
        }
    }

    # Broken junctions
    $ws = "E:\道\道生一\一生二"
    if (Test-Path $ws) {
        $broken = Get-ChildItem $ws -Directory -Force -EA SilentlyContinue | Where-Object {
            ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -and !(Test-Path (Get-Item $_.FullName).Target)
        }
        if ($broken.Count -gt 0) {
            Write-Status "Broken junctions: $($broken.Count) in workspace" 'CRIT'
            $broken | ForEach-Object { Write-Host "  $($_.Name) -> $((Get-Item $_.FullName).Target)" }
        }
        else {
            Write-Status "Workspace junctions: all valid" 'OK'
        }
    }
}

function Get-TopConsumers {
    Write-Host "`n--- Top space consumers ---"
    $dirs = @(
        "C:\Users\zhouyoukang\AppData",
        "C:\Users\zhouyoukang\CrossDevice",
        "D:\桌面",
        "D:\屏幕录制",
        "E:\浏览器下载位置",
        "E:\骑行拍摄",
        "E:\xwechat_files"
    )
    foreach ($d in $dirs) {
        if (Test-Path $d) {
            $isJ = (Get-Item $d -Force).Attributes -band [IO.FileAttributes]::ReparsePoint
            if ($isJ) {
                Write-Status "$d [Junction]" 'OK'
            }
            else {
                $sz = (Get-ChildItem $d -Recurse -File -Force -EA SilentlyContinue | Measure-Object Length -Sum).Sum
                $gb = [math]::Round($sz / 1GB, 1)
                $level = if ($gb -gt 50) { 'WARN' }elseif ($gb -gt 100) { 'CRIT' }else { 'OK' }
                Write-Status "${gb}GB $d" $level
            }
        }
    }
}

# Main
Write-Host "=== Disk Health Monitor ===" -ForegroundColor Cyan
Write-Host "Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Host "Action: $Action`n"

switch ($Action) {
    'diagnose' {
        Get-DiskHealth
        Get-MemoryHealth
        Find-DuplicatePatterns
    }
    'deep' {
        Get-DiskHealth
        Get-MemoryHealth
        Find-DuplicatePatterns
        Find-LargeNewFiles
        Get-TopConsumers
    }
    'watch' {
        while ($true) {
            Clear-Host
            Write-Host "=== Disk Monitor (Ctrl+C to stop) ===" -ForegroundColor Cyan
            Write-Host "$(Get-Date -Format 'HH:mm:ss')`n"
            Get-DiskHealth
            Get-MemoryHealth
            Start-Sleep 60
        }
    }
}

Write-Host "`n=== Done ===" -ForegroundColor Cyan
