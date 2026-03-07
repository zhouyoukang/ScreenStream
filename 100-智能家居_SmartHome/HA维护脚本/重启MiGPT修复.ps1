# MiGPT一键修复启动脚本
# 作者: Claude 3.7 Sonnet
# 创建日期: 2025-06-10

# 设置颜色和控制台
$host.UI.RawUI.BackgroundColor = "Black"
$host.UI.RawUI.ForegroundColor = "Green"
Clear-Host

# 设置脚本路径
$fixScriptPath = "D:/homeassistant/工具库/修复脚本/fix_migpt_reload.ps1"
$diagScriptPath = "D:/homeassistant/工具库/检测脚本/check_migpt_handler.ps1"

# 显示欢迎信息
Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host "                        MiGPT 一键修复工具" -ForegroundColor Yellow
Write-Host "=================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "此工具用于修复MiGPT集成中出现的'Invalid handler specified'错误和实体注册问题"
Write-Host ""
Write-Host "执行此脚本将会:" -ForegroundColor Yellow
Write-Host "  1. 运行诊断检查，找出问题原因"
Write-Host "  2. 清理令牌并重新验证"
Write-Host "  3. 确保Python脚本组件正确配置"
Write-Host "  4. 修复MiGPT实体注册问题"
Write-Host "  5. 尝试重新加载MiGPT集成"
Write-Host "  6. 必要时提示重启Home Assistant"
Write-Host ""

# 询问用户是否继续
$continue = Read-Host "是否继续? (Y/N)"
if ($continue -ne "Y" -and $continue -ne "y") {
    Write-Host "操作已取消，按任意键退出..." -ForegroundColor Red
    $null = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit
}

# 功能函数
function Invoke-Script {
    param (
        [string]$ScriptPath,
        [string]$Description
    )
    
    if (Test-Path $ScriptPath) {
        Write-Host "`n正在执行 $Description..." -ForegroundColor Cyan
        & $ScriptPath
        
        if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq $null) {
            Write-Host "$Description 执行完成" -ForegroundColor Green
            return $true
        } else {
            Write-Host "$Description 执行失败，错误代码: $LASTEXITCODE" -ForegroundColor Red
            return $false
        }
    } else {
        Write-Host "脚本文件不存在: $ScriptPath" -ForegroundColor Red
        return $false
    }
}

# 主流程
try {
    # 先运行诊断脚本
    Write-Host "`n[1/2] 运行MiGPT诊断..." -ForegroundColor Yellow
    $diagResult = Invoke-Script -ScriptPath $diagScriptPath -Description "MiGPT诊断脚本"
    
    # 运行修复脚本
    Write-Host "`n[2/2] 运行MiGPT修复..." -ForegroundColor Yellow
    $fixResult = Invoke-Script -ScriptPath $fixScriptPath -Description "MiGPT修复脚本"
    
    # 完成
    if ($diagResult -and $fixResult) {
        Write-Host "`n修复过程已完成！" -ForegroundColor Green
    } else {
        Write-Host "`n修复过程有部分步骤失败，可能需要手动检查问题。" -ForegroundColor Yellow
    }
    
    Write-Host "`n建议:" -ForegroundColor Cyan
    Write-Host "  - 检查日志文件了解详细信息"
    Write-Host "  - 如果修复后仍有问题，可能需要重启Home Assistant"
    Write-Host "  - 重启后，请检查MiGPT实体是否显示"
    
} catch {
    Write-Host "修复过程中发生错误: $_" -ForegroundColor Red
}

# 结束
Write-Host "`n按任意键退出..." -ForegroundColor Cyan
$null = $host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown") 