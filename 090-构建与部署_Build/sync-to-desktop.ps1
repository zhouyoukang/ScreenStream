<#
.SYNOPSIS
    双机 Windsurf 双向同步（笔记本 ↔ 台式机）
.DESCRIPTION
    同步项目代码(git) + Windsurf配置(.windsurf/ + MCP + global_rules)
    台式机: 192.168.31.141, SMB X:(C盘) W:(D盘)
    笔记本: E:\道\道生一\一生二 | 台式机: D:\道\道生一\一生二
.EXAMPLE
    .\sync-to-desktop.ps1             # 笔记本 → 台式机
    .\sync-to-desktop.ps1 -Reverse    # 台式机 → 笔记本
    .\sync-to-desktop.ps1 -ConfigOnly # 仅同步配置
    .\sync-to-desktop.ps1 -Status     # 双机状态对比
#>
param(
    [switch]$ConfigOnly,
    [switch]$Reverse,
    [switch]$Status
)

$ErrorActionPreference = 'Stop'
$localProject = 'E:\道\道生一\一生二'
$smbProject = 'W:\道\道生一\一生二'  # W: = Desktop D:
$smbCodeium = 'X:\Users\Administrator\.codeium\windsurf'  # X: = Desktop C:
$localCodeium = "$env:USERPROFILE\.codeium\windsurf"

# === Status模式：快速对比双机状态 ===
if ($Status) {
    Write-Host "========== 双机 Windsurf 状态对比 ==========" -ForegroundColor Cyan
    if (-not (Test-Path "W:\")) { Write-Host "SMB不通，无法对比" -ForegroundColor Red; exit 1 }

    $items = @(
        @{Name = 'Git分支'; L = { Push-Location $localProject; $r = git branch --show-current 2>$null; Pop-Location; $r }; R = { Push-Location $smbProject; $r = git branch --show-current 2>$null; Pop-Location; $r } },
        @{Name = 'Git提交'; L = { Push-Location $localProject; $r = git log -1 --format="%h %s" 2>$null; Pop-Location; $r }; R = { Push-Location $smbProject; $r = git log -1 --format="%h %s" 2>$null; Pop-Location; $r } },
        @{Name = '未提交变更'; L = { Push-Location $localProject; $r = (git status --porcelain 2>$null | Measure-Object).Count; Pop-Location; "${r}个" }; R = { Push-Location $smbProject; $r = (git status --porcelain 2>$null | Measure-Object).Count; Pop-Location; "${r}个" } },
        @{Name = 'Rules'; L = { (Get-ChildItem "$localProject\.windsurf\rules" -File -EA 0).Count }; R = { (Get-ChildItem "$smbProject\.windsurf\rules" -File -EA 0).Count } },
        @{Name = 'Skills'; L = { (Get-ChildItem "$localProject\.windsurf\skills" -Dir -EA 0).Count }; R = { (Get-ChildItem "$smbProject\.windsurf\skills" -Dir -EA 0).Count } },
        @{Name = 'Workflows'; L = { (Get-ChildItem "$localProject\.windsurf\workflows" -File -EA 0).Count }; R = { (Get-ChildItem "$smbProject\.windsurf\workflows" -File -EA 0).Count } },
        @{Name = 'MCP大小'; L = { (Get-Item "$localCodeium\mcp_config.json" -EA 0).Length }; R = { (Get-Item "$smbCodeium\mcp_config.json" -EA 0).Length } },
        @{Name = 'GlobalRules'; L = { (Get-Item "$localCodeium\memories\global_rules.md" -EA 0).Length }; R = { (Get-Item "$smbCodeium\memories\global_rules.md" -EA 0).Length } }
    )
    Write-Host ("{0,-15} {1,-35} {2,-35} {3}" -f '项目', '笔记本', '台式机', '一致') -ForegroundColor White
    Write-Host ("-" * 90)
    foreach ($i in $items) {
        $lv = & $i.L; $rv = & $i.R
        $match = if ("$lv" -eq "$rv") { '✅' }else { '❌' }
        Write-Host ("{0,-15} {1,-35} {2,-35} {3}" -f $i.Name, $lv, $rv, $match)
    }
    exit 0
}

# === Reverse模式：台式机 → 笔记本 ===
if ($Reverse) {
    $direction = "台式机 → 笔记本"
    # 反向：SMB→本地
    $srcProj = $smbProject; $dstProj = $localProject
    $srcCfg = $smbCodeium; $dstCfg = $localCodeium
    $mcpPathReplace = @{From = 'D:\\道\\道生一\\一生二'; To = 'E:\\道\\道生一\\一生二' }
}
else {
    $direction = "笔记本 → 台式机"
    $srcProj = $localProject; $dstProj = $smbProject
    $srcCfg = $localCodeium; $dstCfg = $smbCodeium
    $mcpPathReplace = @{From = 'E:\\道\\道生一\\一生二'; To = 'D:\\道\\道生一\\一生二' }
}

Write-Host "========== Windsurf 同步: $direction ==========" -ForegroundColor Cyan

# 1. 检查 SMB 连通性
Write-Host "`n[1/5] 检查SMB连通性..." -ForegroundColor Yellow
if (-not (Test-Path "X:\")) { Write-Host "  FAIL: X: (台式机C盘) 未映射" -ForegroundColor Red; exit 1 }
if (-not (Test-Path "W:\")) { Write-Host "  FAIL: W: (台式机D盘) 未映射" -ForegroundColor Red; exit 1 }
Write-Host "  OK: SMB通道畅通" -ForegroundColor Green

# 2. 同步代码（git push + pull）
if (-not $ConfigOnly) {
    Write-Host "`n[2/5] 同步项目代码..." -ForegroundColor Yellow
    Push-Location $srcProj
    try {
        $status = git status --porcelain
        if ($status) {
            Write-Host "  源端有未提交变更，先提交..."
            git add -A
            git commit -m "sync: auto-commit before sync ($direction)"
        }
        git push origin HEAD 2>&1 | ForEach-Object { Write-Host "  $_" }
        Push-Location $dstProj
        git pull origin HEAD 2>&1 | ForEach-Object { Write-Host "  $_" }
        Pop-Location
        Write-Host "  OK: 代码同步完成" -ForegroundColor Green
    }
    catch {
        Write-Host "  WARN: git同步失败 - $_" -ForegroundColor Yellow
        Write-Host "  回退方案: robocopy 直接同步..."
        robocopy $srcProj $dstProj /MIR /XD .git node_modules build .gradle __pycache__ android-sdk 00-归档 /XF *.apk *.jar *.mp4 /NFL /NDL /NJH /NJS /NC /NS 2>&1 | Out-Null
        Write-Host "  OK: robocopy 同步完成" -ForegroundColor Green
    }
    Pop-Location
}
else {
    Write-Host "`n[2/5] 跳过代码同步 (ConfigOnly模式)" -ForegroundColor Gray
}

# 3. 同步 .windsurf/ 项目配置
Write-Host "`n[3/5] 同步 .windsurf/ 配置..." -ForegroundColor Yellow
$windsurf_dirs = @('rules', 'skills', 'workflows', 'backups')
foreach ($d in $windsurf_dirs) {
    $src = "$srcProj\.windsurf\$d"
    $dst = "$dstProj\.windsurf\$d"
    if (Test-Path $src) {
        robocopy $src $dst /MIR /NFL /NDL /NJH /NJS /NC /NS 2>&1 | Out-Null
        Write-Host "  $d : synced"
    }
}
# 单文件同步
$singleFiles = @('hooks.json', 'github-mcp.cmd', 'code-index.md', 'quick-recipes.md')
foreach ($f in $singleFiles) {
    $src = "$srcProj\.windsurf\$f"
    if (Test-Path $src) {
        Copy-Item $src "$dstProj\.windsurf\$f" -Force
        Write-Host "  $f : synced"
    }
}
# .windsurfrules
Copy-Item "$srcProj\.windsurfrules" "$dstProj\.windsurfrules" -Force -ErrorAction SilentlyContinue
Write-Host "  OK: .windsurf/ 配置同步完成" -ForegroundColor Green

# 4. 同步 MCP 配置 + Global Rules
Write-Host "`n[4/5] 同步全局配置..." -ForegroundColor Yellow
# MCP config (需要路径适配)
$mcpSrc = Get-Content "$srcCfg\mcp_config.json" -Raw
$mcpDst = $mcpSrc -replace [regex]::Escape($mcpPathReplace.From), $mcpPathReplace.To
[System.IO.File]::WriteAllText("$dstCfg\mcp_config.json", $mcpDst, [System.Text.UTF8Encoding]::new($false))
Write-Host "  mcp_config.json : synced (paths adapted)"
# Global rules
Copy-Item "$srcCfg\memories\global_rules.md" "$dstCfg\memories\global_rules.md" -Force
Write-Host "  global_rules.md : synced"
Write-Host "  OK: 全局配置同步完成" -ForegroundColor Green

# 5. 验证
Write-Host "`n[5/5] 验证..." -ForegroundColor Yellow
$checks = @(
    @{Name = '项目目录'; Test = { Test-Path $dstProj } },
    @{Name = '.windsurf/'; Test = { Test-Path "$dstProj\.windsurf" } },
    @{Name = 'rules(6)'; Test = { (Get-ChildItem "$dstProj\.windsurf\rules" -File).Count -eq 6 } },
    @{Name = 'skills(13)'; Test = { (Get-ChildItem "$dstProj\.windsurf\skills" -Directory).Count -eq 13 } },
    @{Name = 'workflows(10)'; Test = { (Get-ChildItem "$dstProj\.windsurf\workflows" -File).Count -eq 10 } },
    @{Name = 'MCP配置'; Test = { Test-Path "$dstCfg\mcp_config.json" } },
    @{Name = 'Global Rules'; Test = { (Get-Item "$dstCfg\memories\global_rules.md").Length -gt 1000 } }
)
$pass = 0; $fail = 0
foreach ($c in $checks) {
    $ok = & $c.Test
    if ($ok) { Write-Host "  OK: $($c.Name)" -ForegroundColor Green; $pass++ }
    else { Write-Host "  FAIL: $($c.Name)" -ForegroundColor Red; $fail++ }
}

Write-Host "`n========== 同步完成: $pass/$($pass+$fail) 通过 ==========" -ForegroundColor $(if ($fail -eq 0) { 'Green' }else { 'Yellow' })
