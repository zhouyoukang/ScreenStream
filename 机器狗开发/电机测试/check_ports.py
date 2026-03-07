#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import serial.tools.list_ports
import time

def list_ports():
    """列出所有可用的串口"""
    print("检查可用的串口...")
    ports = list(serial.tools.list_ports.comports())
    
    if not ports:
        print("未检测到任何串口")
        return []
    
    print(f"检测到 {len(ports)} 个串口:")
    for i, port in enumerate(ports):
        print(f"{i+1}. {port.device}: {port.description}")
        print(f"   - 硬件ID: {port.hwid}")
        print(f"   - 制造商: {port.manufacturer if hasattr(port, 'manufacturer') else '未知'}")
        print(f"   - 接口: {port.interface if hasattr(port, 'interface') else '未知'}")
    
    return [p.device for p in ports]

def test_port(port_name, baudrates=[9600, 19200, 115200, 1000000, 5000000]):
    """测试指定端口在不同波特率下的可用性"""
    print(f"\n测试端口 {port_name}...")
    
    for baudrate in baudrates:
        print(f"  尝试波特率 {baudrate}...")
        try:
            # 尝试打开串口
            ser = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
                parity=serial.PARITY_NONE,
                timeout=0.5,
                write_timeout=0.5
            )
            
            print(f"  成功打开 {port_name} (波特率: {baudrate})")
            
            # 尝试写入一个字节
            try:
                ser.write(b'\x00')
                print("  成功写入数据")
            except Exception as e:
                print(f"  写入失败: {e}")
            
            # 关闭串口
            ser.close()
            print(f"  成功关闭 {port_name}")
            
        except Exception as e:
            print(f"  错误: {e}")
    
    print(f"端口 {port_name} 测试完成")

def main():
    """主函数"""
    print("串口检测和测试工具")
    print("=" * 40)
    
    # 列出所有串口
    ports = list_ports()
    
    if not ports:
        print("没有可用的串口，无法进行测试")
        return
    
    # 询问用户要测试哪个端口
    print("\n请选择要测试的端口:")
    for i, port in enumerate(ports):
        print(f"{i+1}. {port}")
    
    choice = input("请输入端口编号 (直接回车测试所有端口): ")
    
    if choice.strip() and choice.isdigit() and 1 <= int(choice) <= len(ports):
        # 测试选定的端口
        test_port(ports[int(choice) - 1])
    else:
        # 测试所有端口
        print("\n将测试所有可用端口...")
        for port in ports:
            test_port(port)
    
    print("\n测试完成!")

if __name__ == "__main__":
    main() 