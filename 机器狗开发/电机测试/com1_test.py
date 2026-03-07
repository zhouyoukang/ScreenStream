import serial
import time
import sys

def test_com1(baudrate=9600):
    """专门测试COM1端口，使用指定波特率"""
    try:
        # 打开串口
        print(f"尝试打开COM1，波特率 {baudrate}...")
        ser = serial.Serial(
            port="COM1",
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=0.5,
            write_timeout=0.5
        )
        
        print(f"COM1打开成功! 设置: {ser}")
        
        # 硬编码的Go1电机命令
        cmd = "feee04ba0aff0000000000000064000000ffff10000a00020000000000"
        
        try:
            cmd_bytes = bytes.fromhex(cmd)
            print(f"命令长度: {len(cmd_bytes)} 字节")
            
            # 发送命令多次，看是否有响应
            for i in range(10):
                print(f"\n发送命令 {i+1}/10...")
                ser.write(cmd_bytes)
                
                # 等待并检查响应
                time.sleep(0.5)
                if ser.in_waiting > 0:
                    response = ser.read(ser.in_waiting)
                    print(f"收到响应: {response.hex()}")
                else:
                    print("无响应")
                    
                # 等待一会儿
                time.sleep(0.5)
        except Exception as e:
            print(f"发送命令时出错: {e}")
        
        # 关闭串口
        ser.close()
        print("COM1已关闭")
        return True
        
    except Exception as e:
        print(f"打开COM1时出错: {e}")
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
        except:
            pass
        return False

if __name__ == "__main__":
    print("COM1测试工具 - 尝试向Go1电机发送命令")
    print("===================================")
    
    # 要测试的波特率列表
    baudrates = [9600, 115200, 1000000]
    
    # 如果用户指定了波特率，只测试指定的
    if len(sys.argv) > 1:
        try:
            baudrate = int(sys.argv[1])
            print(f"使用指定波特率: {baudrate}")
            test_com1(baudrate)
        except ValueError:
            print(f"无效波特率: {sys.argv[1]}")
            print("将测试所有标准波特率")
            for baudrate in baudrates:
                print(f"\n--- 测试波特率 {baudrate} ---")
                test_com1(baudrate)
    else:
        # 否则测试所有标准波特率
        for baudrate in baudrates:
            print(f"\n--- 测试波特率 {baudrate} ---")
            test_com1(baudrate)
    
    print("\n测试完成!") 