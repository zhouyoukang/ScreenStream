import sys
import serial
import serial.tools.list_ports

def list_available_ports():
    """列出系统中所有可用的串口"""
    ports = serial.tools.list_ports.comports()
    
    if not ports:
        print("未检测到任何串口设备")
        return []
    
    print("可用串口列表:")
    available_ports = []
    for port in ports:
        print(f"- {port.device}: {port.description} [{port.hwid}]")
        available_ports.append(port.device)
    
    return available_ports

def simple_port_test(port_name):
    """执行最简单的串口测试，只打开并关闭"""
    try:
        print(f"\n尝试以最低波特率打开 {port_name}...")
        ser = serial.Serial(port_name, baudrate=9600, timeout=0.5)
        print(f"成功打开 {port_name}")
        print(f"端口信息: {ser.get_settings()}")
        
        print(f"关闭 {port_name}...")
        ser.close()
        print(f"成功关闭 {port_name}")
        return True
    except Exception as e:
        print(f"测试 {port_name} 出错: {e}")
        return False

if __name__ == "__main__":
    print("串口检测工具")
    print("============")
    
    # 列出所有可用串口
    ports = list_available_ports()
    
    if not ports:
        print("\n未找到可用串口，请检查设备连接")
        sys.exit(1)
    
    # 询问用户选择要测试的端口
    print("\n要测试哪个串口?")
    
    if "COM5" in ports:
        default_port = "COM5"
        print(f"默认将测试 {default_port}")
    else:
        default_port = ports[0]
        print(f"默认将测试第一个可用端口: {default_port}")
    
    user_port = input(f"请输入要测试的端口 (直接回车使用{default_port}): ").strip()
    if not user_port:
        user_port = default_port
    
    # 测试所选端口
    if simple_port_test(user_port):
        print(f"\n基本串口测试成功: {user_port} 可以正常打开和关闭")
    else:
        print(f"\n基本串口测试失败: 无法正常访问 {user_port}")
        print("可能的原因:")
        print("1. 端口被其他程序占用")
        print("2. 串口权限问题")
        print("3. 设备连接不良或已断开") 