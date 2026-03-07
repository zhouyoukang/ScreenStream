# ============================================================
# 台式机安全守护者 (Desktop Guardian)
# 笔记本Agent远程执行，保护台式机系统安全
# ============================================================
param(
    [ValidateSet('diagnose', 'fix', 'protect', 'report', 'hosts-guard')]
    [string]$Action = 'diagnose'
)

$ErrorActionPreference = 'Continue'
$results = @()
$fixed = @()
$blocked = @()

function Log($msg, $level = 'INFO') {
    $ts = Get-Date -Format 'HH:mm:ss'
    $line = "[$ts][$level] $msg"
    Write-Host $line -ForegroundColor $(switch ($level) { 'CRIT' { 'Red' } 'WARN' { 'Yellow' } 'FIX' { 'Green' } 'INFO' { 'Cyan' } default { 'White' } })
    $script:results += $line
}

# ============================================================
# Phase 1: DIAGNOSE
# ============================================================
if ($Action -in 'diagnose', 'fix', 'report') {
    Log "=== Phase 1: DIAGNOSE ===" 'INFO'

    # 1.1 ai account - NO PASSWORD + ADMIN = CRITICAL
    $ai = Get-LocalUser -Name 'ai' -ErrorAction SilentlyContinue
    if ($ai -and $ai.Enabled -and -not $ai.PasswordRequired) {
        Log "CRIT-01: ai account ENABLED, NO PASSWORD, in Administrators group" 'CRIT'
        Log "  -> Any network user can RDP/login as admin without password" 'CRIT'
    }

    # 1.2 AlibabaProtect
    $ali = Get-Service AlibabaProtect -ErrorAction SilentlyContinue
    if ($ali -and $ali.Status -eq 'Running') {
        Log "CRIT-02: AlibabaProtect STILL RUNNING (275MB bloatware/spyware)" 'CRIT'
    }

    # 1.3 Firewall + Defender
    $fwOff = (Get-NetFirewallProfile | Where-Object { -not $_.Enabled }).Count
    if ($fwOff -gt 0) {
        $huorong = Get-Service HipsDaemon -ErrorAction SilentlyContinue
        if ($huorong -and $huorong.Status -eq 'Running') {
            Log "WARN-03: Windows Firewall OFF ($fwOff/3 profiles) — Huorong active as replacement" 'WARN'
        }
        else {
            Log "CRIT-03: Windows Firewall OFF AND no alternative firewall!" 'CRIT'
        }
    }

    $def = Get-MpComputerStatus -ErrorAction SilentlyContinue
    if ($def -and -not $def.RealTimeProtectionEnabled) {
        $huorong = Get-Service HipsDaemon -ErrorAction SilentlyContinue
        if ($huorong -and $huorong.Status -eq 'Running') {
            Log "INFO-04: Defender disabled — Huorong (火绒) is active replacement" 'INFO'
        }
        else {
            Log "CRIT-04: BOTH Defender AND Huorong disabled!" 'CRIT'
        }
    }

    # 1.4 unlock_all.bat in Startup
    $unlockBat = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\unlock_all.bat"
    if (Test-Path $unlockBat) {
        Log "CRIT-05: unlock_all.bat in Startup — auto-disables LimitBlankPasswordUse on every boot!" 'CRIT'
        Log "  -> This ACTIVELY UNDERMINES security by allowing blank password network access" 'CRIT'
    }

    # 1.5 windsurf-LG
    $wsLG = "$env:USERPROFILE\Desktop\windsurf-LG_1.0.0.10.p.exe"
    $wsLGlnk = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\windsurf-LG.lnk"
    if (Test-Path $wsLGlnk) {
        Log "WARN-06: windsurf-LG (third-party patcher) in Startup" 'WARN'
    }

    # 1.6 RDP config regression
    $rdp = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' -ErrorAction SilentlyContinue
    if ($rdp.fSingleSessionPerUser -ne 1) {
        Log "WARN-07: fSingleSessionPerUser=$($rdp.fSingleSessionPerUser) (should be 1)" 'WARN'
    }
    $rdpTcp = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -ErrorAction SilentlyContinue
    if ($rdpTcp.Shadow -ne 2) {
        Log "WARN-08: Shadow=$($rdpTcp.Shadow) (should be 2 for no-consent)" 'WARN'
    }

    # 1.7 SMB full disk shares
    $shares = Get-SmbShare | Where-Object { $_.Name -match 'Full' }
    if ($shares.Count -gt 0) {
        Log "WARN-09: $($shares.Count) full-disk SMB shares active (FullC/D/E/F)" 'WARN'
        Log "  -> Combined with firewall off = entire filesystem exposed" 'WARN'
    }

    # 1.8 Remote control tool bloat
    $remoteTools = @()
    foreach ($name in 'ToDesk', 'SunloginClient', 'Sunshine', 'mstsc') {
        $p = Get-Process $name -ErrorAction SilentlyContinue
        if ($p) { $remoteTools += "$name($([math]::Round(($p | Measure-Object WorkingSet64 -Sum).Sum/1MB))MB)" }
    }
    if ($remoteTools.Count -gt 2) {
        Log "WARN-10: $($remoteTools.Count) remote control tools running: $($remoteTools -join ', ')" 'WARN'
    }

    # 1.9 Process bloat
    $procStats = Get-Process | Measure-Object WorkingSet64 -Sum
    $procGB = [math]::Round($procStats.Sum / 1GB, 1)
    if ($procStats.Count -gt 300) {
        Log "WARN-11: $($procStats.Count) processes using ${procGB}GB RAM" 'WARN'
    }

    # 1.10 C: disk space
    $cVol = Get-Volume -DriveLetter C -ErrorAction SilentlyContinue
    if ($cVol) {
        $cFreeGB = [math]::Round($cVol.SizeRemaining / 1GB, 1)
        $cPct = [math]::Round(($cVol.Size - $cVol.SizeRemaining) / $cVol.Size * 100)
        if ($cFreeGB -lt 50) {
            Log "WARN-12: C: drive ${cFreeGB}GB free (${cPct}% used)" 'WARN'
        }
    }

    # 1.11 zhou1 ghost login
    $zhou1 = Get-LocalUser -Name 'zhou1' -ErrorAction SilentlyContinue
    if ($zhou1 -and -not $zhou1.Enabled -and $zhou1.LastLogon -and $zhou1.LastLogon.Date -eq (Get-Date).Date) {
        Log "WARN-13: zhou1 (disabled) has today's LastLogon — ghost activity?" 'WARN'
    }

    # 1.12 BingWallpaper from registry autorun
    $bwReg = Get-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' -ErrorAction SilentlyContinue
    if ($bwReg.BingWallpaperDaemon -and $bwReg.BingWallpaperDaemon -match 'Temp') {
        Log "WARN-14: BingWallpaper daemon running from Temp path" 'WARN'
    }

    # 1.13 OneDriveSetup loop
    if ($bwReg.OneDriveSetup -and $bwReg.OneDriveSetup -match 'thfirstsetup') {
        Log "WARN-15: OneDriveSetup stuck in first-time setup loop" 'WARN'
    }

    # 1.14 Connectify in autorun
    $hklmRun = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' -ErrorAction SilentlyContinue
    if ($hklmRun.'Connectify Hotspot') {
        Log "WARN-16: Connectify Hotspot in autorun (WiFi sharing, security risk)" 'WARN'
    }

    # 1.15 SolidWorks Flexnet
    $sw = Get-Service 'SolidWorks Flexnet Server' -ErrorAction SilentlyContinue
    if ($sw -and $sw.Status -eq 'Running') {
        Log "WARN-17: SolidWorks Flexnet Server running (unnecessary license server)" 'WARN'
    }

    # 1.16 NVIDIA Broadcast memory
    $nvb = Get-Process 'NVIDIA Broadcast' -ErrorAction SilentlyContinue
    if ($nvb) {
        $nvbMB = [math]::Round(($nvb | Measure-Object WorkingSet64 -Sum).Sum / 1MB)
        if ($nvbMB -gt 500) {
            Log "WARN-18: NVIDIA Broadcast using ${nvbMB}MB" 'WARN'
        }
    }

    # 1.17 hosts file windsurf/codeium hijack
    $hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
    $hostsHijack = Get-Content $hostsPath -ErrorAction SilentlyContinue | Where-Object { $_ -match 'windsurf|codeium|exafunction' }
    if ($hostsHijack) {
        Log "WARN-19: hosts file contains windsurf/codeium entries (may block Windsurf)" 'WARN'
        foreach ($line in $hostsHijack) { Log "  -> $line" 'WARN' }
    }

    # 1.18 W3SVC (IIS) must not be Automatic
    $w3svc = Get-Service W3SVC -ErrorAction SilentlyContinue
    if ($w3svc -and $w3svc.StartType -eq 'Automatic') {
        Log "CRIT-18: W3SVC (IIS) is Automatic — will lock port 443 via HTTP.sys!" 'CRIT'
    }

    # 1.19 SstpSvc must be Disabled
    $sstp = Get-Service SstpSvc -ErrorAction SilentlyContinue
    if ($sstp -and $sstp.Status -eq 'Running') {
        Log "WARN-20: SstpSvc (SSTP VPN) is running — may conflict with port 443" 'WARN'
    }

    # 1.20 windsurf-LG process and port 443
    $lgProc = Get-Process '*windsurf-LG*' -ErrorAction SilentlyContinue
    if (-not $lgProc) {
        Log "WARN-21: windsurf-LG process not found (should be running for Windsurf)" 'WARN'
    }
    else {
        $port443 = netstat -ano 2>$null | Select-String ':443\s' | Select-String 'LISTEN'
        if (-not $port443) {
            Log "WARN-22: windsurf-LG running but port 443 not listening" 'WARN'
        }
    }

    # 1.21 portproxy should be empty
    $pp = netsh interface portproxy show v4tov4 2>$null
    if ($pp -and $pp -match '\d+\.\d+\.\d+\.\d+') {
        Log "WARN-23: portproxy rules exist (should be empty)" 'WARN'
        Log "  -> $($pp -join ' | ')" 'WARN'
    }
}

# ============================================================
# Phase 2: FIX (only with -Action fix)
# ============================================================
if ($Action -eq 'fix') {
    Log "`n=== Phase 2: FIX ===" 'INFO'

    # FIX-01: Disable ai account (CRITICAL)
    try {
        Disable-LocalUser -Name 'ai' -ErrorAction Stop
        Log "FIX-01: Disabled ai account (was: no password + admin)" 'FIX'
        $fixed += 'ai account disabled'
    }
    catch { Log "FAILED: Disable ai account: $_" 'CRIT' }

    # FIX-02: Stop and disable AlibabaProtect
    try {
        Stop-Service AlibabaProtect -Force -ErrorAction SilentlyContinue
        Set-Service AlibabaProtect -StartupType Disabled -ErrorAction Stop
        # Also kill process
        Stop-Process -Name AlibabaProtect -Force -ErrorAction SilentlyContinue
        Log "FIX-02: AlibabaProtect stopped and disabled" 'FIX'
        $fixed += 'AlibabaProtect disabled'
    }
    catch { Log "FAILED: AlibabaProtect: $_" 'CRIT' }

    # FIX-03: Remove unlock_all.bat from Startup
    $unlockBat = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\unlock_all.bat"
    if (Test-Path $unlockBat) {
        # Backup first
        Copy-Item $unlockBat "$env:USERPROFILE\Desktop\unlock_all.bat.bak" -Force
        Remove-Item $unlockBat -Force
        Log "FIX-03: Removed unlock_all.bat from Startup (backed up to Desktop)" 'FIX'
        $fixed += 'unlock_all.bat removed from Startup'
    }

    # FIX-04: Re-enable LimitBlankPasswordUse
    try {
        Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' -Name LimitBlankPasswordUse -Value 1 -Type DWord
        Log "FIX-04: LimitBlankPasswordUse re-enabled (blocks blank password network access)" 'FIX'
        $fixed += 'LimitBlankPasswordUse=1'
    }
    catch { Log "FAILED: LimitBlankPasswordUse: $_" 'CRIT' }

    # FIX-05: Remove windsurf-LG from Startup
    $wsLGlnk = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\windsurf-LG.lnk"
    if (Test-Path $wsLGlnk) {
        Remove-Item $wsLGlnk -Force
        Log "FIX-05: Removed windsurf-LG.lnk from Startup" 'FIX'
        $fixed += 'windsurf-LG removed from Startup'
    }

    # FIX-06: Fix RDP settings
    try {
        Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server' -Name fSingleSessionPerUser -Value 1 -Type DWord
        Set-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp' -Name Shadow -Value 2 -Type DWord
        Log "FIX-06: RDP: fSingleSessionPerUser=1, Shadow=2" 'FIX'
        $fixed += 'RDP config fixed'
    }
    catch { Log "FAILED: RDP settings: $_" 'CRIT' }

    # FIX-07: Remove OneDriveSetup from autorun
    try {
        Remove-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' -Name 'OneDriveSetup' -ErrorAction Stop
        Log "FIX-07: Removed OneDriveSetup from autorun" 'FIX'
        $fixed += 'OneDriveSetup removed'
    }
    catch { Log "FAILED: OneDriveSetup: $_" 'CRIT' }

    # FIX-08: Remove BingWallpaper daemon from autorun (runs from Temp)
    try {
        Remove-ItemProperty 'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' -Name 'BingWallpaperDaemon' -ErrorAction Stop
        Log "FIX-08: Removed BingWallpaper daemon from autorun (was in Temp path)" 'FIX'
        $fixed += 'BingWallpaper daemon removed from autorun'
    }
    catch { Log "FAILED: BingWallpaper: $_" 'CRIT' }

    # FIX-09: Disable SolidWorks Flexnet
    try {
        Stop-Service 'SolidWorks Flexnet Server' -Force -ErrorAction SilentlyContinue
        Set-Service 'SolidWorks Flexnet Server' -StartupType Disabled -ErrorAction Stop
        Log "FIX-09: SolidWorks Flexnet Server disabled" 'FIX'
        $fixed += 'SolidWorks Flexnet disabled'
    }
    catch { Log "FAILED: Flexnet: $_" 'CRIT' }

    # FIX-10: Disable Connectify from autorun
    try {
        Remove-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Run' -Name 'Connectify Hotspot' -ErrorAction Stop
        Log "FIX-10: Removed Connectify Hotspot from autorun" 'FIX'
        $fixed += 'Connectify removed from autorun'
    }
    catch { Log "FAILED: Connectify: $_" 'CRIT' }

    # FIX-11: Disable AliProctectUpdate scheduled task
    try {
        Disable-ScheduledTask -TaskName 'AliProctectUpdate' -ErrorAction Stop
        Log "FIX-11: Disabled AliProctectUpdate scheduled task" 'FIX'
        $fixed += 'AliProctectUpdate task disabled'
    }
    catch { Log "FAILED: AliProctectUpdate task: $_" 'CRIT' }

    # FIX-12: Clean hosts file windsurf/codeium entries
    $hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
    $hostsContent = Get-Content $hostsPath -ErrorAction SilentlyContinue
    $dirty = $hostsContent | Where-Object { $_ -match 'windsurf|codeium|exafunction' }
    if ($dirty) {
        $clean = $hostsContent | Where-Object { $_ -notmatch 'windsurf|codeium|exafunction' }
        $clean | Set-Content $hostsPath -Encoding ASCII -Force
        ipconfig /flushdns | Out-Null
        Log "FIX-12: Cleaned $($dirty.Count) windsurf/codeium entries from hosts, flushed DNS" 'FIX'
        $fixed += 'hosts windsurf entries cleaned'
    }

    # FIX-13: Set W3SVC to Manual if Automatic
    $w3svc = Get-Service W3SVC -ErrorAction SilentlyContinue
    if ($w3svc -and $w3svc.StartType -eq 'Automatic') {
        Set-Service W3SVC -StartupType Manual -ErrorAction SilentlyContinue
        Log "FIX-13: W3SVC set to Manual (was Automatic, locks port 443)" 'FIX'
        $fixed += 'W3SVC set to Manual'
    }

    # FIX-14: Disable SstpSvc
    $sstp = Get-Service SstpSvc -ErrorAction SilentlyContinue
    if ($sstp -and $sstp.Status -eq 'Running') {
        Stop-Service SstpSvc -Force -ErrorAction SilentlyContinue
        Set-Service SstpSvc -StartupType Disabled -ErrorAction SilentlyContinue
        Log "FIX-14: SstpSvc stopped and disabled" 'FIX'
        $fixed += 'SstpSvc disabled'
    }

    Log "`nTotal fixed: $($fixed.Count) items" 'FIX'
}

# ============================================================
# Phase 3: PROTECT (Agent safety rules)
# ============================================================
if ($Action -in 'protect', 'fix') {
    Log "`n=== Phase 3: PROTECT (Agent Safety) ===" 'INFO'

    # Create a marker file that Agent scripts can check
    $guardFile = "C:\agent_guard.json"
    $guard = @{
        version          = '1.0'
        created          = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
        created_by       = 'desktop_guardian.ps1'
        frozen_paths     = @(
            'C:\Windows',
            'C:\Program Files',
            'C:\Program Files (x86)',
            'C:\ProgramData',
            'HKLM:\SYSTEM',
            'HKLM:\SOFTWARE'
        )
        safe_zones       = @(
            'D:\*',
            'E:\*',
            'C:\Users\Administrator\Desktop',
            'C:\Users\Administrator\Documents'
        )
        max_processes    = 500
        max_ram_pct      = 90
        blocked_commands = @(
            'format',
            'diskpart',
            'bcdedit',
            'reg delete HKLM',
            'Remove-Item C:\Windows',
            'Remove-Item C:\Program',
            'Stop-Computer',
            'Restart-Computer'
        )
    } | ConvertTo-Json -Depth 3
    $guard | Out-File $guardFile -Encoding UTF8
    Log "PROTECT: Created agent_guard.json at C:\" 'FIX'
}

# ============================================================
# Summary
# ============================================================
Log "`n=== SUMMARY ===" 'INFO'
$crits = ($results | Where-Object { $_ -match '\[CRIT\]' }).Count
$warns = ($results | Where-Object { $_ -match '\[WARN\]' }).Count
$fixes = ($results | Where-Object { $_ -match '\[FIX\]' }).Count
Log "Critical: $crits | Warnings: $warns | Fixed: $fixes" 'INFO'

# Save results
$logPath = "$env:USERPROFILE\Desktop\guardian_log.txt"
$results | Out-File $logPath -Encoding UTF8 -ErrorAction SilentlyContinue
Log "Results saved to $logPath" 'INFO'

# ============================================================
# Phase 4: HOSTS GUARD (continuous monitoring)
# ============================================================
if ($Action -eq 'hosts-guard') {
    Log "=== HOSTS GUARD MODE (60s interval, Ctrl+C to stop) ===" 'INFO'
    $hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
    while ($true) {
        $dirty = Get-Content $hostsPath -ErrorAction SilentlyContinue | Where-Object { $_ -match 'windsurf|codeium|exafunction' }
        if ($dirty) {
            $clean = Get-Content $hostsPath -ErrorAction SilentlyContinue | Where-Object { $_ -notmatch 'windsurf|codeium|exafunction' }
            $clean | Set-Content $hostsPath -Encoding ASCII -Force
            ipconfig /flushdns | Out-Null
            Log "[GUARD] Cleaned $($dirty.Count) windsurf/codeium entries from hosts" 'FIX'
        }
        Start-Sleep -Seconds 60
    }
}

# ============================================================
# Phase 5: REPORT (machine-readable JSON)
# ============================================================
if ($Action -eq 'report') {
    $report = @{
        timestamp = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ss')
        hostname  = $env:COMPUTERNAME
        criticals = ($results | Where-Object { $_ -match '\[CRIT\]' }).Count
        warnings  = ($results | Where-Object { $_ -match '\[WARN\]' }).Count
        details   = $results
    } | ConvertTo-Json -Depth 3
    Write-Output $report
}
