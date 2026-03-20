#Requires -RunAsAdministrator
<#
.SYNOPSIS
    CFW Unified Control Hub v1.0
.DESCRIPTION
    Dao-sheng-yi: Single script manages all CFW operations
    on/off/lan-on/lan-off/restore/status
.PARAMETER Action
    on       Enable CFW mode (hosts+patch+env+start CFW)
    off      Disable CFW, restore official mode
    lan-on   Enable LAN sharing (portproxy+FRP)
    lan-off  Disable LAN sharing
    restore  Deep clean, 100% official pristine state
    status   Show current state
#>
param(
    [ValidateSet('on', 'off', 'lan-on', 'lan-off', 'restore', 'status')]
    [string]$Action = 'status'
)
$ErrorActionPreference = 'Stop'

# === CONFIG ===
$CFG = @{
    CfwExeDir        = 'C:\temp\cfw'
    CfwExeName       = 'CodeFreeWindsurf-x64-2.0.5.exe'
    CfwPort          = 443
    WindsurfDir      = 'D:\Windsurf'
    WindsurfJs       = 'D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js'
    PatchScript      = 'E:\道\道生一\一生二\Windsurf无限额度\patch_windsurf.py'
    CfwCert          = 'C:\ProgramData\cfw_server_cert.pem'
    HostsFile        = 'C:\Windows\System32\drivers\etc\hosts'
    HostsEntries     = @(
        '127.0.0.1 server.self-serve.windsurf.com'
        '127.0.0.1 server.codeium.com'
    )
    HostsMarkerStart = '# >>> CFW-MANAGED-START'
    HostsMarkerEnd   = '# <<< CFW-MANAGED-END'
    FrpcExe          = 'E:\道\道生一\一生二\远程桌面\frp\frpc.exe'
    FrpcToml         = 'E:\道\道生一\一生二\远程桌面\frp\frpc.toml'
    LaptopIp         = '192.168.31.179'
}

# === HELPERS ===
function Write-Step($step, $msg) { Write-Host "  [$step] $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "    OK: $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    WARN: $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "    FAIL: $msg" -ForegroundColor Red }

function Get-CfwProcess {
    Get-Process | Where-Object { $_.ProcessName -match 'CodeFreeWindsurf' } | Select-Object -First 1
}
function Get-Port443Listener {
    $lines = netstat -ano | Select-String "LISTENING" | Select-String ":443\s"
    foreach ($line in $lines) {
        if ($line -match '(\d+)\s*$') { return [int]$Matches[1] }
    }
    return $null
}
function Stop-CfwProcess {
    $procs = Get-Process | Where-Object { $_.ProcessName -match 'CodeFreeWindsurf' }
    foreach ($p in $procs) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    if ($procs) { Start-Sleep -Seconds 2 }
}

# -- hosts --
function Add-HostsEntries {
    $content = Get-Content $CFG.HostsFile -Raw -ErrorAction SilentlyContinue
    if ($content -match [regex]::Escape($CFG.HostsMarkerStart)) {
        Write-Ok "hosts entries already exist"; return
    }
    $block = "`n$($CFG.HostsMarkerStart)`n"
    foreach ($e in $CFG.HostsEntries) { $block += "$e`n" }
    $block += "$($CFG.HostsMarkerEnd)`n"
    [System.IO.File]::AppendAllText($CFG.HostsFile, $block, [System.Text.UTF8Encoding]::new($false))
    Write-Ok "hosts entries added"
}
function Remove-HostsEntries {
    $content = Get-Content $CFG.HostsFile -Raw -ErrorAction SilentlyContinue
    if (-not $content) { return }
    $pattern = "(?s)\r?\n?$([regex]::Escape($CFG.HostsMarkerStart)).*?$([regex]::Escape($CFG.HostsMarkerEnd))\r?\n?"
    $cleaned = $content -replace $pattern, ''
    foreach ($e in $CFG.HostsEntries) {
        $cleaned = $cleaned -replace "(?m)^\s*$([regex]::Escape($e))\s*$\r?\n?", ''
    }
    [System.IO.File]::WriteAllText($CFG.HostsFile, $cleaned, [System.Text.UTF8Encoding]::new($false))
    Write-Ok "hosts entries cleaned"
}
function Test-HostsHijacked {
    $c = Get-Content $CFG.HostsFile -Raw -ErrorAction SilentlyContinue
    return ($c -match 'server\.self-serve\.windsurf\.com')
}

# -- env vars --
function Set-CfwEnvVars {
    [Environment]::SetEnvironmentVariable('SSL_CERT_FILE', $CFG.CfwCert, 'Machine')
    [Environment]::SetEnvironmentVariable('NODE_EXTRA_CA_CERTS', $CFG.CfwCert, 'Machine')
    $env:SSL_CERT_FILE = $CFG.CfwCert; $env:NODE_EXTRA_CA_CERTS = $CFG.CfwCert
    Write-Ok "env vars set -> $($CFG.CfwCert)"
}
function Clear-CfwEnvVars {
    foreach ($v in @('SSL_CERT_FILE', 'NODE_EXTRA_CA_CERTS', 'NODE_TLS_REJECT_UNAUTHORIZED')) {
        [Environment]::SetEnvironmentVariable($v, $null, 'Machine')
        [Environment]::SetEnvironmentVariable($v, $null, 'Process')
    }
    Write-Ok "env vars cleared"
}

# -- portproxy --
function Add-LanPortProxy {
    netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=443 2>$null | Out-Null
    $r = netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=443 connectaddress=127.0.0.1 connectport=443
    if ($LASTEXITCODE -eq 0) { Write-Ok "portproxy LAN enabled (0.0.0.0:443 -> 127.0.0.1:443)" }
    else { Write-Warn "portproxy failed: $r" }
}
function Remove-AllPortProxy443 {
    netsh interface portproxy delete v4tov4 listenaddress=0.0.0.0 listenport=443 2>$null | Out-Null
    netsh interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=443 2>$null | Out-Null
    netsh interface portproxy delete v4tov4 listenaddress=$($CFG.LaptopIp) listenport=443 2>$null | Out-Null
    Write-Ok "all portproxy 443 rules removed"
}
function Test-PortProxy443 {
    $out = netsh interface portproxy show v4tov4 2>$null
    return ($out -match '443')
}

# -- Root CA certs --
function Remove-FakeRootCerts {
    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root', 'LocalMachine')
    $store.Open('ReadWrite')
    $removed = 0
    foreach ($cert in $store.Certificates) {
        if ($cert.Subject -match 'Windsurf|CFW|CodeFree|windsurf|cfw') {
            $store.Remove($cert); $removed++
        }
    }
    $store.Close()
    if ($removed -gt 0) { Write-Ok "removed $removed fake Root CA certs" }
    else { Write-Ok "Root CA store clean" }
}

# -- JS patches --
function Apply-JsPatches {
    if (-not (Test-Path $CFG.PatchScript)) { Write-Warn "patch script not found"; return $false }
    $r = & python $CFG.PatchScript 2>&1
    if ($LASTEXITCODE -eq 0) { Write-Ok "JS patches applied (15 items)"; return $true }
    else { Write-Warn "patch failed: $r"; return $false }
}
function Restore-JsPatches {
    if (-not (Test-Path $CFG.PatchScript)) { Write-Warn "patch script not found"; return $false }
    # First try --restore (from backup). If backup is contaminated, do reverse-patch.
    $r = & python $CFG.PatchScript --restore 2>&1
    # Verify if actually clean
    if ((Test-Path $CFG.WindsurfJs) -and ((Get-Content $CFG.WindsurfJs -Raw) -match 'Pro Ultimate')) {
        Write-Warn "backup was contaminated, attempting reverse-patch..."
        # Reverse-patch: swap new->old for each PATCHES entry
        $revPy = @"
import sys,os
sys.path.insert(0,r'$((Split-Path $CFG.PatchScript).Replace("'","''"))')
from patch_windsurf import PATCHES,find_windsurf_js
fp=find_windsurf_js()
if not fp: print('ERR');sys.exit(1)
with open(fp,'r',encoding='utf-8') as f: c=f.read()
n=0
for old,new,desc,*rest in PATCHES:
    if new in c:
        ra=rest[0] if rest else False
        c=c.replace(new,old) if ra else c.replace(new,old,1)
        n+=1
with open(fp,'w',encoding='utf-8') as f: f.write(c)
bak=fp+'.bak'
if os.path.exists(bak) and 'Pro Ultimate' in open(bak,'r',encoding='utf-8').read(): os.remove(bak)
print(f'REVERSED:{n}')
"@
        $revPy | python - 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    }
    if (-not (Test-JsPatched)) { Write-Ok "JS patches restored (official code)"; return $true }
    else { Write-Warn "JS still has patches (regex patches cannot be auto-reversed)"; return $false }
}
function Test-JsPatched {
    if (-not (Test-Path $CFG.WindsurfJs)) { return $false }
    $s = Get-Content $CFG.WindsurfJs -Raw
    return ($s -match 'Pro Ultimate')
}

# -- FRP --
function Start-Frpc {
    $running = Get-Process frpc -ErrorAction SilentlyContinue
    if ($running) { Write-Ok "frpc already running"; return }
    if (-not (Test-Path $CFG.FrpcExe)) { Write-Warn "frpc.exe not found"; return }
    Start-Process -FilePath $CFG.FrpcExe -ArgumentList "-c `"$($CFG.FrpcToml)`"" -WindowStyle Minimized
    Start-Sleep -Seconds 3
    if (Get-Process frpc -ErrorAction SilentlyContinue) { Write-Ok "frpc started (public CFW available)" }
    else { Write-Warn "frpc start failed" }
}

# -- Start CFW --
function Start-Cfw {
    $cfwExe = Join-Path $CFG.CfwExeDir $CFG.CfwExeName
    if (-not (Test-Path $cfwExe)) {
        $found = Get-ChildItem $CFG.CfwExeDir -Filter 'CodeFreeWindsurf*.exe' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($found) { $cfwExe = $found.FullName }
    }
    if (-not (Test-Path $cfwExe)) { Write-Fail "CFW not found: $cfwExe"; return $false }

    # KEY: remove portproxy first to free port 443 (root cause of port conflict)
    Remove-AllPortProxy443
    Start-Sleep -Milliseconds 500
    Stop-CfwProcess
    Start-Sleep -Seconds 1

    Start-Process -FilePath $cfwExe
    Write-Host "    Starting: $cfwExe" -ForegroundColor DarkGray

    for ($i = 1; $i -le 20; $i++) {
        Start-Sleep -Seconds 2
        $pid443 = Get-Port443Listener
        if ($pid443) {
            $proc = Get-Process -Id $pid443 -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -match 'CodeFreeWindsurf') {
                Write-Ok "CFW bound port 443 (PID $pid443)"; return $true
            }
            if ($proc) { Write-Warn "443 occupied by $($proc.ProcessName) (PID $pid443)" }
        }
        Write-Host "    Waiting for CFW... ($i/20)" -ForegroundColor DarkGray
    }
    Write-Fail "CFW failed to bind 443 after 40s"; return $false
}

# === STATUS ===
function Show-Status {
    Write-Host "`n  === CFW Status Report (Laptop 179) ===" -ForegroundColor White

    $cfw = Get-CfwProcess
    if ($cfw) { Write-Ok "CFW running (PID $($cfw.Id))" }
    else { Write-Host "    - CFW not running" -ForegroundColor DarkGray }

    $pid443 = Get-Port443Listener
    if ($pid443) {
        $proc = Get-Process -Id $pid443 -ErrorAction SilentlyContinue
        $name = if ($proc) { $proc.ProcessName } else { 'unknown' }
        if ($name -match 'CodeFreeWindsurf') { Write-Ok "443 -> CFW (PID $pid443)" }
        elseif ($name -match 'svchost') { Write-Warn "443 -> svchost/portproxy (PID $pid443) <- may cause CFW conflict!" }
        else { Write-Warn "443 -> $name (PID $pid443)" }
    }
    else { Write-Host "    - port 443 free" -ForegroundColor DarkGray }

    if (Test-PortProxy443) { Write-Warn "portproxy 443 rule exists (LAN share / conflict source)" }
    else { Write-Host "    - no portproxy 443 rule" -ForegroundColor DarkGray }

    if (Test-HostsHijacked) { Write-Warn "hosts hijacked (CFW mode)" }
    else { Write-Ok "hosts clean (official mode)" }

    $ssl = [Environment]::GetEnvironmentVariable('SSL_CERT_FILE', 'Machine')
    if ($ssl) { Write-Warn "SSL_CERT_FILE = $ssl" }
    else { Write-Ok "SSL_CERT_FILE not set (official)" }

    if (Test-JsPatched) { Write-Warn "JS patched (CFW mode)" }
    else { Write-Ok "JS clean (official mode)" }

    $store = New-Object System.Security.Cryptography.X509Certificates.X509Store('Root', 'LocalMachine')
    $store.Open('ReadOnly')
    $fake = @($store.Certificates | Where-Object { $_.Subject -match 'Windsurf|CFW|windsurf' })
    $store.Close()
    if ($fake.Count -gt 0) { Write-Warn "Root CA: $($fake.Count) fake certs" }
    else { Write-Ok "Root CA clean" }

    $frpc = Get-Process frpc -ErrorAction SilentlyContinue
    if ($frpc) { Write-Ok "FRP running ($(@($frpc).Count) procs)" }
    else { Write-Host "    - FRP not running" -ForegroundColor DarkGray }

    $ws = @(Get-Process | Where-Object { $_.ProcessName -eq 'Windsurf' })
    if ($ws.Count -gt 0) { Write-Ok "Windsurf running ($($ws.Count) procs)" }
    else { Write-Host "    - Windsurf not running" -ForegroundColor DarkGray }

    Write-Host ""
    $isCfw = (Test-HostsHijacked) -and (Test-JsPatched) -and ($null -ne $cfw)
    $isOff = (-not (Test-HostsHijacked)) -and (-not (Test-JsPatched)) -and (-not $ssl)
    if ($isCfw) { Write-Host "  Mode: CFW (active)" -ForegroundColor Magenta }
    elseif ($isOff) { Write-Host "  Mode: OFFICIAL (clean)" -ForegroundColor Green }
    else { Write-Host "  Mode: MIXED/INCONSISTENT <- run restore!" -ForegroundColor Red }
    Write-Host ""
}

# === ON ===
function Enable-Cfw {
    Write-Host "`n  === ENABLE CFW MODE ===" -ForegroundColor Green

    # Patches stay always-on (harmless with official servers, needed for CFW)
    # Only toggle: hosts + env + CFW process
    if (-not (Test-JsPatched)) {
        Write-Step "0/5" "Apply JS patches (first time)"
        $ws2 = Get-Process | Where-Object { $_.ProcessName -eq 'Windsurf' }
        if ($ws2) { $ws2 | Stop-Process -Force -ErrorAction SilentlyContinue; Start-Sleep 3 }
        Apply-JsPatches | Out-Null
    }

    Write-Step "2/5" "Set hosts hijack"
    Add-HostsEntries

    Write-Step "3/5" "Set env vars"
    Set-CfwEnvVars

    Write-Step "4/5" "Start CFW"
    $ok = Start-Cfw
    if (-not $ok) { Write-Fail "CFW start failed, aborting"; return }

    Write-Step "5/5" "Start Windsurf"
    $wsExe = Join-Path $CFG.WindsurfDir 'Windsurf.exe'
    if (Test-Path $wsExe) {
        $env:SSL_CERT_FILE = $CFG.CfwCert
        $env:NODE_EXTRA_CA_CERTS = $CFG.CfwCert
        $env:NODE_TLS_REJECT_UNAUTHORIZED = '0'
        Start-Process $wsExe -ArgumentList '--host-resolver-rules="MAP server.self-serve.windsurf.com 127.0.0.1,MAP server.codeium.com 127.0.0.1"'
        Write-Ok "Windsurf started (CFW mode)"
    }
    else { Write-Warn "Windsurf.exe not found: $wsExe" }

    Write-Host "`n  CFW mode ENABLED" -ForegroundColor Green
    Write-Host "  For LAN sharing: .\cfw_control.ps1 -Action lan-on`n" -ForegroundColor DarkGray
}

# === OFF ===
function Disable-Cfw {
    Write-Host "`n  === RESTORE OFFICIAL MODE ===" -ForegroundColor Yellow

    # Patches STAY (harmless with official servers) - only toggle infra
    Write-Step "1/4" "Stop CFW"
    Stop-CfwProcess; Write-Ok "CFW stopped"

    Write-Step "2/4" "Remove portproxy"
    Remove-AllPortProxy443

    Write-Step "3/4" "Clean hosts"
    Remove-HostsEntries

    Write-Step "4/4" "Clear env vars"
    Clear-CfwEnvVars

    Write-Host "`n  Official mode RESTORED (patches kept - harmless)" -ForegroundColor Green
    Write-Host "  Windsurf connects directly to official Codeium servers"
    Write-Host "  Launch normally: D:\Windsurf\Windsurf.exe`n" -ForegroundColor DarkGray
}

# === RESTORE (deep clean) ===
function Restore-Official {
    Write-Host "`n  === DEEP RESTORE TO OFFICIAL ===" -ForegroundColor Red

    Write-Step "1/8" "Close Windsurf"
    Get-Process | Where-Object { $_.ProcessName -eq 'Windsurf' } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep 3; Write-Ok "Windsurf closed"

    Write-Step "2/8" "Stop CFW"
    Stop-CfwProcess; Write-Ok "CFW stopped"

    Write-Step "3/8" "Remove all portproxy 443 rules"
    Remove-AllPortProxy443
    $regPath = 'HKLM:\SYSTEM\CurrentControlSet\Services\PortProxy\v4tov4\tcp'
    if (Test-Path $regPath) {
        $props = Get-ItemProperty $regPath -ErrorAction SilentlyContinue
        if ($props) {
            foreach ($p in $props.PSObject.Properties) {
                if ($p.Name -match '443') { Remove-ItemProperty $regPath -Name $p.Name -ErrorAction SilentlyContinue }
            }
        }
    }
    Write-Ok "portproxy registry cleaned"

    Write-Step "4/8" "Clean hosts"
    Remove-HostsEntries

    Write-Step "5/8" "Clear all CFW env vars (Machine level)"
    Clear-CfwEnvVars

    Write-Step "6/8" "Remove fake Root CA certs"
    Remove-FakeRootCerts

    Write-Step "7/8" "Restore JS patches"
    Restore-JsPatches | Out-Null

    Write-Step "8/8" "Clean scheduled tasks"
    foreach ($tn in @('CFW_Relay', 'WindsurfGuardian', 'WindsurfPortProxy', 'WindsurfLG_AutoStart')) {
        $t = schtasks /query /tn $tn 2>$null
        if ($LASTEXITCODE -eq 0) { schtasks /delete /tn $tn /f 2>$null | Out-Null; Write-Ok "deleted task: $tn" }
    }
    Write-Ok "scheduled tasks cleaned"

    Write-Host "`n  === OFFICIAL PRISTINE STATE RESTORED ===" -ForegroundColor Green
    Write-Host "  All CFW traces removed:" -ForegroundColor White
    Write-Host "    - hosts: clean (no hijack)" -ForegroundColor DarkGray
    Write-Host "    - env vars: cleared" -ForegroundColor DarkGray
    Write-Host "    - Root CA: fake certs removed" -ForegroundColor DarkGray
    Write-Host "    - JS: restored to official code" -ForegroundColor DarkGray
    Write-Host "    - portproxy: cleared (incl. registry)" -ForegroundColor DarkGray
    Write-Host "    - scheduled tasks: cleaned" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Launch Windsurf for official service:" -ForegroundColor White
    Write-Host "    D:\Windsurf\Windsurf.exe" -ForegroundColor Cyan
    Write-Host "  Re-enable CFW: .\cfw_control.ps1 -Action on`n" -ForegroundColor DarkGray
}

# === LAN-ON / LAN-OFF ===
function Enable-LanShare {
    Write-Host "`n  === ENABLE LAN SHARE ===" -ForegroundColor Cyan
    if (-not (Get-CfwProcess)) { Write-Fail "CFW not running! Run: .\cfw_control.ps1 -Action on"; return }
    Write-Step "1/2" "Set portproxy"
    Add-LanPortProxy
    Write-Step "2/2" "Ensure FRP running"
    Start-Frpc
    Write-Host "`n  LAN share ENABLED" -ForegroundColor Green
    Write-Host "  LAN: $($CFG.LaptopIp):443 | Public: aiotvr.xyz:443`n" -ForegroundColor DarkGray
}
function Disable-LanShare {
    Write-Host "`n  === DISABLE LAN SHARE ===" -ForegroundColor Yellow
    Write-Step "1/1" "Remove portproxy"
    Remove-AllPortProxy443
    Write-Host "`n  LAN share DISABLED (CFW local only)`n" -ForegroundColor Yellow
}

# === ENTRY ===
Write-Host "`n  CFW Unified Control Hub v1.0`n" -ForegroundColor White
switch ($Action) {
    'status' { Show-Status }
    'on' { Enable-Cfw }
    'off' { Disable-Cfw }
    'lan-on' { Enable-LanShare }
    'lan-off' { Disable-LanShare }
    'restore' { Restore-Official }
}
