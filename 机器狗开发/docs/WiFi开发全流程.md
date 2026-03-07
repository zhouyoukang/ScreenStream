# Go1 WiFi开发全流程指南

> 目标：通过以太网连接Go1进行开发，同时保持PC WiFi(家庭网络)不断连。

## 网络架构

```
PC (台式机)
├── WiFi (WLAN): 周老板的WiFi → 192.168.31.x (互联网/Windsurf)
└── 以太网: Go1头部网口 → 192.168.123.162/24 (Go1开发)

Go1 内部网络 (4台电脑)
├── Raspberry Pi:    192.168.123.161 / 192.168.12.1 (主控/MQTT/WiFi AP)
├── Jetson Nano A:   192.168.123.13  (头部摄像头)
├── Jetson Nano B:   192.168.123.14  (机身)
└── Jetson Xavier NX: 192.168.123.15  (推理计算, GPU)
```

## 两个子网说明

| 子网 | 用途 | 接入方式 | 适用场景 |
|------|------|---------|---------|
| 192.168.12.x | Go1 WiFi AP客户端 | WiFi连接Go1 AP | 手机遥控/简单测试 |
| 192.168.123.x | Go1内部有线网络 | 以太网连Go1头部 | **开发/调试(推荐)** |

## 快速开始

### Step 1: 硬件连接

1. 网线插入Go1**头部**网口（不是尾部充电口旁边的）
2. 网线另一端插入PC以太网口
3. 开启Go1电源

### Step 2: 配置网络（管理员PowerShell）

```powershell
# 一键配置以太网连接Go1（WiFi不受影响）
cd d:\道\道生一\一生二\机器狗开发
.\tools\setup_ethernet.ps1 -Connect

# 查看状态
.\tools\setup_ethernet.ps1 -Status

# 断开恢复
.\tools\setup_ethernet.ps1 -Disconnect
```

### Step 3: 验证连通

```powershell
# 快速ping测试
ping 192.168.123.161    # Go1 Pi
ping 192.168.31.1       # 家庭路由器（验证WiFi仍在线）

# 全面诊断
python go1_test.py --host 192.168.123.161 --skip-motor
```

### Step 4: 开发

```python
# MQTT控制（以太网模式）
import paho.mqtt.client as mqtt
client = mqtt.Client()
client.connect("192.168.123.161", 1883)  # 注意：不是192.168.12.1
client.publish("controller/action", "standUp")

# UDP SDK（以太网模式）
from ucl.unitreeConnection import unitreeConnection, HIGH_WIRED_DEFAULTS
conn = unitreeConnection(HIGH_WIRED_DEFAULTS)  # 192.168.123.161:8082
```

## 开发工具链

### 1. 网络诊断

```bash
python go1_test.py --host 192.168.123.161 --skip-motor   # 以太网模式
python go1_test.py --host 192.168.12.1 --skip-motor      # WiFi模式
```

### 2. SSH访问Go1

```bash
ssh pi@192.168.123.161          # Raspberry Pi (密码: 123)
ssh unitree@192.168.123.13      # Nano A (头部, 密码: 123)
ssh unitree@192.168.123.14      # Nano B (机身, 密码: 123)
ssh unitree@192.168.123.15      # NX (推理, 密码: 123)
```

### 3. MQTT动作控制

```python
# 使用go1pylib（推荐）
from go1pylib import Go1, Go1Mode
dog = Go1(mqtt_options={"host": "192.168.123.161"})
dog.init()
dog.set_mode(Go1Mode.WALK)
await dog.go_forward(speed=0.25, duration_ms=2000)

# 使用原始MQTT
import paho.mqtt.client as mqtt
client = mqtt.Client()
client.connect("192.168.123.161", 1883)
# 动作: standUp / standDown / walk / run / dance1 / dance2 / damping
client.publish("controller/action", "standUp", qos=1)
```

### 4. UDP高层控制

```python
# 使用free-dog-sdk
from ucl.unitreeConnection import unitreeConnection, HIGH_WIRED_DEFAULTS
from ucl.highCmd import highCmd
from ucl.enums import MotorModeHigh, GaitType

conn = unitreeConnection(HIGH_WIRED_DEFAULTS)
conn.startRecv()
cmd = highCmd()
cmd.mode = MotorModeHigh.VEL_WALK
cmd.gaitType = GaitType.TROT
cmd.velocity = [0.3, 0]
conn.send(cmd.buildCmd())
```

### 5. 摄像头流

```python
# 需先SSH到Go1配置mqMNConfig.yaml指向PC IP
# 然后在PC运行StreamCamCross.py接收UDP视频流
python YushuTech参考/StreamCamCross.py
# UDP端口: 9101(前) 9102(下巴) 9103(左) 9104(右) 9105(底)
```

### 6. LED控制

```python
# MQTT LED
client.publish("programming/code", "child_conn.send('change_light(255,0,0)')")  # 红色

# go1pylib LED
dog.set_led_color(0, 255, 0)  # 绿色
```

## 故障排除

### 以太网显示Disconnected
- 检查网线是否插入Go1**头部**网口
- 检查Go1是否已开机（Go1启动约需90秒）
- 尝试换一根网线

### Ping 192.168.123.161 不通
- 运行 `.\tools\setup_ethernet.ps1 -Status` 检查IP配置
- 确认Go1已完全启动（电机初始化完成后约30秒）
- 检查防火墙是否阻止ICMP

### MQTT连接超时
- 确认使用 `192.168.123.161:1883`（以太网）而非 `192.168.12.1:1883`（WiFi）
- SSH到Pi检查MQTT broker: `sudo systemctl status mosquitto`
- 检查端口: `Test-NetConnection 192.168.123.161 -Port 1883`

### WiFi断连了
- `.\tools\setup_ethernet.ps1 -Status` 检查路由优先级
- WiFi Metric应<以太网Metric（WiFi=10, 以太网=100）
- 手动修复: `Set-NetIPInterface -InterfaceAlias "WLAN" -InterfaceMetric 10`

### Go1不响应MQTT动作命令
- 先发 `standUp`，等3秒，再发其他命令
- Go1可能处于低电量保护模式，检查BMS状态
- 确认Go1未处于 `damping`（阻尼/急停）模式

## 安全铁律

1. **测试前确保周围2米无障碍物**
2. **首次测试用 `standUp`/`standDown`，不要直接 `walk`**
3. **随时准备发送 `damping` 急停命令**
4. **低电量(<20%)时不执行运动命令**
5. **USB串口和网络控制不要同时操作同一电机**
