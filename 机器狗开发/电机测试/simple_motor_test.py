#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import time
import struct
import serial
import math
import binascii
from datetime import datetime

# 宇树Go1电机通信协议
# 包格式: [SOF, ID, LEN, CMD, DATA..., CRC32]
# SOF: 0xFE
# ID: 电机ID (0-12)
# LEN: 数据长度 (不包括SOF, ID, LEN和CRC32)
# CMD: 命令码
# DATA: 数据
# CRC32: CRC32校验码 (包括SOF, ID, LEN, CMD, DATA)

# 命令码定义
CMD_READ = 0x01      # 读取电机参数
CMD_WRITE = 0x02     # 写入电机参数
CMD_CTRL = 0x03      # 控制电机

# 控制模式
MODE_POSITION = 0    # 位置控制模式
MODE_SPEED = 1       # 速度控制模式
MODE_TORQUE = 2      # 力矩控制模式

def calculate_crc32(data):
    """计算CRC32校验码"""
    return binascii.crc32(data) & 0xFFFFFFFF

def build_control_packet(motor_id, mode, value):
    """构建控制电机的数据包"""
    # 构建数据包
    sof = 0xFE
    cmd = CMD_CTRL
    
    # 控制数据: [模式(1字节), 值(4字节,float)]
    mode_bytes = struct.pack("<B", mode)
    value_bytes = struct.pack("<f", value)
    data = mode_bytes + value_bytes
    
    # 计算数据长度
    data_len = len(data) + 1  # +1是因为包括CMD
    
    # 构建包头
    header = struct.pack("<BBB", sof, motor_id, data_len)
    
    # 构建完整数据包(不包括CRC32)
    packet = header + struct.pack("<B", cmd) + data
    
    # 计算CRC32
    crc32 = calculate_crc32(packet)
    
    # 添加CRC32
    packet += struct.pack("<I", crc32)
    
    return packet

def test_motor(port_name, motor_id, baudrate=5000000, test_duration=10):
    """测试电机，使用正弦波进行控制"""
    try:
        # 打开串口
        print(f"尝试打开 {port_name}...")
        ser = serial.Serial(
            port=port_name,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=0.1
        )
        print(f"成功打开 {port_name}")
        
        # 测试不同的控制模式
        modes = [
            (MODE_POSITION, "位置控制模式"),
            (MODE_SPEED, "速度控制模式"),
            (MODE_TORQUE, "力矩控制模式")
        ]
        
        start_time = time.time()
        end_time = start_time + test_duration
        
        mode_idx = 0
        mode, mode_name = modes[mode_idx]
        
        print(f"开始测试电机ID {motor_id}，使用{mode_name}")
        
        # 使用正弦波控制电机
        while time.time() < end_time:
            # 计算正弦波值
            t = time.time() - start_time
            
            # 每3秒切换一次控制模式
            if int(t / 3) % len(modes) != mode_idx:
                mode_idx = int(t / 3) % len(modes)
                mode, mode_name = modes[mode_idx]
                print(f"切换到{mode_name}")
            
            # 根据不同模式设置适当的幅值
            if mode == MODE_POSITION:
                # 位置控制: ±1弧度
                value = math.sin(t * 2) * 1.0
            elif mode == MODE_SPEED:
                # 速度控制: ±2弧度/秒
                value = math.sin(t * 2) * 2.0
            else:
                # 力矩控制: ±0.5牛·米
                value = math.sin(t * 2) * 0.5
            
            # 构建并发送控制包
            packet = build_control_packet(motor_id, mode, value)
            ser.write(packet)
            
            # 尝试读取响应
            response = ser.read(100)
            if response:
                print(f"收到响应: {response.hex()}")
            
            # 打印当前状态
            print(f"\r{datetime.now().strftime('%H:%M:%S')} - {mode_name}: {value:.3f}", end="")
            
            # 控制频率
            time.sleep(0.02)  # 50Hz控制频率
        
        print("\n测试完成")
        ser.close()
        
    except Exception as e:
        print(f"错误: {e}")
        return False
    
    return True

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python simple_motor_test.py <串口名> <电机ID> [波特率] [测试时间(秒)]")
        print("例如: python simple_motor_test.py COM5 4 5000000 10")
        sys.exit(1)
    
    port_name = sys.argv[1]
    motor_id = int(sys.argv[2])
    
    baudrate = 5000000
    if len(sys.argv) > 3:
        baudrate = int(sys.argv[3])
    
    test_duration = 10
    if len(sys.argv) > 4:
        test_duration = int(sys.argv[4])
    
    print(f"使用{port_name}端口测试电机ID {motor_id}")
    print(f"波特率: {baudrate}")
    print(f"测试时间: {test_duration}秒")
    
    test_motor(port_name, motor_id, baudrate, test_duration) 