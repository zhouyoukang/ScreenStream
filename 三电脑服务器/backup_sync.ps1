# ═══════════════════════════════════════════════════════════
# 三电脑服务器 · 备份同步策略执行器
# 老子·上善若水 — 备份如水自动流向安全处
# 释迦·中道 — 不过度冗余也不脆弱
#
# 用法:
#   .\backup_sync.ps1                  # 全量备份+同步
#   .\backup_sync.ps1 -GitOnly         # 仅Git提交+推送
#   .\backup_sync.ps1 -SecretsOnly     # 仅凭据备份
#   .\backup_sync.ps1 -CrossDisk       # 跨盘关键数据同步
#   .\backup_sync.ps1 -Check           # 仅检查不操作
# ═══════════════════════════════════════════════════════════

param(
    [switch]$GitOnly,
    [switch]$SecretsOnly,
    [switch]$CrossDisk,
    [switch]$Check,
    [switch]$Force
)

$ROOT = "D:\道\道生一\一生二"
$BACKUP_DIR = Join-Path $ROOT "三电脑服务器\_backups"
$CROSS_DISK_TARGET = "E:\道\道生一\一生二\_critical_backup"
$TS = Get-Date -Format "yyyyMMdd_HHmmss"

# ── 颜色输出 ──
function Write-OK($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  [!]  $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "  [!!] $msg" -ForegroundColor Red }
function Write-Info($msg) { Write-Host "  [i]  $msg" -ForegroundColor Cyan }
function Write-Section($msg) { Write-Host "`n$msg" -ForegroundColor White }

# ══════════════════════════════════════════════════════════
# ☰乾 · Git备份 — 提交+推送
# ══════════════════════════════════════════════════════════

function Invoke-GitBackup {
    Write-Section "☰乾 · Git备份"

    Set-Location $ROOT

    # Check dirty files
    $dirty = (git status --porcelain 2>$null | Measure-Object).Count
    if ($dirty -eq 0) {
        Write-OK "工作区干净，无需提交"
    } else {
        Write-Info "发现 $dirty 个变更文件"
        if ($Check) {
            Write-Info "检查模式: 跳过提交"
        } else {
            git add -A 2>$null
            $msg = "backup: data guardian auto-backup $TS ($dirty files)"
            git commit -m $msg --quiet 2>$null
            Write-OK "已提交: $msg"
        }
    }

    # Check unpushed
    $ahead = 0
    try {
        $ahead = [int](git rev-list --count "origin/main..HEAD" 2>$null)
    } catch {}

    if ($ahead -eq 0) {
        Write-OK "已完全同步到GitHub"
        return
    }

    Write-Warn "$ahead 个commit未推送到GitHub"

    if ($Check) {
        Write-Info "检查模式: 跳过推送"
        return
    }

    Write-Info "正在推送到GitHub..."
    $pushResult = git push origin main 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-OK "推送成功！$ahead 个commit已安全同步到GitHub"
    } else {
        Write-Err "推送失败: $pushResult"
        Write-Info "可能需要: 1) 检查Clash代理 2) git pull --rebase 3) 手动解决冲突"

        # Try with proxy
        Write-Info "尝试通过Clash代理推送..."
        $env:HTTPS_PROXY = "http://127.0.0.1:7890"
        $pushResult2 = git push origin main 2>&1
        $env:HTTPS_PROXY = ""
        if ($LASTEXITCODE -eq 0) {
            Write-OK "通过代理推送成功！"
        } else {
            Write-Err "代理推送也失败。请手动检查网络和GitHub连接。"
        }
    }
}

# ══════════════════════════════════════════════════════════
# ☳震 · 凭据备份 — 加密存储
# ══════════════════════════════════════════════════════════

function Invoke-SecretsBackup {
    Write-Section "☳震 · 凭据备份"

    $secretsPath = Join-Path $ROOT "secrets.env"
    if (-not (Test-Path $secretsPath)) {
        Write-Err "secrets.env不存在！"
        return
    }

    # Create backup dir
    if (-not (Test-Path $BACKUP_DIR)) {
        New-Item -Path $BACKUP_DIR -ItemType Directory -Force | Out-Null
    }

    if ($Check) {
        $existing = Get-ChildItem $BACKUP_DIR -Filter "secrets_*.env" -ErrorAction SilentlyContinue
        Write-Info "当前备份数: $($existing.Count)"
        return
    }

    # Copy with timestamp
    $dest = Join-Path $BACKUP_DIR "secrets_$TS.env"
    Copy-Item $secretsPath $dest -Force
    Write-OK "secrets.env已备份到: $dest"

    # Also maintain a latest copy
    Copy-Item $secretsPath (Join-Path $BACKUP_DIR "secrets.env.backup") -Force

    # Backup 凭据中心.md
    $credCenter = Join-Path $ROOT "凭据中心.md"
    if (Test-Path $credCenter) {
        Copy-Item $credCenter (Join-Path $BACKUP_DIR "凭据中心_$TS.md") -Force
        Write-OK "凭据中心.md已备份"
    }

    # Cleanup old secrets backups (keep 20)
    $oldBackups = Get-ChildItem $BACKUP_DIR -Filter "secrets_*.env" | Sort-Object LastWriteTime -Descending | Select-Object -Skip 20
    foreach ($old in $oldBackups) {
        Remove-Item $old.FullName -Force
        Write-Info "清理旧备份: $($old.Name)"
    }
}

# ══════════════════════════════════════════════════════════
# ☲离 · 关键文件备份
# ══════════════════════════════════════════════════════════

function Invoke-CriticalFilesBackup {
    Write-Section "☲离 · 关键文件备份"

    if ($Check) {
        Write-Info "检查模式: 跳过文件备份"
        return
    }

    # Delegate to data_guardian.py --backup
    $guardianPath = Join-Path $ROOT "三电脑服务器\data_guardian.py"
    if (Test-Path $guardianPath) {
        python $guardianPath --backup
    } else {
        Write-Err "data_guardian.py不存在"
    }
}

# ══════════════════════════════════════════════════════════
# ☴巽 · 跨盘同步 — D→E关键数据
# ══════════════════════════════════════════════════════════

function Invoke-CrossDiskSync {
    Write-Section "☴巽 · 跨盘同步 (D→E)"

    $criticalDirs = @(
        "三电脑服务器",
        ".windsurf\rules",
        ".windsurf\skills",
        "密码管理",
        "手机操控库",
        "05-文档_docs"
    )

    if (-not (Test-Path "E:\")) {
        Write-Err "E:盘不可访问"
        return
    }

    if ($Check) {
        foreach ($dir in $criticalDirs) {
            $src = Join-Path $ROOT $dir
            $dst = Join-Path $CROSS_DISK_TARGET $dir
            $srcExists = Test-Path $src
            $dstExists = Test-Path $dst
            Write-Info "$dir : 源=$srcExists 目标=$dstExists"
        }
        return
    }

    # Create target root
    if (-not (Test-Path $CROSS_DISK_TARGET)) {
        New-Item -Path $CROSS_DISK_TARGET -ItemType Directory -Force | Out-Null
    }

    foreach ($dir in $criticalDirs) {
        $src = Join-Path $ROOT $dir
        if (-not (Test-Path $src)) { continue }
        $dst = Join-Path $CROSS_DISK_TARGET $dir

        # Use robocopy for efficient incremental sync
        $robocopyArgs = @($src, $dst, "/MIR", "/NFL", "/NDL", "/NJH", "/NJS", "/NP", "/XD", ".git", "__pycache__", "node_modules")
        $result = & robocopy @robocopyArgs 2>$null
        Write-OK "$dir → E盘同步完成"
    }

    # Also sync secrets.env and 凭据中心.md
    $secretsSrc = Join-Path $ROOT "secrets.env"
    if (Test-Path $secretsSrc) {
        Copy-Item $secretsSrc (Join-Path $CROSS_DISK_TARGET "secrets.env") -Force
        Write-OK "secrets.env → E盘同步"
    }

    # Timestamp file
    Set-Content (Join-Path $CROSS_DISK_TARGET "_sync_timestamp.txt") "Last sync: $TS from D:\道\道生一\一生二"
    Write-OK "跨盘同步完成 → $CROSS_DISK_TARGET"
}

# ══════════════════════════════════════════════════════════
# ☵坎 · 健康检查
# ══════════════════════════════════════════════════════════

function Invoke-HealthCheck {
    Write-Section "☵坎 · 数据守护者健康检查"
    $guardianPath = Join-Path $ROOT "三电脑服务器\data_guardian.py"
    if (Test-Path $guardianPath) {
        python $guardianPath
    } else {
        Write-Err "data_guardian.py不存在"
    }
}

# ══════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════

Write-Host "`n三电脑服务器 · 备份同步策略执行器" -ForegroundColor Cyan
Write-Host ("=" * 50)
Write-Host "时间: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
if ($Check) { Write-Host "模式: 检查(不修改)" -ForegroundColor Yellow }

if ($GitOnly) {
    Invoke-GitBackup
} elseif ($SecretsOnly) {
    Invoke-SecretsBackup
} elseif ($CrossDisk) {
    Invoke-CrossDiskSync
} elseif ($Check) {
    Invoke-HealthCheck
} else {
    # 全量备份: Git → 凭据 → 关键文件 → 跨盘
    Invoke-GitBackup
    Invoke-SecretsBackup
    Invoke-CriticalFilesBackup
    Invoke-CrossDiskSync
    Write-Section "═══ 全量备份完成 ═══"
}

Write-Host ""
