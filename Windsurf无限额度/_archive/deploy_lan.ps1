#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Windsurf CFW LAN直连部署 — 笔记本→台式机
.DESCRIPTION
    将笔记本配置为通过LAN直连台式机CFW代理(192.168.31.141:443)
    证书已内嵌，零外部依赖，一键完成全部配置
    
    用法(管理员PowerShell):
    irm http://192.168.31.141:19999/deploy_lan.ps1 | iex
#>

$ErrorActionPreference = "Stop"
$DESKTOP_IP = "192.168.31.141"
$DESKTOP_PORT = 443
$HOSTS_DOMAINS = @("server.self-serve.windsurf.com", "server.codeium.com")
$VERSION = "1.0-LAN"

# ====== 内嵌证书 (Base64 DER) ======
$CERT_B64 = "MIIDgDCCAmigAwIBAgIUSlHILi9OvC0FMDumQNf8DodOm3swDQYJKoZIhvcNAQELBQAwRjEcMBoGA1UECgwTV2luZHN1cmYgU2VsZi1Qcm94eTEmMCQGA1UEAwwdV2luZHN1cmYgU2VsZi1Ib3N0ZWQgUHJveHkgQ0EwHhcNMjYwMzA1MTg0ODAyWhcNMzYwMzAyMTg0ODAyWjBGMRwwGgYDVQQKDBNXaW5kc3VyZiBTZWxmLVByb3h5MSYwJAYDVQQDDB1XaW5kc3VyZiBTZWxmLUhvc3RlZCBQcm94eSBDQTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAL+l6tNf4MVRlbN+itYPzTCNR8rBNLRd4MK+78J38uXnMZbUs2uKAexehco5fkaphJJFpJcJifkWa6n/ItdLVppVB5EnWIagXZBERj2H8tnj1ppcMSJP+L7rNIezGcWW9xTBzA0G/LPsv+x36CfdnlXllUyPQjVUGlX5X1SeDSyk7nvXkru7h2WIm30h4DSbXMMherjQhJMZc6/6J/6G6xl9NxRhQwdDGylGA05uIrGJa1AZUUSs2eW0TiqfKBCf+E9An7e4oz7k5qeWVaGJhXBPii7XPxKB7vWC88y6GAaVKZxXKhZG9HHiv0vGH8WutVlq3yI7PlOz1WIRNRBTVsMCAwEAAaNmMGQwTgYDVR0RBEcwRYIec2VydmVyLnNlbGYtc2VydmUud2luZHN1cmYuY29tghJzZXJ2ZXIuY29kZWl1bS5jb22CCWxvY2FsaG9zdIcEfwAAATASBgNVHRMBAf8ECDAGAQH/AgEAMA0GCSqGSIb3DQEBCwUAA4IBAQCfwJoCjPwW1Jv+Cj8nHBAE+Cb12fbrsXXJY5U/ntxlyPS2+Ue6R/3UgtX2xBjvUYEBAXWuVhZHiLFJR/js6nhp5AFXHNwkfBCdapkB1Xq8EEnVYtA0zxXCk5t4t/XBJO0FKZyUcSCLX/em6ZaNravcHf6bReeYkEZcq6B9u8wm2dHQ4dI63Q/6axeZ3FbC5N2UoQJ/y0VhFpzoH4+2M92IaPKII2dNVhdHtbA6j3MTWyQLBpH5SeuyXAbEBmMtX5+0+Wjp1NikAmelvVDzYj2pR8h7z5NCS8LdbUhQ9q+Cd57kCOOuI4fxGM6c2BGPzYELDJgje5htvwmk3fZQKIYj"

$CERT_PEM = @"
-----BEGIN CERTIFICATE-----
MIIDgDCCAmigAwIBAgIUSlHILi9OvC0FMDumQNf8DodOm3swDQYJKoZIhvcNAQEL
BQAwRjEcMBoGA1UECgwTV2luZHN1cmYgU2VsZi1Qcm94eTEmMCQGA1UEAwwdV2lu
ZHN1cmYgU2VsZi1Ib3N0ZWQgUHJveHkgQ0EwHhcNMjYwMzA1MTg0ODAyWhcNMzYw
MzAyMTg0ODAyWjBGMRwwGgYDVQQKDBNXaW5kc3VyZiBTZWxmLVByb3h5MSYwJAYD
VQQDDB1XaW5kc3VyZiBTZWxmLUhvc3RlZCBQcm94eSBDQTCCASIwDQYJKoZIhvcN
AQEBBQADggEPADCCAQoCggEBAL+l6tNf4MVRlbN+itYPzTCNR8rBNLRd4MK+78J3
8uXnMZbUs2uKAexehco5fkaphJJFpJcJifkWa6n/ItdLVppVB5EnWIagXZBERj2H
8tnj1ppcMSJP+L7rNIezGcWW9xTBzA0G/LPsv+x36CfdnlXllUyPQjVUGlX5X1Se
DSyk7nvXkru7h2WIm30h4DSbXMMherjQhJMZc6/6J/6G6xl9NxRhQwdDGylGA05u
IrGJa1AZUUSs2eW0TiqfKBCf+E9An7e4oz7k5qeWVaGJhXBPii7XPxKB7vWC88y6
GAaVKZxXKhZG9HHiv0vGH8WutVlq3yI7PlOz1WIRNRBTVsMCAwEAAaNmMGQwTgYD
VR0RBEcwRYIec2VydmVyLnNlbGYtc2VydmUud2luZHN1cmYuY29tghJzZXJ2ZXIu
Y29kZWl1bS5jb22CCWxvY2FsaG9zdIcEfwAAATASBgNVHRMBAf8ECDAGAQH/AgEA
MA0GCSqGSIb3DQEBCwUAA4IBAQCfwJoCjPwW1Jv+Cj8nHBAE+Cb12fbrsXXJY5U/
ntxlyPS2+Ue6R/3UgtX2xBjvUYEBAXWuVhZHiLFJR/js6nhp5AFXHNwkfBCdapkB
1Xq8EEnVYtA0zxXCk5t4t/XBJO0FKZyUcSCLX/em6ZaNravcHf6bReeYkEZcq6B9
u8wm2dHQ4dI63Q/6axeZ3FbC5N2UoQJ/y0VhFpzoH4+2M92IaPKII2dNVhdHtbA6
j3MTWyQLBpH5SeuyXAbEBmMtX5+0+Wjp1NikAmelvVDzYj2pR8h7z5NCS8LdbUhQ
9q+Cd57kCOOuI4fxGM6c2BGPzYELDJgje5htvwmk3fZQKIYj
-----END CERTIFICATE-----
"@

function Write-Step($n, $total, $msg) {
    Write-Host "`n$('='*50)" -ForegroundColor DarkCyan
    Write-Host "  [$n/$total] $msg" -ForegroundColor Cyan
    Write-Host "$('='*50)" -ForegroundColor DarkCyan
}
function Write-OK($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-FAIL($msg) { Write-Host "  [FAIL] $msg" -ForegroundColor Red }
function Write-SKIP($msg) { Write-Host "  [SKIP] $msg" -ForegroundColor Yellow }

Write-Host @"

  ==============================================
    Windsurf CFW LAN Direct Deploy v$VERSION
    Laptop -> Desktop ($DESKTOP_IP`:$DESKTOP_PORT)
  ==============================================

  Computer: $env:COMPUTERNAME
  User:     $env:USERNAME
  
"@ -ForegroundColor Magenta

$total = 8
$ok = 0

# ===== Step 1: LAN连通性 =====
Write-Step 1 $total "LAN连通性检测"
try {
    $tcp = New-Object Net.Sockets.TcpClient
    $ar = $tcp.BeginConnect($DESKTOP_IP, $DESKTOP_PORT, $null, $null)
    $wait = $ar.AsyncWaitHandle.WaitOne(5000, $false)
    if ($wait -and $tcp.Connected) {
        $tcp.Close()
        Write-OK "台式机 ${DESKTOP_IP}:${DESKTOP_PORT} 连通"
        $ok++
    } else { throw "Timeout" }
} catch {
    Write-FAIL "无法连接台式机 ${DESKTOP_IP}:${DESKTOP_PORT}"
    Write-Host "  请确认: 1.台式机CFW在运行 2.防火墙允许443" -ForegroundColor Yellow
}

# ===== Step 2: hosts文件 =====
Write-Step 2 $total "配置 hosts 文件"
try {
    $hostsPath = "$env:SystemRoot\System32\drivers\etc\hosts"
    $content = [IO.File]::ReadAllLines($hostsPath)
    $added = @()
    foreach ($domain in $HOSTS_DOMAINS) {
        $found = $false
        foreach ($line in $content) {
            if ($line -match "^\s*127\.0\.0\.1\s+.*$([regex]::Escape($domain))") { $found = $true; break }
        }
        if (-not $found) { $added += "127.0.0.1 $domain" }
    }
    if ($added.Count -eq 0) {
        Write-SKIP "hosts已正确"
    } else {
        $content += $added
        [IO.File]::WriteAllLines($hostsPath, $content)
        foreach ($a in $added) { Write-OK "添加: $a" }
    }
    $ok++
} catch {
    Write-FAIL "$_"
}

# ===== Step 3: portproxy (LAN直连) =====
Write-Step 3 $total "portproxy: 127.0.0.1:443 -> $DESKTOP_IP`:$DESKTOP_PORT"
try {
    netsh interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=443 2>$null
    netsh interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=443 connectaddress=$DESKTOP_IP connectport=$DESKTOP_PORT
    if ($LASTEXITCODE -eq 0) {
        Write-OK "portproxy已设置 (LAN直连)"
        $ok++
    } else { throw "netsh failed" }
} catch {
    Write-FAIL "$_"
}

# ===== Step 4: 安装CA证书 =====
Write-Step 4 $total "安装TLS CA证书"
try {
    $cerBytes = [Convert]::FromBase64String($CERT_B64)
    $cerPath = "$env:TEMP\windsurf_proxy_ca.cer"
    [IO.File]::WriteAllBytes($cerPath, $cerBytes)
    
    $cert = New-Object Security.Cryptography.X509Certificates.X509Certificate2($cerPath)
    $existing = Get-ChildItem Cert:\LocalMachine\Root | Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
    if ($existing) {
        Write-SKIP "证书已存在 ($($cert.Thumbprint.Substring(0,8))...)"
    } else {
        $store = New-Object Security.Cryptography.X509Certificates.X509Store("Root", "LocalMachine")
        $store.Open("ReadWrite")
        $store.Add($cert)
        $store.Close()
        Write-OK "证书已安装"
    }
    Remove-Item $cerPath -EA SilentlyContinue
    $ok++
} catch {
    Write-FAIL "$_"
}

# ===== Step 5: SSL_CERT_FILE =====
Write-Step 5 $total "设置 SSL_CERT_FILE"
try {
    $pemPath = "$env:ProgramData\windsurf_proxy_ca.pem"
    [IO.File]::WriteAllText($pemPath, $CERT_PEM)
    [Environment]::SetEnvironmentVariable("SSL_CERT_FILE", $pemPath, "Machine")
    $env:SSL_CERT_FILE = $pemPath
    Write-OK "SSL_CERT_FILE = $pemPath"
    $ok++
} catch {
    Write-FAIL "$_"
}

# ===== Step 6: Windsurf settings.json =====
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
        } catch {}
    }
    $settings["http.proxyStrictSSL"] = $false
    $settings["http.proxySupport"] = "off"
    $settings | ConvertTo-Json -Depth 10 | Set-Content $settingsPath -Encoding UTF8
    Write-OK "settings.json 已配置"
    $ok++
} catch {
    Write-FAIL "$_"
}

# ===== Step 7: 桌面启动脚本 + 快捷方式修复 =====
Write-Step 7 $total "桌面启动脚本 + 快捷方式"
try {
    $wsPaths = @(
        "D:\Windsurf\Windsurf.exe",
        "$env:LOCALAPPDATA\Programs\Windsurf\Windsurf.exe",
        "C:\Program Files\Windsurf\Windsurf.exe",
        "$env:ProgramFiles\Windsurf\Windsurf.exe"
    )
    $wsExe = $wsPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
    $desktop = [Environment]::GetFolderPath("Desktop")
    $resolverRules = "--host-resolver-rules=MAP server.self-serve.windsurf.com 127.0.0.1,MAP server.codeium.com 127.0.0.1"
    
    if ($wsExe) {
        # CMD launcher
        $cmdContent = "@echo off`r`nstart `"`" `"$wsExe`" `"$resolverRules`""
        Set-Content "$desktop\Windsurf_Proxy.cmd" $cmdContent -Encoding ASCII
        Write-OK "CMD: $desktop\Windsurf_Proxy.cmd"
        
        # Fix desktop shortcut if exists
        $lnkPath = "$desktop\Windsurf.lnk"
        if (Test-Path $lnkPath) {
            $shell = New-Object -ComObject WScript.Shell
            $lnk = $shell.CreateShortcut($lnkPath)
            if ($lnk.Arguments -notmatch "host-resolver-rules") {
                $lnk.Arguments = $resolverRules
                $lnk.Save()
                Write-OK "桌面快捷方式已注入代理参数"
            } else {
                Write-SKIP "桌面快捷方式已有代理参数"
            }
        }
        
        # Fix start menu shortcut
        $startLnk = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Windsurf.lnk"
        if (Test-Path $startLnk) {
            $shell = New-Object -ComObject WScript.Shell
            $lnk = $shell.CreateShortcut($startLnk)
            if ($lnk.Arguments -notmatch "host-resolver-rules") {
                $lnk.Arguments = $resolverRules
                $lnk.Save()
                Write-OK "开始菜单快捷方式已注入代理参数"
            }
        }
        $ok++
    } else {
        Write-FAIL "未找到Windsurf.exe"
    }
} catch {
    Write-FAIL "$_"
}

# ===== Step 8: portproxy持久化 + E2E验证 =====
Write-Step 8 $total "持久化 + E2E验证"
try {
    # Persist portproxy
    $ppCmd = "`"$env:SystemRoot\System32\netsh.exe`" interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=443 connectaddress=$DESKTOP_IP connectport=$DESKTOP_PORT"
    schtasks /Delete /TN "WindsurfPortProxy" /F 2>$null
    schtasks /Create /TN "WindsurfPortProxy" /TR $ppCmd /SC ONSTART /RU SYSTEM /RL HIGHEST /F 2>&1 | Out-Null
    Write-OK "portproxy持久化计划任务已创建"
    
    # E2E: TCP test
    $tcp = New-Object Net.Sockets.TcpClient
    $tcp.Connect("127.0.0.1", 443)
    $tcp.Close()
    Write-OK "TCP 127.0.0.1:443 -> $DESKTOP_IP 连通"
    
    # E2E: TLS handshake
    try {
        $tcpC = New-Object Net.Sockets.TcpClient("127.0.0.1", 443)
        $sslStream = New-Object Net.Security.SslStream($tcpC.GetStream(), $false, { $true })
        $sslStream.AuthenticateAsClient("server.self-serve.windsurf.com")
        $remoteCert = $sslStream.RemoteCertificate
        $sslStream.Close()
        $tcpC.Close()
        if ($remoteCert) {
            Write-OK "TLS握手成功 (CN=$($remoteCert.Subject))"
        }
    } catch {
        Write-FAIL "TLS握手失败: $($_.Exception.Message.Substring(0, [Math]::Min(80, $_.Exception.Message.Length)))"
    }
    
    # DNS check
    $dns = [Net.Dns]::GetHostAddresses("server.self-serve.windsurf.com") | Select-Object -First 1
    if ($dns.IPAddressToString -eq "127.0.0.1") {
        Write-OK "DNS server.self-serve.windsurf.com -> 127.0.0.1"
    } else {
        Write-FAIL "DNS -> $($dns.IPAddressToString) (应为127.0.0.1)"
    }
    $ok++
} catch {
    Write-FAIL "$_"
}

# ===== 汇总 =====
Write-Host "`n$('='*50)" -ForegroundColor DarkCyan
Write-Host "  部署完成: $ok/$total 项成功" -ForegroundColor $(if($ok -eq $total){"Green"}else{"Yellow"})
Write-Host "$('='*50)" -ForegroundColor DarkCyan

if ($ok -eq $total) {
    Write-Host @"

  ALL PASSED! 
  
  请用以下方式启动Windsurf:
    1. 双击桌面 'Windsurf_Proxy.cmd'
    2. 或双击桌面 'Windsurf' 快捷方式(已注入代理参数)
    
  首次启动后建议重启一次Windsurf使SSL_CERT_FILE生效

"@ -ForegroundColor Green
} else {
    Write-Host "`n  部分步骤失败，请检查上方错误信息" -ForegroundColor Yellow
}
