#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time

def test_com5():
    """测试COM5端口是否可以打开"""
    port = "COM5"
    print(f"尝试打开 {port} 端口...")
    
    try:
        # 尝试以不同波特率打开端口
        baudrates = [9600, 115200, 1000000, 5000000]
        
        for baudrate in baudrates:
            try:
                print(f"  尝试波特率 {baudrate}...")
                ser = serial.Serial(
                    port=port,
                    baudrate=baudrate,
                    timeout=1
                )
                print(f"  成功打开 {port} (波特率: {baudrate})")
                
                # 尝试写入一些数据
                test_data = b'\xFE\x04\x06\x03\x01\x00\x00\x80\x3F\x00\x00\x00\x00'
                ser.write(test_data)
                print(f"  成功写入测试数据")
                
                # 尝试读取响应
                response = ser.read(100)
                if response:
                    print(f"  收到响应: {response.hex()}")
                else:
                    print("  未收到响应")
                
                # 关闭端口
                ser.close()
                print(f"  成功关闭 {port}")
                
                return True
            except Exception as e:
                print(f"  错误: {e}")
    
    except Exception as e:
        print(f"测试失败: {e}")
    
    return False

if __name__ == "__main__":
    print("COM5端口简单测试工具")
    print("=" * 40)
    
    success = test_com5()
    
    if success:
        print("\nCOM5端口测试成功!")
    else:
        print("\nCOM5端口测试失败!")
        print("请尝试以下解决方法:")
        print("1. 重启计算机")
        print("2. 重新插拔USB-RS485适配器")
        print("3. 在设备管理器中禁用再启用COM5端口")
        print("4. 检查是否有其他程序正在使用COM5端口")
    
    input("\n按回车键退出...") 