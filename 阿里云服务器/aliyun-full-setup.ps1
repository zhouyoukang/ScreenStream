###############################################################################
# 阿里云服务器一键全量部署
#
# 功能：SSH密钥部署 → FRP Server安装 → 本地FRP Client启动 → 全链路验证
# 前提：你知道服务器root密码（阿里云控制台可重置）
#
# 用法：
#   .\aliyun-full-setup.ps1                        # 交互式输入密码
#   .\aliyun-full-setup.ps1 -Password "你的密码"    # 命令行传入
#   .\aliyun-full-setup.ps1 -SkipServerSetup        # 只配本地（服务端已就绪）
#   .\aliyun-full-setup.ps1 -DiagnoseOnly           # 只诊断不修改
###############################################################################

param(
    [string]$Password = "",
    [string]$HostIP = "60.205.171.100",
    [string]$User = "root",
    [switch]$SkipServerSetup,
    [switch]$DiagnoseOnly
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PlinkExe = "C:\Program Files\PuTTY\plink.exe"
$HostKey = "SHA256:j6Sq67ryKmH8BjB0zUDW8ul5BCn0zGPBpCRpeNK7AbU"
$LocalPubKey = Get-Content "$env:USERPROFILE\.ssh\id_ed25519.pub" -Raw
$LocalPubKey = $LocalPubKey.Trim()

# ── 读取secrets.toml ──
$SecretsFile = Join-Path $ScriptDir "secrets.toml"
$FrpToken = ""; $FrpDashPwd = ""
if (Test-Path $SecretsFile) {
    $secrets = Get-Content $SecretsFile -Raw
    if ($secrets -match 'token\s*=\s*"([^"]+)"') { $FrpToken = $Matches[1] }
    if ($secrets -match 'dashboard_password\s*=\s*"([^"]+)"') { $FrpDashPwd = $Matches[1] }
}

function Write-Step($num, $total, $msg) {
    Write-Host "`n[$num/$total] $msg" -ForegroundColor Cyan
}

function Write-OK($msg) { Write-Host "  OK: $msg" -ForegroundColor Green }
function Write-FAIL($msg) { Write-Host "  FAIL: $msg" -ForegroundColor Red }
function Write-INFO($msg) { Write-Host "  $msg" -ForegroundColor Yellow }

function Test-Port($ip, $port, $timeout = 3000) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $r = $c.BeginConnect($ip, $port, $null, $null)
        $ok = $r.AsyncWaitHandle.WaitOne($timeout)
        if ($ok -and $c.Connected) { $c.Close(); return $true }
        $c.Close(); return $false
    } catch { return $false }
}

function Invoke-Plink($cmd) {
    $args = @("-ssh", "-batch", "-hostkey", $HostKey, "-pw", $Password, "$User@$HostIP", $cmd)
    $result = & $PlinkExe @args 2>&1
    return ($result -join "`n")
}

function Invoke-SSH($cmd) {
    $result = ssh -o ConnectTimeout=15 -o BatchMode=yes -o StrictHostKeyChecking=no "$User@$HostIP" $cmd 2>&1
    return ($result -join "`n")
}

# ══════════════════════════════════════════════════════════════
Write-Host ""
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host "  阿里云服务器一键全量部署" -ForegroundColor Cyan
Write-Host "  目标: $User@$HostIP" -ForegroundColor Cyan
Write-Host "  ========================================" -ForegroundColor Cyan
$totalSteps = if ($DiagnoseOnly) { 3 } elseif ($SkipServerSetup) { 4 } else { 8 }

# ══════ Phase 0: 基础连通性 ══════
Write-Step 1 $totalSteps "检查基础连通性"

if (-not (Test-Port $HostIP 22)) {
    Write-FAIL "端口22不通 — 服务器可能已关机或安全组未开放SSH"
    Write-INFO "请登录 https://swas.console.aliyun.com 检查实例状态和防火墙规则"
    exit 1
}
Write-OK "SSH端口22开放"

$p7000 = Test-Port $HostIP 7000
$p7500 = Test-Port $HostIP 7500
$p19903 = Test-Port $HostIP 19903
Write-Host "  FRP绑定(7000): $(if($p7000){'OPEN'}else{'CLOSED'})" -ForegroundColor $(if($p7000){'Green'}else{'Yellow'})
Write-Host "  FRP控制台(7500): $(if($p7500){'OPEN'}else{'CLOSED'})" -ForegroundColor $(if($p7500){'Green'}else{'Yellow'})
Write-Host "  remote_agent(19903): $(if($p19903){'OPEN'}else{'CLOSED'})" -ForegroundColor $(if($p19903){'Green'}else{'Yellow'})

# ══════ Phase 1: SSH密钥认证测试 ══════
Write-Step 2 $totalSteps "测试SSH密钥认证"

$sshTest = ssh -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=no "$User@$HostIP" "echo SSH_KEY_OK" 2>&1
$sshKeyOK = ($sshTest -join " ") -match "SSH_KEY_OK"

if ($sshKeyOK) {
    Write-OK "SSH密钥认证已就绪"
} else {
    Write-INFO "SSH密钥认证未就绪 — 需要部署公钥"

    if ($DiagnoseOnly) {
        Write-INFO "诊断模式：跳过修复"
        Write-INFO "修复方法：运行此脚本（不带 -DiagnoseOnly）并提供root密码"
    } else {
        # 需要密码来部署公钥
        if (-not $Password) {
            Write-Host ""
            Write-Host "  需要服务器root密码来部署SSH公钥。" -ForegroundColor Yellow
            Write-Host "  如果不知道密码，请到阿里云控制台重置：" -ForegroundColor Yellow
            Write-Host "  https://swas.console.aliyun.com → 服务器 → 远程连接 → 重置密码" -ForegroundColor Cyan
            Write-Host ""
            $secPwd = Read-Host "请输入root密码（输入后按回车）"
            $Password = $secPwd
        }

        if (-not $Password) {
            Write-FAIL "未提供密码，无法继续"
            exit 1
        }

        # 检查plink
        if (-not (Test-Path $PlinkExe)) {
            Write-FAIL "未找到 plink.exe ($PlinkExe)"
            Write-INFO "请安装 PuTTY: https://www.putty.org/"
            exit 1
        }

        # 用plink+密码部署SSH公钥
        Write-Host "  正在通过密码登录部署SSH公钥..." -ForegroundColor Yellow
        $deployCmd = "mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo '$LocalPubKey' >> ~/.ssh/authorized_keys && sort -u ~/.ssh/authorized_keys -o ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && echo PUBKEY_DEPLOYED"
        $deployResult = Invoke-Plink $deployCmd

        if ($deployResult -match "PUBKEY_DEPLOYED") {
            Write-OK "SSH公钥已部署到服务器"
        } else {
            Write-FAIL "公钥部署失败: $deployResult"
            if ($deployResult -match "Access denied") {
                Write-INFO "密码错误。请到阿里云控制台重置密码后重试。"
            }
            exit 1
        }

        # 验证密钥认证
        Start-Sleep -Seconds 1
        $sshVerify = ssh -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=no "$User@$HostIP" "echo SSH_KEY_VERIFIED" 2>&1
        if (($sshVerify -join " ") -match "SSH_KEY_VERIFIED") {
            Write-OK "SSH密钥认证验证通过！从此免密登录"
            $sshKeyOK = $true
        } else {
            Write-FAIL "密钥部署后仍无法免密登录"
            Write-INFO "可能原因：sshd_config 禁用了 PubkeyAuthentication"
            # 尝试修复sshd配置
            $fixCmd = "sed -i 's/^#*PubkeyAuthentication.*/PubkeyAuthentication yes/' /etc/ssh/sshd_config && systemctl restart sshd && echo SSHD_FIXED"
            $fixResult = Invoke-Plink $fixCmd
            if ($fixResult -match "SSHD_FIXED") {
                Start-Sleep -Seconds 2
                $sshVerify2 = ssh -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=no "$User@$HostIP" "echo SSH_KEY_VERIFIED" 2>&1
                if (($sshVerify2 -join " ") -match "SSH_KEY_VERIFIED") {
                    Write-OK "sshd配置已修复，密钥认证通过"
                    $sshKeyOK = $true
                } else {
                    Write-FAIL "仍然无法密钥认证，请手动检查"
                    exit 1
                }
            }
        }
    }
}

if ($DiagnoseOnly) {
    # ══════ 诊断: 服务器状态 ══════
    Write-Step 3 $totalSteps "服务器详细状态"
    if ($sshKeyOK) {
        $info = Invoke-SSH "echo '=== SYSTEM ===' && uname -a && echo '=== UPTIME ===' && uptime && echo '=== MEMORY ===' && free -h && echo '=== DISK ===' && df -h / && echo '=== FRP ===' && systemctl is-active frps 2>/dev/null || echo 'frps: not installed' && echo '=== XRDP ===' && systemctl is-active xrdp 2>/dev/null || echo 'xrdp: not installed' && echo '=== PORTS ===' && ss -tlnp 2>/dev/null | grep -E '7000|7500|3389|22'"
        Write-Host $info
    } else {
        Write-INFO "无SSH密钥访问，无法获取服务器详情"
    }
    Write-Host "`n=== 诊断完成 ===" -ForegroundColor Cyan
    exit 0
}

if (-not $sshKeyOK) { Write-FAIL "SSH未就绪，无法继续"; exit 1 }

# ══════ Phase 2: 服务器信息采集 ══════
Write-Step 3 $totalSteps "采集服务器信息"
$serverInfo = Invoke-SSH "echo OS=`$(cat /etc/os-release 2>/dev/null | grep ^PRETTY_NAME | cut -d= -f2 | tr -d '""'); echo CPU=`$(nproc); echo MEM=`$(free -h | awk '/^Mem:/{print `$2}'); echo DISK=`$(df -h / | awk 'NR==2{print `$4}'); echo FRPS=`$(systemctl is-active frps 2>/dev/null || echo inactive); echo XRDP=`$(systemctl is-active xrdp 2>/dev/null || echo inactive); echo UPTIME=`$(uptime -p 2>/dev/null || uptime)"
Write-Host $serverInfo -ForegroundColor Gray

$frpsActive = $serverInfo -match "FRPS=active"

if ($SkipServerSetup) {
    Write-INFO "跳过服务端部署（-SkipServerSetup）"
} else {
    # ══════ Phase 3: FRP Server部署 ══════
    if ($frpsActive) {
        Write-Step 4 $totalSteps "FRP Server已运行，检查配置"
        $frpsConfig = Invoke-SSH "cat /opt/frp/frps.toml 2>/dev/null || echo NO_CONFIG"
        if ($frpsConfig -match "NO_CONFIG") {
            Write-INFO "frps运行中但配置文件不存在，需要重新部署"
            $frpsActive = $false
        } else {
            Write-OK "FRP Server配置存在且服务运行中"
            Write-Host $frpsConfig -ForegroundColor Gray
        }
    }

    if (-not $frpsActive) {
        Write-Step 4 $totalSteps "部署FRP Server"

        if (-not $FrpToken) {
            Write-FAIL "secrets.toml中未找到FRP token"
            exit 1
        }

        # 直接在服务器上执行安装（不依赖scp上传脚本）
        $installCmd = @"
set -e
FRP_VERSION="0.61.1"
cd /opt

# 下载FRP
if [ ! -d "frp_\${FRP_VERSION}_linux_amd64" ]; then
    echo "Downloading FRP \$FRP_VERSION..."
    wget -q "https://ghfast.top/https://github.com/fatedier/frp/releases/download/v\${FRP_VERSION}/frp_\${FRP_VERSION}_linux_amd64.tar.gz" 2>/dev/null \
    || wget -q "https://mirror.ghproxy.com/https://github.com/fatedier/frp/releases/download/v\${FRP_VERSION}/frp_\${FRP_VERSION}_linux_amd64.tar.gz" 2>/dev/null \
    || wget -q "https://github.com/fatedier/frp/releases/download/v\${FRP_VERSION}/frp_\${FRP_VERSION}_linux_amd64.tar.gz"
    tar xzf "frp_\${FRP_VERSION}_linux_amd64.tar.gz"
fi
ln -sfn "/opt/frp_\${FRP_VERSION}_linux_amd64" /opt/frp

# 写配置
cat > /opt/frp/frps.toml << 'FRPEOF'
bindPort = 7000

webServer.addr = "0.0.0.0"
webServer.port = 7500
webServer.user = "admin"
webServer.password = "$FrpDashPwd"

auth.method = "token"
auth.token = "$FrpToken"

transport.tls.force = false

log.to = "/var/log/frps.log"
log.level = "info"
log.maxDays = 7
FRPEOF

# 替换变量（因为heredoc用了单引号，需要sed替换）
sed -i "s|\\\$FrpDashPwd|$FrpDashPwd|g" /opt/frp/frps.toml
sed -i "s|\\\$FrpToken|$FrpToken|g" /opt/frp/frps.toml

# systemd服务
cat > /etc/systemd/system/frps.service << 'SVCEOF'
[Unit]
Description=FRP Server
After=network.target

[Service]
Type=simple
ExecStart=/opt/frp/frps -c /opt/frp/frps.toml
Restart=always
RestartSec=5
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable frps
systemctl restart frps
sleep 2
systemctl is-active frps && echo "FRPS_INSTALLED_OK" || echo "FRPS_INSTALL_FAILED"
"@
        $installResult = Invoke-SSH $installCmd
        Write-Host $installResult -ForegroundColor Gray

        if ($installResult -match "FRPS_INSTALLED_OK") {
            Write-OK "FRP Server安装成功并已启动"
        } else {
            Write-FAIL "FRP Server安装失败"
            Write-INFO "检查: ssh root@$HostIP 'journalctl -u frps -n 20'"
            exit 1
        }
    }

    # ══════ Phase 4: 安全组提醒 + 端口验证 ══════
    Write-Step 5 $totalSteps "验证FRP Server端口"
    Start-Sleep -Seconds 3  # 等待服务完全启动

    $p7000_after = Test-Port $HostIP 7000
    $p7500_after = Test-Port $HostIP 7500

    if ($p7000_after) {
        Write-OK "FRP绑定端口7000已开放"
    } else {
        Write-FAIL "端口7000不通 — 请检查阿里云安全组/防火墙"
        Write-INFO "阿里云控制台 → 轻量应用服务器 → 安全 → 防火墙 → 添加规则: TCP 7000"
        Write-INFO "同时添加: TCP 7500, TCP 19903, TCP 13389"

        # 尝试在服务器上开放防火墙
        Write-INFO "尝试在服务器上开放防火墙..."
        $fwResult = Invoke-SSH "if command -v ufw &>/dev/null; then ufw allow 7000/tcp && ufw allow 7500/tcp && ufw allow 19903/tcp && ufw allow 13389/tcp && echo FW_OK; elif command -v firewall-cmd &>/dev/null; then firewall-cmd --permanent --add-port=7000/tcp && firewall-cmd --permanent --add-port=7500/tcp && firewall-cmd --permanent --add-port=19903/tcp && firewall-cmd --permanent --add-port=13389/tcp && firewall-cmd --reload && echo FW_OK; else echo NO_FW; fi"
        if ($fwResult -match "FW_OK") {
            Write-OK "服务器防火墙规则已添加"
            Start-Sleep -Seconds 2
            $p7000_retry = Test-Port $HostIP 7000
            if ($p7000_retry) { Write-OK "端口7000现在已开放" }
            else { Write-INFO "服务器防火墙已开放，但阿里云安全组可能仍未开放 — 请手动检查" }
        } else {
            Write-INFO "服务器无本地防火墙，问题在阿里云安全组层面"
        }
    }

    if ($p7500_after) { Write-OK "FRP控制台端口7500已开放" }
    else { Write-INFO "端口7500未开放（需要在阿里云安全组添加）" }
}

# ══════ Phase 5: 本地FRP Client ══════
$localStep = if ($SkipServerSetup) { 3 } else { 6 }
Write-Step $localStep $totalSteps "配置本地FRP Client"

$frpcExe = Join-Path $ScriptDir "frpc.exe"
$frpcToml = Join-Path $ScriptDir "frpc.toml"

if (-not (Test-Path $frpcExe)) {
    Write-FAIL "frpc.exe不存在: $frpcExe"
    Write-INFO "请下载: https://github.com/fatedier/frp/releases → frp_0.61.1_windows_amd64.zip"
    exit 1
}

if (-not (Test-Path $frpcToml)) {
    Write-FAIL "frpc.toml不存在"
    exit 1
}

# 检查是否已有frpc进程
$existingFrpc = Get-Process frpc -ErrorAction SilentlyContinue
if ($existingFrpc) {
    Write-INFO "发现已运行的frpc进程(PID: $($existingFrpc.Id))，先停止"
    Stop-Process -Name frpc -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# 启动frpc
Write-Host "  启动frpc..." -ForegroundColor Yellow
$frpcProc = Start-Process -FilePath $frpcExe -ArgumentList "-c `"$frpcToml`"" -WorkingDirectory $ScriptDir -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 5

$frpcRunning = Get-Process frpc -ErrorAction SilentlyContinue
if ($frpcRunning) {
    Write-OK "frpc运行中 (PID: $($frpcRunning.Id))"
} else {
    Write-FAIL "frpc启动失败"
    Write-INFO "手动测试: cd '$ScriptDir' && .\frpc.exe -c frpc.toml"
    exit 1
}

# ══════ Phase 6: 安装frpc计划任务 ══════
$taskStep = if ($SkipServerSetup) { 4 } else { 7 }
Write-Step $taskStep $totalSteps "安装frpc开机自启（计划任务）"

$taskName = "FRP Client"
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-INFO "已有计划任务 '$taskName'，跳过创建"
} else {
    try {
        $action = New-ScheduledTaskAction -Execute $frpcExe -Argument "-c `"$frpcToml`"" -WorkingDirectory $ScriptDir
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
        $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description "FRP Client - 阿里云穿透" -ErrorAction Stop | Out-Null
        Write-OK "计划任务 '$taskName' 已创建（开机自启）"
    } catch {
        Write-INFO "创建计划任务需要管理员权限: $_"
        Write-INFO "请以管理员身份运行: powershell -File '$ScriptDir\install-frpc.ps1'"
    }
}

# ══════ Phase 7: 全链路验证 ══════
$verifyStep = if ($SkipServerSetup) { 5 } else { 8 }
Write-Step $verifyStep $totalSteps "全链路验证"

Write-Host ""
Write-Host "  === 端口检查 ===" -ForegroundColor White
$ports = @(
    @{Port=22;    Name="SSH";            Expected=$true},
    @{Port=7000;  Name="FRP绑定";        Expected=$true},
    @{Port=7500;  Name="FRP控制台";       Expected=$true},
    @{Port=19903; Name="remote_agent穿透"; Expected=$true},
    @{Port=13389; Name="RDP穿透";         Expected=$true}
)
$allGreen = $true
foreach ($p in $ports) {
    $open = Test-Port $HostIP $p.Port
    $status = if ($open) { "OPEN" } else { "CLOSED" }
    $color = if ($open) { "Green" } elseif ($p.Expected) { "Red" } else { "Yellow" }
    Write-Host "    $($p.Port) ($($p.Name)): $status" -ForegroundColor $color
    if ($p.Expected -and -not $open) { $allGreen = $false }
}

Write-Host ""
Write-Host "  === SSH密钥认证 ===" -ForegroundColor White
$sshFinal = ssh -o ConnectTimeout=10 -o BatchMode=yes "$User@$HostIP" "echo FINAL_OK" 2>&1
if (($sshFinal -join " ") -match "FINAL_OK") {
    Write-Host "    SSH密钥认证: OK" -ForegroundColor Green
} else {
    Write-Host "    SSH密钥认证: FAILED" -ForegroundColor Red
    $allGreen = $false
}

Write-Host ""
Write-Host "  === FRP Server ===" -ForegroundColor White
$frpsStatus = Invoke-SSH "systemctl is-active frps 2>/dev/null && echo FRPS_OK || echo FRPS_DOWN"
if ($frpsStatus -match "FRPS_OK") {
    Write-Host "    frps服务: 运行中" -ForegroundColor Green
} else {
    Write-Host "    frps服务: 未运行" -ForegroundColor Red
    $allGreen = $false
}

Write-Host ""
Write-Host "  === 本地FRP Client ===" -ForegroundColor White
$localFrpc = Get-Process frpc -ErrorAction SilentlyContinue
if ($localFrpc) {
    Write-Host "    frpc进程: 运行中 (PID: $($localFrpc.Id))" -ForegroundColor Green
} else {
    Write-Host "    frpc进程: 未运行" -ForegroundColor Red
    $allGreen = $false
}

# ══════ 结果汇总 ══════
Write-Host ""
Write-Host "  ========================================" -ForegroundColor $(if($allGreen){"Green"}else{"Yellow"})
if ($allGreen) {
    Write-Host "  全部就绪！" -ForegroundColor Green
    Write-Host ""
    Write-Host "  远程访问地址:" -ForegroundColor Cyan
    Write-Host "    SSH:           ssh root@$HostIP" -ForegroundColor White
    Write-Host "    remote_agent:  http://${HostIP}:19903" -ForegroundColor White
    Write-Host "    RDP:           ${HostIP}:13389" -ForegroundColor White
    Write-Host "    FRP控制台:     http://${HostIP}:7500  (admin/$FrpDashPwd)" -ForegroundColor White
} else {
    Write-Host "  部分服务未就绪" -ForegroundColor Yellow
    Write-Host ""
    if (-not (Test-Port $HostIP 7000)) {
        Write-Host "  需要在阿里云安全组开放端口:" -ForegroundColor Yellow
        Write-Host "    https://swas.console.aliyun.com → 安全 → 防火墙 → 添加规则" -ForegroundColor Cyan
        Write-Host "    TCP 7000 / TCP 7500 / TCP 19903 / TCP 13389" -ForegroundColor White
    }
}
Write-Host "  ========================================" -ForegroundColor $(if($allGreen){"Green"}else{"Yellow"})
