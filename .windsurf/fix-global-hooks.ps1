# Windsurf 全局 hooks.json 一键修复脚本
# 用途：清空全局 hooks，消除跨窗口终端卡死问题
# 运行方式：在 Windows 文件管理器中右键此文件 → "使用 PowerShell 运行"

$hooksPath = "$env:USERPROFILE\.codeium\windsurf\hooks.json"

if (Test-Path $hooksPath) {
    $backup = "$hooksPath.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
    Copy-Item $hooksPath $backup
    Write-Host "[OK] 已备份原文件到: $backup" -ForegroundColor Yellow
    
    '{"hooks": {}}' | Set-Content $hooksPath -Encoding UTF8
    Write-Host "[OK] 全局 hooks.json 已清空" -ForegroundColor Green
} else {
    '{"hooks": {}}' | Set-Content $hooksPath -Encoding UTF8
    Write-Host "[OK] 已创建空的全局 hooks.json" -ForegroundColor Green
}

Write-Host ""
Write-Host "修复完成！请重启所有 Windsurf 窗口使设置生效。" -ForegroundColor Cyan
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
