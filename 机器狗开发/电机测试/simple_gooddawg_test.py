#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import time
import math

# 添加gooddawg库路径
gooddawg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "宇树go1电机/gooddawg")
sys.path.append(gooddawg_path)

try:
    import build_a_packet as bp
    print(f"成功导入build_a_packet模块")
except ImportError as e:
    print(f"导入build_a_packet模块失败: {e}")
    print(f"查找路径: {gooddawg_path}")
    sys.exit(1)

def main():
    # 默认参数
    port = "COM5"
    motor_id = 4
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        port = sys.argv[1]
    
    if len(sys.argv) > 2:
        try:
            motor_id = int(sys.argv[2])
        except ValueError:
            print(f"警告: 无效的电机ID '{sys.argv[2]}'，使用默认值 {motor_id}")
    
    print(f"简单电机测试 - 使用gooddawg库")
    print(f"串口: {port}")
    print(f"电机ID: {motor_id}")
    print("-" * 40)
    
    # 打开串口
    try:
        print(f"尝试打开串口 {port}...")
        ser = bp.configure_serial(port)
        print(f"串口 {port} 打开成功")
    except Exception as e:
        print(f"打开串口失败: {e}")
        return
    
    # 测试时间
    duration = 30  # 30秒
    
    try:
        print(f"开始测试电机 {motor_id}，持续 {duration} 秒...")
        start_time = time.time()
        
        while time.time() - start_time < duration:
            t = time.time() - start_time
            
            # 生成正弦波位置命令
            q = math.sin(t * 2) * 0.2 + 0.2  # 振幅0.2，偏移0.2
            dq = math.cos(t * 2) * 0.2  # 速度
            
            # 发送控制命令
            packet = bp.build_a_packet(id=motor_id, q=q, dq=dq, Kp=4, Kd=0.3, tau=0.0)
            bp.send_packet(ser, packet)
            
            # 读取电机数据
            bp.read_and_update_motor_data(ser)
            
            # 显示电机数据
            motor_key = f"mot{motor_id}_angle"
            vel_key = f"mot{motor_id}_velocity"
            
            angle = bp.motor_data.get(motor_key)
            velocity = bp.motor_data.get(vel_key, 0.0)
            
            print(f"\r时间: {t:.2f}s, 目标位置: {q:.4f}, 实际位置: {angle:.4f if angle is not None else 'N/A'}, 速度: {velocity:.4f}", end="")
            
            # 控制频率
            time.sleep(0.01)
        
        print("\n测试完成")
        
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

if __name__ == "__main__":
    main() 