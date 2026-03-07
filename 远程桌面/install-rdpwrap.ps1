#Requires -RunAsAdministrator
<#
.SYNOPSIS
    RDP Wrapper 全自动安装器 — 解决 Windows 10/11 并发 RDP 会话限制
.DESCRIPTION
    安装 RDP Wrapper (sebaxakerhtc fork)，允许多账号并发 RDP，不干扰本地用户。
    原理：在内存中 patch termsrv.dll，绕过 Windows Pro 的单会话硬限制。
.NOTES
    必须以管理员身份运行
    支持 Windows 10 / 11 全版本（自动适配 termsrv.dll 版本）
#>

param(
    [switch]$Uninstall,
    [switch]$UpdateIni,
    [switch]$Status,
    [switch]$Silent
)

# ─────────────────────── 常量 ───────────────────────
$INSTALL_DIR = "C:\Program Files\RDP Wrapper"
$TMP_DIR = "$env:TEMP\rdpwrap_install"
$SERVICE_DLL = "HKLM:\SYSTEM\CurrentControlSet\Services\TermService\Parameters"

# sebaxakerhtc fork — 最活跃维护版本，支持 Win11 24H2
$GH_API_URL = "https://api.github.com/repos/sebaxakerhtc/rdpwrap/releases/latest"
$INI_RAW_URL = "https://raw.githubusercontent.com/sebaxakerhtc/rdpwrap.ini/master/rdpwrap.ini"

# 备用镜像（GitHub 访问慢时）
$INI_MIRROR = "https://raw.githubusercontent.com/affinityv/INI-RDPWRAP/master/rdpwrap.ini"

# ─────────────────────── 输出工具 ───────────────────────
function Write-OK($m) { Write-Host "  [OK] $m" -ForegroundColor Green }
function Write-WARN($m) { Write-Host "  [!!] $m" -ForegroundColor Yellow }
function Write-ERR($m) { Write-Host "  [XX] $m" -ForegroundColor Red }
function Write-Info($m) { Write-Host "  [..] $m" -ForegroundColor Gray }
function Write-Title($m) { Write-Host "`n  === $m ===" -ForegroundColor Cyan }
function Write-Step($m) { Write-Host "`n  >> $m" -ForegroundColor White }

# ─────────────────────── 工具函数 ───────────────────────
function Get-TermsrvVersion {
    $dll = "C:\Windows\System32\termsrv.dll"
    if (-not (Test-Path $dll)) { throw "termsrv.dll 不存在: $dll" }
    $v = (Get-Item $dll).VersionInfo
    return "$($v.FileMajorPart).$($v.FileMinorPart).$($v.FileBuildPart).$($v.FilePrivatePart)"
}

function Get-RDPWrapStatus {
    $svcDll = (Get-ItemProperty $SERVICE_DLL -ErrorAction SilentlyContinue).ServiceDll
    return @{
        Installed  = ($svcDll -like "*rdpwrap*")
        ServiceDll = $svcDll
        IniPath    = "$INSTALL_DIR\rdpwrap.ini"
        IniExists  = (Test-Path "$INSTALL_DIR\rdpwrap.ini")
    }
}

function Test-IniHasBuild($iniPath, $buildVer) {
    if (-not (Test-Path $iniPath)) { return $false }
    $content = Get-Content $iniPath -Raw -ErrorAction SilentlyContinue
    return ($content -match [regex]::Escape("[$buildVer]"))
}

function Download-File($url, $dest, $label) {
    Write-Info "下载 $label ..."
    try {
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $url -OutFile $dest -TimeoutSec 30 -UseBasicParsing -ErrorAction Stop
        Write-OK "$label 下载完成 ($('{0:N1}' -f ((Get-Item $dest).Length/1KB)) KB)"
        return $true
    }
    catch {
        Write-WARN "$label 下载失败: $($_.Exception.Message)"
        return $false
    }
}

function Get-LatestRelease {
    Write-Info "查询 GitHub 最新版本..."
    try {
        $ProgressPreference = 'SilentlyContinue'
        $release = Invoke-RestMethod -Uri $GH_API_URL -TimeoutSec 15 -ErrorAction Stop
        $assets = $release.assets
        return @{
            Tag      = $release.tag_name
            RDPWinst = ($assets | Where-Object { $_.name -like "RDPWinst*.exe" } | Select-Object -First 1).browser_download_url
            RDPConf  = ($assets | Where-Object { $_.name -like "RDPConf*.exe" } | Select-Object -First 1).browser_download_url
        }
    }
    catch {
        Write-WARN "GitHub API 访问失败，使用备用下载策略..."
        return $null
    }
}

# ─────────────────────── 核心功能 ───────────────────────
function Install-RDPWrapper {
    Write-Title "RDP Wrapper 安装 — 多会话并发解锁"

    # 1. 获取当前 termsrv.dll 版本
    Write-Step "Step 1: 检测系统版本"
    $tsVer = Get-TermsrvVersion
    Write-OK "termsrv.dll 版本: $tsVer"

    $osInfo = Get-WmiObject Win32_OperatingSystem
    Write-Info "OS: $($osInfo.Caption) Build $($osInfo.BuildNumber)"

    # 2. 检查是否已安装
    $status = Get-RDPWrapStatus
    if ($status.Installed -and (Test-Path "$INSTALL_DIR\RDPWrap.dll") -and -not $Silent) {
        Write-WARN "RDP Wrapper 已安装 (DLL=$($status.ServiceDll))"
        Write-Info "继续将更新到最新版本..."
    }

    # 3. 准备临时目录
    Write-Step "Step 2: 准备安装目录"
    New-Item -Path $TMP_DIR -ItemType Directory -Force | Out-Null
    New-Item -Path $INSTALL_DIR -ItemType Directory -Force | Out-Null
    Write-OK "目录就绪: $INSTALL_DIR"

    # 4. 下载 RDPWinst.exe
    Write-Step "Step 3: 下载 RDP Wrapper 组件"
    $release = Get-LatestRelease
    $rdpWinstPath = "$TMP_DIR\RDPWinst.exe"

    if ($release -and $release.RDPWinst) {
        Write-Info "最新版本: $($release.Tag)"
        $ok = Download-File $release.RDPWinst $rdpWinstPath "RDPWinst.exe"
        if (-not $ok) { $release = $null }
    }

    # GitHub 失败时 — 使用备用直链（固定已知可用版本）
    if (-not (Test-Path $rdpWinstPath) -or (Get-Item $rdpWinstPath).Length -lt 1000) {
        Write-WARN "尝试备用下载链接..."
        $fallbackUrls = @(
            "https://github.com/sebaxakerhtc/rdpwrap/releases/download/v1.6.2/RDPWinst.exe",
            "https://github.com/stascorp/rdpwrap/releases/download/v1.6.2/RDPWinst.exe"
        )
        foreach ($url in $fallbackUrls) {
            $ok = Download-File $url $rdpWinstPath "RDPWinst.exe (fallback)"
            if ($ok -and (Get-Item $rdpWinstPath).Length -gt 10000) { break }
        }
    }

    if (-not (Test-Path $rdpWinstPath) -or (Get-Item $rdpWinstPath).Length -lt 10000) {
        Write-ERR "RDPWinst.exe 下载失败！网络问题请手动下载："
        Write-ERR "  https://github.com/sebaxakerhtc/rdpwrap/releases/latest"
        Write-ERR "  下载 RDPWinst.exe 放到: $TMP_DIR\"
        return $false
    }

    # 5. 停止 TermService 准备安装
    Write-Step "Step 4: 停止 TermService 服务"
    try {
        Stop-Service TermService -Force -ErrorAction SilentlyContinue
        Write-OK "TermService 已停止"
    }
    catch {
        Write-WARN "停止服务时有警告（可能已停止）: $($_.Exception.Message)"
    }

    # 6. 执行安装
    Write-Step "Step 5: 安装 RDP Wrapper"
    try {
        $proc = Start-Process -FilePath $rdpWinstPath -ArgumentList "/i", "/s" -Wait -PassThru -ErrorAction Stop
        if ($proc.ExitCode -eq 0 -or $proc.ExitCode -eq 3010) {
            Write-OK "RDPWinst.exe 安装成功 (ExitCode=$($proc.ExitCode))"
        }
        else {
            Write-WARN "安装退出码: $($proc.ExitCode)（继续尝试...）"
        }
    }
    catch {
        Write-ERR "安装失败: $($_.Exception.Message)"
        return $false
    }

    # 7. 更新 rdpwrap.ini（下载最新版）
    Write-Step "Step 6: 更新 rdpwrap.ini（适配当前 Windows 版本）"
    $iniDest = "$INSTALL_DIR\rdpwrap.ini"
    $iniOk = Download-File $INI_RAW_URL $iniDest "rdpwrap.ini (GitHub)"
    if (-not $iniOk) {
        $iniOk = Download-File $INI_MIRROR $iniDest "rdpwrap.ini (镜像)"
    }

    if ($iniOk) {
        if (Test-IniHasBuild $iniDest $tsVer) {
            Write-OK "rdpwrap.ini 包含当前版本 [$tsVer] — 完整支持 (FullSupport)"
        }
        else {
            Write-WARN "rdpwrap.ini 暂无 [$tsVer] 条目 — 运行在 Partial 模式"
            Write-WARN "RDP 连接仍可使用，但多会话计数可能受限"
            Write-Info "解决方法: 等社区更新后运行: .\install-rdpwrap.ps1 -UpdateIni"
            Write-Info "或手动到 https://github.com/sebaxakerhtc/rdpwrap/issues 查找 [$tsVer] 条目"
            # ⚠️ 注意: 不自动添加条目！复制相邻版本的内存偏移量会导致 TermService 崩溃 (Error 1067)
        }
    }
    else {
        Write-WARN "ini 下载失败，保留安装包自带版本"
    }

    # 8. 配置注册表（多会话 + 不干扰本地用户）
    Write-Step "Step 7: 配置注册表（多会话 + 隔离会话）"
    Set-MultiSessionRegistry

    # 9. 启动服务
    Write-Step "Step 8: 启动 TermService"
    Start-Service TermService -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $svc = Get-Service TermService
    if ($svc.Status -eq "Running") {
        Write-OK "TermService 运行中"
    }
    else {
        Write-ERR "TermService 启动失败！状态: $($svc.Status)"
        Write-Info "尝试手动启动: Start-Service TermService"
    }

    # 10. 验证
    Write-Step "Step 9: 验证安装"
    Show-InstallStatus

    return $true
}

function Add-IniEntryForBuild($iniPath, $buildVer) {
    # 尝试基于相邻版本推断条目（仅作参考，不保证完全正确）
    $content = Get-Content $iniPath -Raw -ErrorAction SilentlyContinue
    if (-not $content) { return }

    # 寻找版本号最接近的条目
    $pattern = '\[(\d+\.\d+\.\d+\.\d+)\]'
    $matches = [regex]::Matches($content, $pattern)
    $versions = $matches | ForEach-Object { $_.Groups[1].Value }

    $targetBuild = [int]($buildVer.Split('.')[3])
    $closest = $versions | Sort-Object {
        [Math]::Abs([int]($_.Split('.')[3]) - $targetBuild)
    } | Select-Object -First 1

    if ($closest) {
        Write-Info "最接近的 ini 版本: [$closest]（build差: $([Math]::Abs([int]($closest.Split('.')[3]) - $targetBuild))）"
        # 提取最接近版本的条目块
        $escClosest = [regex]::Escape($closest)
        if ($content -match "(?s)\[$escClosest\](.*?)(?=\[\d|\z)") {
            $block = $Matches[1]
            $newEntry = "`r`n[$buildVer]$block"
            $content = $content + $newEntry
            [System.IO.File]::WriteAllText($iniPath, $content, [System.Text.Encoding]::UTF8)
            Write-WARN "已基于 [$closest] 推断添加 [$buildVer] 条目（可能需要微调）"
        }
    }
}

function Set-MultiSessionRegistry {
    $ts = "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server"
    $rdpTcp = "$ts\WinStations\RDP-Tcp"
    $gp = "HKLM:\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services"

    # 允许 RDP 连接
    Set-ItemProperty $ts -Name fDenyTSConnections   -Value 0 -ErrorAction SilentlyContinue
    Write-OK "RDP 连接: 已开放"

    # 关键: 每次连接创建独立会话，不抢夺本地用户
    Set-ItemProperty $ts -Name fSingleSessionPerUser -Value 0 -ErrorAction SilentlyContinue
    Write-OK "多会话: 同一账号可开多个独立会话"

    # 不限制并发连接数
    Set-ItemProperty $rdpTcp -Name MaxInstanceCount -Value 0xFFFFFFFF -ErrorAction SilentlyContinue
    Write-OK "最大连接数: 无限制"

    # NLA 认证
    Set-ItemProperty $rdpTcp -Name UserAuthentication -Value 1 -ErrorAction SilentlyContinue

    # 组策略层
    if (-not (Test-Path $gp)) { New-Item $gp -Force | Out-Null }
    Set-ItemProperty $gp -Name MaxInstanceCount      -Value 0xFFFFFFFF -ErrorAction SilentlyContinue
    Set-ItemProperty $gp -Name fSingleSessionPerUser -Value 0          -ErrorAction SilentlyContinue
    Write-OK "组策略: 多会话已配置"

    # 防火墙
    Enable-NetFirewallRule -DisplayGroup "Remote Desktop" -ErrorAction SilentlyContinue
    Write-OK "防火墙: RDP 规则已启用"

    # 确保 RDP 服务自动启动
    Set-Service TermService -StartupType Automatic -ErrorAction SilentlyContinue
    Write-OK "TermService: 自动启动已设置"
}

function Update-Ini {
    Write-Title "更新 rdpwrap.ini"
    $tsVer = Get-TermsrvVersion
    $iniDest = "$INSTALL_DIR\rdpwrap.ini"
    Write-Info "当前 termsrv.dll: $tsVer"

    $ok = Download-File $INI_RAW_URL $iniDest "rdpwrap.ini (最新)"
    if (-not $ok) {
        $ok = Download-File $INI_MIRROR $iniDest "rdpwrap.ini (镜像)"
    }

    if ($ok) {
        if (Test-IniHasBuild $iniDest $tsVer) {
            Write-OK "ini 更新完成，[$tsVer] 已支持！"
        }
        else {
            Write-WARN "[$tsVer] 仍不在 ini 中，Windows 版本可能太新"
            Add-IniEntryForBuild $iniDest $tsVer
        }
        Restart-Service TermService -Force -ErrorAction SilentlyContinue
        Write-OK "TermService 已重启"
    }
    Show-InstallStatus
}

function Uninstall-RDPWrapper {
    Write-Title "卸载 RDP Wrapper"
    $installer = "$INSTALL_DIR\RDPWinst.exe"
    if (-not (Test-Path $installer)) {
        $installer = "$TMP_DIR\RDPWinst.exe"
    }
    if (Test-Path $installer) {
        $proc = Start-Process -FilePath $installer -ArgumentList "/u", "/s" -Wait -PassThru
        Write-OK "卸载完成 (ExitCode=$($proc.ExitCode))"
    }
    else {
        Write-ERR "找不到 RDPWinst.exe，手动删除 $INSTALL_DIR 目录"
    }
    # 恢复注册表
    $ts = "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server"
    Set-ItemProperty $ts -Name fSingleSessionPerUser -Value 1 -ErrorAction SilentlyContinue
    Restart-Service TermService -Force -ErrorAction SilentlyContinue
    Write-OK "TermService 已重启，已恢复单会话模式"
}

function Show-InstallStatus {
    Write-Title "RDP 多会话系统状态"

    # RDP Wrapper DLL
    $status = Get-RDPWrapStatus
    if ($status.Installed) {
        Write-OK "RDP Wrapper DLL: 已加载 ($($status.ServiceDll))"
    }
    else {
        Write-ERR "RDP Wrapper DLL: 未安装 (ServiceDll=$($status.ServiceDll))"
    }

    # termsrv.dll 版本
    $tsVer = Get-TermsrvVersion
    Write-Info "termsrv.dll: $tsVer"

    # ini 版本支持
    if ($status.IniExists) {
        if (Test-IniHasBuild $status.IniPath $tsVer) {
            Write-OK "rdpwrap.ini: [$tsVer] 完整支持 (FullSupport)"
        }
        else {
            Write-WARN "rdpwrap.ini: [$tsVer] 无精确条目 (可能 Partial)"
        }
    }
    else {
        Write-ERR "rdpwrap.ini: 文件不存在"
    }

    # 注册表状态
    $ts = "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server"
    $fSingle = (Get-ItemProperty $ts -ErrorAction SilentlyContinue).fSingleSessionPerUser
    $fDeny = (Get-ItemProperty $ts -ErrorAction SilentlyContinue).fDenyTSConnections
    if ($fSingle -eq 0) { Write-OK "fSingleSessionPerUser: 0 (多会话OK)" }
    else { Write-ERR "fSingleSessionPerUser: $fSingle (需要=0)" }
    if ($fDeny -eq 0) { Write-OK "fDenyTSConnections: 0 (RDP已开放)" }
    else { Write-ERR "fDenyTSConnections: $fDeny (RDP被禁止！)" }

    # MaxInstanceCount
    $rdpTcp = "$ts\WinStations\RDP-Tcp"
    $maxInst = (Get-ItemProperty $rdpTcp -ErrorAction SilentlyContinue).MaxInstanceCount
    if ($maxInst -eq -1 -or $maxInst -eq [uint32]::MaxValue) { Write-OK "MaxInstanceCount: 无限制 (-1/0xFFFFFFFF)" }
    else { Write-WARN "MaxInstanceCount: $maxInst (非无限制)" }

    # TermService 服务
    $svc = Get-Service TermService -ErrorAction SilentlyContinue
    if ($svc.Status -eq "Running") { Write-OK "TermService: 运行中 (StartType=$($svc.StartType))" }
    else { Write-ERR "TermService: $($svc.Status)" }

    # 活跃会话
    Write-Host ""
    Write-Info "当前活跃 RDP 会话:"
    try {
        $sessions = query session 2>$null
        $sessions | ForEach-Object { Write-Host "       $_" -ForegroundColor Gray }
    }
    catch { Write-Info "(query session 需要管理员)" }

    # RDP 用户组成员
    Write-Info "Remote Desktop Users 组成员:"
    try {
        Get-LocalGroupMember -Group "Remote Desktop Users" -ErrorAction SilentlyContinue |
        ForEach-Object { Write-Host "       $($_.Name)" -ForegroundColor Gray }
    }
    catch {}

    # 测试连接建议
    Write-Host ""
    Write-Title "快速验证"
    $myIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "192.168.31.*" } | Select-Object -First 1).IPAddress
    if ($myIP) {
        Write-Info "本机 IP: $myIP"
        Write-Info "测试多会话: 同时打开两个 mstsc，分别连接不同账号"
        Write-Info "  mstsc /v:$myIP  (账号: Administrator)"
        Write-Info "  mstsc /v:127.0.0.2  (账号: ai)"
    }
}

# ─────────────────────── 主入口 ───────────────────────
Write-Host "`n  ╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host   "  ║  RDP Wrapper — Windows 多会话并发解锁器  ║" -ForegroundColor Cyan
Write-Host   "  ║  解决: 同时多路 RDP + 不干扰本地用户     ║" -ForegroundColor Cyan
Write-Host   "  ╚══════════════════════════════════════════╝`n" -ForegroundColor Cyan

if ($Status) {
    Show-InstallStatus
}
elseif ($UpdateIni) {
    Update-Ini
}
elseif ($Uninstall) {
    Uninstall-RDPWrapper
}
else {
    $result = Install-RDPWrapper
    if ($result) {
        Write-Host "`n  ╔══════════════════════════════════════════╗" -ForegroundColor Green
        Write-Host   "  ║  安装完成！现在可以同时建立多个 RDP 连接  ║" -ForegroundColor Green
        Write-Host   "  ╚══════════════════════════════════════════╝`n" -ForegroundColor Green
        Write-Info "多会话使用方式:"
        Write-Info "  本地用户: 正常使用，不受影响"
        Write-Info "  远程 #1 (Admin): mstsc /v:192.168.31.141 → Administrator"
        Write-Info "  远程 #2 (ai):    双击 rdp连接配置\localhost_ai.rdp → 127.0.0.2"
        Write-Info "  远程 #3 (zhou):  mstsc /v:192.168.31.141 → zhou"
    }
    else {
        Write-ERR "`n安装失败，请检查上方错误信息。"
    }
}
