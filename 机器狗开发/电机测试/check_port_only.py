import serial
import time
import sys

def check_com_ports():
    """检查哪些COM端口可用"""
    available_ports = []
    for i in range(1, 21):  # 检查COM1-COM20
        port_name = f"COM{i}"
        try:
            # 尝试打开并立即关闭端口
            ser = serial.Serial(port_name, 9600, timeout=0.1)
            ser.close()
            available_ports.append(port_name)
            print(f"端口 {port_name} 可用")
        except:
            pass
    
    return available_ports

def test_port_basic(port_name, baudrate):
    """测试特定端口的基本功能"""
    try:
        print(f"尝试打开 {port_name}，波特率: {baudrate}...")
        # 使用较短的超时
        ser = serial.Serial(
            port=port_name,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=0.2,
            rtscts=False,
            dsrdtr=False
        )
        print(f"成功打开 {port_name}，波特率: {baudrate}")
        
        # 发送一个简单的命令 (电机ID 4，位置控制命令)
        cmd = bytes.fromhex("FEEE04BA0AFF00000000000000500000000FFFF10000A00020000000000BC594C4E")
        print(f"发送命令: {cmd[:10].hex()}...")
        ser.write(cmd)
        print(f"命令已发送")
        
        # 立即关闭端口，不等待响应
        ser.close()
        print(f"端口 {port_name} 已关闭")
        return True
    except Exception as e:
        print(f"错误: {e}")
        try:
            ser.close()
        except:
            pass
        return False

if __name__ == "__main__":
    # 检查哪些端口可用
    print("检查可用的COM端口...")
    ports = check_com_ports()
    
    if not ports:
        print("未找到可用的COM端口")
        sys.exit(1)
    
    print(f"\n可用端口: {ports}")
    
    # 默认测试COM5
    test_port = "COM5"
    if test_port not in ports:
        print(f"警告: {test_port} 不在可用端口列表中")
        if ports:
            test_port = ports[0]
            print(f"改用第一个可用端口: {test_port}")
    
    # 测试不同波特率
    baudrates = [115200, 1000000, 5000000]
    for baudrate in baudrates:
        print(f"\n测试端口 {test_port}，波特率: {baudrate}")
        if test_port_basic(test_port, baudrate):
            print(f"端口 {test_port} 在波特率 {baudrate} 下工作正常")
            
            # 询问用户是否看到电机有反应
            response = input("电机是否有反应? (y/n): ").lower()
            if response == 'y':
                print(f"确认电机在端口 {test_port}，波特率 {baudrate} 下有反应")
                break
        else:
            print(f"端口 {test_port} 在波特率 {baudrate} 下测试失败")
    
    print("\n测试完成") 