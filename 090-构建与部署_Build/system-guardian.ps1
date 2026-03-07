<#
.SYNOPSIS
    System Guardian - Protect core system from Agent-induced overload
.DESCRIPTION
    Triple defense: Monitor, Clean, Protect.
    Does NOT reduce Agent capability - only intervenes when system is critical.
.NOTES
    MECHREVO WUJIE 14 / AMD Ryzen / 15.2GB RAM / C:300GB + D:653GB + E:954GB
    Root cause: 10x BSOD 0x133 DPC_WATCHDOG_VIOLATION = OOM + C: full
#>

[CmdletBinding()]
param(
    [ValidateSet('diagnose', 'clean', 'protect', 'fix-drivers', 'full', 'monitor')]
    [string]$Action = 'diagnose',
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

function Write-Status($msg, $level = 'info') {
    switch ($level) {
        'ok' { Write-Host "  [OK] $msg" -ForegroundColor Green }
        'warn' { Write-Host "  [!!] $msg" -ForegroundColor Yellow }
        'error' { Write-Host "  [XX] $msg" -ForegroundColor Red }
        'info' { Write-Host "  [..] $msg" -ForegroundColor Cyan }
        'title' { Write-Host "`n=== $msg ===" -ForegroundColor White }
    }
}

# ============================================================
# 1. DIAGNOSE
# ============================================================
function Invoke-Diagnose {
    Write-Status "System Diagnosis" 'title'

    $os = Get-CimInstance Win32_OperatingSystem
    $memTotal = [math]::Round($os.TotalVisibleMemorySize / 1MB, 1)
    $memFree = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
    $memPct = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize * 100, 1)

    $memLvl = if ($memPct -gt 90) { 'error' } elseif ($memPct -gt 80) { 'warn' } else { 'ok' }
    Write-Status "Memory: ${memPct}% used (${memFree}GB free / ${memTotal}GB)" $memLvl

    $cVol = Get-Volume -DriveLetter C
    $cFreeGB = [math]::Round($cVol.SizeRemaining / 1GB, 1)
    $cFreePct = [math]::Round($cVol.SizeRemaining / $cVol.Size * 100, 1)
    $diskLvl = if ($cFreePct -lt 15) { 'error' } elseif ($cFreePct -lt 25) { 'warn' } else { 'ok' }
    Write-Status "C: drive: ${cFreeGB}GB free (${cFreePct}%)" $diskLvl

    $tempSize = [math]::Round((Get-ChildItem $env:TEMP -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum / 1GB, 1)
    $winTemp = [math]::Round((Get-ChildItem C:\Windows\Temp -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum / 1GB, 1)
    $tempLvl = if (($tempSize + $winTemp) -gt 2) { 'warn' } else { 'ok' }
    Write-Status "Temp files: User=${tempSize}GB + System=${winTemp}GB" $tempLvl

    $wsProcs = Get-Process | Where-Object { $_.Name -match 'Windsurf|node|pwsh|language_server' }
    $wsMem = [math]::Round(($wsProcs | Measure-Object WorkingSet64 -Sum).Sum / 1GB, 1)
    $wsLvl = if ($wsMem -gt 5) { 'warn' } else { 'ok' }
    Write-Status "Windsurf ecosystem: ${wsMem}GB / $($wsProcs.Count) procs" $wsLvl

    # Detail breakdown
    $pwshCount = @(Get-Process -Name pwsh -EA SilentlyContinue).Count
    $pwshMem = [math]::Round((Get-Process -Name pwsh -EA SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum / 1GB, 1)
    $nodeCount = @(Get-Process -Name node -EA SilentlyContinue).Count
    $nodeMem = [math]::Round((Get-Process -Name node -EA SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum / 1GB, 1)
    $wsMainMem = [math]::Round((Get-Process -Name Windsurf -EA SilentlyContinue | Measure-Object WorkingSet64 -Sum).Sum / 1GB, 1)
    Write-Status "  Windsurf: ${wsMainMem}GB | pwsh: ${pwshMem}GB x${pwshCount} | node: ${nodeMem}GB x${nodeCount}" 'info'
    if ($pwshCount -gt 6) { Write-Status "  Too many terminals ($pwshCount)! Close unused tabs to save ${pwshMem}GB" 'warn' }

    $brProcs = Get-Process | Where-Object { $_.Name -match 'msedge|chrome|Weixin|WeChatAppEx|PhoneExperienceHost' }
    $brMem = [math]::Round(($brProcs | Measure-Object WorkingSet64 -Sum).Sum / 1GB, 1)
    $brLvl = if ($brMem -gt 3) { 'warn' } else { 'ok' }
    Write-Status "Browser+WeChat: ${brMem}GB / $($brProcs.Count) procs" $brLvl

    $badSvcs = Get-Service -Name 'AMDRyzenMasterDriverV26', 'TsQBDrv', 'AliPaladin' -EA SilentlyContinue
    $activeBad = $badSvcs | Where-Object { $_.StartType -ne 'Disabled' }
    $disabledBad = $badSvcs | Where-Object { $_.StartType -eq 'Disabled' }
    if ($activeBad) { Write-Status "Bad drivers ACTIVE: $($activeBad.Name -join ', ')" 'error' }
    elseif ($disabledBad) { Write-Status "Bad drivers disabled (fixed): $($disabledBad.Name -join ', ')" 'ok' }
    else { Write-Status "Bad drivers: none found" 'ok' }

    $crashes = @(Get-WinEvent -FilterHashtable @{LogName = 'System'; Id = 41; StartTime = (Get-Date).AddDays(-1) } -EA SilentlyContinue).Count
    $crashLvl = if ($crashes -gt 0) { 'error' } else { 'ok' }
    Write-Status "Crashes (24h): $crashes" $crashLvl

    $scheme = powercfg /getactivescheme 2>$null
    if ($scheme -match 'High performance|8c5e7fda') { Write-Status "Power plan: High Performance (no thermal protection!)" 'warn' }
    else { Write-Status "Power plan: OK" 'ok' }

    return @{ MemPct = $memPct; MemFreeGB = $memFree; CDiskFreeGB = $cFreeGB; CDiskFreePct = $cFreePct; TempGB = $tempSize + $winTemp; WsMemGB = $wsMem; WsProcs = $wsProcs.Count; Crashes = $crashes }
}

# ============================================================
# 2. CLEAN
# ============================================================
function Invoke-Clean {
    Write-Status "System Cleanup" 'title'
    $cBefore = (Get-Volume -DriveLetter C).SizeRemaining

    # User TEMP
    Write-Status "Cleaning user TEMP: $env:TEMP" 'info'
    if (-not $DryRun) {
        Get-ChildItem $env:TEMP -Recurse -Force -EA SilentlyContinue |
        Where-Object { -not $_.PSIsContainer -and $_.LastWriteTime -lt (Get-Date).AddHours(-2) } |
        Remove-Item -Force -EA SilentlyContinue
        Get-ChildItem $env:TEMP -Directory -Force -EA SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddHours(-2) } |
        Remove-Item -Recurse -Force -EA SilentlyContinue
    }
    Write-Status "User TEMP cleaned" 'ok'

    # Windows TEMP
    if (-not $DryRun) {
        Get-ChildItem C:\Windows\Temp -Recurse -Force -EA SilentlyContinue |
        Where-Object { -not $_.PSIsContainer -and $_.LastWriteTime -lt (Get-Date).AddHours(-2) } |
        Remove-Item -Force -EA SilentlyContinue
    }
    Write-Status "Windows TEMP cleaned" 'ok'

    # Windows Update cache
    $wuSize = [math]::Round((Get-ChildItem C:\Windows\SoftwareDistribution\Download -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum / 1GB, 1)
    if ($wuSize -gt 0.5 -and -not $DryRun) {
        Stop-Service wuauserv -Force -EA SilentlyContinue
        Remove-Item C:\Windows\SoftwareDistribution\Download\* -Recurse -Force -EA SilentlyContinue
        Start-Service wuauserv -EA SilentlyContinue
        Write-Status "WU cache cleaned: ${wuSize}GB" 'ok'
    }

    # Windsurf caches
    foreach ($p in @("$env:APPDATA\Windsurf\CachedExtensionVSIXs", "$env:APPDATA\Windsurf\CachedData", "$env:APPDATA\Windsurf\logs", "$env:LOCALAPPDATA\windsurf-unlimited-updater")) {
        if (Test-Path $p) {
            $sz = [math]::Round((Get-ChildItem $p -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum / 1GB, 1)
            if ($sz -gt 0.1) {
                Write-Status "Windsurf cache $([IO.Path]::GetFileName($p)): ${sz}GB" 'info'
                if (-not $DryRun -and $Force) { Remove-Item "$p\*" -Recurse -Force -EA SilentlyContinue }
            }
        }
    }

    # npm cache
    $npmCache = "$env:LOCALAPPDATA\npm-cache"
    if (Test-Path $npmCache) {
        $npmSz = [math]::Round((Get-ChildItem $npmCache -Recurse -File -EA SilentlyContinue | Measure-Object Length -Sum).Sum / 1GB, 1)
        if ($npmSz -gt 0.5) { Write-Status "npm cache: ${npmSz}GB (run: npm cache clean --force)" 'info' }
    }

    # Recycle bin
    if (-not $DryRun -and $Force) {
        Clear-RecycleBin -Force -EA SilentlyContinue
        Write-Status "Recycle bin emptied" 'ok'
    }

    $cAfter = (Get-Volume -DriveLetter C).SizeRemaining
    $recovered = [math]::Round(($cAfter - $cBefore) / 1GB, 1)
    Write-Status "C: recovered: ${recovered}GB (now $([math]::Round($cAfter/1GB,1))GB free)" 'ok'
}

# ============================================================
# 3. PROTECT
# ============================================================
function Invoke-Protect {
    Write-Status "System Protection" 'title'

    # Power plan -> Balanced (thermal protection)
    $current = powercfg /getactivescheme 2>$null
    if ($current -match 'High performance|8c5e7fda') {
        Write-Status "Switching power plan: High Performance -> Balanced" 'info'
        if (-not $DryRun) { powercfg /setactive '381b4222-f694-41f0-9685-ff5bb260df2e' }
        Write-Status "Power plan switched to Balanced" 'ok'
    }
    else {
        Write-Status "Power plan: already Balanced" 'ok'
    }

    # Crash dump -> small minidump on D: (reduce C: pressure)
    Write-Status "Configuring crash dump -> D:\\Minidump" 'info'
    if (-not $DryRun) {
        Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl" -Name "CrashDumpEnabled" -Value 3 -EA SilentlyContinue
        Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\CrashControl" -Name "MinidumpDir" -Value "D:\Minidump" -EA SilentlyContinue
        New-Item -ItemType Directory -Path "D:\Minidump" -Force -EA SilentlyContinue | Out-Null
    }
    Write-Status "Crash dumps -> D:\\Minidump" 'ok'

    # Page file check
    $pf = Get-CimInstance Win32_PageFileUsage
    if ($pf.Name -match 'D:') { Write-Status "Page file on D: $($pf.AllocatedBaseSize)MB - good" 'ok' }
    else { Write-Status "Page file: $($pf.Name)" 'info' }
}

# ============================================================
# 4. FIX DRIVERS
# ============================================================
function Invoke-FixDrivers {
    Write-Status "Fix Bad Drivers" 'title'

    $drivers = @(
        @{ Name = 'AMDRyzenMasterDriverV26'; Desc = 'AMD OC driver (file missing)' }
        @{ Name = 'TsQBDrv'; Desc = 'Tencent security driver (orphan)' }
        @{ Name = 'AliPaladin'; Desc = 'Alibaba security driver (orphan)' }
    )

    foreach ($d in $drivers) {
        $svc = Get-Service -Name $d.Name -EA SilentlyContinue
        if ($svc) {
            Write-Status "$($d.Name): $($d.Desc)" 'warn'
            if (-not $DryRun) {
                Set-Service -Name $d.Name -StartupType Disabled -EA SilentlyContinue
                Stop-Service -Name $d.Name -Force -EA SilentlyContinue
                Write-Status "$($d.Name): DISABLED (restore: Set-Service -Name $($d.Name) -StartupType Manual)" 'ok'
            }
            else {
                Write-Status "$($d.Name): [DryRun] would disable" 'info'
            }
        }
        else {
            Write-Status "$($d.Name): not found or already clean" 'ok'
        }
    }
}

# ============================================================
# 5. MONITOR (real-time)
# ============================================================
function Invoke-Monitor {
    Write-Status "Real-time Monitor (Ctrl+C to stop)" 'title'
    Write-Host ""
    $lastClean = Get-Date

    while ($true) {
        $os = Get-CimInstance Win32_OperatingSystem
        $memPct = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize * 100, 1)
        $memFree = [math]::Round($os.FreePhysicalMemory / 1MB, 1)
        $cFree = [math]::Round((Get-Volume -DriveLetter C -EA SilentlyContinue).SizeRemaining / 1GB, 1)
        $procCount = @(Get-Process).Count
        $nodeCount = @(Get-Process -Name node -EA SilentlyContinue).Count

        $memColor = if ($memPct -gt 90) { 'Red' } elseif ($memPct -gt 80) { 'Yellow' } else { 'Green' }
        $diskColor = if ($cFree -lt 20) { 'Red' } elseif ($cFree -lt 40) { 'Yellow' } else { 'Green' }

        $ts = Get-Date -Format "HH:mm:ss"
        Write-Host -NoNewline "[$ts] "
        Write-Host -NoNewline "MEM: " ; Write-Host -NoNewline "${memPct}% (${memFree}GB free) " -ForegroundColor $memColor
        Write-Host -NoNewline "| C: " ; Write-Host -NoNewline "${cFree}GB " -ForegroundColor $diskColor
        Write-Host "| Procs: $procCount | Node: $nodeCount"

        # Auto-protect: kill biggest node process if memory > 95%
        if ($memPct -gt 95) {
            Write-Host "  CRITICAL: Memory >95%! Auto-releasing..." -ForegroundColor Red
            $bigNode = Get-Process -Name node -EA SilentlyContinue | Sort-Object WorkingSet64 -Descending | Select-Object -First 1
            if ($bigNode) {
                Write-Host "  Killing node PID=$($bigNode.Id) ($([math]::Round($bigNode.WorkingSet64/1MB))MB)" -ForegroundColor Red
                $bigNode | Stop-Process -Force
            }
        }

        # Auto-clean TEMP every 30 min
        if ((Get-Date) - $lastClean -gt [TimeSpan]::FromMinutes(30)) {
            $stale = Get-ChildItem $env:TEMP -Recurse -File -EA SilentlyContinue | Where-Object { $_.LastWriteTime -lt (Get-Date).AddHours(-1) }
            if ($stale) {
                $stale | Remove-Item -Force -EA SilentlyContinue
                Write-Host "  AUTO-CLEAN: $($stale.Count) temp files removed" -ForegroundColor Cyan
            }
            $lastClean = Get-Date
        }

        Start-Sleep -Seconds 10
    }
}

# ============================================================
# MAIN
# ============================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "    System Guardian v1.0" -ForegroundColor Cyan
Write-Host "    MECHREVO WUJIE 14" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

switch ($Action) {
    'diagnose' { Invoke-Diagnose }
    'clean' { Invoke-Clean }
    'protect' { Invoke-Protect }
    'fix-drivers' { Invoke-FixDrivers }
    'monitor' { Invoke-Monitor }
    'full' {
        Invoke-Diagnose | Out-Null
        Invoke-Clean
        Invoke-Protect
        Invoke-FixDrivers
        Write-Status "Full treatment complete" 'title'
        Write-Status "Recommend: reboot then run -Action monitor" 'info'
    }
}
