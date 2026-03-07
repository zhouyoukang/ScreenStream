import serial
import time
import sys
import serial.tools.list_ports

def test_port_baudrate(port, baudrate, motor_id=4):
    """测试特定端口和波特率的组合"""
    try:
        print(f"\n尝试 {port} 波特率 {baudrate}...")
        
        # 尝试打开串口
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=0.1,
            write_timeout=0.1
        )
        
        print(f"成功打开 {port}，波特率 {baudrate}")
        
        # 发送一个简单的命令到电机 - 确保生成的是有效的十六进制字符串
        # 使用固定的十六进制字符串而不是动态生成，避免解析错误
        cmd = f"feee{motor_id:02x}ba0aff00000000000000640000000ffff10000a0002000000000000"
        
        try:
            # 验证是否是有效的十六进制字符串
            cmd_bytes = bytes.fromhex(cmd)
            print(f"发送命令: {cmd[:20]}...")
            ser.write(cmd_bytes)
            
            # 尝试读取响应
            time.sleep(0.5)
            if ser.in_waiting > 0:
                response = ser.read(ser.in_waiting)
                print(f"收到响应: {response.hex()}")
                success = True
            else:
                print("未收到响应")
                success = False
                
        except ValueError as hex_error:
            print(f"十六进制转换错误: {hex_error}")
            success = False
        
        # 关闭串口
        ser.close()
        print(f"{port} 已关闭")
        
        return True, success  # 返回 (端口可用, 收到响应)
        
    except Exception as e:
        print(f"错误: {e}")
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
        except:
            pass
        return False, False  # 返回 (端口不可用, 无响应)

def scan_all_ports():
    """扫描所有可用的串口和波特率"""
    # 检测系统中的串口
    print("检测系统中的串口...")
    available_ports = []
    try:
        ports = serial.tools.list_ports.comports()
        for i, p in enumerate(ports):
            print(f"{i+1}. {p.device}: {p.description} [{p.hwid}]")
            available_ports.append(p.device)
    except Exception as e:
        print(f"列出串口时出错: {e}")
    
    if not available_ports:
        print("未检测到串口设备")
        return
    
    # 要测试的波特率
    baudrates = [9600, 115200, 1000000, 5000000]
    
    # 要测试的电机ID
    motor_ids = [4, 1, 2, 0]  # 常用的Go1电机ID
    
    # 开始测试各个组合
    results = []
    
    for port in available_ports:
        for baudrate in baudrates:
            for motor_id in motor_ids:
                print(f"\n测试 {port}, 波特率 {baudrate}, 电机ID {motor_id}")
                port_available, got_response = test_port_baudrate(port, baudrate, motor_id)
                
                if port_available:
                    results.append({
                        'port': port, 
                        'baudrate': baudrate, 
                        'motor_id': motor_id, 
                        'response': got_response
                    })
                    
                    if got_response:
                        print(f"成功! 在 {port}, 波特率 {baudrate}, 电机ID {motor_id} 下收到了响应!")
                        
                        # 询问用户是否看到电机反应
                        user_input = input("电机是否有物理移动反应? (y/n): ").lower()
                        if user_input == 'y':
                            print(f"找到工作组合: {port}, 波特率 {baudrate}, 电机ID {motor_id}")
                            
                            # 保存成功的组合到文件
                            with open("working_motor_settings.txt", "w") as f:
                                f.write(f"工作设置:\n")
                                f.write(f"端口: {port}\n")
                                f.write(f"波特率: {baudrate}\n")
                                f.write(f"电机ID: {motor_id}\n")
                            
                            # 进行更多测试
                            detailed_test(port, baudrate, motor_id)
                            return
    
    # 显示测试结果
    print("\n\n测试结果:")
    print("==========")
    
    if results:
        print("可访问的端口组合:")
        for r in results:
            print(f"端口: {r['port']}, 波特率: {r['baudrate']}, 电机ID: {r['motor_id']}, 收到响应: {r['response']}")
    else:
        print("所有端口组合均无法访问或没有响应")
    
    print("\n如果没有找到工作组合，请检查:")
    print("1. 电机电源是否接通 (需要23-25V)")
    print("2. RS485接线是否正确 (A+/B-)")
    print("3. 尝试拔插USB设备后重试")

def detailed_test(port, baudrate, motor_id):
    """当找到工作组合时，进行更详细的测试"""
    print(f"\n对 {port}, 波特率 {baudrate}, 电机ID {motor_id} 进行详细测试...")
    
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=1.0
        )
        
        # 进行10个循环的位置控制测试
        positions = [50, 100, 150, 200, 150, 100, 50]  # 位置序列
        
        print("开始位置控制测试...")
        for i in range(5):  # 进行5轮测试
            print(f"\n测试轮次 {i+1}/5")
            for pos in positions:
                # 构建命令 - 确保十六进制格式正确
                # 使用02x格式确保位置值是2位十六进制
                pos_hex = f"{pos:02x}"
                cmd = f"feee{motor_id:02x}ba0aff00000000000000{pos_hex}0000000ffff10000a0002000000000000"
                
                try:
                    cmd_bytes = bytes.fromhex(cmd)
                    print(f"发送位置 {pos} (hex: {pos_hex})...")
                    ser.write(cmd_bytes)
                    
                    # 等待响应
                    time.sleep(0.5)
                    if ser.in_waiting > 0:
                        response = ser.read(ser.in_waiting)
                        print(f"收到响应: {response.hex()}")
                    else:
                        print("此命令无响应")
                    
                except ValueError as hex_error:
                    print(f"十六进制转换错误: {hex_error}")
                    print(f"错误的命令字符串: {cmd}")
                
                # 等待电机移动
                time.sleep(0.5)
        
        ser.close()
        print("详细测试完成")
        
    except Exception as e:
        print(f"详细测试失败: {e}")
        try:
            if 'ser' in locals() and ser.is_open:
                ser.close()
        except:
            pass

if __name__ == "__main__":
    print("Go1电机通信扫描工具")
    print("===================")
    print("该工具将尝试所有可能的串口、波特率和电机ID组合")
    print("这可能需要一些时间...\n")
    
    scan_all_ports() 