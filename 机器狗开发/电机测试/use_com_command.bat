@echo off
echo Go1电机测试脚本 (批处理版)
echo ======================
echo.

echo 检查COM5端口是否存在...
mode COM5 > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 错误: COM5端口不存在或无法访问
    exit /b 1
)

echo COM5端口存在

echo 配置COM5端口参数...
echo 注意: 批处理脚本无法设置5M波特率，将使用最高支持的波特率115200
mode COM5 BAUD=115200 PARITY=N DATA=8 STOP=1 > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo 错误: 无法配置COM5端口
    exit /b 1
)

echo COM5端口配置完成
echo.
echo 接下来将尝试发送一些基本命令到电机ID 4
echo 观察电机是否有反应
echo.
echo 按任意键开始发送命令...
pause > nul

echo 正在发送命令...
echo 这可能需要一些时间，请耐心等待

:: 使用PowerShell更可靠地向COM端口发送二进制数据
powershell -Command "$port = new-Object System.IO.Ports.SerialPort COM5,115200,None,8,one; $port.Open(); $bytes = [byte[]](0xFE,0xEE,0x04,0xBA,0x0A,0xFF,0x00,0x00,0x00,0x00,0x00,0x50,0x00,0x00,0x00,0xFF,0xFF,0x10,0x00,0x0A,0x00,0x02,0x00,0x00,0x00,0x00,0x00,0xBC,0x59,0x4C,0x4E); $port.Write($bytes, 0, $bytes.Length); Start-Sleep -Seconds 1; $port.Close(); Write-Host 'Command sent successfully'"

echo.
echo 测试完成
echo.
echo 如果电机有任何移动或反应，表示通信成功
echo 如果没有反应，可能存在以下问题:
echo 1. 电机ID不是4
echo 2. 波特率不匹配 (批处理只能使用115200)
echo 3. 硬件连接问题
echo 4. 电机需要不同的命令格式
echo. 