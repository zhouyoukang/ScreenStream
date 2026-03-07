#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import struct
import serial
import time
import math
import sys
import os

# CRC计算相关常量和函数
POLY = 0x04C11DB7

def crc32_core(data_words):
    """计算CRC32校验和"""
    crc = 0xFFFFFFFF
    for word in data_words:
        crc ^= word
        for _ in range(32):
            if crc & 0x80000000:
                crc = (crc << 1) ^ POLY
            else:
                crc <<= 1
            crc &= 0xFFFFFFFF
    return crc

def get_go1_crc(hex_string):
    """计算Go1电机通信协议的CRC校验"""
    data_bytes = bytes.fromhex(hex_string)
    data_words = struct.unpack('<7I', data_bytes[:28])
    crc = crc32_core(data_words)
    crc_bytes = struct.pack('<I', crc)
    return crc_bytes.hex()

def build_motor_packet(motor_id, q=0.0, dq=0.0, kp=4, kd=0.3, tau=0.0):
    """构建电机控制数据包"""
    # 基本包头
    header = "feee"
    motor_id_hex = '{:02x}'.format(motor_id)
    reserved = "ba0aff000000000000"
    
    # 力矩转换
    tau_value = int(tau*100000)
    if tau_value >= 0:
        tau_hex = '{:02x}'.format(tau_value // 256 & 0xFF) + "00"
    else:
        tau_hex = '{:02x}'.format((tau_value + 65281) // 256 & 0xFF) + "ff"
    
    # 速度转换
    vel_value = int(dq*65000) & 0xFFFF
    vel_hex = f"{(vel_value & 0xFF):02x}{((vel_value >> 8) & 0xFF):02x}"
    
    # 位置转换
    pos_value = int((q)*65000+65536) & 0xFFFF
    pos_sign = "ffff" if q < 0 else "0000"
    pos_hex = f"{(pos_value & 0xFF):02x}{((pos_value >> 8) & 0xFF):02x}{pos_sign}"
    
    # Kp转换
    kp_hex = '{:02x}'.format(int(kp))
    reserved2 = "00"
    
    # Kd转换
    kd_value = int(kd * 2553)
    kd_hex = f"{(kd_value & 0xFF):02x}{((kd_value >> 8) & 0xFF):02x}"
    
    # 保留字段
    reserved3 = "020000000000"
    
    # 组合数据包并添加CRC校验
    packet = header + motor_id_hex + reserved + tau_hex + vel_hex + pos_hex + kp_hex + reserved2 + kd_hex + reserved3
    crc = get_go1_crc(packet)
    
    return packet + crc

def test_motor(port, motor_id, baudrate=5000000, duration=2):
    """测试单个电机"""
    print(f"\n开始测试电机 ID {motor_id}，串口 {port}，波特率 {baudrate}...")
    
    try:
        # 打开串口
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=0.1,
            rtscts=False,
            dsrdtr=False
        )
        
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        print(f"串口 {port} 打开成功")
        
        # 设置测试开始时间
        start_time = time.time()
        
        print(f"正在发送电机控制命令到电机 ID {motor_id}...")
        
        # 测试循环
        while time.time() - start_time < duration:
            current_time = time.time() - start_time
            
            # 生成正弦波动作
            position = math.sin(current_time * 3) * 0.2  # 振幅
            velocity = math.cos(current_time * 3) * 0.4  # 速度
            
            # 构建并发送电机控制命令
            packet = build_motor_packet(
                motor_id=motor_id,
                q=position,
                dq=velocity,
                kp=4,      # 位置增益
                kd=0.3,    # 速度增益
                tau=0.0    # 不加额外力矩
            )
            
            # 发送数据
            ser.write(bytes.fromhex(packet))
            
            # 尝试读取响应
            response = ser.read(100).hex()
            if response:
                print(f"收到响应: {response[:30]}...")
                return True  # 电机有响应
            
            # 控制频率
            time.sleep(0.01)
        
        print(f"电机 ID {motor_id} 测试完成，无响应")
        return False  # 电机无响应
        
    except Exception as e:
        print(f"测试出错: {e}")
        return False
    finally:
        try:
            # 发送停止命令
            stop_packet = build_motor_packet(motor_id=motor_id, q=0, dq=0, kp=0, kd=0, tau=0)
            ser.write(bytes.fromhex(stop_packet))
            
            # 关闭串口
            ser.close()
            print(f"串口 {port} 已关闭")
        except:
            pass

def test_all_motors(port, baudrate=5000000, duration=2):
    """测试所有电机ID"""
    print("宇树Go1电机批量测试工具")
    print("=" * 40)
    print(f"串口: {port}")
    print(f"波特率: {baudrate}")
    print(f"每个ID测试时长: {duration} 秒")
    print("=" * 40)
    
    # 记录有响应的电机ID
    responsive_motors = []
    
    # 测试所有电机ID (0-12)
    for motor_id in range(13):
        has_response = test_motor(port, motor_id, baudrate, duration)
        if has_response:
            responsive_motors.append(motor_id)
    
    # 显示测试结果
    print("\n测试结果汇总:")
    print("=" * 40)
    
    if responsive_motors:
        print(f"有响应的电机ID: {responsive_motors}")
    else:
        print("所有电机ID均无响应")
    
    print("=" * 40)
    print("测试完成")

if __name__ == "__main__":
    # 默认参数
    port = "COM5"
    baudrate = 5000000
    duration = 2
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        port = sys.argv[1]
    
    if len(sys.argv) > 2:
        try:
            baudrate = int(sys.argv[2])
        except ValueError:
            print(f"警告: 无效的波特率 '{sys.argv[2]}'，使用默认值 {baudrate}")
    
    if len(sys.argv) > 3:
        try:
            duration = int(sys.argv[3])
        except ValueError:
            print(f"警告: 无效的测试时长 '{sys.argv[3]}'，使用默认值 {duration} 秒")
    
    # 确认启动
    confirm = input("按回车键开始测试所有电机ID (0-12)，输入其他内容退出: ")
    if not confirm.strip():
        test_all_motors(port, baudrate, duration)
    else:
        print("测试已取消") 