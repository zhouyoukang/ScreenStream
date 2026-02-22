# git_cleanup.ps1 - 关闭IDE后在终端中运行
# 用途: 压缩.git目录中2.7GB的loose objects + 清理历史大文件
# 使用: 关闭Windsurf → 打开PowerShell → cd到项目根目录 → .\管理\00-归档\screen-capture-bridge\git_cleanup.ps1

$ErrorActionPreference = 'Stop'
$root = 'e:\github\AIOT\ScreenStream_v2'

Write-Host "`n=== Git Cleanup Script ===" -ForegroundColor Cyan
Write-Host "项目: $root"

# Phase 1: 清理gc残留的临时文件
Write-Host "`n[1/4] 清理pack临时文件..." -ForegroundColor Yellow
Get-ChildItem "$root\.git\objects\pack" -File | Where-Object { $_.Name -match '^(tmp_|\.tmp-)' } | ForEach-Object {
    Write-Host "  删除: $($_.Name) ($([math]::Round($_.Length/1MB,1)) MB)"
    Remove-Item $_.FullName -Force
}

# Phase 2: 显示清理前状态
Write-Host "`n[2/4] 清理前状态:" -ForegroundColor Yellow
git -C $root count-objects -v 2>&1

$beforeSize = [math]::Round((Get-ChildItem "$root\.git" -Recurse -File | Measure-Object Length -Sum).Sum/1MB,1)
Write-Host ".git size before: $beforeSize MB"

# Phase 3: git gc --aggressive
Write-Host "`n[3/4] 执行 git gc --aggressive (可能需要几分钟)..." -ForegroundColor Yellow
git -C $root gc --aggressive --prune=now 2>&1

# Phase 4: 显示清理后状态
Write-Host "`n[4/4] 清理后状态:" -ForegroundColor Yellow
git -C $root count-objects -v 2>&1

$afterSize = [math]::Round((Get-ChildItem "$root\.git" -Recurse -File | Measure-Object Length -Sum).Sum/1MB,1)
Write-Host ".git size after: $afterSize MB"
Write-Host "节省: $([math]::Round($beforeSize - $afterSize, 1)) MB" -ForegroundColor Green

Write-Host "`n=== 完成 ===" -ForegroundColor Cyan
