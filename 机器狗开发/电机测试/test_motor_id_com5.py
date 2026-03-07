import sys
import time
import math
import serial

# 导入build_a_packet模块，使用相对路径
sys.path.append("../宇树go1电机/gooddawg")
# 如果相对路径不起作用，可以尝试使用绝对路径
# sys.path.append("F:/github/机器狗维修研究/宇树go1电机/gooddawg")
import build_a_packet as bp

# 修改bp中的configure_serial函数，添加超时设置
def configure_serial_with_timeout(port, timeout=0.1, baudrate=5000000):
    print(f"尝试以波特率 {baudrate} 连接到 {port}...")
    ser = serial.Serial(
        port=port,
        baudrate=baudrate,
        bytesize=serial.EIGHTBITS,
        stopbits=serial.STOPBITS_ONE,
        parity=serial.PARITY_NONE,
        timeout=timeout,  # 添加超时设置，防止永久阻塞
        rtscts=False,
        dsrdtr=False
    )
    
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    
    print(f"串口连接成功: {port}")
    return ser

def test_motor_id(ser, motor_id):
    print(f"测试电机ID: {motor_id}")
    responses = 0
    
    # 发送5次命令，查看是否有响应（减少次数以加快测试）
    for i in range(5):
        print(f"  发送命令 {i+1}/5 到电机 {motor_id}...")
        # 发送一个小振幅的控制命令
        try:
            bp.send_packet(ser, bp.build_a_packet(id=motor_id, q=0.1, dq=0, Kp=1, Kd=0.1, tau=0.0))
            print(f"  命令已发送，等待响应...")
            
            # 读取数据，设置超时
            start_time = time.time()
            bp.read_and_update_motor_data(ser)
            elapsed = time.time() - start_time
            print(f"  读取操作耗时: {elapsed:.3f}秒")
            
            # 检查是否获得数据
            key = f'mot{motor_id}_angle'
            if key in bp.motor_data and bp.motor_data[key] is not None:
                responses += 1
                print(f"  收到响应! 电机角度: {bp.motor_data[key]:.4f}")
            else:
                print(f"  未收到电机 {motor_id} 的有效响应")
            
        except Exception as e:
            print(f"  与电机 {motor_id} 通信出错: {e}")
        
        # 确保缓冲区清空
        ser.reset_input_buffer()
        time.sleep(0.05)  # 增加延迟时间
    
    return responses > 0  # 如果至少有一次响应，则认为此ID有效

if __name__ == "__main__":
    # 尝试几个常见波特率
    baudrates = [5000000, 2500000, 1000000, 115200]
    ser = None
    
    for baudrate in baudrates:
        try:
            # 使用修改后的函数打开COM5端口，添加超时设置
            ser = configure_serial_with_timeout("COM5", timeout=0.5, baudrate=baudrate)
            print(f"使用波特率 {baudrate} 连接成功")
            
            # 先测试特定的ID 4
            print("\n首先测试ID 4...")
            if test_motor_id(ser, 4):
                print(f"ID 4 有响应! 使用波特率 {baudrate}")
                active_id = 4
                break
            else:
                print(f"ID 4 在波特率 {baudrate} 下没有响应，尝试测试ID 0-12")
                
                # 测试ID 0-12
                active_id = None
                for i in range(13):
                    print(f"\n尝试电机ID {i}...")
                    if test_motor_id(ser, i):
                        print(f"\nID {i} 在波特率 {baudrate} 下有响应!")
                        active_id = i
                        break
                    
                    # 清除缓冲区并暂停一下
                    ser.reset_input_buffer()
                    ser.reset_output_buffer()
                    time.sleep(0.1)
                
                if active_id is not None:
                    print(f"找到活动的电机ID {active_id}，使用波特率 {baudrate}")
                    break
                
            # 如果当前波特率没有找到电机，关闭串口准备尝试下一个波特率
            ser.close()
            print(f"在波特率 {baudrate} 下未找到电机，尝试下一个波特率")
            
        except Exception as e:
            print(f"尝试波特率 {baudrate} 时出错: {e}")
            if ser and ser.is_open:
                ser.close()
    
    if active_id is None:
        print("\n在所有尝试的波特率下均未找到响应的电机ID，请检查连接和电源")
        sys.exit(1)
    
    # 找到活动的电机ID后，进行简单的控制测试
    print(f"\n使用ID {active_id}，波特率 {baudrate} 进行控制测试...")
    try:
        for i in range(10):  # 减少测试次数
            # 产生简单的正弦波运动
            q = math.sin(time.time()*2)*0.1 + 0.1  # 轻微振荡
            print(f"发送命令 {i+1}/10: 目标位置 {q:.4f}")
            bp.send_packet(ser, bp.build_a_packet(id=active_id, q=q, dq=0, Kp=3, Kd=0.3, tau=0.0))
            
            start_time = time.time()
            bp.read_and_update_motor_data(ser)
            elapsed = time.time() - start_time
            print(f"读取耗时: {elapsed:.3f}秒")
            
            key = f'mot{active_id}_angle'
            if key in bp.motor_data and bp.motor_data[key] is not None:
                print(f"电机角度: {bp.motor_data[key]:.4f}, 目标: {q:.4f}")
            else:
                print("等待电机数据...")
                
            time.sleep(0.1)  # 增加延迟时间
    
    except Exception as e:
        print(f"控制测试过程中发生错误: {e}")
    
    finally:
        try:
            if ser and ser.is_open:
                ser.close()
                print("串口已关闭")
        except:
            pass 