import serial
import time
import sys

def listen_com1(baudrate=115200, duration=60):
    """监听COM1端口上的任何数据"""
    try:
        # 打开串口
        print(f"尝试打开COM1，波特率 {baudrate}...")
        ser = serial.Serial(
            port="COM1",
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=1.0  # 较长的超时时间
        )
        
        print(f"COM1打开成功! 设置: {ser}")
        print(f"开始监听COM1端口，持续{duration}秒...\n")
        
        # 发送一个初始命令
        cmd = "feee04ba0aff0000000000000064000000ffff10000a00020000000000"
        cmd_bytes = bytes.fromhex(cmd)
        print(f"发送初始命令: {cmd[:20]}...")
        ser.write(cmd_bytes)
        
        # 持续监听指定时间
        start_time = time.time()
        received_data = False
        
        while time.time() - start_time < duration:
            # 检查是否有数据可读
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting)
                print(f"收到数据: {data.hex()}")
                received_data = True
                
                # 再次发送命令
                time.sleep(1)
                print("发送响应命令...")
                ser.write(cmd_bytes)
            
            # 每10秒发送一次命令，增加被电机发现的机会
            elapsed = time.time() - start_time
            if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                if int(elapsed) % 20 == 0:  # 每20秒显示一次状态
                    print(f"已监听 {int(elapsed)} 秒，继续发送命令...")
                ser.write(cmd_bytes)
            
            # 短暂等待以减少CPU占用
            time.sleep(0.1)
        
        # 关闭串口
        ser.close()
        print("\nCOM1监听完成，已关闭")
        
        if not received_data:
            print("在监听期间未收到任何数据")
            
        return True
    
    except Exception as e:
        print(f"监听COM1时出错: {e}")
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
        except:
            pass
        return False

if __name__ == "__main__":
    print("COM1监听工具 - 等待来自Go1电机的响应")
    print("===================================")
    
    # 默认参数
    baudrate = 115200
    duration = 60  # 默认监听60秒
    
    # 处理命令行参数
    if len(sys.argv) > 1:
        try:
            baudrate = int(sys.argv[1])
        except:
            print(f"无效波特率: {sys.argv[1]}，使用默认值 {baudrate}")
    
    if len(sys.argv) > 2:
        try:
            duration = int(sys.argv[2])
        except:
            print(f"无效持续时间: {sys.argv[2]}，使用默认值 {duration}秒")
    
    print(f"使用波特率: {baudrate}，持续时间: {duration}秒")
    listen_com1(baudrate, duration)
    
    print("\n监听完成!") 