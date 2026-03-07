#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time

def test_basic_com1():
    """测试COM1端口的基本打开和关闭功能"""
    port = "COM1"
    
    print(f"测试COM1端口的基本功能")
    print("=" * 40)
    
    # 尝试不同的波特率
    baudrates = [9600, 19200, 115200]  # COM1可能不支持太高的波特率
    
    for baudrate in baudrates:
        print(f"\n尝试波特率: {baudrate}")
        
        try:
            # 打开串口
            print(f"  尝试打开 {port}...")
            ser = serial.Serial(
                port=port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
                parity=serial.PARITY_NONE,
                timeout=0.5
            )
            
            print(f"  串口 {port} 打开成功!")
            print(f"  端口信息: {ser}")
            
            # 发送一个简单的字节
            try:
                print(f"  尝试发送一个字节...")
                ser.write(b'\x00')
                print(f"  发送成功")
            except Exception as e:
                print(f"  发送失败: {e}")
            
            # 关闭串口
            ser.close()
            print(f"  串口 {port} 已关闭")
            print(f"  波特率 {baudrate} 测试成功")
            
        except Exception as e:
            print(f"  错误: {e}")
            try:
                if 'ser' in locals() and ser.is_open:
                    ser.close()
                    print(f"  串口 {port} 已关闭")
            except:
                pass
            print(f"  波特率 {baudrate} 测试失败")
    
    print("\n所有波特率测试完成")

if __name__ == "__main__":
    test_basic_com1()
    print("\n测试完成!") 