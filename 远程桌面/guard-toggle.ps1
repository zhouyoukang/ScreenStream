<# Guard Toggle — 一键切换 MouseGuard 状态
   双击运行或右键 "用 PowerShell 运行"
   也可以创建桌面快捷方式指向此脚本
#>
$ports = @(9903, 9904)

foreach ($port in $ports) {
    try {
        $g = Invoke-RestMethod -Uri "http://localhost:$port/guard" -TimeoutSec 2
        if ($g.paused) {
            Invoke-RestMethod -Uri "http://localhost:$port/guard/resume" -Method POST | Out-Null
            Write-Host "Port $port : Guard RESUMED (protecting user)" -ForegroundColor Green
        } else {
            Invoke-RestMethod -Uri "http://localhost:$port/guard/pause" -Method POST | Out-Null
            Write-Host "Port $port : Guard PAUSED (automation allowed)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "Port $port : offline" -ForegroundColor DarkGray
    }
}

Start-Sleep -Seconds 2
