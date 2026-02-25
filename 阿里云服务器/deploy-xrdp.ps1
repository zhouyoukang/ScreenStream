###############################################################################
# Windows 端一键部署 Linux 远程桌面到阿里云
#
# 用法：
#   .\deploy-xrdp.ps1 -HostIP 60.205.171.100 -User root
#   .\deploy-xrdp.ps1 -HostIP 60.205.171.100 -User root -Password
#   .\deploy-xrdp.ps1 -HostIP 60.205.171.100 -User root -DiagnoseOnly
###############################################################################

param(
    [Parameter(Mandatory=$true)]
    [string]$HostIP,

    [string]$User = "root",
    [int]$Port = 22,
    [switch]$Password,
    [switch]$SkipUpload,
    [switch]$DiagnoseOnly
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SetupScript = Join-Path $ScriptDir "xrdp-setup.sh"

Write-Host ""
Write-Host "  Linux 远程桌面一键部署" -ForegroundColor Cyan
Write-Host "  目标: $User@$HostIP`:$Port" -ForegroundColor Cyan
Write-Host ""

# ── SSH参数 ──
$sshArgs = @("-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", "-p", "$Port")

if (-not $Password) {
    $keyFile = @("$env:USERPROFILE\.ssh\id_ed25519", "$env:USERPROFILE\.ssh\id_rsa") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($keyFile) { $sshArgs += @("-i", $keyFile) }
}

# ── 测试连接 ──
Write-Host "[1/5] 测试SSH连接..." -ForegroundColor Green
$testResult = & ssh @sshArgs "$User@$HostIP" "echo SSH_OK; cat /etc/os-release 2>/dev/null | head -2" 2>&1
if (($testResult -join "`n") -notmatch "SSH_OK") {
    Write-Host "  SSH连接失败！" -ForegroundColor Red
    Write-Host "  检查: IP/端口/用户名/SSH Key/安全组" -ForegroundColor Yellow
    exit 1
}
Write-Host "  SSH连接成功" -ForegroundColor Green

# ── 仅诊断 ──
if ($DiagnoseOnly) {
    Write-Host "`n[诊断] 服务器信息:" -ForegroundColor Cyan
    & ssh @sshArgs "$User@$HostIP" @"
echo "CPU: `$(nproc)核  内存: `$(free -h | awk '/^Mem:/{print `$2}')  磁盘: `$(df -h / | awk 'NR==2{print `$4}')可用"
echo "桌面: `$(dpkg -l 2>/dev/null | grep -c xfce4 || rpm -qa 2>/dev/null | grep -c xfce4 || echo 0) 个XFCE包"
echo "xrdp: `$(systemctl is-active xrdp 2>/dev/null || echo '未安装')"
echo "3389: `$(ss -tlnp 2>/dev/null | grep 3389 | head -1 || echo '未监听')"
echo "公网IP: `$(curl -s --connect-timeout 3 http://ifconfig.me 2>/dev/null || echo '未知')"
"@
    exit 0
}

# ── 上传脚本 ──
if (-not $SkipUpload) {
    Write-Host "`n[2/5] 上传部署脚本..." -ForegroundColor Green
    if (-not (Test-Path $SetupScript)) {
        Write-Host "  找不到 $SetupScript" -ForegroundColor Red; exit 1
    }
    $scpArgs = @("-o", "StrictHostKeyChecking=no", "-P", "$Port")
    if ($keyFile) { $scpArgs += @("-i", $keyFile) }
    & scp @scpArgs $SetupScript "$User@$HostIP`:/tmp/xrdp-setup.sh"
    if ($LASTEXITCODE -ne 0) { Write-Host "  上传失败" -ForegroundColor Red; exit 1 }
    Write-Host "  上传成功" -ForegroundColor Green
}

# ── 执行安装 ──
Write-Host "`n[3/5] 执行安装（约3-10分钟）..." -ForegroundColor Green
& ssh @sshArgs "$User@$HostIP" "chmod +x /tmp/xrdp-setup.sh && sudo /tmp/xrdp-setup.sh"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  安装有错误 (exit: $LASTEXITCODE)" -ForegroundColor Red; exit 1
}

# ── 验证 ──
Write-Host "`n[4/5] 验证..." -ForegroundColor Green
$verify = & ssh @sshArgs "$User@$HostIP" "systemctl is-active xrdp && ss -tlnp | grep 3389" 2>&1
if (($verify -join "`n") -match "active" -and ($verify -join "`n") -match "3389") {
    Write-Host "  xrdp运行中，3389已监听" -ForegroundColor Green
} else {
    Write-Host "  可能需要手动检查" -ForegroundColor Yellow
}

# ── 连接 ──
Write-Host "`n[5/5] 部署完成！" -ForegroundColor Green
Write-Host "  连接: mstsc → $HostIP`:3389" -ForegroundColor Cyan
Write-Host "  确保阿里云安全组已开放 TCP 3389！" -ForegroundColor Yellow

$openRDP = Read-Host "`n立即连接? (Y/n)"
if ($openRDP -ne "n") {
    $rdpFile = Join-Path $env:TEMP "aliyun-xrdp.rdp"
    @"
full address:s:$HostIP`:3389
username:s:$User
session bpp:i:24
smart sizing:i:1
dynamic resolution:i:1
prompt for credentials:i:1
audiomode:i:2
redirectclipboard:i:1
autoreconnection enabled:i:1
"@ | Set-Content $rdpFile -Encoding ASCII
    Start-Process "mstsc.exe" $rdpFile
}
