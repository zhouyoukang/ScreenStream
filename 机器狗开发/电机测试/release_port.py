#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import time
import subprocess

def release_port(port="COM5"):
    """尝试释放指定的COM端口"""
    print(f"尝试释放 {port} 端口...")
    
    # 方法1: 使用Python的serial模块
    try:
        import serial
        print(f"尝试方法1: 使用serial模块打开并立即关闭端口...")
        
        try:
            # 尝试以最低波特率打开端口
            ser = serial.Serial(port, 9600, timeout=0.1)
            print(f"  成功打开 {port}")
            ser.close()
            print(f"  成功关闭 {port}")
            return True
        except Exception as e:
            print(f"  方法1失败: {e}")
    except ImportError:
        print("  未安装serial模块，跳过方法1")
    
    # 方法2: 使用PowerShell命令
    print(f"尝试方法2: 使用PowerShell命令...")
    try:
        # 查找使用该端口的进程
        cmd = f'powershell -Command "Get-CimInstance Win32_SerialPort | Where-Object {{ $_.DeviceID -eq \'{port}\' }} | Select-Object Name, PNPDeviceID"'
        print(f"  执行命令: {cmd}")
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        print(f"  命令输出: {result.stdout}")
        
        if result.returncode == 0:
            print(f"  成功执行PowerShell命令")
        else:
            print(f"  PowerShell命令执行失败: {result.stderr}")
    except Exception as e:
        print(f"  方法2失败: {e}")
    
    # 方法3: 使用设备管理器禁用再启用
    print(f"尝试方法3: 使用devcon工具禁用再启用端口...")
    try:
        # 这需要管理员权限和devcon工具
        # 此处仅提供命令，实际执行需要管理员权限
        print(f"  请以管理员权限运行以下命令:")
        print(f"  devcon disable =ports\\{port}")
        print(f"  devcon enable =ports\\{port}")
    except Exception as e:
        print(f"  方法3失败: {e}")
    
    print("\n请尝试以下手动方法:")
    print("1. 关闭所有可能使用该端口的程序")
    print("2. 打开设备管理器，找到该端口，禁用后再启用")
    print("3. 重新插拔USB设备")
    print("4. 重启计算机")
    
    return False

if __name__ == "__main__":
    port = "COM5"  # 默认释放COM5
    
    # 如果提供了命令行参数，使用指定的端口
    if len(sys.argv) > 1:
        port = sys.argv[1]
    
    release_port(port) 