import serial
import time
import sys

def test_port(port_name="COM1", baudrate=9600):
    """使用硬编码的十六进制字符串测试端口"""
    try:
        # 打开串口
        print(f"尝试打开 {port_name}，波特率 {baudrate}...")
        ser = serial.Serial(
            port=port_name,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=0.5,
            write_timeout=0.5
        )
        
        print(f"串口 {port_name} 打开成功!")
        
        # 对各个电机ID使用硬编码的十六进制命令
        test_commands = [
            # 电机ID 4 的命令
            "feee04ba0aff0000000000000064000000ffff10000a00020000000000",
            # 电机ID 1 的命令
            "feee01ba0aff0000000000000064000000ffff10000a00020000000000",
            # 电机ID 2 的命令
            "feee02ba0aff0000000000000064000000ffff10000a00020000000000",
            # 电机ID 0 的命令
            "feee00ba0aff0000000000000064000000ffff10000a00020000000000"
        ]
        
        for i, cmd in enumerate(test_commands):
            motor_id = cmd[4:6]  # 提取电机ID（字符串形式）
            
            print(f"\n发送命令到电机ID {motor_id}...")
            
            # 转换为字节并发送
            try:
                cmd_bytes = bytes.fromhex(cmd)
                print(f"命令长度: {len(cmd_bytes)} 字节")
                
                # 发送5次，增加成功机会
                for attempt in range(5):
                    print(f"  尝试 {attempt+1}/5...")
                    ser.write(cmd_bytes)
                    
                    # 检查响应
                    time.sleep(0.5)
                    if ser.in_waiting > 0:
                        response = ser.read(ser.in_waiting)
                        print(f"  收到响应: {response.hex()}")
                    else:
                        print("  无响应")
                    
                    time.sleep(0.5)
            except Exception as e:
                print(f"发送命令时出错: {e}")
        
        # 关闭串口
        ser.close()
        print(f"\n串口 {port_name} 已关闭")
        return True
    
    except Exception as e:
        print(f"错误: {e}")
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
        except:
            pass
        return False

def test_all_available_ports():
    """测试所有可用的端口"""
    # 尝试不同的波特率
    baudrates = [9600, 115200, 1000000, 5000000]
    
    # 尝试导入串口列表工具
    try:
        import serial.tools.list_ports
        ports = list(serial.tools.list_ports.comports())
        
        if not ports:
            print("未检测到串口")
            return
            
        print("检测到以下串口:")
        for i, p in enumerate(ports):
            print(f"{i+1}. {p.device}: {p.description}")
        
        # 询问用户选择端口
        port_choice = input("请选择要测试的端口号(直接回车测试COM1): ")
        
        if port_choice.strip() and port_choice.isdigit() and 1 <= int(port_choice) <= len(ports):
            port = ports[int(port_choice) - 1].device
        else:
            port = "COM1"
            
        # 询问用户选择波特率    
        baud_choice = input("请选择波特率 (1=9600, 2=115200, 3=1000000, 4=5000000, 默认=9600): ")
        
        if baud_choice.strip() and baud_choice.isdigit() and 1 <= int(baud_choice) <= 4:
            baudrate = baudrates[int(baud_choice) - 1]
        else:
            baudrate = 9600
            
        print(f"\n将使用 {port}, 波特率 {baudrate} 进行测试")
        test_port(port, baudrate)
        
    except ImportError:
        print("未安装串口列表工具，将使用默认COM1")
        test_port("COM1", 9600)
    except Exception as e:
        print(f"列出串口时出错: {e}")
        test_port("COM1", 9600)

if __name__ == "__main__":
    print("Go1电机硬编码命令测试工具")
    print("=======================")
    
    # 如果命令行提供了参数，直接使用这些参数
    if len(sys.argv) > 1:
        port = sys.argv[1]
        baudrate = 9600  # 默认波特率
        
        if len(sys.argv) > 2:
            try:
                baudrate = int(sys.argv[2])
            except:
                pass
                
        print(f"使用指定参数: 端口={port}, 波特率={baudrate}")
        test_port(port, baudrate)
    else:
        # 否则测试所有可用端口
        test_all_available_ports()
        
    print("\n测试完成! 如果电机有反应，表示通信成功。") 