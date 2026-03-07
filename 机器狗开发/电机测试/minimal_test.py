import serial
import time
import sys

def minimal_port_test(port_name="COM5"):
    """尝试最小化的串口测试，绕过可能的锁定"""
    try:
        # 尝试非常短的超时
        print(f"尝试直接打开 {port_name}...")
        
        # 尝试直接创建串口对象但不打开
        ser = serial.Serial()
        ser.port = port_name
        ser.baudrate = 115200  # 使用较低波特率
        ser.bytesize = serial.EIGHTBITS
        ser.parity = serial.PARITY_NONE
        ser.stopbits = serial.STOPBITS_ONE
        ser.timeout = 0.1  # 极短超时
        ser.write_timeout = 0.1
        
        # 尝试强制打开
        print("强制打开串口...")
        ser.open()
        print(f"串口 {port_name} 打开成功!")
        
        # 发送一个最简单的数据包
        test_data = bytes.fromhex("FEEE")
        print(f"发送测试数据: {test_data.hex()}")
        ser.write(test_data)
        print("数据发送成功")
        
        # 尝试读取
        print("等待响应...")
        time.sleep(0.5)
        
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting)
            print(f"收到响应: {response.hex()}")
        else:
            print("未收到响应")
        
        # 确保关闭
        ser.close()
        print(f"串口 {port_name} 关闭")
        return True
    
    except Exception as e:
        print(f"测试失败: {e}")
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
                print("串口已关闭")
        except:
            pass
        return False

if __name__ == "__main__":
    # 确定要测试的端口
    if len(sys.argv) > 1:
        port = sys.argv[1]
    else:
        print("可用串口:")
        # 列出所有串口
        try:
            import serial.tools.list_ports
            ports = serial.tools.list_ports.comports()
            for i, p in enumerate(ports):
                print(f"{i+1}. {p.device}: {p.description}")
            
            choice = input("请选择要测试的串口编号 (默认COM5): ")
            if choice.strip() and choice.isdigit() and 1 <= int(choice) <= len(ports):
                port = ports[int(choice) - 1].device
            else:
                port = "COM5"
        except:
            port = "COM5"  # 默认使用COM5
    
    print(f"将测试串口 {port}")
    for attempt in range(3):
        print(f"\n尝试 {attempt+1}/3...")
        if minimal_port_test(port):
            print(f"尝试 {attempt+1} 成功!")
            break
        time.sleep(1)  # 在尝试之间等待 