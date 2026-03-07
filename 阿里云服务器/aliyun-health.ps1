###############################################################################
# 阿里云服务器一键健康检查
# 用法：.\阿里云服务器\aliyun-health.ps1
###############################################################################

param(
    [string]$HostIP = "60.205.171.100",
    [string]$Domain = "aiotvr.xyz"
)

$ErrorActionPreference = "Continue"

function Test-Port($ip, $port, $timeout = 3000) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $r = $c.BeginConnect($ip, $port, $null, $null)
        $ok = $r.AsyncWaitHandle.WaitOne($timeout)
        if ($ok -and $c.Connected) { $c.Close(); return $true }
        $c.Close(); return $false
    }
    catch { return $false }
}

function Test-Http($url, $timeout = 5) {
    try {
        $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec $timeout -SkipCertificateCheck -ErrorAction Stop
        return $r.StatusCode
    }
    catch {
        if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }
        return 0
    }
}

Write-Host ""
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host "  Aliyun Server Health Check" -ForegroundColor Cyan
Write-Host "  Target: $Domain ($HostIP)" -ForegroundColor Cyan
Write-Host "  Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
Write-Host "  ========================================" -ForegroundColor Cyan

$total = 0; $pass = 0; $fail = 0

function Report($name, $ok, $detail = "") {
    $script:total++
    if ($ok) { $script:pass++; Write-Host "  [OK] $name $detail" -ForegroundColor Green }
    else { $script:fail++; Write-Host "  [FAIL] $name $detail" -ForegroundColor Red }
}

# ═══ 1. 端口检查 ═══
Write-Host "`n-- Port Check --" -ForegroundColor White

$ports = @(
    @{Port = 22; Name = "SSH" },
    @{Port = 80; Name = "HTTP" },
    @{Port = 443; Name = "HTTPS" },
    @{Port = 7000; Name = "FRP-Bind" },
    @{Port = 7500; Name = "FRP-Console" },
    @{Port = 8443; Name = "HA-Proxy" },
    @{Port = 19903; Name = "RemoteAgent" },
    @{Port = 13389; Name = "RDP-Tunnel" },
    @{Port = 18086; Name = "ScreenStream" },
    @{Port = 18084; Name = "SS-Input" },
    @{Port = 18088; Name = "BookshopAPI" },
    @{Port = 18900; Name = "Gateway" },
    @{Port = 18000; Name = "GhostShell" }
)

foreach ($p in $ports) {
    $open = Test-Port $HostIP $p.Port
    Report "$($p.Name)(:$($p.Port))" $open $(if (-not $open) { "port closed" })
}

# ═══ 2. HTTPS服务检查 ═══
Write-Host "`n-- HTTPS Service Check --" -ForegroundColor White

$httpTests = @(
    @{Path = "/"; Name = "Homepage"; Expect = 200 },
    @{Path = "/api/status"; Name = "API-Status"; Expect = 200 },
    @{Path = "/book/"; Name = "Bookshop"; Expect = 200 },
    @{Path = "/cast/"; Name = "WebRTC-Relay"; Expect = 200 },
    @{Path = "/app/ping"; Name = "Relay-Ping"; Expect = 204 },
    @{Path = "/api/relay-status"; Name = "Relay-Status"; Expect = 200 },
    @{Path = "/frp/"; Name = "FRP-Console"; Expect = 401 }
)

foreach ($t in $httpTests) {
    $code = Test-Http "https://${Domain}$($t.Path)"
    $ok = ($code -eq $t.Expect) -or ($code -gt 0 -and $t.Expect -eq 200 -and $code -lt 500)
    Report "$($t.Name)($($t.Path))" $ok "HTTP $code"
}

# FRP依赖隧道的服务（502=笔记本未连接，正常）
$frpTests = @(
    @{Path = "/screen/"; Name = "ScreenStream" },
    @{Path = "/input/"; Name = "SS-Input" },
    @{Path = "/wx"; Name = "WeChat-GW" }
)

Write-Host "`n-- FRP Tunnel Services (502=laptop offline) --" -ForegroundColor White
foreach ($t in $frpTests) {
    $code = Test-Http "https://${Domain}$($t.Path)"
    $status = if ($code -eq 200) { "online" } elseif ($code -eq 502) { "tunnel down (laptop offline)" } else { "error" }
    $ok = ($code -eq 200) -or ($code -eq 502) -or ($code -eq 403)
    Report "$($t.Name)($($t.Path))" $ok "$status (HTTP $code)"
}

# ═══ 3. SSH远程诊断 ═══
Write-Host "`n-- SSH Remote Diagnostics --" -ForegroundColor White

$sshOK = $false
try {
    $sshTest = ssh -o ConnectTimeout=10 -o BatchMode=yes aliyun "echo SSH_OK" 2>&1
    $sshOK = ($sshTest -join " ") -match "SSH_OK"
}
catch {}

Report "SSH-KeyAuth" $sshOK

if ($sshOK) {
    $sshCmd = 'echo FRPS=$(systemctl is-active frps 2>/dev/null) && echo RELAY=$(systemctl is-active ss-relay 2>/dev/null) && echo HA=$(docker inspect -f "{{.State.Status}}" homeassistant_haa7-homeassistant_haA7-1 2>/dev/null || echo none) && echo DISK=$(df -h / | awk "NR==2{print \$4}") && echo MEM=$(free -h | awk "/^Mem:/{print \$3\"/\"\$2}") && echo SSL=$(openssl x509 -enddate -noout -in /etc/letsencrypt/live/aiotvr.xyz/fullchain.pem 2>/dev/null | cut -d= -f2) && echo NODE=$(pgrep -c node 2>/dev/null || echo 0)'
    $remoteInfo = ssh -o ConnectTimeout=15 -o BatchMode=yes aliyun $sshCmd 2>&1

    foreach ($line in ($remoteInfo -split "`n")) {
        $line = $line.Trim()
        if ($line -match '^FRPS=(.+)') { Report "frps-svc" ($Matches[1] -eq "active") $Matches[1] }
        if ($line -match '^RELAY=(.+)') { Report "ss-relay-svc" ($Matches[1] -eq "active") $Matches[1] }
        if ($line -match '^HA=(.+)') { Report "HA-Docker" ($Matches[1] -eq "running") $Matches[1] }
        if ($line -match '^DISK=(.+)') { Write-Host "  Disk free: $($Matches[1])" -ForegroundColor Gray }
        if ($line -match '^MEM=(.+)') { Write-Host "  Memory: $($Matches[1])" -ForegroundColor Gray }
        if ($line -match '^SSL=(.+)') {
            $expiry = $Matches[1].Trim() -replace ' GMT$', ''
            $days = try { ([datetime]::ParseExact($expiry.Trim(), "MMM dd HH:mm:ss yyyy", [System.Globalization.CultureInfo]::InvariantCulture) - (Get-Date)).Days } catch { try { ([datetime]$expiry - (Get-Date)).Days } catch { -1 } }
            $sslOK = $days -gt 14
            $color = if ($days -gt 30) { "Green" } elseif ($days -gt 14) { "Yellow" } else { "Red" }
            Write-Host "  SSL expires: $expiry ($days days)" -ForegroundColor $color
            if (-not $sslOK) { Report "SSL-Cert" $false "<14 days, renew now!" }
        }
    }
}

# ═══ 4. 本地FRP Client ═══
Write-Host "`n-- Local FRP Client --" -ForegroundColor White
$frpc = Get-Process frpc -ErrorAction SilentlyContinue
Report "frpc-process" ($null -ne $frpc) $(if ($frpc) { "PID: $($frpc.Id)" }else { "not running" })

# ═══ 汇总 ═══
Write-Host ""
Write-Host "  ========================================" -ForegroundColor $(if ($fail -eq 0) { "Green" }else { "Yellow" })
Write-Host "  Total: $total | Pass: $pass | Fail: $fail" -ForegroundColor $(if ($fail -eq 0) { "Green" }else { "Yellow" })
Write-Host "  ========================================" -ForegroundColor $(if ($fail -eq 0) { "Green" }else { "Yellow" })
Write-Host ""
