#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import struct
import serial
import time
import math
import build_a_packet as bp
import sys

if __name__ == "__main__":
    import platform
    # 根据平台选择默认端口
    port = "COM5" if platform.system() == "Windows" else "/dev/ttyUSB0"
    motor_id = 0
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        try:
            motor_id = int(sys.argv[1])
        except ValueError:
            print(f"警告: 无效的电机ID '{sys.argv[1]}'，使用默认值 {motor_id}")
    if len(sys.argv) > 2:
        port = sys.argv[2]
    
    print(f"宇树Go1电机测试 - 使用 {port} 端口")
    print(f"电机ID: {motor_id}")
    print("-" * 40)
    
    try:
        print(f"尝试打开串口 {port}...")
        ser = bp.configure_serial(port)
        print(f"串口 {port} 打开成功")
    except Exception as e:
        print(f"打开串口失败: {e}")
        sys.exit(1)
    
    try:
        print("开始测试，按Ctrl+C终止...")
        while True:
            # 生成正弦波位置命令
            q = math.sin(time.time())*0.09 + 0.2  # 正弦波，振幅0.09，偏移0.2
            dq = math.cos(time.time())*0.09  # 速度

            # 发送控制命令
            bp.send_packet(ser, bp.build_a_packet(id=motor_id, q=q, dq=dq, Kp=4, Kd=0.3, tau=0.0))
            bp.read_and_update_motor_data(ser)
            
            # 显示电机数据
            motor_key = f"mot{motor_id}_angle"
            vel_key = f"mot{motor_id}_velocity"
            
            angle = bp.motor_data.get(motor_key)
            velocity = bp.motor_data.get(vel_key, 0.0)
            
            angle_str = f"{angle:.4f}" if angle is not None else "N/A"
            print(f"\r目标位置: {q:.4f}, 实际位置: {angle_str}, 速度: {velocity:.4f}", end="")
            
            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试出错: {e}")
    finally:
        # 发送停止命令
        try:
            stop_packet = bp.build_a_packet(id=motor_id, q=0, dq=0, Kp=0, Kd=0, tau=0)
            bp.send_packet(ser, stop_packet)
            print("已发送停止命令")
        except:
            pass
        
        # 关闭串口
        try:
            ser.close()
            print(f"串口 {port} 已关闭")
        except:
            pass
