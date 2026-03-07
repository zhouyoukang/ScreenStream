#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import serial
import time
import struct
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

def test_all_motor_ids(port="COM1", baudrate=115200):
    """测试所有电机ID (0-12)"""
    print(f"使用 {port} 端口测试所有电机ID (0-12)")
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
        
        # 测试每个电机ID
        for motor_id in range(13):  # 0-12
            print(f"\n测试电机ID {motor_id}...")
            
            # 构建简单的位置控制命令
            packet_hex = build_motor_packet(
                motor_id=motor_id,
                q=1.0,        # 位置设为1.0弧度
                dq=0.0,       # 速度设为0
                kp=4.0,       # 位置增益
                kd=0.3,       # 速度增益
                tau=0.0       # 力矩设为0
            )
            
            # 发送数据包
            packet_bytes = bytes.fromhex(packet_hex)
            print(f"发送命令: {packet_hex}")
            print(f"命令长度: {len(packet_bytes)} 字节")
            
            # 发送3次，增加成功机会
            for attempt in range(3):
                print(f"  尝试 {attempt+1}/3...")
                ser.write(packet_bytes)
                
                # 检查响应
                time.sleep(0.5)
                if ser.in_waiting > 0:
                    response = ser.read(ser.in_waiting)
                    print(f"  收到响应: {response.hex()}")
                else:
                    print("  无响应")
                
                time.sleep(0.5)
            
            # 等待2秒后测试下一个ID
            print(f"等待2秒...")
            time.sleep(2)
        
        # 关闭串口
        ser.close()
        print(f"\n串口 {port} 已关闭")
        print("所有电机ID测试完成")
        
    except Exception as e:
        print(f"错误: {e}")
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
                print(f"串口 {port} 已关闭")
        except:
            pass

if __name__ == "__main__":
    # 如果命令行提供了参数，使用指定的参数
    port = "COM1"
    baudrate = 115200
    
    if len(sys.argv) > 1:
        port = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            baudrate = int(sys.argv[2])
        except:
            pass
    
    test_all_motor_ids(port, baudrate)
    print("\n测试完成!") 