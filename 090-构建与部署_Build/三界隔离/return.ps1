# 三界隔离 — 返回天界
# 在地界(windsurf-test)会话中运行此脚本, 切回天界(zhouyoukang)
# Usage: .\return.ps1

$MainUser = 'zhouyoukang'

$raw = query session 2>$null
$mainLine = $raw | Where-Object { $_ -match $MainUser }

if ($mainLine -and $mainLine -match '\s+(\d+)\s+') {
    $mainId = $matches[1]
    Write-Host "  >> 切回天界 (Session $mainId)..." -ForegroundColor Green
    Write-Host "  >> 地界会断开但程序继续运行" -ForegroundColor DarkGray
    tscon $mainId /dest:console
} else {
    Write-Host "  >> 天界会话未找到, 请使用 Ctrl+Alt+Del 切换用户" -ForegroundColor Yellow
}
