#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
import struct
import math
import sys

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
    
    # 电机ID (1字节)
    id_hex = f"{motor_id:02x}"
    
    # 命令类型 (2字节) - 0xba0a 是控制命令
    cmd_type = "ba0a"
    
    # 保留字段 (1字节)
    reserved = "ff"
    
    # 位置 q (4字节浮点数)
    q_hex = struct.pack('<f', q).hex()
    
    # 速度 dq (4字节浮点数)
    dq_hex = struct.pack('<f', dq).hex()
    
    # 位置增益 Kp (4字节浮点数)
    kp_hex = struct.pack('<f', kp).hex()
    
    # 速度增益 Kd (4字节浮点数)
    kd_hex = struct.pack('<f', kd).hex()
    
    # 力矩 tau (4字节浮点数)
    tau_hex = struct.pack('<f', tau).hex()
    
    # 保留字段 (8字节)
    reserved2 = "0000000000000000"
    
    # 组合成完整的数据包 (不含CRC)
    packet_without_crc = header + id_hex + cmd_type + reserved + q_hex + dq_hex + kp_hex + kd_hex + tau_hex + reserved2
    
    # 计算CRC
    crc = get_go1_crc(packet_without_crc)
    
    # 返回完整数据包
    return packet_without_crc + crc

def test_motor_com1():
    """使用COM1端口测试电机ID 4"""
    port = "COM1"
    baudrate = 115200  # COM1最高支持的波特率
    motor_id = 4
    
    print(f"使用COM1端口测试电机ID {motor_id}")
    print(f"波特率: {baudrate}")
    print("=" * 40)
    
    try:
        # 打开串口
        print(f"尝试打开 {port}...")
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=0.5
        )
        
        print(f"串口 {port} 打开成功!")
        
        # 测试时长
        duration = 10  # 秒
        start_time = time.time()
        
        print(f"开始测试，持续 {duration} 秒...")
        
        # 生成正弦波命令
        while time.time() - start_time < duration:
            # 计算当前时间点的正弦值
            t = time.time() - start_time
            position = math.sin(t * 2.0) * 1.0  # 振幅为1.0弧度的正弦波
            velocity = math.cos(t * 2.0) * 2.0  # 对应的速度
            
            # 构建数据包
            packet_hex = build_motor_packet(
                motor_id=motor_id,
                q=position,
                dq=velocity,
                kp=4.0,
                kd=0.3,
                tau=0.0
            )
            
            # 发送数据包
            packet_bytes = bytes.fromhex(packet_hex)
            ser.write(packet_bytes)
            
            # 打印调试信息
            print(f"时间: {t:.2f}s, 位置: {position:.2f}, 速度: {velocity:.2f}")
            
            # 检查响应
            time.sleep(0.01)  # 短暂等待响应
            if ser.in_waiting > 0:
                response = ser.read(ser.in_waiting)
                print(f"收到响应: {response.hex()}")
            
            # 控制发送频率
            time.sleep(0.1)  # 每0.1秒发送一次命令
        
        # 关闭串口
        ser.close()
        print(f"\n串口 {port} 已关闭")
        print("测试完成")
        
    except Exception as e:
        print(f"错误: {e}")
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
                print(f"串口 {port} 已关闭")
        except:
            pass

if __name__ == "__main__":
    test_motor_com1()
    print("\n测试完成!") 