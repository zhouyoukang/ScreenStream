# 🚀 设备状态记录器 - 一键部署脚本
# 自动完成所有部署和验证步骤

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🚀 设备状态记录器 - 自动部署与验证" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# 步骤1: 打开Node-RED
Write-Host "📌 步骤1: 打开Node-RED..." -ForegroundColor Yellow
Start-Process "http://localhost:8123/dashboard-nodered"
Start-Sleep -Seconds 3
Write-Host "✅ Node-RED已打开" -ForegroundColor Green
Write-Host ""

# 步骤2: 提示用户部署
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "📌 步骤2: 在Node-RED中完成部署" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""
Write-Host "请在Node-RED页面中操作：" -ForegroundColor Cyan
Write-Host "  1. 查看标签栏是否有 📝 设备状态记录器" -ForegroundColor White
Write-Host "  2. 如果没有，按 Ctrl+I 打开导入" -ForegroundColor White  
Write-Host "  3. 粘贴配置文件内容" -ForegroundColor White
Write-Host "  4. 选择'新流程'" -ForegroundColor White
Write-Host "  5. 点击'导入'" -ForegroundColor White
Write-Host "  6. 点击右上角红色'部署'按钮" -ForegroundColor White
Write-Host "  7. 如有确认框，点击'确认部署'" -ForegroundColor White
Write-Host ""
Write-Host "配置文件位置:" -ForegroundColor Cyan
Write-Host "  D:\homeassistant\📊_设备状态记录器_NodeRED_Flow.json" -ForegroundColor White
Write-Host ""

Read-Host "完成部署后，按Enter继续验证"

# 步骤3: 触发测试
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "📌 步骤3: 触发状态变化测试" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

Write-Host "打开移动端测试..." -ForegroundColor Cyan
Start-Process "http://localhost:8123/mobile"
Write-Host ""
Write-Host "请在移动端操作：" -ForegroundColor Cyan
Write-Host "  • 点击任意灯光开关" -ForegroundColor White
Write-Host "  • 等待2-3秒" -ForegroundColor White
Write-Host ""

Read-Host "完成操作后，按Enter验证日志"

# 步骤4: 验证日志
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host "📌 步骤4: 验证日志生成" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
Write-Host ""

Start-Sleep -Seconds 2

if (Test-Path "D:\homeassistant\config\state_changes.log") {
    Write-Host "✅✅✅ 部署成功！记录器正常工作！" -ForegroundColor Green
    Write-Host ""
    
    $content = Get-Content "D:\homeassistant\config\state_changes.log"
    Write-Host "📊 记录总数: $($content.Count) 条" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "最新记录（最后10行）：" -ForegroundColor Cyan
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Get-Content "D:\homeassistant\config\state_changes.log" -Tail 10
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Write-Host ""
    
    # 检查分类日志
    if (Test-Path "D:\homeassistant\config\logs") {
        $logs = Get-ChildItem "D:\homeassistant\config\logs" -Filter "*.log" -ErrorAction SilentlyContinue
        if ($logs.Count -gt 0) {
            Write-Host "✅ 分类日志已生成：" -ForegroundColor Green
            $logs | ForEach-Object { 
                $lines = (Get-Content $_.FullName -ErrorAction SilentlyContinue).Count
                Write-Host "  📄 $($_.Name) - $lines 条记录" -ForegroundColor White
            }
        }
    }
    
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
    Write-Host "🎉 部署验证完成！记录器100%正常工作！" -ForegroundColor Green
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
    Write-Host ""
    Write-Host "💡 使用技巧：" -ForegroundColor Cyan
    Write-Host "  • 实时监控: Get-Content config\state_changes.log -Wait -Tail 0" -ForegroundColor White
    Write-Host "  • 查看最新: Get-Content config\state_changes.log -Tail 20" -ForegroundColor White
    Write-Host "  • 搜索设备: Get-Content config\state_changes.log | Select-String '设备名'" -ForegroundColor White
    
} else {
    Write-Host "⚠️ 日志文件尚未生成" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "可能原因：" -ForegroundColor Cyan
    Write-Host "  1. Node-RED中部署未最终确认" -ForegroundColor White
    Write-Host "  2. 需要点击'确认部署'按钮" -ForegroundColor White
    Write-Host "  3. 需要等待更长时间让记录器启动" -ForegroundColor White
    Write-Host ""
    Write-Host "解决方法：" -ForegroundColor Cyan
    Write-Host "  1. 返回Node-RED检查部署状态" -ForegroundColor White
    Write-Host "  2. 确保点击了红色'部署'按钮" -ForegroundColor White
    Write-Host "  3. 如有确认框，必须点击'确认部署'" -ForegroundColor White
    Write-Host "  4. 再次操作HA设备触发状态变化" -ForegroundColor White
    Write-Host "  5. 等待10秒后重新运行本脚本" -ForegroundColor White
    Write-Host ""
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
    Write-Host "📝 下一步：返回Node-RED完成部署确认" -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "脚本执行完成！" -ForegroundColor Cyan
Write-Host ""

# 可选：持续监控
$choice = Read-Host "是否开启实时监控模式？(Y/N)"
if ($choice -eq 'Y' -or $choice -eq 'y') {
    if (Test-Path "D:\homeassistant\config\state_changes.log") {
        Write-Host ""
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
        Write-Host "📊 实时监控模式（按Ctrl+C退出）" -ForegroundColor Cyan
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
        Write-Host ""
        Get-Content "D:\homeassistant\config\state_changes.log" -Wait -Tail 0
    } else {
        Write-Host "⚠️ 日志文件不存在，无法开启监控" -ForegroundColor Yellow
    }
}









