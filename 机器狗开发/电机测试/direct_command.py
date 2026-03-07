import serial
import time
import sys

# 硬编码的命令集 - 这些是从成功控制Go1电机的程序中提取的原始命令
# 命令格式：前2字节为帧头(FEEE)，第3字节为电机ID，后续为数据和CRC
# 这些命令将使电机在两个位置之间来回移动

# 位置1命令集合，ID 0-12
CMD_POS1 = {
    0: bytes.fromhex("FEEE00BA0AFF00000000000000500000000FFFF10000A00020000000000F4A90C4E"),
    1: bytes.fromhex("FEEE01BA0AFF00000000000000500000000FFFF10000A00020000000000E8B8144E"),
    2: bytes.fromhex("FEEE02BA0AFF00000000000000500000000FFFF10000A00020000000000DCF9084E"),
    3: bytes.fromhex("FEEE03BA0AFF00000000000000500000000FFFF10000A00020000000000C8E8104E"),
    4: bytes.fromhex("FEEE04BA0AFF00000000000000500000000FFFF10000A00020000000000BC594C4E"),
    5: bytes.fromhex("FEEE05BA0AFF00000000000000500000000FFFF10000A00020000000000A848444E"),
    6: bytes.fromhex("FEEE06BA0AFF00000000000000500000000FFFF10000A00020000000000B4094F4E"),
    7: bytes.fromhex("FEEE07BA0AFF00000000000000500000000FFFF10000A00020000000000A018474E"),
    8: bytes.fromhex("FEEE08BA0AFF00000000000000500000000FFFF10000A00020000000000842B654E"),
    9: bytes.fromhex("FEEE09BA0AFF00000000000000500000000FFFF10000A00020000000000903A6D4E"),
    10: bytes.fromhex("FEEE0ABA0AFF00000000000000500000000FFFF10000A00020000000000887B714E"),
    11: bytes.fromhex("FEEE0BBA0AFF00000000000000500000000FFFF10000A00020000000000946A794E"),
    12: bytes.fromhex("FEEE0CBA0AFF00000000000000500000000FFFF10000A00020000000000782FE14E")
}

# 位置2命令集合，ID 0-12
CMD_POS2 = {
    0: bytes.fromhex("FEEE00BA0AFF00000000000000C00000000FFFF10000A000200000000005D83934F"),
    1: bytes.fromhex("FEEE01BA0AFF00000000000000C00000000FFFF10000A000200000000004B929B4F"),
    2: bytes.fromhex("FEEE02BA0AFF00000000000000C00000000FFFF10000A000200000000007FD3814F"),
    3: bytes.fromhex("FEEE03BA0AFF00000000000000C00000000FFFF10000A000200000000006DC2894F"),
    4: bytes.fromhex("FEEE04BA0AFF00000000000000C00000000FFFF10000A000200000000001173C54F"),
    5: bytes.fromhex("FEEE05BA0AFF00000000000000C00000000FFFF10000A000200000000000762CD4F"),
    6: bytes.fromhex("FEEE06BA0AFF00000000000000C00000000FFFF10000A000200000000003323D74F"),
    7: bytes.fromhex("FEEE07BA0AFF00000000000000C00000000FFFF10000A000200000000002532DF4F"),
    8: bytes.fromhex("FEEE08BA0AFF00000000000000C00000000FFFF10000A000200000000002101FD4F"),
    9: bytes.fromhex("FEEE09BA0AFF00000000000000C00000000FFFF10000A000200000000003710F54F"),
    10: bytes.fromhex("FEEE0ABA0AFF00000000000000C00000000FFFF10000A000200000000002F51FB4F"),
    11: bytes.fromhex("FEEE0BBA0AFF00000000000000C00000000FFFF10000A000200000000003B40F34F"),
    12: bytes.fromhex("FEEE0CBA0AFF00000000000000C00000000FFFF10000A000200000000000F05754F")
}

def test_motor_id_direct(motor_id, baudrate=5000000):
    """直接测试指定ID的电机，使用预编码的命令"""
    print(f"\n测试电机ID: {motor_id}, 波特率: {baudrate}")
    
    try:
        # 打开串口，不等待响应
        ser = serial.Serial(
            port="COM5",
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            stopbits=serial.STOPBITS_ONE,
            parity=serial.PARITY_NONE,
            timeout=0.1,  # 短超时
            rtscts=False,
            dsrdtr=False
        )
        
        print(f"串口打开成功，开始测试电机ID {motor_id}")
        
        # 循环发送命令，让电机在两个位置间振荡
        for _ in range(10):  # 振荡10次
            print(f"发送位置1命令: {CMD_POS1[motor_id][:10].hex()}...")
            ser.write(CMD_POS1[motor_id])
            # 不等待响应，直接清空缓冲区
            ser.reset_input_buffer()
            time.sleep(0.5)  # 等待电机移动
            
            print(f"发送位置2命令: {CMD_POS2[motor_id][:10].hex()}...")
            ser.write(CMD_POS2[motor_id])
            # 不等待响应，直接清空缓冲区
            ser.reset_input_buffer()
            time.sleep(0.5)  # 等待电机移动
        
        ser.close()
        print(f"电机ID {motor_id} 测试完成\n")
        return True
        
    except Exception as e:
        print(f"测试电机ID {motor_id} 时出错: {e}")
        try:
            ser.close()
        except:
            pass
        return False

def main():
    """主函数，测试多个电机ID和波特率"""
    # 测试波特率列表
    baudrates = [5000000, 1000000, 115200]
    
    print("开始直接电机命令测试")
    print("注意观察电机是否有任何运动")
    
    # 首先测试ID 4（最可能的ID）
    print("\n先测试最可能的电机ID 4...")
    
    for baudrate in baudrates:
        # 测试电机ID 4
        test_motor_id_direct(4, baudrate)
        response = input(f"在波特率 {baudrate} 下，电机ID 4 是否有反应？(y/n): ").lower()
        if response == 'y':
            print(f"确认电机ID 4 在波特率 {baudrate} 下有反应！")
            # 如果有反应，执行更多的振荡测试
            for _ in range(3):
                test_motor_id_direct(4, baudrate)
            return  # 测试成功，退出程序
    
    # 如果ID 4没有反应，测试其他ID
    print("\n电机ID 4 在所有波特率下均无反应，开始测试其他ID...")
    
    # 使用最高波特率测试其他ID
    for motor_id in range(13):
        if motor_id == 4:  # 已经测试过ID 4
            continue
        
        test_motor_id_direct(motor_id, 5000000)
        response = input(f"电机ID {motor_id} 是否有反应？(y/n): ").lower()
        if response == 'y':
            print(f"确认电机ID {motor_id} 有反应！")
            # 继续执行更多振荡测试
            for _ in range(3):
                test_motor_id_direct(motor_id, 5000000)
            return  # 测试成功，退出程序
    
    # 如果所有ID都没有反应，尝试低波特率
    print("\n所有电机ID在5000000波特率下均无反应，尝试低波特率...")
    
    for baudrate in [1000000, 115200]:
        for motor_id in range(13):
            if motor_id == 4:  # ID 4在低波特率下已经测试过
                continue
                
            test_motor_id_direct(motor_id, baudrate)
            response = input(f"在波特率 {baudrate} 下，电机ID {motor_id} 是否有反应？(y/n): ").lower()
            if response == 'y':
                print(f"确认电机ID {motor_id} 在波特率 {baudrate} 下有反应！")
                # 继续执行更多振荡测试
                for _ in range(3):
                    test_motor_id_direct(motor_id, baudrate)
                return  # 测试成功，退出程序
    
    # 如果所有尝试都失败
    print("\n所有测试均无反应。可能的原因:")
    print("1. 电源电压不足 (需要23-25V)")
    print("2. RS485接线有问题")
    print("3. 串口适配器不支持所需波特率")
    print("4. 电机型号与Go1不兼容")

if __name__ == "__main__":
    main() 