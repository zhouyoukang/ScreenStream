import sys

print("串口检测脚本 (不打开任何端口)")
print("===========================")

try:
    print("尝试导入serial库...")
    import serial.tools.list_ports
    print("成功导入serial库")
    
    print("\n检测系统中的串口设备:")
    ports = serial.tools.list_ports.comports()
    
    if not ports:
        print("未检测到任何串口设备")
    else:
        print(f"检测到 {len(ports)} 个串口设备:")
        for i, port in enumerate(ports):
            print(f"{i+1}. {port.device}: {port.description}")
            print(f"   - 硬件ID: {port.hwid}")
            print(f"   - 制造商: {port.manufacturer if hasattr(port, 'manufacturer') else '未知'}")
    
except ImportError:
    print("错误: 未安装pyserial库")
    print("请运行以下命令安装: pip install pyserial")
    
except Exception as e:
    print(f"发生错误: {e}")
    
print("\n脚本执行完毕") 