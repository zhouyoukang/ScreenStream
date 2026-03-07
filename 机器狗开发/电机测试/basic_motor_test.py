import serial
import struct
import time
import sys

# 构建非常简单的命令包
def build_simple_packet(motor_id):
    """构建最简单的控制数据包，不考虑CRC校验"""
    # 这是一个预构建的数据包，设置电机为位置模式并旋转到一个位置
    # feee开头是Go1电机的标准头部
    packet = "feee" + f"{motor_id:02x}" + "ba0aff0000000000000000000000000000ffff04000300020000000000"
    return packet

# 直接向所有可能的电机ID发送命令
def test_all_motors():
    try:
        # 打开COM5串口，短超时
        ser = serial.Serial(
            port="COM5",
            baudrate=5000000,  # 使用Go1标准波特率
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=0.1,  # 非常短的超时
            rtscts=False,
            dsrdtr=False
        )
        print("串口打开成功")
        
        # 尝试向多个电机ID发送命令
        print("开始发送电机命令...")
        for motor_id in range(13):  # 测试ID 0-12
            packet = build_simple_packet(motor_id)
            print(f"向电机 {motor_id} 发送命令: {packet[:10]}...")
            
            # 发送命令
            ser.write(bytes.fromhex(packet))
            
            # 不等待响应，直接清空缓冲区
            ser.reset_input_buffer()
            
            # 暂停一下让电机有时间响应
            print(f"等待电机 {motor_id} 响应...")
            time.sleep(1)
        
        # 发送电机前后振荡测试 (仅对电机ID 4)
        print("\n开始电机振荡测试 (ID 4)...")
        positions = [10, 250]  # 两个极端位置的简单值
        
        for _ in range(10):  # 振荡10次
            for pos in positions:
                # 这是另一个预构建的数据包，设置不同的位置
                packet = f"feee04ba0aff00000000000000{pos:02x}000000ffff08000500020000000000"
                print(f"发送振荡命令: {packet[:10]}...")
                ser.write(bytes.fromhex(packet))
                time.sleep(0.5)  # 等待电机移动
        
        ser.close()
        print("测试完成，串口已关闭")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        try:
            ser.close()
        except:
            pass

if __name__ == "__main__":
    print("开始基础电机测试...")
    test_all_motors()
    print("\n如果电机有反应，请注意观察它的动作。")
    print("如果没有反应，请检查电源和接线。") 