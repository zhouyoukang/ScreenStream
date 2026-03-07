import serial
import struct
import time
import math
import sys

# 正确的CRC32计算函数 - 根据Go1电机协议
POLY = 0x04C11DB7

def crc32_core(data_words):
    """使用正确的位操作计算CRC32"""
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

def get_crc(data_bytes):
    """从字节数据计算CRC32"""
    # 确保数据长度是32字节
    if len(data_bytes) < 28:
        data_bytes = data_bytes.ljust(28, b'\x00')
    elif len(data_bytes) > 28:
        data_bytes = data_bytes[:28]
    
    # 以小端模式解析7个32位整数
    data_words = struct.unpack('<7I', data_bytes)
    crc = crc32_core(data_words)
    return crc

# 此函数用于准确构建电机控制数据包
def build_motor_packet(motor_id, position=0.0, velocity=0.0, kp=0.0, kd=0.0, torque=0.0):
    """构建精确的电机控制数据包"""
    # 构建正确的命令头
    cmd_bytes = bytearray()
    
    # 添加帧头 (0xFE 0xEE)
    cmd_bytes.extend(b'\xFE\xEE')
    
    # 添加电机ID
    cmd_bytes.append(motor_id & 0xFF)
    
    # 添加预留区域和模式选择 (预设为位置控制模式)
    cmd_bytes.extend(b'\xBA\x0A\xFF\x00\x00\x00\x00\x00\x00')
    
    # 转换转矩为有效格式 (限制在合理范围内)
    limited_torque = max(min(torque, 10.0), -10.0)  # 限制转矩范围
    torque_value = int(limited_torque * 100000)
    cmd_bytes.extend(struct.pack('<i', torque_value)[:2])  # 使用小端序，取前2字节
    
    # 转换速度为有效格式
    limited_vel = max(min(velocity, 1.0), -1.0)  # 限制速度范围
    vel_value = int(limited_vel * 65000)
    cmd_bytes.extend(struct.pack('<h', vel_value))  # 使用小端序，2字节
    
    # 转换位置为有效格式
    limited_pos = max(min(position, 1.0), -1.0)  # 限制位置范围
    pos_value = int(limited_pos * 65000 + 65536) & 0xFFFF
    cmd_bytes.extend(struct.pack('<h', pos_value))  # 使用小端序，2字节
    
    # 处理位置符号
    if position < 0:
        cmd_bytes.extend(b'\xFF\xFF')  # 负值标志
    else:
        cmd_bytes.extend(b'\x00\x00')  # 正值标志
    
    # 添加KP参数 (限制在0-255范围内)
    cmd_bytes.append(max(min(int(kp), 255), 0) & 0xFF)
    cmd_bytes.append(0x00)  # KP预留字节
    
    # 添加KD参数
    kd_value = int(kd * 2553) & 0xFFFF
    cmd_bytes.extend(struct.pack('<h', kd_value))  # 使用小端序，2字节
    
    # 添加预留区域
    cmd_bytes.extend(b'\x02\x00\x00\x00\x00\x00')
    
    # 计算CRC32
    crc = get_crc(cmd_bytes)
    cmd_bytes.extend(struct.pack('<I', crc))  # 使用小端序，4字节
    
    return cmd_bytes

# 直接测试指定ID电机，确保通信协议正确
def test_specific_motor(motor_id, baudrate=5000000):
    try:
        # 打开串口
        print(f"尝试打开COM5串口，波特率: {baudrate}...")
        ser = serial.Serial(
            port="COM5",
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=0.5,  # 设置较长的超时
            rtscts=False,
            dsrdtr=False
        )
        
        print(f"串口打开成功，开始测试电机ID: {motor_id}")
        
        # 先发送一个零位置命令，确保电机初始化
        print("发送初始化命令...")
        cmd = build_motor_packet(motor_id, position=0.0, kp=2, kd=0.1)
        ser.write(cmd)
        time.sleep(1)  # 给电机响应的时间
        
        # 执行简单的正弦波振荡测试
        print("\n开始执行正弦波振荡测试...")
        for i in range(20):
            # 使用正弦波生成平滑的位置命令
            pos = 0.3 * math.sin(i * 0.3)
            print(f"命令 {i+1}/20: 位置={pos:.4f}")
            
            # 构建并发送控制命令
            cmd = build_motor_packet(motor_id, position=pos, kp=10, kd=0.5)
            print(f"发送命令: {cmd[:10].hex()}...")
            ser.write(cmd)
            
            # 等待电机响应时间
            time.sleep(0.5)
            
            # 尝试读取反馈
            data = ser.read(100)
            if data:
                print(f"收到数据: {data[:20].hex()}... ({len(data)} 字节)")
            else:
                print("未收到数据反馈")
        
        # 完成后发送归零命令
        print("\n发送归零命令...")
        cmd = build_motor_packet(motor_id, position=0.0, kp=5, kd=0.5)
        ser.write(cmd)
        time.sleep(1)
        
        # 关闭串口
        ser.close()
        print("测试完成，串口已关闭")
        return True
    
    except Exception as e:
        print(f"测试过程中出错: {e}")
        try:
            ser.close()
        except:
            pass
        return False

if __name__ == "__main__":
    # 默认测试ID 4
    motor_id = 4
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        try:
            motor_id = int(sys.argv[1])
            print(f"使用命令行指定的电机ID: {motor_id}")
        except:
            print(f"命令行参数无效，使用默认ID: {motor_id}")
    else:
        try:
            user_input = input(f"请输入电机ID (默认为{motor_id}): ").strip()
            if user_input:
                motor_id = int(user_input)
        except:
            print(f"输入无效，使用默认ID: {motor_id}")
    
    # 尝试不同波特率
    baudrates = [5000000, 1000000, 115200]
    for baudrate in baudrates:
        print(f"\n尝试波特率: {baudrate}")
        if test_specific_motor(motor_id, baudrate):
            print(f"使用波特率 {baudrate} 测试成功!")
            break
    else:
        print("\n所有波特率测试均失败。")
        print("请检查:")
        print("1. 电源连接 (需要23-25V)")
        print("2. 电机ID是否正确")
        print("3. 通信协议是否匹配") 