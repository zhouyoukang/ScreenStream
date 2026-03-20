#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Windsurf CFW 公网一键部署 v7.0 (VPN兼容)
.DESCRIPTION
    任何Windows电脑运行此脚本即可连接CFW中枢，享受Windsurf Pro服务。
    证书内嵌，零外部依赖，全自动10步配置。
    
    管理员PowerShell执行:
    irm https://aiotvr.xyz/hub/static/deploy.ps1 | iex
#>
$ErrorActionPreference = "Stop"
$V = "7.0"
$PROXY_HOST = "aiotvr.xyz"
$PROXY_PORT = 443
$DOMAINS = @("server.self-serve.windsurf.com", "server.codeium.com")

$CER_B64 = "MIIB9jCCAZ2gAwIBAgIUXPEpy+R315LkHilwMdOFTVHFejgwCgYIKoZIzj0EAwIwQjEnMCUGA1UEAwwec2VydmVyLnNlbGYtc2VydmUud2luZHN1cmYuY29tMRcwFQYDVQQKDA5XaW5kc3VyZiBQcm94eTAeFw0yNjAzMDcwODEzMjRaFw0zNjAzMDQwODEzMjRaMEIxJzAlBgNVBAMMHnNlcnZlci5zZWxmLXNlcnZlLndpbmRzdXJmLmNvbTEXMBUGA1UECgwOV2luZHN1cmYgUHJveHkwWTATBgcqhkjOPQIBBggqhkjOPQMBBwNCAASFDBYKdH9aRnNTmIvxZSOfyJ6EqWsD9aSAysO991O4QMnlRHxbV6x7+RQrpjLUeSu+cmJdweoCCD/VPdRVZEDDo3EwbzA9BgNVHREENjA0gh5zZXJ2ZXIuc2VsZi1zZXJ2ZS53aW5kc3VyZi5jb22CEnNlcnZlci5jb2RlaXVtLmNvbTAdBgNVHQ4EFgQUB6864OU80TdOrJ/OjTiK2oem4VswDwYDVR0TAQH/BAUwAwEB/zAKBggqhkjOPQQDAgNHADBEAiBa8ipAicUB5ThQoC7iDDqQ8Qw3Qa1zDG4mxwK9jSSiKgIgZ/FByRpF4ugyNG4BOz8knfipu0bfu46lSWHOiA6w2og="

$PEM = @"
-----BEGIN CERTIFICATE-----
MIIB9jCCAZ2gAwIBAgIUXPEpy+R315LkHilwMdOFTVHFejgwCgYIKoZIzj0EAwIw
QjEnMCUGA1UEAwwec2VydmVyLnNlbGYtc2VydmUud2luZHN1cmYuY29tMRcwFQYD
VQQKDA5XaW5kc3VyZiBQcm94eTAeFw0yNjAzMDcwODEzMjRaFw0zNjAzMDQwODEz
MjRaMEIxJzAlBgNVBAMMHnNlcnZlci5zZWxmLXNlcnZlLndpbmRzdXJmLmNvbTEX
MBUGA1UECgwOV2luZHN1cmYgUHJveHkwWTATBgcqhkjOPQIBBggqhkjOPQMBBwNC
AASFDBYKDH9aRnNTmIvxZSOfyJ6EqWsD9aSAysO991O4QMnlRHxbV6x7+RQrpjLU
eSu+cmJdweoCCD/VPdRVZEDDo3EwbzA9BgNVHREENjA0gh5zZXJ2ZXIuc2VsZi1z
ZXJ2ZS53aW5kc3VyZi5jb22CEnNlcnZlci5jb2RlaXVtLmNvbTAdBgNVHQ4EFgQU
B6864OU80TdOrJ/OjTiK2oem4VswDwYDVR0TAQH/BAUwAwEB/zAKBggqhkjOPQQD
AgNHADBEAiBa8ipAicUB5ThQoC7iDDqQ8Qw3Qa1zDG4mxwK9jSSiKgIgZ/FByRpF
4ugyNG4BOz8knfipu0bfu46lSWHOiA6w2og=
-----END CERTIFICATE-----
"@

function S($n,$t,$m){Write-Host "`n$('='*50)" -Fore DarkCyan;Write-Host "  [$n/$t] $m" -Fore Cyan;Write-Host "$('='*50)" -Fore DarkCyan}
function OK($m){Write-Host "  [OK] $m" -Fore Green}
function FL($m){Write-Host "  [FAIL] $m" -Fore Red}
function SK($m){Write-Host "  [SKIP] $m" -Fore Yellow}

Write-Host @"

  ========================================================
    Windsurf CFW Hub - Deploy v$V
    One command, any machine, full Pro access
  ========================================================
  Host: $PROXY_HOST`:$PROXY_PORT
  PC:   $env:COMPUTERNAME ($env:USERNAME)

"@ -Fore Magenta

$t=8; $ok=0

# === 1. Connectivity ===
S 1 $t "Outbound connectivity check"
try {
    $tcp=New-Object Net.Sockets.TcpClient;$ar=$tcp.BeginConnect($PROXY_HOST,$PROXY_PORT,$null,$null)
    if($ar.AsyncWaitHandle.WaitOne(8000,$false) -and $tcp.Connected){$tcp.Close();OK "TCP $PROXY_HOST`:$PROXY_PORT reachable";$ok++}
    else{throw "timeout"}
} catch {FL "Cannot reach $PROXY_HOST`:$PROXY_PORT - check firewall/network";$tcp.Close()}

# === 2. Hosts ===
S 2 $t "Configure hosts file"
try {
    $hp="$env:SystemRoot\System32\drivers\etc\hosts"
    $lines=[IO.File]::ReadAllLines($hp)
    $add=@()
    foreach($d in $DOMAINS){$found=$false;foreach($l in $lines){if($l -match "127\.0\.0\.1\s+.*$([regex]::Escape($d))"){$found=$true;break}};if(-not $found){$add+="127.0.0.1 $d"}}
    if($add.Count -eq 0){SK "Already configured";$ok++}
    else{$lines+=$add;[IO.File]::WriteAllLines($hp,$lines);$add|ForEach-Object{OK "Added: $_"};$ok++}
} catch {FL "$_"}

# === 3. Portproxy ===
S 3 $t "Port forwarding (127.0.0.1:443 -> $PROXY_HOST`:$PROXY_PORT)"
try {
    netsh interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=443 2>$null
    netsh interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=443 connectaddress=$PROXY_HOST connectport=$PROXY_PORT
    if($LASTEXITCODE -eq 0){OK "portproxy set";$ok++}else{throw "netsh failed"}
} catch {FL "$_"}

# === 4. Certificate ===
S 4 $t "Install TLS CA certificate"
try {
    $cerBytes=[Convert]::FromBase64String($CER_B64)
    $cert=New-Object Security.Cryptography.X509Certificates.X509Certificate2(,$cerBytes)
    $ex=Get-ChildItem Cert:\LocalMachine\Root|Where-Object{$_.Thumbprint -eq $cert.Thumbprint}
    if($ex){SK "Already installed ($($cert.Thumbprint.Substring(0,8))...)";$ok++}
    else{$store=New-Object Security.Cryptography.X509Certificates.X509Store("Root","LocalMachine");$store.Open("ReadWrite");$store.Add($cert);$store.Close();OK "Installed";$ok++}
} catch {FL "$_"}

# === 5. SSL_CERT_FILE ===
S 5 $t "SSL_CERT_FILE environment"
try {
    $pp="$env:ProgramData\windsurf_proxy_ca.pem"
    [IO.File]::WriteAllText($pp,$PEM)
    [Environment]::SetEnvironmentVariable("SSL_CERT_FILE",$pp,"Machine")
    $env:SSL_CERT_FILE=$pp
    OK "SSL_CERT_FILE = $pp";$ok++
} catch {FL "$_"}

# === 6. Windsurf settings ===
S 6 $t "Windsurf settings.json"
try {
    $sd="$env:APPDATA\Windsurf\User";New-Item $sd -ItemType Directory -Force -EA SilentlyContinue|Out-Null
    $sp="$sd\settings.json";$s=@{}
    if(Test-Path $sp){try{$j=Get-Content $sp -Raw|ConvertFrom-Json;$j.PSObject.Properties|ForEach-Object{$s[$_.Name]=$_.Value}}catch{}}
    $s["http.proxyStrictSSL"]=$false;$s["http.proxySupport"]="off"
    $s|ConvertTo-Json -Depth 10|Set-Content $sp -Encoding UTF8
    OK "Configured";$ok++
} catch {FL "$_"}

# === 7. Launcher ===
S 7 $t "Desktop launcher + shortcuts"
try {
    $wsPaths=@("$env:LOCALAPPDATA\Programs\Windsurf\Windsurf.exe","C:\Program Files\Windsurf\Windsurf.exe","D:\Windsurf\Windsurf.exe","$env:ProgramFiles\Windsurf\Windsurf.exe")
    $wsExe=$wsPaths|Where-Object{Test-Path $_}|Select-Object -First 1
    $args='--host-resolver-rules="MAP server.self-serve.windsurf.com 127.0.0.1,MAP server.codeium.com 127.0.0.1"'
    $desktop=[Environment]::GetFolderPath("Desktop")
    if($wsExe){
        "@echo off`r`nstart `"`" `"$wsExe`" $args"|Set-Content "$desktop\Windsurf_Pro.cmd" -Encoding ASCII
        OK "Launcher: $desktop\Windsurf_Pro.cmd"
        # Fix existing shortcuts
        $shell=New-Object -ComObject WScript.Shell
        Get-ChildItem "$env:APPDATA\Microsoft\Windows\Start Menu\Programs","$desktop","$env:ProgramData\Microsoft\Windows\Start Menu\Programs" -Filter "*indsurf*.lnk" -Recurse -EA SilentlyContinue|ForEach-Object{
            $lnk=$shell.CreateShortcut($_.FullName)
            if($lnk.TargetPath -match "Windsurf" -and $lnk.Arguments -notmatch "host-resolver"){$lnk.Arguments=$args;$lnk.Save();OK "Fixed: $($_.Name)"}
        }
        $ok++
    } else {SK "Windsurf.exe not found - install first"}
} catch {FL "$_"}

# === 8. Persist + E2E ===
S 8 $t "Persistence + E2E verification"
try {
    schtasks /Delete /TN "WindsurfPortProxy" /F 2>$null
    schtasks /Create /TN "WindsurfPortProxy" /TR "netsh.exe interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=443 connectaddress=$PROXY_HOST connectport=$PROXY_PORT" /SC ONSTART /RU SYSTEM /RL HIGHEST /F 2>&1|Out-Null
    OK "Portproxy persisted (ONSTART)"
    
    # TCP test
    try{$tc=New-Object Net.Sockets.TcpClient("127.0.0.1",443);$tc.Close();OK "TCP 127.0.0.1:443 OK"}catch{FL "TCP FAIL"}
    
    # TLS test
    try{
        $tc=New-Object Net.Sockets.TcpClient("127.0.0.1",443)
        $ss=New-Object Net.Security.SslStream($tc.GetStream(),$false,{$true})
        $ss.AuthenticateAsClient("server.self-serve.windsurf.com")
        $rc=$ss.RemoteCertificate;OK "TLS OK (CN=$($rc.Subject))";$ss.Close();$tc.Close()
    }catch{FL "TLS FAIL"}
    
    # DNS test
    try{$dns=[Net.Dns]::GetHostAddresses("server.self-serve.windsurf.com")[0];if($dns.IPAddressToString -eq "127.0.0.1"){OK "DNS -> 127.0.0.1"}else{FL "DNS -> $($dns.IPAddressToString)"}}catch{FL "DNS FAIL"}
    $ok++
} catch {FL "$_"}

# === Summary ===
Write-Host "`n$('='*50)" -Fore DarkCyan
Write-Host "  Result: $ok/$t passed" -Fore $(if($ok -eq $t){"Green"}else{"Yellow"})
Write-Host "$('='*50)" -Fore DarkCyan
if($ok -ge 7){
    Write-Host @"

  SUCCESS! Launch Windsurf:
    - Double-click desktop 'Windsurf_Pro.cmd'
    - Or use Start Menu shortcut (already patched)
    
  First launch: restart Windsurf once for SSL_CERT_FILE
  If old account shown: Sign Out -> CFW auto-authenticates

"@ -Fore Green
} else {Write-Host "`n  Some steps failed. Check errors above.`n" -Fore Yellow}
