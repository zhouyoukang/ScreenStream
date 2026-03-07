import serial
import time
import sys

def direct_motor_control(port_name, motor_id=4):
    """直接发送可能启动电机的命令"""
    try:
        # 尝试打开串口
        print(f"尝试打开{port_name}串口...")
        ser = serial.Serial(
            port=port_name,
            baudrate=5000000,  # Go1标准波特率
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=1.0
        )
        print(f"串口{port_name}打开成功")
        
        # 电机启动命令 - 这是一个基本的电机通电命令
        # FEEE为起始头，XX为电机ID
        enable_cmd = f"feee{motor_id:02x}ba0aff000000000000000000000000ffff90000000000000000000"
        print("发送电机启动命令...")
        ser.write(bytes.fromhex(enable_cmd))
        time.sleep(2)  # 等待电机启动
        
        # 电机零位命令 - 移动到中间位置
        zero_cmd = f"feee{motor_id:02x}ba0aff000000000000000000000000ffff11000000000000000000"
        print("发送电机零位命令...")
        ser.write(bytes.fromhex(zero_cmd))
        time.sleep(2)
        
        # 尝试振动电机 - 简单的小幅振动
        print("尝试电机振动...")
        for i in range(5):
            # 位置1
            pos1_cmd = f"feee{motor_id:02x}ba0aff000000000000002d000000ffff10000a00020000000000"
            ser.write(bytes.fromhex(pos1_cmd))
            time.sleep(0.5)
            
            # 位置2
            pos2_cmd = f"feee{motor_id:02x}ba0aff0000000000000064000000ffff10000a00020000000000"
            ser.write(bytes.fromhex(pos2_cmd))
            time.sleep(0.5)
        
        # 尝试发送简单的速度命令
        speed_cmd = f"feee{motor_id:02x}ba0aff0000000000000064000000ffff20000a00020000000000"
        print("发送速度控制命令...")
        ser.write(bytes.fromhex(speed_cmd))
        time.sleep(3)
        
        # 发送停止命令
        stop_cmd = f"feee{motor_id:02x}ba0aff000000000000000000000000ffff00000000000000000000"
        print("发送停止命令...")
        ser.write(bytes.fromhex(stop_cmd))
        
        # 关闭串口
        ser.close()
        print(f"串口{port_name}已关闭")
        return True
        
    except Exception as e:
        print(f"控制失败: {e}")
        try:
            ser.close()
        except:
            pass
        return False

if __name__ == "__main__":
    # 获取命令行参数
    port = "COM5"  # 默认COM口
    motor_id = 4   # 默认电机ID
    
    if len(sys.argv) > 1:
        port = sys.argv[1]
    
    if len(sys.argv) > 2:
        try:
            motor_id = int(sys.argv[2])
        except:
            pass
    
    print(f"将向电机ID {motor_id} 通过{port}发送直接控制命令")
    print("请观察电机是否有任何反应")
    
    for attempt in range(3):
        print(f"\n尝试 {attempt+1}/3...")
        if direct_motor_control(port, motor_id):
            print(f"尝试 {attempt+1} 完成")
        else:
            print(f"尝试 {attempt+1} 失败")
        time.sleep(1) 