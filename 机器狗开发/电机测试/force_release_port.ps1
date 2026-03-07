# PowerShell脚本：强制释放COM端口

# 以管理员身份运行检查
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Warning: This script needs admin rights to work fully." -ForegroundColor Yellow
    Write-Host "Some operations may not work." -ForegroundColor Yellow
}

# 设置要释放的端口
$port = "COM5"
if ($args.Length -gt 0) {
    $port = $args[0]
}

Write-Host "Trying to release port $port..." -ForegroundColor Cyan

# 1. 尝试使用设备管理器命令禁用并重新启用端口
try {
    Write-Host "Method 1: Using PnP commands to disable and re-enable port..." -ForegroundColor Yellow
    $deviceInstance = Get-PnpDevice | Where-Object { $_.FriendlyName -like "*$port*" } | Select-Object -ExpandProperty InstanceId
    
    if ($deviceInstance) {
        Write-Host "Device found: $deviceInstance"
        Disable-PnpDevice -InstanceId $deviceInstance -Confirm:$false
        Start-Sleep -Seconds 2
        Enable-PnpDevice -InstanceId $deviceInstance -Confirm:$false
        Write-Host "Device disabled and re-enabled" -ForegroundColor Green
    } else {
        Write-Host "No device matching $port found" -ForegroundColor Red
    }
} catch {
    Write-Host "Method 1 failed: $($_.Exception.Message)" -ForegroundColor Red
}

# 2. 尝试使用.NET关闭任何打开的端口
try {
    Write-Host "Method 2: Trying to terminate serial port connections using .NET..." -ForegroundColor Yellow
    [System.IO.Ports.SerialPort]::GetPortNames() | ForEach-Object {
        if ($_ -eq $port) {
            try {
                $serialPort = New-Object System.IO.Ports.SerialPort($port)
                if ($serialPort.IsOpen) {
                    $serialPort.Close()
                    Write-Host "Successfully closed port $port" -ForegroundColor Green
                } else {
                    Write-Host "Port $port is not open" -ForegroundColor Yellow
                }
            } catch {
                Write-Host "Cannot operate on port $port: $($_.Exception.Message)" -ForegroundColor Red
            }
        }
    }
} catch {
    Write-Host "Method 2 failed: $($_.Exception.Message)" -ForegroundColor Red
}

# 3. 尝试终止使用此COM端口的进程
try {
    Write-Host "Method 3: Trying to find and terminate processes using $port..." -ForegroundColor Yellow
    
    # 此命令需要管理员权限才能有效
    if ($isAdmin) {
        # 使用handle64.exe (如果有的话) 或其他工具
        Write-Host "This feature would need additional tools like handle64.exe to find processes" -ForegroundColor Yellow
        Write-Host "Please try to manually close applications that might use serial ports:" -ForegroundColor Yellow
        Write-Host " - Terminal programs" -ForegroundColor Yellow
        Write-Host " - Debug tools" -ForegroundColor Yellow
        Write-Host " - Serial port monitoring software" -ForegroundColor Yellow
    } else {
        Write-Host "Admin rights needed to find and terminate processes using COM ports" -ForegroundColor Red
    }
} catch {
    Write-Host "Method 3 failed: $($_.Exception.Message)" -ForegroundColor Red
}

# 4. 简单测试端口是否可用
try {
    Write-Host "Testing if port $port is now available..." -ForegroundColor Cyan
    $testPort = New-Object System.IO.Ports.SerialPort($port, 9600)
    $testPort.Open()
    Write-Host "Successfully opened port $port! Port is now available." -ForegroundColor Green
    $testPort.Close()
} catch {
    Write-Host "Port $port is still inaccessible: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Try these manual steps:" -ForegroundColor Yellow
    Write-Host "1. Open Device Manager" -ForegroundColor Yellow
    Write-Host "2. Expand 'Ports (COM & LPT)'" -ForegroundColor Yellow
    Write-Host "3. Right-click on the problem port and select 'Disable device'" -ForegroundColor Yellow
    Write-Host "4. Right-click again and select 'Enable device'" -ForegroundColor Yellow
    Write-Host "5. Or try unplugging and reconnecting the USB device" -ForegroundColor Yellow
}

Write-Host "Operation completed" -ForegroundColor Cyan 