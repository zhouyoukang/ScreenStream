# Remote Desktop Agent — 防火墙配置脚本
# 允许手机通过局域网访问远程桌面服务
# 需要以管理员权限运行

param(
    [int[]]$Ports = @(9903, 9904, 9905),
    [switch]$Remove
)

$RuleName = "RemoteDesktopAgent"

if ($Remove) {
    Write-Host "Removing firewall rules..." -ForegroundColor Yellow
    Get-NetFirewallRule -DisplayName "$RuleName*" -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    Write-Host "Done. All RemoteDesktopAgent rules removed." -ForegroundColor Green
    exit 0
}

Write-Host "=== Remote Desktop Agent Firewall Setup ===" -ForegroundColor Cyan
Write-Host "Ports: $($Ports -join ', ')" -ForegroundColor White

foreach ($port in $Ports) {
    $name = "${RuleName}_TCP_${port}"
    $existing = Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "  Port $port — already configured" -ForegroundColor Gray
    } else {
        New-NetFirewallRule -DisplayName $name -Direction Inbound -Protocol TCP -LocalPort $port -Action Allow -Profile Private | Out-Null
        Write-Host "  Port $port — rule created (Private network)" -ForegroundColor Green
    }
}

# Show current LAN IPs for phone connection
Write-Host "`n=== Connect from phone ===" -ForegroundColor Cyan
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback' -and $_.IPAddress -notmatch '^169\.' } | ForEach-Object {
    foreach ($port in $Ports) {
        Write-Host "  http://$($_.IPAddress):$port/" -ForegroundColor Yellow
    }
}
Write-Host "`nTip: Add to Home Screen on phone for fullscreen PWA mode" -ForegroundColor Gray
