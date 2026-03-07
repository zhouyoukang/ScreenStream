import serial
import time

# 预构建的电机命令
def get_command_packet(motor_id):
    """返回预设的电机命令包"""
    # 这些是从Unitree Go1协议中提取的预构建数据包
    # ID 4的电机命令 - 位置控制模式
    if motor_id == 4:
        return "feee04ba0aff00000000000000640000000ffff10000a00020000000000"
    # ID 1的电机命令
    elif motor_id == 1:
        return "feee01ba0aff00000000000000640000000ffff10000a00020000000000"
    # ID 2的电机命令
    elif motor_id == 2:
        return "feee02ba0aff00000000000000640000000ffff10000a00020000000000"
    # ID 0的电机命令
    elif motor_id == 0:
        return "feee00ba0aff00000000000000640000000ffff10000a00020000000000"
    # 通用电机命令
    else:
        return f"feee{motor_id:02x}ba0aff00000000000000640000000ffff10000a00020000000000"

def test_baudrate(baudrate, motor_ids=[4, 1, 2, 0]):
    """使用指定波特率测试电机"""
    print(f"\n尝试波特率: {baudrate} bps")
    try:
        # 打开串口
        ser = serial.Serial(
            port="COM5",
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=0.1,
            rtscts=False,
            dsrdtr=False
        )
        
        print(f"串口COM5以{baudrate} bps波特率打开成功")
        
        # 向每个电机ID发送命令
        for motor_id in motor_ids:
            packet = get_command_packet(motor_id)
            print(f"向电机ID {motor_id} 发送命令...")
            
            # 连续发送三次命令增加可能性
            for _ in range(3):
                ser.write(bytes.fromhex(packet))
                time.sleep(0.05)
                
            print(f"等待电机ID {motor_id} 响应(请观察电机是否有动作)...")
            time.sleep(2)  # 等待2秒观察电机是否有反应
            
            # 清空缓冲区
            ser.reset_input_buffer()
        
        # 关闭串口
        ser.close()
        print(f"波特率 {baudrate} bps 测试完成")
        return True
        
    except Exception as e:
        print(f"波特率 {baudrate} bps 测试出错: {e}")
        try:
            ser.close()
        except:
            pass
        return False

def main():
    # 测试多个波特率
    baudrates = [5000000, 1000000, 115200]
    tested_ids = [4, 1, 2, 0]  # 要测试的电机ID
    
    print("开始多波特率电机测试")
    print("注意: 请观察电机是否有任何移动或声音反应")
    print(f"将测试电机ID: {tested_ids}")
    
    for baudrate in baudrates:
        test_baudrate(baudrate, tested_ids)
        
        response = input(f"\n在波特率 {baudrate} bps 下，电机是否有反应? (y/n): ").lower()
        if response == 'y':
            print(f"确认电机在波特率 {baudrate} bps 下有反应")
            
            # 询问具体哪个电机ID有反应
            id_response = input("请输入有反应的电机ID (如不确定请输入'不确定'): ")
            
            if id_response.isdigit():
                active_id = int(id_response)
                print(f"将进一步测试电机ID {active_id} 在波特率 {baudrate} bps 下的反应...")
                
                # 进行简单的振荡测试
                try:
                    ser = serial.Serial(port="COM5", baudrate=baudrate, timeout=0.1)
                    
                    # 振荡测试
                    print("开始振荡测试...")
                    positions = [100, 200]  # 两个位置值
                    
                    for _ in range(5):  # 振荡5次
                        for pos in positions:
                            packet = f"feee{active_id:02x}ba0aff00000000000000{pos:02x}000000ffff10000a00020000000000"
                            print(f"发送位置 {pos}...")
                            ser.write(bytes.fromhex(packet))
                            time.sleep(1)  # 等待电机移动
                    
                    ser.close()
                    print("振荡测试完成")
                    
                except Exception as e:
                    print(f"振荡测试出错: {e}")
                    try:
                        ser.close()
                    except:
                        pass
                
                # 退出循环
                break
            elif id_response == '不确定':
                print("将继续测试所有电机ID...")
            else:
                print("输入无效，将继续测试其他波特率...")
    
    print("\n测试完成!")
    print("如果在任何波特率下看到电机反应，请记录该波特率和电机ID以便将来使用")
    print("如果没有看到反应，请检查:")
    print("1. 电源连接 (需要23-25V)")
    print("2. RS485接线是否正确 (A+/B-)")
    print("3. USB转RS485适配器是否工作正常")

if __name__ == "__main__":
    main() 