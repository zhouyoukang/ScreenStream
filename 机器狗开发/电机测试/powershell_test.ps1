# PowerShell脚本用于测试与Go1电机通信
# 无需使用pyserial，直接使用.NET框架的串口类

Write-Host "PowerShell电机通信测试" -ForegroundColor Green
Write-Host "------------------" -ForegroundColor Green

# 列出当前系统中的所有串口
Write-Host "检测可用串口..." -ForegroundColor Cyan
$ports = [System.IO.Ports.SerialPort]::GetPortNames()
if ($ports.Count -eq 0) {
    Write-Host "未检测到串口设备" -ForegroundColor Red
    exit
}

Write-Host "检测到以下串口:"
foreach ($p in $ports) {
    Write-Host " - $p"
}

# 默认使用COM5
$portName = "COM5"
$baudRate = 5000000  # Go1标准波特率

# 询问用户是否要更改
$input = Read-Host "请输入要使用的COM端口 (默认 $portName)"
if ($input) {
    $portName = $input
}

# 创建串口对象
try {
    $port = New-Object System.IO.Ports.SerialPort
    $port.PortName = $portName
    $port.BaudRate = $baudRate
    $port.DataBits = 8
    $port.StopBits = [System.IO.Ports.StopBits]::One
    $port.Parity = [System.IO.Ports.Parity]::None
    $port.ReadTimeout = 1000  # 1秒超时
    $port.WriteTimeout = 1000
    
    Write-Host "尝试打开串口 $portName..." -ForegroundColor Cyan
    $port.Open()
    
    Write-Host "串口已成功打开!" -ForegroundColor Green
    
    # 电机ID (默认4)
    $motorID = 4
    $input = Read-Host "请输入电机ID (默认 $motorID)"
    if ($input) {
        $motorID = [int]$input
    }
    
    # 构建Go1电机命令
    $hexID = [Convert]::ToString($motorID, 16).PadLeft(2, '0')
    $cmd1 = "FEEE${hexID}BA0AFF00000000000000320000000FFFF10000A00020000000000"
    $cmd2 = "FEEE${hexID}BA0AFF00000000000000960000000FFFF10000A00020000000000"
    
    # 将命令转换为字节数组
    $bytesCmd1 = @()
    for ($i = 0; $i -lt $cmd1.Length; $i += 2) {
        $bytesCmd1 += [Convert]::ToByte($cmd1.Substring($i, 2), 16)
    }
    
    $bytesCmd2 = @()
    for ($i = 0; $i -lt $cmd2.Length; $i += 2) {
        $bytesCmd2 += [Convert]::ToByte($cmd2.Substring($i, 2), 16)
    }
    
    # 发送命令
    Write-Host "开始向电机ID $motorID 发送振荡命令..." -ForegroundColor Yellow
    
    for ($i = 1; $i -le 5; $i++) {
        Write-Host "振荡 $i/5"
        
        # 发送第一个位置命令
        $port.Write($bytesCmd1, 0, $bytesCmd1.Length)
        Write-Host "  发送命令1: $cmd1"
        Start-Sleep -Seconds 1
        
        # 尝试读取响应
        if ($port.BytesToRead -gt 0) {
            $responseBytes = New-Object byte[] $port.BytesToRead
            $port.Read($responseBytes, 0, $responseBytes.Length)
            $responseHex = [BitConverter]::ToString($responseBytes).Replace("-", "")
            Write-Host "  收到响应: $responseHex" -ForegroundColor Green
        } else {
            Write-Host "  无响应" -ForegroundColor Yellow
        }
        
        # 发送第二个位置命令
        $port.Write($bytesCmd2, 0, $bytesCmd2.Length)
        Write-Host "  发送命令2: $cmd2"
        Start-Sleep -Seconds 1
        
        # 尝试读取响应
        if ($port.BytesToRead -gt 0) {
            $responseBytes = New-Object byte[] $port.BytesToRead
            $port.Read($responseBytes, 0, $responseBytes.Length)
            $responseHex = [BitConverter]::ToString($responseBytes).Replace("-", "")
            Write-Host "  收到响应: $responseHex" -ForegroundColor Green
        } else {
            Write-Host "  无响应" -ForegroundColor Yellow
        }
    }
    
    # 关闭端口
    $port.Close()
    Write-Host "串口已关闭" -ForegroundColor Green
    
} catch {
    Write-Host "出错: $_" -ForegroundColor Red
    if ($port -and $port.IsOpen) {
        $port.Close()
    }
}

Write-Host "`n测试完成" -ForegroundColor Green
Write-Host "如果您看到电机有反应，表示通信成功" -ForegroundColor Cyan
Write-Host "如果没有反应，请检查:" -ForegroundColor Cyan
Write-Host "- 电源连接 (电机需要23-25V)" -ForegroundColor Cyan
Write-Host "- RS485连接 (A+/B- 接线正确)" -ForegroundColor Cyan
Write-Host "- 电机ID是否正确" -ForegroundColor Cyan 