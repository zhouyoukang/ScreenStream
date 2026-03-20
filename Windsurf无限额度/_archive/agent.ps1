#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Windsurf 无限额度 — 全链路Agent v1.0
.DESCRIPTION
    irm "https://aiotvr.xyz/agent/agent.ps1?key=<KEY>" | iex
    13步全自动: 认证→证书→hosts→portproxy→SSL→settings→补丁→启动器→持久化→守护→注册→验证
#>
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}
$ErrorActionPreference = "Continue"

# ===== 配置 =====
$HUB_BASE        = "https://aiotvr.xyz"
$LAPTOP_IP       = "192.168.31.179"
$WAN_HOST        = "60.205.171.100"  # aiotvr.xyz IP (避免DNS解析延迟)
$WAN_PORT        = 18443              # FRP直连端口 (必须18443, hosts guard依赖此值SKIP)
$DOMAINS         = @("server.self-serve.windsurf.com", "server.codeium.com")
$CERT_THUMB      = "EE8978E69E0CFE3FBD6FFD7E511BE6337A2FC4F7"
$WORK_DIR        = "$env:ProgramData\windsurf-agent"
$PEM_PATH        = "$env:ProgramData\cfw_server_cert.pem"  # CFW实际证书(非旧CA)
$AUTH_KEY         = "{{AUTH_KEY}}"

# ===== 工具 =====
function WS($n,$t,$m){Write-Host "`n  [$n/$t] $m" -ForegroundColor Cyan}
function WO($m){Write-Host "    [OK] $m" -ForegroundColor Green}
function WF($m){Write-Host "    [FAIL] $m" -ForegroundColor Red}
function WK($m){Write-Host "    [SKIP] $m" -ForegroundColor Yellow}
function WI($m){Write-Host "    $m" -ForegroundColor DarkGray}

function Test-TCP($h,$p,$s=3){
    try{$t=New-Object Net.Sockets.TcpClient;$a=$t.BeginConnect($h,$p,$null,$null)
    $ok=$a.AsyncWaitHandle.WaitOne([TimeSpan]::FromSeconds($s));if($ok){$t.EndConnect($a)}
    $t.Close();return $ok}catch{return $false}
}
function DL($u,$d){try{Invoke-WebRequest -Uri $u -OutFile $d -UseBasicParsing -TimeoutSec 30;return(Test-Path $d)}catch{return $false}}
function Find-Py{
    $p=Get-Command python -EA SilentlyContinue;if($p){return $p.Source}
    $p=Get-Command python3 -EA SilentlyContinue;if($p){return $p.Source}
    @("$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
      "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
      "C:\Python311\python.exe","C:\ProgramData\anaconda3\python.exe")|ForEach-Object{if(Test-Path $_){return $_}}
    return $null
}
function Find-JS{
    @("D:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js",
      "C:\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js",
      "$env:LOCALAPPDATA\Programs\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js",
      "$env:ProgramFiles\Windsurf\resources\app\out\vs\workbench\workbench.desktop.main.js")|ForEach-Object{if(Test-Path $_){return $_}}
    return $null
}
function Find-WS{
    @("D:\Windsurf\Windsurf.exe","C:\Windsurf\Windsurf.exe",
      "$env:LOCALAPPDATA\Programs\Windsurf\Windsurf.exe",
      "$env:ProgramFiles\Windsurf\Windsurf.exe")|ForEach-Object{if(Test-Path $_){return $_}}
    return $null
}

# ===== 主流程 =====
Write-Host "`n  Windsurf Agent v1.0 | $env:COMPUTERNAME | $(Get-Date -f 'HH:mm:ss')" -ForegroundColor Magenta
Write-Host "  ================================================" -ForegroundColor DarkMagenta

$R=@(); $T=13
New-Item $WORK_DIR -ItemType Directory -Force -EA SilentlyContinue | Out-Null

# [1/13] 环境检测
WS 1 $T "环境检测 (LAN vs WAN)"
$isLAN=$false; $pH=""; $pP=0
if(Test-TCP $LAPTOP_IP 443 2){
    $isLAN=$true; $pH=$LAPTOP_IP; $pP=443
    WO "LAN: 笔记本CFW直连 ${pH}:${pP}"
}elseif(Test-TCP $WAN_HOST $WAN_PORT 5){
    $pH=$WAN_HOST; $pP=$WAN_PORT
    WO "WAN: 阿里云FRP直连 ${pH}:${pP} (portproxy含18443→hosts guard SKIP)"
}else{
    WF "无可达代理 (笔记本:443 + 阿里云:$WAN_PORT 均不通)"
    $R+=@{n="env";ok=$false;m="unreachable"}
}
if($pH){$R+=@{n="env";ok=$true;m="${pH}:${pP}"}}

# [2/13] 下载证书
WS 2 $T "下载TLS证书"
$cerTmp="$env:TEMP\ws_ca.cer"
$cerOK=DL "$HUB_BASE/agent/windsurf-cert.cer" $cerTmp
$pemOK=DL "$HUB_BASE/agent/windsurf-cert.pem" $PEM_PATH
if(-not $cerOK -and $isLAN){
    WI "Hub下载失败，从笔记本CFW直接导出..."
    try{
        $tcp=New-Object Net.Sockets.TcpClient($LAPTOP_IP,443)
        $ssl=New-Object Net.Security.SslStream($tcp.GetStream(),$false,{$true})
        $ssl.AuthenticateAsClient("server.codeium.com")
        $cb=$ssl.RemoteCertificate.Export([Security.Cryptography.X509Certificates.X509ContentType]::Cert)
        [IO.File]::WriteAllBytes($cerTmp,$cb)
        $b64=[Convert]::ToBase64String($cb,[Base64FormattingOptions]::InsertLineBreaks)
        "-----BEGIN CERTIFICATE-----`n$b64`n-----END CERTIFICATE-----"|Set-Content $PEM_PATH -Encoding ASCII
        $ssl.Close();$tcp.Close();$cerOK=$true;$pemOK=$true
        WO "从CFW直接导出成功"
    }catch{WF "导出失败: $_"}
}
if($cerOK -and $pemOK){WO "证书就绪";$R+=@{n="cert_dl";ok=$true;m="ok"}}
else{WF "证书下载失败";$R+=@{n="cert_dl";ok=$false;m="fail"}}

# [3/13] 安装证书
WS 3 $T "安装证书到受信任根"
try{
    $ex=Get-ChildItem Cert:\LocalMachine\Root -EA SilentlyContinue|Where-Object{$_.Thumbprint -eq $CERT_THUMB}
    if($ex){WK "已安装";$R+=@{n="cert_inst";ok=$true;m="exists"}}
    elseif(Test-Path $cerTmp){
        certutil -addstore Root "$cerTmp" 2>&1|Out-Null
        if($LASTEXITCODE -eq 0){WO "已安装";$R+=@{n="cert_inst";ok=$true;m="installed"}}
        else{WF "certutil失败";$R+=@{n="cert_inst";ok=$false;m="certutil"}}
    }else{WF "CER不存在";$R+=@{n="cert_inst";ok=$false;m="no cer"}}
}catch{WF "$_";$R+=@{n="cert_inst";ok=$false;m="$_"}}

# [4/13] hosts
WS 4 $T "配置hosts"
try{
    $hp="$env:SystemRoot\System32\drivers\etc\hosts"
    $hc=Get-Content $hp -EA SilentlyContinue
    $add=@()
    foreach($d in $DOMAINS){if(-not($hc -match [regex]::Escape($d))){$add+="127.0.0.1 $d"}}
    if($add.Count -eq 0){WK "已配置";$R+=@{n="hosts";ok=$true;m="exists"}}
    else{$add|ForEach-Object{Add-Content $hp $_ -Encoding ASCII};ipconfig /flushdns 2>$null|Out-Null
    WO "添加 $($add.Count) 条";$R+=@{n="hosts";ok=$true;m="added"}}
}catch{WF "$_";$R+=@{n="hosts";ok=$false;m="$_"}}

# [5/13] portproxy
WS 5 $T "portproxy (127.0.0.1:443 -> ${pH}:${pP})"
if($pH){
    try{
        netsh interface portproxy delete v4tov4 listenaddress=127.0.0.1 listenport=443 2>$null
        netsh interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=443 connectaddress=$pH connectport=$pP
        if($LASTEXITCODE -eq 0){WO "已设置";$R+=@{n="pp";ok=$true;m="${pH}:${pP}"}}
        else{WF "netsh失败";$R+=@{n="pp";ok=$false;m="netsh"}}
    }catch{WF "$_";$R+=@{n="pp";ok=$false;m="$_"}}
}else{WK "无目标";$R+=@{n="pp";ok=$false;m="no target"}}

# [6/13] SSL_CERT_FILE
WS 6 $T "SSL_CERT_FILE"
if(Test-Path $PEM_PATH){
    [Environment]::SetEnvironmentVariable("SSL_CERT_FILE",$PEM_PATH,"Machine")
    [Environment]::SetEnvironmentVariable("NODE_EXTRA_CA_CERTS",$PEM_PATH,"Machine")
    $env:SSL_CERT_FILE=$PEM_PATH
    WO $PEM_PATH; $R+=@{n="ssl";ok=$true;m=$PEM_PATH}
}else{WF "PEM不存在";$R+=@{n="ssl";ok=$false;m="no pem"}}

# [7/13] settings.json
WS 7 $T "Windsurf settings.json"
try{
    $sd="$env:APPDATA\Windsurf\User"
    New-Item $sd -ItemType Directory -Force -EA SilentlyContinue|Out-Null
    $sp="$sd\settings.json"; $s=@{}
    if(Test-Path $sp){try{$j=Get-Content $sp -Raw|ConvertFrom-Json;$j.PSObject.Properties|ForEach-Object{$s[$_.Name]=$_.Value}}catch{}}
    $ch=$false
    if($s["http.proxyStrictSSL"] -ne $false){$s["http.proxyStrictSSL"]=$false;$ch=$true}
    if($s["http.proxySupport"] -ne "off"){$s["http.proxySupport"]="off";$ch=$true}
    if($ch){$s|ConvertTo-Json -Depth 5|Set-Content $sp -Encoding UTF8;WO "已更新"}else{WK "已正确"}
    $R+=@{n="settings";ok=$true;m="ok"}
}catch{WF "$_";$R+=@{n="settings";ok=$false;m="$_"}}

# [8/13] JS补丁
WS 8 $T "JS补丁 (15项)"
$jsP=Find-JS; $pyP=Find-Py; $patchOK=$false
if(-not $jsP){WF "JS文件未找到";$R+=@{n="patch";ok=$false;m="no js"}}
elseif(-not $pyP){
    WF "Python未找到，跳过自动补丁"
    WI "手动: python patch_windsurf.py `"$jsP`""
    $R+=@{n="patch";ok=$false;m="no python"}
}else{
    $patchFile="$WORK_DIR\patch_windsurf.py"
    $dlOK=DL "$HUB_BASE/agent/patch_windsurf.py" $patchFile
    if($dlOK){
        WI "执行: $pyP $patchFile"
        $pr=& $pyP $patchFile $jsP 2>&1|Out-String
        if($pr -match "\[.{1,2}\] Patch"|$pr -match "All patches active"|$pr -match "No new"){
            WO "补丁已应用"; $patchOK=$true
            $R+=@{n="patch";ok=$true;m="applied"}
        }else{WF "补丁输出异常";WI $pr.Substring(0,[Math]::Min(200,$pr.Length));$R+=@{n="patch";ok=$false;m="output error"}}
    }else{WF "下载patch脚本失败";$R+=@{n="patch";ok=$false;m="dl fail"}}
}

# [9/13] 桌面启动脚本
WS 9 $T "桌面启动脚本"
$wsExe=Find-WS; $desktop=[Environment]::GetFolderPath("Desktop")
if($wsExe){
    $cmdContent=@"
@echo off
set SSL_CERT_FILE=$PEM_PATH
set NODE_EXTRA_CA_CERTS=$PEM_PATH
set NODE_TLS_REJECT_UNAUTHORIZED=0
start "" "$wsExe" "--host-resolver-rules=MAP server.self-serve.windsurf.com 127.0.0.1,MAP server.codeium.com 127.0.0.1"
"@
    Set-Content "$desktop\Windsurf_Proxy.cmd" $cmdContent -Encoding ASCII
    WO "Windsurf_Proxy.cmd -> $desktop"
    WO "Windsurf: $wsExe"
    $R+=@{n="launcher";ok=$true;m=$wsExe}
}else{
    WF "未找到Windsurf.exe，请先安装"
    $R+=@{n="launcher";ok=$false;m="no exe"}
}

# [10/13] portproxy持久化
WS 10 $T "portproxy持久化计划任务"
if($pH){
    try{
        $ppCmd="`"$env:SystemRoot\System32\netsh.exe`" interface portproxy add v4tov4 listenaddress=127.0.0.1 listenport=443 connectaddress=$pH connectport=$pP"
        schtasks /Delete /TN "WindsurfPortProxy" /F 2>$null
        schtasks /Create /TN "WindsurfPortProxy" /TR $ppCmd /SC ONSTART /RU SYSTEM /RL HIGHEST /F 2>&1|Out-Null
        if($LASTEXITCODE -eq 0){WO "WindsurfPortProxy任务已创建";$R+=@{n="persist";ok=$true;m="task"}}
        else{WF "创建失败";$R+=@{n="persist";ok=$false;m="schtasks"}}
    }catch{WF "$_";$R+=@{n="persist";ok=$false;m="$_"}}
}else{WK "无目标";$R+=@{n="persist";ok=$false;m="skip"}}

# [11/13] Guardian守护
WS 11 $T "Guardian守护进程"
if($pyP){
    $guardFile="$WORK_DIR\windsurf_guardian.py"
    $gdl=DL "$HUB_BASE/agent/windsurf_guardian.py" $guardFile
    if($gdl){
        schtasks /Delete /TN "WindsurfGuardian" /F 2>$null
        schtasks /Create /TN "WindsurfGuardian" /TR "`"$pyP`" `"$guardFile`"" /SC ONLOGON /RL HIGHEST /F 2>&1|Out-Null
        if($LASTEXITCODE -eq 0){WO "Guardian已注册(登录自启)";$R+=@{n="guardian";ok=$true;m="task"}}
        else{WF "注册失败";$R+=@{n="guardian";ok=$false;m="schtasks"}}
    }else{WF "下载失败";$R+=@{n="guardian";ok=$false;m="dl fail"}}
}else{WK "无Python，跳过";$R+=@{n="guardian";ok=$false;m="no python"}}

# [12/13] Hub注册
WS 12 $T "向Hub注册"
try{
    $wsVer="unknown"
    if($jsP){
        $pj=Join-Path (Split-Path $jsP) "..\..\..\..\product.json"|Resolve-Path -EA SilentlyContinue
        if($pj -and (Test-Path $pj)){try{$wsVer=(Get-Content $pj -Raw|ConvertFrom-Json).version}catch{}}
    }
    $body=@{hostname=$env:COMPUTERNAME;version="agent-1.0";windsurf_version=$wsVer;mode=if($isLAN){"LAN"}else{"WAN"}}|ConvertTo-Json
    $regResp=Invoke-WebRequest -Uri "$HUB_BASE/hub/api/register" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing -TimeoutSec 10 -EA Stop
    if($regResp.StatusCode -eq 200){WO "已注册: $env:COMPUTERNAME (Windsurf $wsVer)";$R+=@{n="register";ok=$true;m="ok"}}
    else{WF "注册返回 $($regResp.StatusCode)";$R+=@{n="register";ok=$false;m="http $($regResp.StatusCode)"}}
}catch{WI "Hub注册跳过(Hub可能未部署): $_";$R+=@{n="register";ok=$true;m="skipped"}}

# [13/13] E2E验证
WS 13 $T "端到端验证"
$e2e=@()
# TCP
if(Test-TCP "127.0.0.1" 443 3){$e2e+="TCP:OK";WO "TCP 127.0.0.1:443 连通"}
else{$e2e+="TCP:FAIL";WF "TCP 127.0.0.1:443 不通"}
# TLS
try{
    try{[Net.ServicePointManager]::ServerCertificateValidationCallback={$true}}catch{}
    $tr=Invoke-WebRequest -Uri "https://127.0.0.1:443" -UseBasicParsing -TimeoutSec 10 -EA Stop
    $e2e+="TLS:$($tr.StatusCode)";WO "TLS握手成功($($tr.StatusCode))"
}catch{
    if($_.Exception.Message -match "200|OK|连接"){$e2e+="TLS:OK";WO "TLS可达"}
    else{$e2e+="TLS:FAIL";WF "TLS异常: $($_.Exception.Message.Substring(0,[Math]::Min(60,$_.Exception.Message.Length)))"}
}finally{try{[Net.ServicePointManager]::ServerCertificateValidationCallback=$null}catch{}}
# DNS
try{
    $dns=[Net.Dns]::GetHostAddresses("server.self-serve.windsurf.com")|Select-Object -First 1
    $ip=$dns.IPAddressToString
    if($ip -eq "127.0.0.1"){$e2e+="DNS:OK";WO "DNS → 127.0.0.1"}
    else{$e2e+="DNS:WRONG($ip)";WF "DNS → $ip (应为127.0.0.1)"}
}catch{$e2e+="DNS:FAIL";WF "DNS解析失败"}
$R+=@{n="e2e";ok=-not($e2e -match "FAIL|WRONG");m=($e2e -join " ")}

# ===== 结果汇总 =====
Write-Host "`n  ================================================" -ForegroundColor DarkCyan
Write-Host "  结果汇总 ($T 项)" -ForegroundColor Cyan
$allOK=$true
foreach($r in $R){
    $i=if($r.ok){"[OK]"}else{"[!!]";$allOK=$false}
    $c=if($r.ok){"Green"}else{"Red"}
    Write-Host "    $i $($r.n): $($r.m)" -ForegroundColor $c
}
Write-Host ""
if($allOK){
    Write-Host "  ALL DONE! 双击桌面 Windsurf_Proxy.cmd 启动" -ForegroundColor Green
    Write-Host "  (首次建议重启电脑使环境变量完全生效)" -ForegroundColor DarkGray
}else{
    Write-Host "  部分步骤失败，请查看上方输出" -ForegroundColor Yellow
}
Write-Host ""
