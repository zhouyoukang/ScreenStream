import serial
import time
import sys

def test_motor_with_different_params(com_port, motor_id=4):
    """尝试不同参数和命令组合来控制电机"""
    baudrates = [115200, 460800, 921600, 1000000, 1500000, 2000000, 3000000, 5000000]
    
    # 预定义几种不同的命令类型
    # 位置控制命令
    position_cmd = lambda id: f"feee{id:02x}ba0aff0000000000000064000000ffff10000a00020000000000"
    # 速度控制命令
    velocity_cmd = lambda id: f"feee{id:02x}ba0aff0000000000000000000000ffff20000a00020000000000"
    # 扭矩控制命令
    torque_cmd = lambda id: f"feee{id:02x}ba0aff0000000000000000000000ffff30000a00020000000000"
    # 标定命令
    calib_cmd = lambda id: f"feee{id:02x}ba0aff000000000000000000000000000000010000000000000000"

    for baudrate in baudrates:
        print(f"\n正在尝试波特率: {baudrate}")
        try:
            ser = serial.Serial(
                port=com_port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                stopbits=serial.STOPBITS_ONE,
                parity=serial.PARITY_NONE,
                timeout=0.5,
                rtscts=False,
                dsrdtr=False
            )
            print(f"成功以波特率 {baudrate} 打开串口 {com_port}")
            
            # 尝试不同的电机ID (有些电机可能使用0, 1, 2作为ID)
            for test_id in [motor_id, 0, 1, 2]:
                print(f"尝试电机ID: {test_id}")
                
                # 发送位置控制命令
                print(f"发送位置控制命令...")
                cmd = position_cmd(test_id)
                ser.write(bytes.fromhex(cmd))
                time.sleep(1)
                
                # 发送速度控制命令
                print(f"发送速度控制命令...")
                cmd = velocity_cmd(test_id)
                ser.write(bytes.fromhex(cmd))
                time.sleep(1)
                
                # 发送扭矩控制命令
                print(f"发送扭矩控制命令...")
                cmd = torque_cmd(test_id)
                ser.write(bytes.fromhex(cmd))
                time.sleep(1)
                
                # 发送标定命令
                print(f"发送标定命令...")
                cmd = calib_cmd(test_id)
                ser.write(bytes.fromhex(cmd))
                time.sleep(2)
            
            # 关闭串口
            ser.close()
            
        except Exception as e:
            print(f"波特率 {baudrate} 测试失败: {e}")
            try:
                ser.close()
            except:
                pass
            
    print("所有波特率测试完成")
    return True

if __name__ == "__main__":
    # 默认COM口和电机ID
    com_port = "COM5"
    motor_id = 4
    
    # 处理命令行参数
    if len(sys.argv) > 1:
        com_port = sys.argv[1]
    
    if len(sys.argv) > 2:
        try:
            motor_id = int(sys.argv[2])
        except:
            pass
    
    print(f"将在{com_port}上测试电机ID {motor_id} 的多种控制命令")
    print("测试期间请观察电机是否有任何反应")
    print("按Ctrl+C可随时中断测试")
    
    try:
        test_motor_with_different_params(com_port, motor_id)
        print("\n测试完成，如果电机有任何反应，请记下当时的波特率和命令类型")
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中出现错误: {e}") 