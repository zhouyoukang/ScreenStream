<#
.SYNOPSIS
    Go1 以太网连接配置脚本 — 保持WiFi不断连
.DESCRIPTION
    配置PC以太网适配器连接Go1，同时保持WiFi(家庭网络)在线。
    Go1内部网络: 192.168.123.x (以太网直连)
    Go1 WiFi AP:  192.168.12.x  (WiFi连接)
    
    以太网连接后可访问Go1内部所有4台电脑:
    - Pi:    192.168.123.161 (主控/MQTT/SSH)
    - NanoA: 192.168.123.13  (头部摄像头)
    - NanoB: 192.168.123.14  (机身)
    - NX:    192.168.123.15  (推理计算)
.NOTES
    需要管理员权限运行
    用法: .\setup_ethernet.ps1 [-Connect] [-Disconnect] [-Status]
#>

param(
    [switch]$Connect,
    [switch]$Disconnect,
    [switch]$Status
)

$ErrorActionPreference = "Stop"
$EthName = "以太网"
$Go1IP_Eth = "192.168.123.162"
$Go1Subnet = "255.255.255.0"
$Go1Gateway = $null  # 不设网关，避免抢占默认路由
$Go1Targets = @(
    @{Name="Pi (主控)"; IP="192.168.123.161"},
    @{Name="NanoA (头部)"; IP="192.168.123.13"},
    @{Name="NanoB (机身)"; IP="192.168.123.14"},
    @{Name="NX (推理)"; IP="192.168.123.15"}
)

function Show-Status {
    Write-Host "`n=== 网络状态 ===" -ForegroundColor Cyan
    
    # WiFi状态
    $wifi = Get-NetAdapter -Name "WLAN" -ErrorAction SilentlyContinue
    if ($wifi -and $wifi.Status -eq "Up") {
        $wifiIP = (Get-NetIPAddress -InterfaceAlias "WLAN" -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress
        Write-Host "[OK] WiFi: $wifiIP (家庭网络在线)" -ForegroundColor Green
    } else {
        Write-Host "[!!] WiFi: 未连接" -ForegroundColor Red
    }
    
    # 以太网状态
    $eth = Get-NetAdapter -Name $EthName -ErrorAction SilentlyContinue
    if ($eth) {
        if ($eth.Status -eq "Up") {
            $ethIP = (Get-NetIPAddress -InterfaceAlias $EthName -AddressFamily IPv4 -ErrorAction SilentlyContinue).IPAddress
            Write-Host "[OK] 以太网: $ethIP (Go1连接)" -ForegroundColor Green
            
            # Ping Go1 Pi
            Write-Host "`n--- Go1设备探测 ---"
            foreach ($target in $Go1Targets) {
                $ping = Test-Connection -ComputerName $target.IP -Count 1 -Quiet -TimeoutSeconds 2
                if ($ping) {
                    Write-Host "  [OK] $($target.Name): $($target.IP)" -ForegroundColor Green
                } else {
                    Write-Host "  [--] $($target.Name): $($target.IP) 不可达" -ForegroundColor Yellow
                }
            }
        } else {
            Write-Host "[--] 以太网: 未连接 (请插入网线到Go1头部)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[!!] 以太网适配器未找到" -ForegroundColor Red
    }
    
    # 路由检查
    Write-Host "`n--- 默认路由 ---"
    $routes = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue
    foreach ($r in $routes) {
        $ifAlias = (Get-NetAdapter -InterfaceIndex $r.InterfaceIndex -ErrorAction SilentlyContinue).Name
        Write-Host "  $ifAlias -> $($r.NextHop) (Metric: $($r.RouteMetric))"
    }
}

function Connect-Go1 {
    Write-Host "`n=== 配置以太网连接Go1 ===" -ForegroundColor Cyan
    
    # 检查以太网适配器
    $eth = Get-NetAdapter -Name $EthName -ErrorAction SilentlyContinue
    if (-not $eth) {
        Write-Host "[ERROR] 找不到以太网适配器 '$EthName'" -ForegroundColor Red
        return
    }
    
    if ($eth.Status -ne "Up") {
        Write-Host "[WARN] 以太网未连接，请先将网线插入Go1头部网口" -ForegroundColor Yellow
        Write-Host "       然后重新运行此脚本" -ForegroundColor Yellow
        return
    }
    
    # 移除现有IP配置
    Write-Host "[1/4] 清除旧IP配置..."
    Get-NetIPAddress -InterfaceAlias $EthName -AddressFamily IPv4 -ErrorAction SilentlyContinue | Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
    
    # 设置静态IP
    Write-Host "[2/4] 设置IP: $Go1IP_Eth/24..."
    New-NetIPAddress -InterfaceAlias $EthName -IPAddress $Go1IP_Eth -PrefixLength 24 -ErrorAction Stop | Out-Null
    
    # 确保以太网Metric高于WiFi（避免抢占默认路由）
    Write-Host "[3/4] 设置路由优先级 (WiFi > 以太网)..."
    Set-NetIPInterface -InterfaceAlias $EthName -InterfaceMetric 100 -ErrorAction SilentlyContinue
    Set-NetIPInterface -InterfaceAlias "WLAN" -InterfaceMetric 10 -ErrorAction SilentlyContinue
    
    # 添加Go1子网路由
    Write-Host "[4/4] 添加Go1子网路由..."
    # 192.168.123.0/24 通过以太网
    New-NetRoute -DestinationPrefix "192.168.123.0/24" -InterfaceAlias $EthName -NextHop "0.0.0.0" -RouteMetric 1 -ErrorAction SilentlyContinue | Out-Null
    # 192.168.12.0/24 也通过以太网（Go1 Pi同时在这个子网）
    New-NetRoute -DestinationPrefix "192.168.12.0/24" -InterfaceAlias $EthName -NextHop "0.0.0.0" -RouteMetric 1 -ErrorAction SilentlyContinue | Out-Null
    
    Write-Host "`n[DONE] 以太网已配置" -ForegroundColor Green
    Write-Host "  PC IP: $Go1IP_Eth"
    Write-Host "  Go1 Pi: 192.168.123.161"
    Write-Host "  MQTT: 192.168.123.161:1883"
    Write-Host "  SSH: ssh pi@192.168.123.161"
    
    Show-Status
}

function Disconnect-Go1 {
    Write-Host "`n=== 断开Go1以太网连接 ===" -ForegroundColor Cyan
    
    # 移除IP配置
    Get-NetIPAddress -InterfaceAlias $EthName -AddressFamily IPv4 -ErrorAction SilentlyContinue | Remove-NetIPAddress -Confirm:$false -ErrorAction SilentlyContinue
    
    # 移除Go1路由
    Remove-NetRoute -DestinationPrefix "192.168.123.0/24" -InterfaceAlias $EthName -Confirm:$false -ErrorAction SilentlyContinue
    Remove-NetRoute -DestinationPrefix "192.168.12.0/24" -InterfaceAlias $EthName -Confirm:$false -ErrorAction SilentlyContinue
    
    # 恢复DHCP
    Set-NetIPInterface -InterfaceAlias $EthName -Dhcp Enabled -ErrorAction SilentlyContinue
    
    Write-Host "[DONE] 以太网已恢复为DHCP模式" -ForegroundColor Green
}

# 主逻辑
if ($Connect) {
    Connect-Go1
} elseif ($Disconnect) {
    Disconnect-Go1
} elseif ($Status) {
    Show-Status
} else {
    Write-Host "Go1 以太网配置工具"
    Write-Host "用法:"
    Write-Host "  .\setup_ethernet.ps1 -Connect      # 配置以太网连接Go1"
    Write-Host "  .\setup_ethernet.ps1 -Disconnect   # 断开Go1恢复DHCP"
    Write-Host "  .\setup_ethernet.ps1 -Status       # 查看网络状态"
    Show-Status
}
