#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import struct
import serial
import time
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
    
    # 打印详细的数据包信息
    print(f"数据包详情:")
    print(f"  头部: {header}")
    print(f"  电机ID: {motor_id_hex}")
    print(f"  保留字段1: {reserved}")
    print(f"  力矩: {tau_hex}")
    print(f"  速度: {vel_hex}")
    print(f"  位置: {pos_hex}")
    print(f"  Kp: {kp_hex}")
    print(f"  保留字段2: {reserved2}")
    print(f"  Kd: {kd_hex}")
    print(f"  保留字段3: {reserved3}")
    print(f"  CRC: {crc}")
    print(f"  完整数据包: {packet + crc}")
    
    return packet + crc

def debug_motor(port, motor_id=4, baudrate=5000000, duration=5):
    """调试电机通信"""
    print(f"开始调试电机 ID {motor_id}，串口 {port}，波特率 {baudrate}...")
    
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
        
        print("正在发送电机控制命令...")
        print("按 Ctrl+C 可随时终止测试")
        
        # 测试循环
        command_count = 0
        response_count = 0
        
        while time.time() - start_time < duration:
            current_time = time.time() - start_time
            
            # 生成正弦波动作
            position = math.sin(current_time * 2) * 0.2  # 振幅
            velocity = math.cos(current_time * 2) * 0.4  # 速度
            
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
            command_count += 1
            
            # 尝试读取响应
            response = ser.read(100).hex()
            if response:
                print(f"\n收到响应 [{len(response)//2} 字节]: {response}")
                print(f"响应前缀: {response[:10]}")
                response_count += 1
            
            # 控制频率
            time.sleep(0.5)  # 降低频率以便观察
        
        print("\n测试完成")
        print(f"发送命令次数: {command_count}")
        print(f"收到响应次数: {response_count}")
        print(f"响应率: {response_count/command_count*100:.1f}%")
        
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试出错: {e}")
    finally:
        try:
            # 发送停止命令
            stop_packet = build_motor_packet(motor_id=motor_id, q=0, dq=0, kp=0, kd=0, tau=0)
            ser.write(bytes.fromhex(stop_packet))
            print("已发送停止命令")
            
            # 关闭串口
            ser.close()
            print(f"串口 {port} 已关闭")
        except:
            pass

if __name__ == "__main__":
    # 默认参数
    port = "COM5"
    motor_id = 4
    baudrate = 5000000
    duration = 5
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        port = sys.argv[1]
    
    if len(sys.argv) > 2:
        try:
            motor_id = int(sys.argv[2])
            if not (0 <= motor_id <= 12):
                print(f"警告: 电机ID应在0-12范围内，当前为 {motor_id}")
        except ValueError:
            print(f"警告: 无效的电机ID '{sys.argv[2]}'，使用默认值 {motor_id}")
    
    if len(sys.argv) > 3:
        try:
            baudrate = int(sys.argv[3])
        except ValueError:
            print(f"警告: 无效的波特率 '{sys.argv[3]}'，使用默认值 {baudrate}")
    
    if len(sys.argv) > 4:
        try:
            duration = int(sys.argv[4])
        except ValueError:
            print(f"警告: 无效的测试时长 '{sys.argv[4]}'，使用默认值 {duration} 秒")
    
    print("宇树Go1电机调试工具")
    print("=" * 40)
    print(f"串口: {port}")
    print(f"电机ID: {motor_id} (0-12)")
    print(f"波特率: {baudrate}")
    print(f"测试时长: {duration} 秒")
    print("=" * 40)
    
    # 确认启动
    confirm = input("按回车键开始调试，输入其他内容退出: ")
    if not confirm.strip():
        debug_motor(port, motor_id, baudrate, duration)
    else:
        print("调试已取消") 