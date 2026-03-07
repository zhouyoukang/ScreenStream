import serial
import time
import sys

def send_motor_cmd(ser, motor_id=4):
    """发送Go1电机控制命令"""
    # 构建一个完整的位置控制命令
    # FEEE + 电机ID + BA0AFF + 位置控制参数 + 校验码(暂不计算)
    cmd = f"feee{motor_id:02x}ba0aff0000000000000064000000ffff10000a00020000000000"
    
    # 将hex字符串转换为字节
    cmd_bytes = bytes.fromhex(cmd)
    print(f"发送命令: {cmd_bytes[:10].hex()}...")
    
    ser.write(cmd_bytes)
    print("命令已发送")
    return True

def write_only_test(port_name="COM1", baudrate=115200):
    """只尝试向端口写入Go1电机控制命令，不读取"""
    try:
        # 打开串口
        print(f"尝试打开 {port_name}，波特率 {baudrate}...")
        
        # 创建串口对象，使用指定波特率
        ser = serial.Serial(
            port=port_name,
            baudrate=baudrate,  # 使用较低波特率
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=0.1,
            write_timeout=0.1,
            rtscts=False,
            dsrdtr=False
        )
        
        print(f"串口 {port_name} 打开成功!")
        print(f"串口设置: {ser}")
        
        # 向电机发送10个振荡命令
        print(f"\n开始发送振荡命令到电机...")
        positions = [50, 100, 150, 100, 50]  # 不同位置的列表
        
        for i in range(5):
            print(f"\n发送命令组 {i+1}/5")
            for pos in positions:
                cmd = f"feee04ba0aff00000000000000{pos:02x}000000ffff10000a00020000000000"
                cmd_bytes = bytes.fromhex(cmd)
                print(f"发送位置命令: 位置={pos}")
                ser.write(cmd_bytes)
                time.sleep(0.5)  # 等待电机移动
        
        # 关闭串口
        ser.close()
        print(f"\n串口 {port_name} 已关闭")
        print("电机控制命令发送完成")
        return True
        
    except Exception as e:
        print(f"错误: {e}")
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
                print("串口已关闭")
        except:
            pass
        return False

if __name__ == "__main__":
    # 默认端口和波特率
    port = "COM1"
    baudrate = 115200  # 使用较低波特率
    
    # 如果用户提供了参数，使用用户指定的端口
    if len(sys.argv) > 1:
        port = sys.argv[1]
    
    # 如果用户提供了第二个参数，使用用户指定的波特率
    if len(sys.argv) > 2:
        try:
            baudrate = int(sys.argv[2])
        except:
            pass
    
    print(f"将测试 {port} 端口，波特率 {baudrate}，向Go1电机发送控制命令...")
    write_only_test(port, baudrate)
    
    print("\n如果电机有反应，表示通信成功!")
    print("如果没有反应，请检查:")
    print("1. 是否选择了正确的COM端口")
    print("2. 电机电源是否接通 (需要23-25V)")
    print("3. RS485接线是否正确 (A+/B-)")
    print("4. 电机ID是否是4")
    print("5. 波特率是否正确 (Go1通常需要5000000)") 