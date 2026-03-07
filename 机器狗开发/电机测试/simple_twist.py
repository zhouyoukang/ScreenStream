import serial
import time
import sys

def send_command_to_motor(motor_id, com_port="COM7"):
    """向指定ID的电机发送简单的扭动命令"""
    try:
        # 尝试打开串口
        print(f"尝试打开{com_port}串口...")
        ser = serial.Serial(
            port=com_port,
            baudrate=1000000,  # 修改为较低波特率
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=0.5,
            rtscts=False,
            dsrdtr=False
        )
        print("串口打开成功")
        
        # 两个预构建的命令包，让电机在两个位置之间来回运动
        cmd1 = f"feee{motor_id:02x}ba0aff0000000000000032000000ffff10000a00020000000000"
        cmd2 = f"feee{motor_id:02x}ba0aff0000000000000096000000ffff10000a00020000000000"
        
        # 执行10次振荡
        print(f"开始向电机ID {motor_id} 发送振荡命令...")
        for i in range(10):
            print(f"振荡 {i+1}/10")
            # 发送第一个位置命令
            ser.write(bytes.fromhex(cmd1))
            time.sleep(1)  # 等待1秒
            
            # 发送第二个位置命令
            ser.write(bytes.fromhex(cmd2))
            time.sleep(1)  # 等待1秒
        
        # 完成后关闭串口
        ser.close()
        print("命令发送完成，串口已关闭")
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        try:
            ser.close()
        except:
            pass
        return False

if __name__ == "__main__":
    # 默认值
    motor_id = 4  # 默认使用ID 4
    com_port = "COM7"  # 默认COM口
    
    # 处理命令行参数
    if len(sys.argv) > 1:
        com_port = sys.argv[1]  # 第一个参数作为COM口
    
    if len(sys.argv) > 2:
        try:
            motor_id = int(sys.argv[2])
            print(f"使用命令行参数指定的电机ID: {motor_id}")
        except:
            print(f"电机ID参数无效，使用默认电机ID: {motor_id}")
    else:
        try:
            user_input = input(f"请输入电机ID (默认为{motor_id}): ")
            if user_input.strip():
                motor_id = int(user_input)
        except:
            print(f"输入无效，使用默认电机ID: {motor_id}")
    
    # 向指定的电机ID发送命令
    print(f"将向电机ID {motor_id} 通过{com_port}发送命令")
    result = send_command_to_motor(motor_id, com_port)
    
    if result:
        print("\n命令发送成功! 请观察电机是否有反应。")
    else:
        print("\n命令发送失败。请检查:")
        print(f"1. 确保没有其他程序正在使用{com_port}串口")
        print("2. 检查电源连接 (需要23-25V)")
        print("3. 检查RS485接线是否正确") 