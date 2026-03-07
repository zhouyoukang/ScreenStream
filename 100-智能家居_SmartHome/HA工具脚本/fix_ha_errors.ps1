# Home Assistant 错误修复主脚本
# 功能：集成所有错误检测和修复工具，提供交互式选择
# 作者：Claude
# 版本：1.0

# 设置日志
$logFile = "fix_ha_errors_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"
Start-Transcript -Path $logFile -Append

Write-Host "===== Home Assistant 错误修复工具 =====" -ForegroundColor Cyan
Write-Host "开始时间: $(Get-Date)" -ForegroundColor Yellow
Write-Host "日志文件: $logFile" -ForegroundColor Yellow
Write-Host ""

# 检查必要的脚本是否存在
$requiredScripts = @(
    "check_ha_errors.ps1", 
    "fix_lovelace_resources.ps1", 
    "check_and_fix_cards.ps1"
)

$missingScripts = $requiredScripts | Where-Object { -not (Test-Path $_) }
if ($missingScripts.Count -gt 0) {
    Write-Host "错误: 无法找到以下必需的脚本:" -ForegroundColor Red
    foreach ($script in $missingScripts) {
        Write-Host "  - $script" -ForegroundColor Red
    }
    Write-Host "请确保所有脚本都在当前目录中" -ForegroundColor Red
    Stop-Transcript
    exit 1
}

# 显示菜单
function Show-Menu {
    Write-Host "`n选择要执行的操作:" -ForegroundColor Green
    Write-Host "  1. 检测配置错误 (不修复)" -ForegroundColor Yellow
    Write-Host "  2. 修复资源引用问题" -ForegroundColor Yellow
    Write-Host "  3. 检查并修复卡片重复注册" -ForegroundColor Yellow
    Write-Host "  4. 全面检测和修复 (执行所有操作)" -ForegroundColor Yellow
    Write-Host "  5. 重启Home Assistant" -ForegroundColor Yellow
    Write-Host "  q. 退出" -ForegroundColor Yellow
    
    $choice = Read-Host "请输入选项 (1-5 或 q)"
    return $choice
}

# 执行检测配置错误
function Check-ConfigErrors {
    Write-Host "`n[步骤1] 检测配置错误..." -ForegroundColor Magenta
    & ./check_ha_errors.ps1
    
    Write-Host "`n配置检测完成. " -ForegroundColor Green
    Write-Host "查看上面的输出了解检测到的问题." -ForegroundColor Yellow
    Read-Host "按Enter继续..."
}

# 修复资源引用问题
function Fix-ResourceReferences {
    Write-Host "`n[步骤2] 修复资源引用问题..." -ForegroundColor Magenta
    & ./fix_lovelace_resources.ps1
    
    Write-Host "`n资源引用修复完成. " -ForegroundColor Green
    Write-Host "查看上面的输出了解修复的问题." -ForegroundColor Yellow
    Read-Host "按Enter继续..."
}

# 检查并修复卡片重复注册
function Fix-CardRegistrations {
    Write-Host "`n[步骤3] 检查并修复卡片重复注册..." -ForegroundColor Magenta
    & ./check_and_fix_cards.ps1
    
    Write-Host "`n卡片重复注册修复完成. " -ForegroundColor Green
    Write-Host "查看上面的输出了解修复的问题." -ForegroundColor Yellow
    Read-Host "按Enter继续..."
}

# 重启Home Assistant
function Restart-HomeAssistant {
    if (Test-Path "./restart_homeassistant.ps1") {
        Write-Host "`n[重启] 重启Home Assistant..." -ForegroundColor Magenta
        & ./restart_homeassistant.ps1
    } else {
        Write-Host "`n无法找到重启脚本 (restart_homeassistant.ps1)" -ForegroundColor Red
        Write-Host "请手动重启Home Assistant." -ForegroundColor Yellow
    }
    
    Read-Host "按Enter继续..."
}

# 主循环
$exit = $false

while (-not $exit) {
    $choice = Show-Menu
    
    switch ($choice) {
        "1" {
            Check-ConfigErrors
        }
        "2" {
            Fix-ResourceReferences
        }
        "3" {
            Fix-CardRegistrations
        }
        "4" {
            # 全面检测和修复
            Check-ConfigErrors
            Fix-ResourceReferences
            Fix-CardRegistrations
            
            Write-Host "`n所有操作已完成. 建议重启Home Assistant应用更改." -ForegroundColor Green
            $restartChoice = Read-Host "是否立即重启Home Assistant? (y/n)"
            if ($restartChoice -eq "y") {
                Restart-HomeAssistant
            }
        }
        "5" {
            Restart-HomeAssistant
        }
        "q" {
            $exit = $true
        }
        default {
            Write-Host "无效选项，请重试" -ForegroundColor Red
        }
    }
}

# 总结
Write-Host "`n===== Home Assistant 错误修复工具 - 执行完毕 =====" -ForegroundColor Cyan
Write-Host "结束时间: $(Get-Date)" -ForegroundColor Yellow
Write-Host "详细日志可以查看: $logFile" -ForegroundColor Yellow
Write-Host "感谢使用!" -ForegroundColor Green

Stop-Transcript 