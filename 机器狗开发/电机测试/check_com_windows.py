import os
import sys
import subprocess
import time
import winreg

def list_com_ports_via_registry():
    """通过Windows注册表获取所有COM端口"""
    try:
        ports = []
        # 打开串口信息的注册表键
        path = 'HARDWARE\\DEVICEMAP\\SERIALCOMM'
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path)
        
        # 读取所有值
        i = 0
        while True:
            try:
                name, value, type = winreg.EnumValue(key, i)
                ports.append((value, name))
                i += 1
            except WindowsError:
                break
        
        if ports:
            print("通过注册表找到以下COM端口:")
            for port, device in sorted(ports):
                print(f"- {port}: {device}")
        else:
            print("在注册表中未找到COM端口")
        
        return ports
    except Exception as e:
        print(f"读取注册表时出错: {e}")
        return []

def list_com_ports_via_wmic():
    """使用WMIC命令列出COM端口"""
    try:
        # 使用WMIC命令获取串口信息
        cmd = "wmic path Win32_SerialPort get DeviceID, Description, PNPDeviceID"
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        
        if proc.returncode != 0:
            print(f"WMIC命令执行失败: {stderr.decode('gbk', errors='ignore')}")
            return []
        
        # 解析结果
        output = stdout.decode('gbk', errors='ignore').strip().split('\n')
        if len(output) <= 1:
            print("WMIC未找到任何串口设备")
            return []
        
        print("\n通过WMIC找到以下串口设备:")
        ports = []
        for line in output[1:]:  # 跳过标题行
            if line.strip():
                parts = line.strip().split()
                if parts:
                    port = parts[0]
                    desc = ' '.join(parts[1:-1]) if len(parts) > 2 else "未知"
                    pnp_id = parts[-1] if len(parts) > 1 else "未知"
                    print(f"- {port}: {desc} [{pnp_id}]")
                    ports.append(port)
        
        return ports
    except Exception as e:
        print(f"执行WMIC命令时出错: {e}")
        return []

def check_port_via_powershell(port_name):
    """使用PowerShell测试串口访问"""
    try:
        print(f"\n使用PowerShell测试端口 {port_name}...")
        
        # 创建PowerShell脚本
        ps_script = f"""
        try {{
            $port = New-Object System.IO.Ports.SerialPort("{port_name}", 9600)
            $port.Open()
            Write-Output "成功打开端口 {port_name}"
            Start-Sleep -Milliseconds 500
            $port.Close()
            Write-Output "成功关闭端口 {port_name}"
            exit 0
        }} catch {{
            Write-Output "无法访问端口 {port_name}: $_"
            exit 1
        }}
        """
        
        # 保存到临时文件
        temp_script = os.path.join(os.environ['TEMP'], 'test_com.ps1')
        with open(temp_script, 'w') as f:
            f.write(ps_script)
        
        # 执行PowerShell脚本
        cmd = f'powershell -ExecutionPolicy Bypass -File "{temp_script}"'
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        
        output = stdout.decode('gbk', errors='ignore').strip()
        print(output)
        
        # 删除临时文件
        try:
            os.remove(temp_script)
        except:
            pass
        
        return proc.returncode == 0
    except Exception as e:
        print(f"PowerShell测试出错: {e}")
        return False

def check_port_is_in_use(port_name):
    """检查端口是否被其他进程占用"""
    try:
        print(f"\n检查端口 {port_name} 是否被占用...")
        
        # 使用PowerShell检查端口是否被占用
        ps_script = f"""
        $portInUse = $false
        try {{
            $port = New-Object System.IO.Ports.SerialPort("{port_name}", 9600)
            $port.Open()
            $port.Close()
            Write-Output "端口 {port_name} 当前未被占用"
        }} catch [System.UnauthorizedAccessException] {{
            Write-Output "端口 {port_name} 当前被其他进程占用"
            $portInUse = $true
        }} catch {{
            Write-Output "检查端口 {port_name} 时出错: $_"
        }}
        exit [int]$portInUse
        """
        
        # 保存到临时文件
        temp_script = os.path.join(os.environ['TEMP'], 'check_port_use.ps1')
        with open(temp_script, 'w') as f:
            f.write(ps_script)
        
        # 执行PowerShell脚本
        cmd = f'powershell -ExecutionPolicy Bypass -File "{temp_script}"'
        proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        
        output = stdout.decode('gbk', errors='ignore').strip()
        print(output)
        
        # 删除临时文件
        try:
            os.remove(temp_script)
        except:
            pass
        
        return proc.returncode == 1  # 1表示端口被占用
    except Exception as e:
        print(f"检查端口占用时出错: {e}")
        return False

if __name__ == "__main__":
    print("Windows串口检测工具")
    print("=================")
    
    # 先尝试通过注册表获取COM端口
    reg_ports = list_com_ports_via_registry()
    
    # 再通过WMIC获取COM端口
    wmic_ports = list_com_ports_via_wmic()
    
    # 合并结果
    all_ports = set()
    for port, _ in reg_ports:
        all_ports.add(port)
    for port in wmic_ports:
        all_ports.add(port)
    
    if not all_ports:
        print("\n未找到任何可用的COM端口")
        sys.exit(1)
    
    # 选择要测试的端口
    if "COM5" in all_ports:
        test_port = "COM5"
        print(f"\n将测试您提到的 {test_port} 端口")
    else:
        test_port = sorted(list(all_ports))[0]
        print(f"\n未找到COM5端口，将测试第一个可用端口: {test_port}")
    
    # 检查端口是否被占用
    if check_port_is_in_use(test_port):
        print(f"\n警告: {test_port} 当前被其他进程占用")
        print("请关闭所有可能使用此端口的程序后重试")
    else:
        # 尝试通过PowerShell测试端口
        check_port_via_powershell(test_port)
    
    print("\n测试完成") 