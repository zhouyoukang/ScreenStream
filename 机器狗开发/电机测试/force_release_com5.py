#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import subprocess
import ctypes

def is_admin():
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def force_release_com5():
    """尝试强制释放COM5端口"""
    port = "COM5"
    print(f"尝试强制释放 {port} 端口...")
    
    # 方法1: 使用serial模块尝试多次打开关闭
    try:
        import serial
        print(f"方法1: 尝试多次打开关闭端口...")
        
        # 尝试不同的波特率
        baudrates = [9600, 19200, 115200, 1000000, 5000000]
        
        for baudrate in baudrates:
            try:
                print(f"  尝试波特率 {baudrate}...")
                ser = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    bytesize=serial.EIGHTBITS,
                    stopbits=serial.STOPBITS_ONE,
                    parity=serial.PARITY_NONE,
                    timeout=0.1,
                    write_timeout=0.1,
                    exclusive=False  # 尝试非独占模式
                )
                print(f"  成功打开 {port}")
                time.sleep(0.5)
                ser.close()
                print(f"  成功关闭 {port}")
                time.sleep(0.5)
                
                # 再次尝试打开，确认端口已释放
                ser = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=0.1,
                    exclusive=True  # 尝试独占模式
                )
                print(f"  成功再次打开 {port}，端口已释放")
                ser.close()
                return True
            except Exception as e:
                print(f"  波特率 {baudrate} 失败: {e}")
    except ImportError:
        print("  未安装serial模块，跳过方法1")
    
    # 方法2: 使用Windows API强制关闭端口
    if is_admin():
        try:
            print(f"方法2: 使用Windows API强制关闭端口...")
            
            # 使用Windows设备管理器命令
            cmds = [
                f'powershell -Command "Get-PnpDevice | Where-Object {{$_.FriendlyName -like \"*{port}*\"}} | Disable-PnpDevice -Confirm:$false"',
                "timeout /t 2",
                f'powershell -Command "Get-PnpDevice | Where-Object {{$_.FriendlyName -like \"*{port}*\"}} | Enable-PnpDevice -Confirm:$false"',
            ]
            
            for cmd in cmds:
                print(f"  执行: {cmd}")
                subprocess.run(cmd, shell=True)
            
            print("  设备已禁用后重新启用")
        except Exception as e:
            print(f"  方法2失败: {e}")
    else:
        print("  方法2需要管理员权限，跳过")
    
    # 方法3: 查找并终止使用该端口的进程
    try:
        print(f"方法3: 查找并终止使用该端口的进程...")
        
        # 使用PowerShell查找使用该端口的进程
        cmd = f'powershell -Command "$port = New-Object System.IO.Ports.SerialPort \'{port}\'; try {{ $port.Open(); $port.Close(); Write-Host \'Port is free\' }} catch {{ Get-Process | ForEach-Object {{ if ($_.Modules.FileName -like \'*serial*\') {{ $_.ProcessName, $_.Id }} }} }}"'
        
        print(f"  执行: {cmd}")
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        print(f"  结果: {result.stdout}")
        
        if "Port is free" not in result.stdout and result.stdout.strip():
            print("  发现可能占用端口的进程，尝试终止...")
            
            # 提取进程ID
            lines = result.stdout.strip().split('\n')
            for i in range(0, len(lines), 2):
                if i+1 < len(lines):
                    process_name = lines[i].strip()
                    try:
                        process_id = int(lines[i+1].strip())
                        print(f"  尝试终止进程: {process_name} (ID: {process_id})")
                        
                        # 终止进程
                        if is_admin():
                            subprocess.run(f"taskkill /F /PID {process_id}", shell=True)
                        else:
                            print("  需要管理员权限终止进程")
                    except:
                        pass
    except Exception as e:
        print(f"  方法3失败: {e}")
    
    # 方法4: 使用设备管理器命令行工具
    print(f"方法4: 使用设备管理器命令行工具...")
    print("  请手动运行以下命令(需要管理员权限):")
    print("  1. 打开设备管理器")
    print("  2. 找到COM5端口")
    print("  3. 右键点击COM5端口，选择'禁用设备'")
    print("  4. 等待几秒钟")
    print("  5. 右键点击COM5端口，选择'启用设备'")
    
    # 最后的建议
    print("\n如果以上方法都无效，请尝试:")
    print("1. 重启计算机")
    print("2. 重新插拔USB-RS485适配器")
    print("3. 尝试使用不同的USB端口")
    print("4. 检查设备驱动是否正确安装")
    
    return False

if __name__ == "__main__":
    print("COM5端口强制释放工具")
    print("=" * 40)
    
    if is_admin():
        print("正在以管理员权限运行")
    else:
        print("警告: 未以管理员权限运行，某些功能可能受限")
        print("建议: 以管理员权限重新运行此脚本")
    
    success = force_release_com5()
    
    if success:
        print("\nCOM5端口已成功释放!")
    else:
        print("\nCOM5端口释放尝试完成，请检查端口状态")
    
    input("\n按回车键退出...") 