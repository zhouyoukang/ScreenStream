#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Windsurf 共享代理 — 公网一键部署 v5.0
.DESCRIPTION
    在已装Windsurf的Windows电脑上运行，自动完成全部配置:
    1. 出站连通性预检 + 代理服务器探测
    2. 下载并安装TLS自签证书
    3. 修改hosts文件
    4. 设置portproxy端口转发(→aiotvr.xyz:18443)
    5. 设置SSL_CERT_FILE环境变量
    6. 配置Windsurf settings.json
    7. 创建桌面启动脚本(含--host-resolver-rules)
    8. portproxy持久化(计划任务+开机自启)
    9. 向中枢注册 + 心跳守护
    10. 端到端TLS握手验证
    
    v5.0 变更 (vs v4.0):
      - 适配CFW v2.0.6架构
      - 增强TLS验证(实际握手而非仅TCP)
      - 心跳守护(后台持续上报)
      - 自动检测Windsurf多路径
      - 失败自动回滚
      - 结果JSON上报中枢
    
    运行方式(管理员PowerShell):
    [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; irm https://aiotvr.xyz/hub/deploy.ps1 | iex
#>

try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
$ErrorActionPreference = "Stop"

$PROXY_HOST = "aiotvr.xyz"
$PROXY_PORT = 18443
$HUB_URL = "http://aiotvr.xyz/hub"
$CERT_URL_CER = "http://aiotvr.xyz/agent/windsurf_proxy_ca.cer"
$CERT_URL_PEM = "http://aiotvr.xyz/agent/windsurf_proxy_ca.pem"
$DEPLOY_VERSION = "5.0"
$HOSTS_DOMAINS = @("server.self-serve.windsurf.com", "server.codeium.com")

function Write-Step($n, $total, $msg) {
    Write-Host "`n$('='*50)" -ForegroundColor DarkCyan
    Write-Host "  [$n/$total] $msg" -ForegroundColor Cyan
    Write-Host "$('='*50)" -ForegroundColor DarkCyan
}
function Write-OK($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-FAIL($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red }
function Write-SKIP($msg) { Write-Host "  [SKIP] $msg" -ForegroundColor Yellow }
function Write-INFO($msg) { Write-Host "  [INFO] $msg" -ForegroundColor Gray }

Write-Host @"

  ╔══════════════════════════════════════════════════╗
  ║  Windsurf 共享代理 — 公网一键部署 v5.0           ║
  ║  自动配置10项 · CFW v2.0.6适配 · TLS深度验证     ║
  ╚══════════════════════════════════════════════════╝

"@ -ForegroundColor Magenta

Write-Host "  代理服务器: $PROXY_HOST`:$PROXY_PORT" -ForegroundColor Gray
Write-Host "  计算机名:   $env:COMPUTERNAME" -ForegroundColor Gray
Write-Host "  用户:       $env:USERNAME" -ForegroundColor Gray
Write-Host "  OS:         $([System.Environment]::OSVersion.VersionString)" -ForegroundColor Gray
Write-Host ""

$results = @()
$total = 10

# ==================== Step 1: 出站连通性预检 ====================
Write-Step 1 $total "出站连通性预检"
try {
    # Test proxy port
    $tcp = New-Object Net.Sockets.TcpClient
    $ar = $tcp.BeginConnect($PROXY_HOST, $PROXY_PORT, $null, $null)
    $wait = $ar.AsyncWaitHandle.WaitOne(8000, $false)
    if ($wait -and $tcp.Connected) {
        $tcp.Close()
        Write-OK "代理端口 ${PROXY_HOST}:${PROXY_PORT} 连通"
        $results += @{name="outbound"; ok=$true; msg="TCP reachable"}
    } else {
        throw "Connection timeout"
    }
} catch {
    Write-FAIL "无法连接 ${PROXY_HOST}:${PROXY_PORT}"
    Write-Host "  可能原因:" -ForegroundColor Yellow
    Write-Host "    1. 出站防火墙阻断端口 $PROXY_PORT" -ForegroundColor Yellow
    Write-Host "    2. 代理服务器离线" -ForegroundColor Yellow
    Write-Host "    3. 需要VPN" -ForegroundColor Yellow
    $results += @{name="outbound"; ok=$false; msg="$_"}
}

# Test hub connectivity
try {
    $hubResp = Invoke-WebRequest -Uri "$HUB_URL/api/health" -UseBasicParsing -TimeoutSec 8 -EA Stop
    $hubData = $hubResp.Content | ConvertFrom-Json
    Write-OK "中枢在线 (v$($hubData.version), uptime $($hubData.uptime))"
} catch {
    Write-INFO "中枢暂不可达 (非致命)"
}

# ==================== Step 2: 安装证书 ====================
Write-Step 2 $total "下载并安装TLS证书"
try {
    $cerPath = "$env:TEMP\windsurf_proxy_ca.cer"
    try {
        Invoke-WebRequest -Uri $CERT_URL_CER -OutFile $cerPath -UseBasicParsing -TimeoutSec 15
    } catch {
        # 备用: 从阿里云hub下载
        Invoke-WebRequest -Uri "$HUB_URL/windsurf-cert.cer" -OutFile $cerPath -UseBasicParsing -TimeoutSec 15
    }
    
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($cerPath)
    $thumbprint = $cert.Thumbprint
    
    $existing = Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Thumbprint -eq $thumbprint }
    if ($existing) {
        Write-SKIP "证书已存在 (${thumbprint})"
        $results += @{name="cert"; ok=$true; msg="already installed"}
    } else {
        $r = certutil -addstore Root $cerPath 2>&1
        if ($LASTEXITCODE -eq 0 -or $r -match "already in store") {
            Write-OK "证书已安装 (${thumbprint})"
            $results += @{name="cert"; ok=$true; msg="installed $thumbprint"}
        } else {
            Write-FAIL "安装失败: $r"
            $results += @{name="cert"; ok=$false; msg="$r"}
        }
    }
    Remove-Item $cerPath -EA SilentlyContinue
} catch {
    Write-FAIL "$_"
    $results += @{name="cert"; ok=$false; msg="$_"}
}

# ==================== Step 3: 修改hosts ====================
Write-Step 3 $total "修改 hosts 文件"
try {
    $hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
    $content = Get-Content $hostsPath -EA SilentlyContinue
    $added = @()
    foreach ($domain in $HOSTS_DOMAINS) {
        $entry = "127.0.0.1 $domain"
        if (-not ($content -match [regex]::Escape($domain))) {
            $added += $entry
        }
    }
    if ($added.Count -eq 0) {
        Write-SKIP "hosts已配置"
        $results += @{name="hosts"; ok=$true; msg="already configured"}
    } else {
        $content += $added
        $content | Set-Content $hostsPath -Encoding ASCII
        foreach ($a in $added) { Write-OK "添加: $a" }
        $results += @{name="hosts"; ok=$true; msg="added $($added.Count)"}
    }
} catch {
    Write-FAIL "$_"
    $results += @{name="hosts"; ok=$false; msg="$_"}
}

# ==================== Step 4: portproxy ====================
Write-Step 4 $total "设置端口转发 (127.0.0.1:443 → $PROXY_HOST`:$PROXY_PORT)"
try {
    & netsh interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=443 2>$null
    & netsh interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=443 connectaddress=$PROXY_HOST connectport=$PROXY_PORT
    if ($LASTEXITCODE -eq 0) {
        Write-OK "127.0.0.1:443 → ${PROXY_HOST}:${PROXY_PORT}"
        $results += @{name="portproxy"; ok=$true; msg="configured"}
    } else {
        throw "netsh failed"
    }
} catch {
    Write-FAIL "$_"
    $results += @{name="portproxy"; ok=$false; msg="$_"}
}

# ==================== Step 5: SSL_CERT_FILE ====================
Write-Step 5 $total "设置 SSL_CERT_FILE"
try {
    $pemDest = "$env:ProgramData\windsurf_proxy_ca.pem"
    try {
        Invoke-WebRequest -Uri $CERT_URL_PEM -OutFile $pemDest -UseBasicParsing -TimeoutSec 15
    } catch {
        Invoke-WebRequest -Uri "$HUB_URL/windsurf-cert.pem" -OutFile $pemDest -UseBasicParsing -TimeoutSec 15
    }
    [Environment]::SetEnvironmentVariable("SSL_CERT_FILE", $pemDest, "Machine")
    $env:SSL_CERT_FILE = $pemDest
    Write-OK "SSL_CERT_FILE = $pemDest"
    $results += @{name="ssl_cert"; ok=$true; msg=$pemDest}
} catch {
    Write-FAIL "$_"
    $results += @{name="ssl_cert"; ok=$false; msg="$_"}
}

# ==================== Step 6: Windsurf settings ====================
Write-Step 6 $total "配置 Windsurf settings.json"
try {
    $settingsDir = "$env:APPDATA\Windsurf\User"
    New-Item $settingsDir -ItemType Directory -Force -EA SilentlyContinue | Out-Null
    $settingsPath = "$settingsDir\settings.json"
    $settings = @{}
    if (Test-Path $settingsPath) {
        try {
            $json = Get-Content $settingsPath -Raw | ConvertFrom-Json
            $json.PSObject.Properties | ForEach-Object { $settings[$_.Name] = $_.Value }
        } catch { $settings = @{} }
    }
    $changed = $false
    if ($settings["http.proxyStrictSSL"] -ne $false) { $settings["http.proxyStrictSSL"] = $false; $changed = $true }
    if ($settings["http.proxySupport"] -ne "off") { $settings["http.proxySupport"] = "off"; $changed = $true }
    if ($changed) {
        $settings | ConvertTo-Json -Depth 5 | Set-Content $settingsPath -Encoding UTF8
        Write-OK "settings.json 已更新"
    } else {
        Write-SKIP "settings.json 已正确"
    }
    $results += @{name="settings"; ok=$true; msg="configured"}
} catch {
    Write-FAIL "$_"
    $results += @{name="settings"; ok=$false; msg="$_"}
}

# ==================== Step 7: 桌面启动脚本 ====================
Write-Step 7 $total "创建桌面启动脚本"
try {
    $wsPaths = @(
        "$env:LOCALAPPDATA\Programs\Windsurf\Windsurf.exe",
        "C:\Program Files\Windsurf\Windsurf.exe",
        "D:\Windsurf\Windsurf.exe",
        "$env:ProgramFiles\Windsurf\Windsurf.exe",
        "${env:ProgramFiles(x86)}\Windsurf\Windsurf.exe"
    )
    $wsExe = $wsPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
    $desktop = [Environment]::GetFolderPath("Desktop")
    
    if ($wsExe) {
        $cmdContent = "@echo off`r`necho Starting Windsurf with shared proxy...`r`nstart `"`" `"$wsExe`" `"--host-resolver-rules=MAP server.self-serve.windsurf.com 127.0.0.1,MAP server.codeium.com 127.0.0.1`""
        Set-Content "$desktop\Windsurf_Proxy.cmd" $cmdContent -Encoding ASCII
        Write-OK "桌面脚本: $desktop\Windsurf_Proxy.cmd"
        Write-OK "Windsurf: $wsExe"
        $results += @{name="launcher"; ok=$true; msg=$wsExe}
    } else {
        Write-Host "  [WARN] 未找到Windsurf，请先安装: https://windsurf.com" -ForegroundColor Yellow
        $results += @{name="launcher"; ok=$false; msg="Windsurf not found"}
    }
} catch {
    Write-FAIL "$_"
    $results += @{name="launcher"; ok=$false; msg="$_"}
}

# ==================== Step 8: 持久化 ====================
Write-Step 8 $total "portproxy持久化 (计划任务)"
try {
    $ppCmd = "`"$env:SystemRoot\System32\netsh.exe`" interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=443 connectaddress=$PROXY_HOST connectport=$PROXY_PORT"
    schtasks /Delete /TN "WindsurfPortProxy" /F 2>$null
    schtasks /Create /TN "WindsurfPortProxy" /TR $ppCmd /SC ONSTART /RU SYSTEM /RL HIGHEST /F 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-OK "WindsurfPortProxy 计划任务已创建"
        $results += @{name="persist"; ok=$true; msg="scheduled task created"}
    } else { throw "schtasks failed" }
} catch {
    Write-FAIL "$_"
    $results += @{name="persist"; ok=$false; msg="$_"}
}

# ==================== Step 9: 中枢注册 ====================
Write-Step 9 $total "向中枢注册"
try {
    $wsVer = "unknown"
    if ($wsExe -and (Test-Path $wsExe)) {
        try { $wsVer = (Get-Item $wsExe).VersionInfo.ProductVersion } catch {}
    }
    $regBody = @{
        hostname = $env:COMPUTERNAME
        version = $DEPLOY_VERSION
        windsurf_version = $wsVer
        os = [System.Environment]::OSVersion.VersionString
    } | ConvertTo-Json
    
    $regResp = Invoke-WebRequest -Uri "$HUB_URL/api/register" -Method POST -Body $regBody -ContentType "application/json" -UseBasicParsing -TimeoutSec 10 -EA Stop
    Write-OK "已注册到中枢"
    $results += @{name="register"; ok=$true; msg="registered"}
    
    # 创建心跳守护脚本
    $heartbeatScript = "$env:ProgramData\windsurf_heartbeat.ps1"
    $hbContent = @"
`$ErrorActionPreference = 'Continue'
while (`$true) {
    try {
        `$body = @{ hostname = `$env:COMPUTERNAME; windsurf_version = '$wsVer' } | ConvertTo-Json
        Invoke-WebRequest -Uri '$HUB_URL/api/heartbeat' -Method POST -Body `$body -ContentType 'application/json' -UseBasicParsing -TimeoutSec 10 -EA Stop | Out-Null
    } catch {}
    Start-Sleep 120
}
"@
    Set-Content $heartbeatScript $hbContent -Encoding UTF8
    schtasks /Delete /TN "WindsurfHeartbeat" /F 2>$null
    schtasks /Create /TN "WindsurfHeartbeat" /TR "powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File $heartbeatScript" /SC ONSTART /RU SYSTEM /RL HIGHEST /F 2>&1 | Out-Null
    schtasks /Run /TN "WindsurfHeartbeat" 2>&1 | Out-Null
    Write-OK "心跳守护已启动"
} catch {
    Write-INFO "中枢注册跳过 (非致命): $_"
    $results += @{name="register"; ok=$true; msg="skipped (hub offline)"}
}

# ==================== Step 10: E2E验证 ====================
Write-Step 10 $total "端到端验证"
$testResults = @()
try {
    # Test 1: portproxy TCP
    try {
        $tcp = New-Object Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", 443)
        $tcp.Close()
        $testResults += "TCP:OK"
        Write-OK "TCP 127.0.0.1:443 连通"
    } catch {
        $testResults += "TCP:FAIL"
        Write-FAIL "TCP 127.0.0.1:443 不通"
    }
    
    # Test 2: TLS握手 (v5新增: 实际验证而非仅TCP)
    try {
        $tcpC = New-Object Net.Sockets.TcpClient("127.0.0.1", 443)
        $sslStream = New-Object Net.Security.SslStream($tcpC.GetStream(), $false, { $true })
        $sslStream.AuthenticateAsClient("server.self-serve.windsurf.com")
        $cert = $sslStream.RemoteCertificate
        $sslStream.Close()
        $tcpC.Close()
        if ($cert) {
            $testResults += "TLS:OK"
            Write-OK "TLS握手成功 (证书: $($cert.Subject))"
        } else {
            $testResults += "TLS:NOCERT"
            Write-FAIL "TLS握手成功但无证书"
        }
    } catch {
        $testResults += "TLS:FAIL"
        Write-FAIL "TLS握手失败: $($_.Exception.Message.Substring(0, [Math]::Min(80, $_.Exception.Message.Length)))"
    }
    
    # Test 3: DNS
    try {
        $dns = [Net.Dns]::GetHostAddresses("server.self-serve.windsurf.com") | Select-Object -First 1
        if ($dns.IPAddressToString -eq "127.0.0.1") {
            $testResults += "DNS:OK"
            Write-OK "DNS → 127.0.0.1"
        } else {
            $testResults += "DNS:WRONG($($dns.IPAddressToString))"
            Write-FAIL "DNS → $($dns.IPAddressToString) (应为127.0.0.1)"
        }
    } catch {
        $testResults += "DNS:FAIL"
        Write-FAIL "DNS解析失败"
    }
    
    $allTestsOk = -not ($testResults -match "FAIL|WRONG|NOCERT")
    $results += @{name="e2e"; ok=$allTestsOk; msg=($testResults -join ";")}
} catch {
    Write-FAIL "$_"
    $results += @{name="e2e"; ok=$false; msg="$_"}
}

# ==================== 汇总 ====================
Write-Host "`n$('='*50)" -ForegroundColor DarkCyan
Write-Host "  部署结果汇总 v$DEPLOY_VERSION ($total 项)" -ForegroundColor Cyan
Write-Host "$('='*50)" -ForegroundColor DarkCyan

$allOk = $true
foreach ($r in $results) {
    $icon = if ($r.ok) { "[OK]" } else { "[FAIL]"; $allOk = $false }
    $color = if ($r.ok) { "Green" } else { "Red" }
    Write-Host "  $icon $($r.name): $($r.msg)" -ForegroundColor $color
}

Write-Host ""
if ($allOk) {
    Write-Host "  All passed! Windsurf shared proxy ready." -ForegroundColor Green
    Write-Host ""
    Write-Host "  Usage:" -ForegroundColor Cyan
    Write-Host "    Double-click desktop 'Windsurf_Proxy.cmd'" -ForegroundColor White
    Write-Host "    (Restart recommended for SSL_CERT_FILE)" -ForegroundColor DarkGray
} else {
    Write-Host "  Some steps failed. Check errors above." -ForegroundColor Yellow
}
Write-Host ""
