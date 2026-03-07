# Home Assistant 脚本启动器
# 集成所有维护和工具脚本功能

$backupScriptPath = ".\HA备份\备份脚本.ps1"
$restartScriptPath = ".\HA备份\重启HA.ps1" 
$systemMaintenancePath = ".\HA备份\系统维护.ps1"

function Show-Menu {
    Clear-Host
    Write-Host "======== Home Assistant 脚本启动器 ========" -ForegroundColor Cyan
    Write-Host "1: 备份工具" -ForegroundColor Yellow
    Write-Host "2: 系统维护工具" -ForegroundColor Yellow
    Write-Host "3: 重启Home Assistant" -ForegroundColor Yellow
    Write-Host "0: 退出" -ForegroundColor Yellow
    Write-Host "============================================" -ForegroundColor Cyan
    
    $choice = Read-Host "请输入选择 (0-3)"
    
    switch ($choice) {
        "1" { 
            if (Test-Path $backupScriptPath) {
                & $backupScriptPath
            } else {
                Write-Host "❌ 找不到备份脚本文件: $backupScriptPath" -ForegroundColor Red
                Start-Sleep -Seconds 2
            }
        }
        "2" { 
            if (Test-Path $systemMaintenancePath) {
                & $systemMaintenancePath
            } else {
                Write-Host "❌ 找不到系统维护脚本文件: $systemMaintenancePath" -ForegroundColor Red
                Start-Sleep -Seconds 2
            }
        }
        "3" { 
            if (Test-Path $restartScriptPath) {
                & $restartScriptPath
            } else {
                Write-Host "❌ 找不到重启脚本文件: $restartScriptPath" -ForegroundColor Red
                Start-Sleep -Seconds 2
            }
        }
        "0" { return }
        default { 
            Write-Host "❌ 无效选择，请重新输入" -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
    
    # 如果不是退出选项，重新显示菜单
    if ($choice -ne "0") {
        Show-Menu
    }
}

# 运行菜单
Show-Menu 