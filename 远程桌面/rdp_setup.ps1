param(
    [string]$Action = "menu",
    [string]$UserName = "",
    [string]$Password = "",
    [string]$TargetIP = "localhost"
)

function Write-OK($m) { Write-Host "  [OK] $m" -ForegroundColor Green }
function Write-WARN($m) { Write-Host "  [!!] $m" -ForegroundColor Yellow }
function Write-ERR($m) { Write-Host "  [XX] $m" -ForegroundColor Red }
function Write-Info($m) { Write-Host "  [..] $m" -ForegroundColor Gray }
function Write-Title($m) { Write-Host "`n  === $m ===" -ForegroundColor Cyan }

function Require-Admin {
    $isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Write-ERR "Need admin. Relaunching elevated..."
        Start-Process pwsh "-ExecutionPolicy Bypass -File `"$PSCommandPath`" -Action $Action" -Verb RunAs
        exit
    }
}

function Set-RDPCore {
    Write-Title "RDP Multi-Session Core Config"
    $ts = "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server"
    $rdpTcp = "$ts\WinStations\RDP-Tcp"
    $gp = "HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services"

    Set-ItemProperty $ts -Name fDenyTSConnections -Value 0
    Write-OK "RDP enabled"

    Set-ItemProperty $ts -Name fSingleSessionPerUser -Value 0
    Write-OK "Multi-session: fSingleSessionPerUser=0"

    Set-ItemProperty $rdpTcp -Name MaxInstanceCount -Value 0xFFFFFFFF
    Write-OK "MaxInstanceCount: unlimited"

    Set-ItemProperty $rdpTcp -Name UserAuthentication -Value 1
    Write-OK "NLA auth: enabled"

    if (-not (Test-Path $gp)) { New-Item $gp -Force | Out-Null }
    Set-ItemProperty $gp -Name MaxInstanceCount -Value 0xFFFFFFFF
    Set-ItemProperty $gp -Name fSingleSessionPerUser -Value 0
    Write-OK "Group Policy: multi-session configured"

    $fw = Get-NetFirewallRule -DisplayGroup "Remote Desktop" -ErrorAction SilentlyContinue
    if ($fw) {
        Enable-NetFirewallRule -DisplayGroup "Remote Desktop" -ErrorAction SilentlyContinue
        Write-OK "Firewall: Remote Desktop rules enabled"
    }
}

function Set-FiveSenses {
    Write-Title "Five Senses Full Mapping"
    $rdpTcp = "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp"
    $gp = "HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services"
    if (-not (Test-Path $gp)) { New-Item $gp -Force | Out-Null }

    # Vision: color depth
    Set-ItemProperty $rdpTcp -Name ColorDepth -Value 4
    Write-OK "Vision: 32-bit color depth"

    # Audio: playback + mic
    Set-ItemProperty $rdpTcp -Name AudioMode -Value 0
    Set-ItemProperty $gp -Name AudioRedirectionMode -Value 0
    Set-ItemProperty $gp -Name fDisableCam -Value 0
    Write-OK "Audio: playback + microphone redirection ON"

    # Touch: clipboard
    Set-ItemProperty $rdpTcp -Name fDisableClip -Value 0
    Set-ItemProperty $gp -Name fDisableClip -Value 0
    Write-OK "Touch: clipboard bidirectional sync ON"

    # Action: drives + printers
    Set-ItemProperty $rdpTcp -Name fDisableCdm -Value 0
    Set-ItemProperty $rdpTcp -Name fDisablePrnt -Value 0
    Set-ItemProperty $gp -Name fDisableCdm -Value 0
    Write-OK "Action: local drives + printers mapped"

    # Perception: COM/USB ports + multi-monitor
    Set-ItemProperty $rdpTcp -Name fDisableCcm -Value 0
    Set-ItemProperty $rdpTcp -Name fDisableLPT -Value 0
    Set-ItemProperty $gp -Name fDisableCcm -Value 0
    Set-ItemProperty $gp -Name MaxMonitors -Value 16
    Write-OK "Perception: COM/LPT ports + 16-monitor support ON"
}

function Manage-Users {
    Write-Title "RDP User Account Management"
    $rdpGroup = "Remote Desktop Users"

    Write-Info "Current local users:"
    Get-LocalUser | ForEach-Object {
        $tag = if ($_.Enabled) { "[ON] " } else { "[OFF]" }
        Write-Host "       $tag  $($_.Name)"
    }

    foreach ($uname in @("zhou", "zhou1")) {
        $u = Get-LocalUser -Name $uname -ErrorAction SilentlyContinue
        if ($u) {
            if (-not $u.Enabled) { Enable-LocalUser -Name $uname; Write-OK "Enabled user: $uname" }
            else { Write-OK "User already enabled: $uname" }
            try {
                Add-LocalGroupMember -Group $rdpGroup -Member $uname -ErrorAction Stop
                Write-OK "$uname added to Remote Desktop Users"
            }
            catch { Write-Info "$uname already in Remote Desktop Users" }
        }
    }
    Write-Info "To add a new user: .\rdp_setup.ps1 -Action adduser -UserName NAME -Password PASS"
}

function Add-RDPUser($name, $pass) {
    Write-Title "Create RDP user: $name"
    try {
        $secPass = ConvertTo-SecureString $pass -AsPlainText -Force
        New-LocalUser -Name $name -Password $secPass -PasswordNeverExpires -ErrorAction Stop
        Add-LocalGroupMember -Group "Remote Desktop Users" -Member $name
        Write-OK "User $name created and added to RDP group"
    }
    catch { Write-ERR "Failed: $_" }
}

function New-RDPFiles {
    Write-Title "Generate .rdp connection files"
    $rdpDir = "E:\道\AI之电脑\rdp连接配置"
    if (-not (Test-Path $rdpDir)) { New-Item $rdpDir -ItemType Directory | Out-Null }

    # Auto-detect own IP, prefer 192.168.31.x (WiFi) subnet
    $allIPs = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
    Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.*' }
    $desktopIP = ($allIPs | Where-Object { $_.IPAddress -like '192.168.31.*' } | Select-Object -First 1).IPAddress
    if (-not $desktopIP) {
        $desktopIP = ($allIPs | Where-Object { $_.IPAddress -like '192.168.*' } | Select-Object -First 1).IPAddress
    }
    if (-not $desktopIP) { $desktopIP = "127.0.0.1" }
    Write-Info "Desktop IP: $desktopIP (auto-detected)"

    $template = "screen mode id:i:2`r`nuse multimon:i:1`r`ndesktopwidth:i:2560`r`ndesktopheight:i:1440`r`nsession bpp:i:32`r`ncompression:i:1`r`nkeyboardhook:i:2`r`naudiocapturemode:i:1`r`nvideoplaybackmode:i:1`r`nconnection type:i:7`r`nnetworkautodetect:i:1`r`nbandwidthautodetect:i:1`r`ndisplayconnectionbar:i:1`r`nallow font smoothing:i:1`r`nallow desktop composition:i:1`r`ndisable wallpaper:i:0`r`nbitmapcachepersistenable:i:1`r`naudiomode:i:0`r`nredirectprinters:i:1`r`nredirectcomports:i:1`r`nredirectsmartcards:i:1`r`nredirectclipboard:i:1`r`ndrivestoredirect:s:*`r`nautoreconnection enabled:i:1`r`nauthentication level:i:2`r`nnegotiate security layer:i:1`r`n"

    foreach ($user in @("zhou", "zhou1", "Administrator")) {
        $content = "full address:s:$desktopIP`r`nusername:s:$user`r`n" + $template
        $f = Join-Path $rdpDir "desktop_$user.rdp"
        [System.IO.File]::WriteAllText($f, $content, [System.Text.Encoding]::ASCII)
        Write-OK "Created: desktop_$user.rdp"

        $localContent = "full address:s:127.0.0.2`r`nusername:s:.\$user`r`ndisable wallpaper:i:1`r`nprompt for credentials:i:0`r`n" + $template
        $f2 = Join-Path $rdpDir "localhost_$user.rdp"
        [System.IO.File]::WriteAllText($f2, $localContent, [System.Text.Encoding]::ASCII)
        Write-OK "Created: localhost_$user.rdp (127.0.0.2 — 强制新会话)"
    }

    # ai 账号：只生成 localhost 文件（ai 专用于本机多会话，不暴露到 LAN）
    $aiLocal = "full address:s:127.0.0.2`r`nusername:s:.\ai`r`ndisable wallpaper:i:1`r`nprompt for credentials:i:0`r`n" + $template
    $fAi = Join-Path $rdpDir "localhost_ai.rdp"
    [System.IO.File]::WriteAllText($fAi, $aiLocal, [System.Text.Encoding]::ASCII)
    Write-OK "Created: localhost_ai.rdp (ai 专用多会话入口)"
    Write-Info "RDP files saved to: $rdpDir"
}

function Show-Status {
    Write-Title "RDP Multi-Session System Status"

    $svcDll = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\TermService\Parameters" -ErrorAction SilentlyContinue).ServiceDll
    if ($svcDll -like "*rdpwrap*") { Write-OK "RDP Wrapper: ACTIVE" }
    else { Write-WARN "RDP Wrapper: not active (dll=$svcDll)" }

    $vi = (Get-Item "C:\Windows\System32\termsrv.dll").VersionInfo
    $ver = "$($vi.FileMajorPart).$($vi.FileMinorPart).$($vi.FileBuildPart).$($vi.FilePrivatePart)"
    Write-Info "termsrv.dll: $ver"

    $iniPath = "C:\Program Files\RDP Wrapper\rdpwrap.ini"
    if (Test-Path $iniPath) {
        $iniContent = Get-Content $iniPath -Raw -ErrorAction SilentlyContinue
        if ($iniContent -match [regex]::Escape("[$ver]")) {
            Write-OK "rdpwrap.ini: [$ver] 完整支持 (FullSupport)"
        }
        else {
            Write-ERR "rdpwrap.ini: [$ver] 无条目 (Partial/NotSupported) — 运行选项[7]更新"
        }
    }
    else {
        Write-WARN "rdpwrap.ini: 文件不存在 — RDP Wrapper 未安装，请选项[6]"
    }

    $svc = Get-Service TermService
    Write-OK "TermService: $($svc.Status)"

    $fSingle = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server").fSingleSessionPerUser
    if ($fSingle -eq 0) { Write-OK "Single-session lock: OFF (multi-session OK)" }
    else { Write-ERR "Single-session lock: ON (fSingleSessionPerUser=$fSingle)" }

    $fDeny = (Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server").fDenyTSConnections
    if ($fDeny -eq 0) { Write-OK "RDP connections: ALLOWED" }
    else { Write-ERR "RDP connections: DENIED (fDenyTSConnections=$fDeny)" }

    Write-Info "Local users in RDP group:"
    Get-LocalGroupMember -Group "Remote Desktop Users" -ErrorAction SilentlyContinue | ForEach-Object {
        Write-Host "       $($_.Name)"
    }
}

function Show-Menu {
    Clear-Host
    Write-Host "`n  +--------------------------------------------+" -ForegroundColor Cyan
    Write-Host "  |  Windows RDP Multi-Session Manager          |" -ForegroundColor Cyan
    Write-Host "  |  Multi-Account / Multi-Device / 5-Senses    |" -ForegroundColor Cyan
    Write-Host "  +--------------------------------------------+`n" -ForegroundColor Cyan
    Write-Host "  [1] Show system status"
    Write-Host "  [2] Apply full config (RDP core + 5 senses)"
    Write-Host "  [3] Manage RDP user accounts"
    Write-Host "  [4] Generate .rdp connection files"
    Write-Host "  [5] Restart TermService"
    Write-Host "  [6] Install/Update RDP Wrapper (unlock multi-session)" -ForegroundColor Yellow
    Write-Host "  [7] Update rdpwrap.ini (fix Partial/NotSupported)" -ForegroundColor Yellow
    Write-Host "  [8] Install Guardian (auto-repair on Windows Update + ai session)" -ForegroundColor Magenta
    Write-Host "  [9] Guardian status / recent log" -ForegroundColor Magenta
    Write-Host "  [0] Exit`n"
    $c = Read-Host "  Select"
    switch ($c) {
        "1" { Show-Status; Read-Host "`n  Press Enter to continue"; Show-Menu }
        "2" { Require-Admin; Set-RDPCore; Set-FiveSenses; Restart-Service TermService -Force; Write-OK "TermService restarted"; Read-Host "`n  Done. Press Enter"; Show-Menu }
        "3" { Require-Admin; Manage-Users; Read-Host "`n  Press Enter"; Show-Menu }
        "4" { New-RDPFiles; Read-Host "`n  Press Enter"; Show-Menu }
        "5" { Require-Admin; Restart-Service TermService -Force; Write-OK "Restarted"; Start-Sleep 1; Show-Menu }
        "6" { Require-Admin; Start-Process pwsh "-ExecutionPolicy Bypass -File `"$PSScriptRoot\install-rdpwrap.ps1`"" -Verb RunAs -Wait; Read-Host "`n  Press Enter"; Show-Menu }
        "7" { Require-Admin; Start-Process pwsh "-ExecutionPolicy Bypass -File `"$PSScriptRoot\install-rdpwrap.ps1`" -UpdateIni" -Verb RunAs -Wait; Read-Host "`n  Press Enter"; Show-Menu }
        "8" { Require-Admin; Start-Process pwsh "-ExecutionPolicy Bypass -File `"$PSScriptRoot\rdp_guardian.ps1`" -Install" -Verb RunAs -Wait; Read-Host "`n  Press Enter"; Show-Menu }
        "9" { Start-Process pwsh "-ExecutionPolicy Bypass -File `"$PSScriptRoot\rdp_guardian.ps1`" -Status" -Wait; Read-Host "`n  Press Enter"; Show-Menu }
        "0" { exit }
        default { Show-Menu }
    }
}

switch ($Action.ToLower()) {
    "menu" { Show-Menu }
    "setup" { Require-Admin; Set-RDPCore; Set-FiveSenses; Manage-Users; New-RDPFiles; Restart-Service TermService -Force; Show-Status }
    "status" { Show-Status }
    "config" { Require-Admin; Set-RDPCore; Set-FiveSenses; Restart-Service TermService -Force; Write-OK "Done" }
    "users" { Require-Admin; Manage-Users }
    "rdpfiles" { New-RDPFiles }
    "adduser" { Require-Admin; Add-RDPUser $UserName $Password }
    "installwrap" { Require-Admin; Start-Process pwsh "-ExecutionPolicy Bypass -File `"$PSScriptRoot\install-rdpwrap.ps1`"" -Verb RunAs -Wait }
    "updateini" { Require-Admin; Start-Process pwsh "-ExecutionPolicy Bypass -File `"$PSScriptRoot\install-rdpwrap.ps1`" -UpdateIni" -Verb RunAs -Wait }
    "guardian" { Require-Admin; Start-Process pwsh "-ExecutionPolicy Bypass -File `"$PSScriptRoot\rdp_guardian.ps1`" -Install" -Verb RunAs -Wait }
    "guardstatus" { Start-Process pwsh "-ExecutionPolicy Bypass -File `"$PSScriptRoot\rdp_guardian.ps1`" -Status" -Wait }
    "fullsetup" { Require-Admin; Set-RDPCore; Set-FiveSenses; Manage-Users; New-RDPFiles; Restart-Service TermService -Force; Start-Process pwsh "-ExecutionPolicy Bypass -File `"$PSScriptRoot\install-rdpwrap.ps1`"" -Verb RunAs -Wait; Start-Process pwsh "-ExecutionPolicy Bypass -File `"$PSScriptRoot\rdp_guardian.ps1`" -Install" -Verb RunAs -Wait; Show-Status }
    default { Show-Menu }
}
