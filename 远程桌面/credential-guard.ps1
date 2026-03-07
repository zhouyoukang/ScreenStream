<#
.SYNOPSIS
    凭据守护：secrets.env 双机同步 + 备份 + 变更检测 + 防散落扫描
.DESCRIPTION
    - Sync: 比较双机secrets.env哈希，newer覆盖older，同步前自动备份
    - Backup: 创建带时间戳的备份到 .windsurf/backups/credentials/
    - Scan: 扫描tracked文件中的凭据泄露
    - Status: 显示双机secrets.env状态对比
.EXAMPLE
    .\credential-guard.ps1              # 默认：Status + Sync
    .\credential-guard.ps1 -Backup      # 仅备份
    .\credential-guard.ps1 -Scan        # 扫描tracked文件泄露
    .\credential-guard.ps1 -Status      # 仅状态对比
#>
param(
    [switch]$Backup,
    [switch]$Scan,
    [switch]$Status,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# === 路径配置 ===
$isDesktop = $env:COMPUTERNAME -eq 'DESKTOP-MASTER'
if ($isDesktop) {
    $localFile = 'D:\道\道生一\一生二\secrets.env'
    $remoteFile = '\\192.168.31.179\E$\道\道生一\一生二\secrets.env'
    $projectRoot = 'D:\道\道生一\一生二'
} else {
    $localFile = 'E:\道\道生一\一生二\secrets.env'
    $remoteFile = 'W:\道\道生一\一生二\secrets.env'
    $projectRoot = 'E:\道\道生一\一生二'
}
$backupDir = Join-Path $projectRoot '.windsurf\backups\credentials'

# === 工具函数 ===
function Get-FileHash256($path) {
    if (Test-Path $path) { (Get-FileHash $path -Algorithm SHA256).Hash } else { $null }
}

function Get-KeyCount($path) {
    if (Test-Path $path) {
        (Get-Content $path | Where-Object { $_ -match '^\s*[^#]\s*\w+=.' } | Measure-Object).Count
    } else { 0 }
}

function Backup-SecretsEnv {
    if (-not (Test-Path $backupDir)) { New-Item -ItemType Directory -Path $backupDir -Force | Out-Null }
    $ts = Get-Date -Format 'yyyyMMdd_HHmmss'
    $dest = Join-Path $backupDir "secrets.env.$ts.bak"
    Copy-Item $localFile $dest -Force
    Write-Host "  备份: $dest" -ForegroundColor Green
    # 保留最近10个备份
    $old = Get-ChildItem $backupDir -Filter "secrets.env.*.bak" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 10
    $old | ForEach-Object { Remove-Item $_.FullName -Force; Write-Host "  清理旧备份: $($_.Name)" -ForegroundColor DarkGray }
}

# === Backup模式 ===
if ($Backup) {
    Write-Host "=== 凭据备份 ===" -ForegroundColor Cyan
    Backup-SecretsEnv
    exit 0
}

# === Scan模式：扫描tracked文件中的凭据泄露 ===
if ($Scan) {
    Write-Host "=== 凭据泄露扫描 ===" -ForegroundColor Cyan
    Push-Location $projectRoot
    # 从secrets.env提取实际敏感值（长度>8的非空值）
    $sensitiveValues = Get-Content $localFile | ForEach-Object {
        if ($_ -match '^\s*([^#=]+?)\s*=\s*(.{8,})$') {
            $key = $Matches[1].Trim()
            $val = $Matches[2].Trim()
            # 排除非敏感值（IP、端口、URL路径、区域代码等）
            if ($key -notmatch 'IP$|HOSTNAME$|PORT_|REGION$|SERVER$|_URL$|_ALIAS$|_USER$|_EMAIL$|EXPIRY$|_ID$|PROXY$|_PORT$|ENDPOINT$|DOMAIN$|PUBKEY|_PHONE$|_CONFIG$|_KEY$|_SUB_') {
                @{Key=$key; Pattern=$val}
            }
        }
    }
    $leaks = 0
    foreach ($sv in $sensitiveValues) {
        $hits = git grep -l ([regex]::Escape($sv.Pattern)) -- '*.md' '*.py' '*.ps1' '*.json' '*.toml' '*.kt' '*.xml' 2>$null
        if ($hits) {
            $leaks++
            Write-Host "  🔴 $($sv.Key) 泄露在: $($hits -join ', ')" -ForegroundColor Red
        }
    }
    if ($leaks -eq 0) { Write-Host "  ✅ 零泄露 — tracked文件中无明文凭据" -ForegroundColor Green }
    else { Write-Host "  ⚠️ 发现 $leaks 处泄露！请检查并替换为 [见secrets.env]" -ForegroundColor Yellow }
    Pop-Location
    exit 0
}

# === Status + Sync（默认） ===
Write-Host "=== 凭据守护 — secrets.env 双机状态 ===" -ForegroundColor Cyan

$localExists = Test-Path $localFile
$remoteExists = Test-Path $remoteFile -ErrorAction SilentlyContinue

if (-not $localExists) { Write-Host "  ❌ 本地 secrets.env 不存在: $localFile" -ForegroundColor Red; exit 1 }

$localHash = Get-FileHash256 $localFile
$localTime = (Get-Item $localFile).LastWriteTime
$localKeys = Get-KeyCount $localFile
$localSize = (Get-Item $localFile).Length

Write-Host "  本地: $localFile"
Write-Host "    大小: ${localSize}B | 键数: $localKeys | 修改: $($localTime.ToString('yyyy-MM-dd HH:mm:ss'))"

if ($remoteExists) {
    $remoteHash = Get-FileHash256 $remoteFile
    $remoteTime = (Get-Item $remoteFile).LastWriteTime
    $remoteKeys = Get-KeyCount $remoteFile
    $remoteSize = (Get-Item $remoteFile).Length

    Write-Host "  远程: $remoteFile"
    Write-Host "    大小: ${remoteSize}B | 键数: $remoteKeys | 修改: $($remoteTime.ToString('yyyy-MM-dd HH:mm:ss'))"

    if ($localHash -eq $remoteHash) {
        Write-Host "  ✅ 双机一致 (SHA256前8位: $($localHash.Substring(0,8)))" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️ 双机不一致!" -ForegroundColor Yellow
        if (-not $Status) {
            # 自动同步：newer覆盖older
            if ($localTime -gt $remoteTime) {
                Write-Host "  → 本地较新，同步到远程..." -ForegroundColor Yellow
                Backup-SecretsEnv
                Copy-Item $localFile $remoteFile -Force
                Write-Host "  ✅ 已同步到远程" -ForegroundColor Green
            } elseif ($remoteTime -gt $localTime) {
                Write-Host "  → 远程较新，拉取到本地..." -ForegroundColor Yellow
                Backup-SecretsEnv
                Copy-Item $remoteFile $localFile -Force
                Write-Host "  ✅ 已从远程拉取" -ForegroundColor Green
            } else {
                Write-Host "  → 修改时间相同但内容不同，需手动处理" -ForegroundColor Red
            }
        }
    }
} else {
    Write-Host "  ⚠️ 远程不可达: $remoteFile" -ForegroundColor Yellow
    Write-Host "  提示: 确保SMB共享可用或目标机器在线" -ForegroundColor DarkGray
}

# SECRETS_ENV_PATH 验证
$envPath = [Environment]::GetEnvironmentVariable("SECRETS_ENV_PATH", "User")
if ($envPath -and (Test-Path $envPath)) {
    Write-Host "  ✅ SECRETS_ENV_PATH: $envPath" -ForegroundColor Green
} elseif ($envPath) {
    Write-Host "  ⚠️ SECRETS_ENV_PATH设置但文件不存在: $envPath" -ForegroundColor Yellow
} else {
    Write-Host "  ❌ SECRETS_ENV_PATH 未设置!" -ForegroundColor Red
}
