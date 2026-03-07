#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import struct
import serial
import time
import math
import os
import binascii

# 添加gooddawg库路径
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "宇树go1电机/gooddawg"))
try:
    import build_a_packet as bp
except ImportError:
    print("错误: 无法导入build_a_packet模块，请确保路径正确")
    sys.exit(1)

# 全局电机数据
motor_data = {
    "mot0_angle": None,
    "mot1_angle": None,
    "mot2_angle": None,
    "mot0_velocity": 0.0,
    "mot1_velocity": 0.0,
    "mot2_velocity": 0.0,
}

def configure_serial(port):
    """配置串口"""
    try:
        ser = serial.Serial(
            port=port,
            baudrate=5000000,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=0.1,
            rtscts=False,
            dsrdtr=False
        )

        ser.reset_input_buffer()
        ser.reset_output_buffer()
        print(f"成功打开串口 {port}")
        return ser
    except Exception as e:
        print(f"打开串口 {port} 失败: {e}")
        return None

def test_position_control(ser, motor_id, duration=30):
    """位置控制测试 - 正弦波"""
    print(f"开始位置控制测试，电机ID: {motor_id}，持续时间: {duration}秒")
    start_time = time.time()
    
    while time.time() - start_time < duration:
        t = time.time() - start_time
        # 正弦波位置控制，振幅0.5弧度
        q = math.sin(t * 2) * 0.5
        
        try:
            # 发送控制命令
            packet = bp.build_a_packet(id=motor_id, q=q, dq=0.0, Kp=4, Kd=0.3, tau=0.0)
            bp.send_packet(ser, packet)
            
            # 读取电机数据
            bp.read_and_update_motor_data(ser)
            
            # 显示当前状态
            motor_key = f"mot{motor_id}_angle"
            vel_key = f"mot{motor_id}_velocity"
            angle = bp.motor_data.get(motor_key)
            velocity = bp.motor_data.get(vel_key, 0.0)
            
            print(f"\r时间: {t:.2f}s, 目标位置: {q:.4f}, 实际位置: {angle:.4f if angle is not None else 'N/A'}, 速度: {velocity:.4f}", end="")
            
            # 控制频率
            time.sleep(0.01)
            
        except Exception as e:
            print(f"\n错误: {e}")
            break
    
    print("\n位置控制测试完成")

def test_velocity_control(ser, motor_id, duration=30):
    """速度控制测试 - 正弦波"""
    print(f"开始速度控制测试，电机ID: {motor_id}，持续时间: {duration}秒")
    start_time = time.time()
    
    while time.time() - start_time < duration:
        t = time.time() - start_time
        # 正弦波速度控制，振幅1.0弧度/秒
        dq = math.sin(t * 1) * 1.0
        
        try:
            # 发送控制命令 (Kp=0 for velocity mode)
            packet = bp.build_a_packet(id=motor_id, q=0.0, dq=dq, Kp=0, Kd=0.3, tau=0.0)
            bp.send_packet(ser, packet)
            
            # 读取电机数据
            bp.read_and_update_motor_data(ser)
            
            # 显示当前状态
            motor_key = f"mot{motor_id}_angle"
            vel_key = f"mot{motor_id}_velocity"
            angle = bp.motor_data.get(motor_key)
            velocity = bp.motor_data.get(vel_key, 0.0)
            
            print(f"\r时间: {t:.2f}s, 目标速度: {dq:.4f}, 实际速度: {velocity:.4f}, 位置: {angle:.4f if angle is not None else 'N/A'}", end="")
            
            # 控制频率
            time.sleep(0.01)
            
        except Exception as e:
            print(f"\n错误: {e}")
            break
    
    print("\n速度控制测试完成")

def test_torque_control(ser, motor_id, duration=30):
    """力矩控制测试 - 正弦波"""
    print(f"开始力矩控制测试，电机ID: {motor_id}，持续时间: {duration}秒")
    start_time = time.time()
    
    while time.time() - start_time < duration:
        t = time.time() - start_time
        # 正弦波力矩控制，振幅0.3牛·米
        tau = math.sin(t * 1) * 0.3
        
        try:
            # 发送控制命令 (Kp=0, Kd=0 for torque mode)
            packet = bp.build_a_packet(id=motor_id, q=0.0, dq=0.0, Kp=0, Kd=0, tau=tau)
            bp.send_packet(ser, packet)
            
            # 读取电机数据
            bp.read_and_update_motor_data(ser)
            
            # 显示当前状态
            motor_key = f"mot{motor_id}_angle"
            vel_key = f"mot{motor_id}_velocity"
            angle = bp.motor_data.get(motor_key)
            velocity = bp.motor_data.get(vel_key, 0.0)
            
            print(f"\r时间: {t:.2f}s, 目标力矩: {tau:.4f}, 位置: {angle:.4f if angle is not None else 'N/A'}, 速度: {velocity:.4f}", end="")
            
            # 控制频率
            time.sleep(0.01)
            
        except Exception as e:
            print(f"\n错误: {e}")
            break
    
    print("\n力矩控制测试完成")

def test_all_motors(ser, duration=10):
    """测试所有电机"""
    print(f"开始测试所有电机，每个电机持续时间: {duration}秒")
    
    for motor_id in range(13):  # 电机ID 0-12
        print(f"\n测试电机ID: {motor_id}")
        
        # 测试位置控制
        test_position_control(ser, motor_id, duration)
        
        # 等待一小段时间
        time.sleep(1)
        
        # 测试速度控制
        test_velocity_control(ser, motor_id, duration)
        
        # 等待一小段时间
        time.sleep(1)
        
        # 测试力矩控制
        test_torque_control(ser, motor_id, duration)
        
        print(f"电机ID {motor_id} 测试完成")
        
        # 询问是否继续测试下一个电机
        if motor_id < 12:
            response = input("按回车键测试下一个电机，输入'q'退出: ")
            if response.lower() == 'q':
                break

def main():
    """主函数"""
    print("宇树Go1电机测试工具 (使用gooddawg库)")
    print("=" * 50)
    
    # 默认参数
    port = "COM5"
    motor_id = 4  # 默认电机ID
    
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
    
    print(f"串口: {port}")
    print(f"电机ID: {motor_id}")
    print("=" * 50)
    
    # 打开串口
    ser = configure_serial(port)
    if not ser:
        print("串口打开失败，请检查连接或手动插拔USB-RS485适配器")
        return
    
    try:
        # 显示菜单
        print("\n请选择测试模式:")
        print("1. 位置控制测试")
        print("2. 速度控制测试")
        print("3. 力矩控制测试")
        print("4. 测试所有控制模式")
        print("5. 测试所有电机")
        print("0. 退出")
        
        choice = input("请输入选项(0-5): ")
        
        if choice == "1":
            test_position_control(ser, motor_id)
        elif choice == "2":
            test_velocity_control(ser, motor_id)
        elif choice == "3":
            test_torque_control(ser, motor_id)
        elif choice == "4":
            print("\n开始测试所有控制模式")
            test_position_control(ser, motor_id, 10)
            time.sleep(1)
            test_velocity_control(ser, motor_id, 10)
            time.sleep(1)
            test_torque_control(ser, motor_id, 10)
        elif choice == "5":
            test_all_motors(ser)
        else:
            print("退出测试")
    
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    finally:
        # 关闭串口
        if ser:
            ser.close()
            print(f"串口 {port} 已关闭")

if __name__ == "__main__":
    main() 