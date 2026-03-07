# Go1 全链路诊断报告

> 日期: 2026-03-05 → 2026-03-06 | 连接方式: Phase 1 WiFi(Pi) → Phase 2 网线直连(绕过Pi)

## 连接概览

| 项目 | 状态 | 详情 |
|------|------|------|
| WiFi AP | ✅ | Unitree_Go116748A, 5GHz AC ch165, pwd=00000000 |
| Ping | ✅ | 192.168.12.1 → 1ms |
| SSH | ✅ | pi@192.168.12.1, pwd=123, OpenSSH 7.9p1 |
| MQTT | ✅ | 1883端口, 10主题, ~15msg/s |
| HTTP:80 | ✅ | UnitreeRobotics WebUI (Vue.js) |
| HTTP:8080 | ✅ | UnitreeUpdate WebUI |
| TCP端口 | ✅ | 22, 80, 1883, 8080, 9800, 9801 |
| 摄像头UDP | ❌ | 9101-9105 全部无数据 |
| 内部以太网 | ❌ | eth0 NO-CARRIER, 所有内部板子不可达 |

## 系统信息

| 项目 | 值 |
|------|-----|
| 硬件 | Raspberry Pi Compute Module 4 Rev 1.0 (BCM2835, aarch64) |
| OS | Debian 10 (buster) |
| 内核 | 5.4.81-rt45-v8+ PREEMPT_RT |
| 内存 | 1.8GB (529MB used, 811MB free) |
| 磁盘 | 29GB (19GB used, 69%) |
| CPU温度 | 46.2°C |
| Python | 3.7.3 + 2.7.16 |
| App版本 | 1.38.0 |
| SportMode | 1.38.0 ([Wait] for check) |
| UTrack | 3.9.4 |

## 🔴 根因问题: 内部以太网断开

### 症状
- `eth0: <NO-CARRIER,BROADCAST,MULTICAST,UP> state DOWN`
- dmesg: `bcmgenet fd580000.ethernet: failed to get enet clock`
- dmesg: `bcmgenet fd580000.ethernet eth0: Link is Down`
- 所有内部IP不可达: 192.168.123.13/14/15/161/10 全部DEAD

### 影响
| 影响项 | 说明 |
|--------|------|
| robot/state全零 | MCU无法通信, SportMode显示 `[Wait] for check` |
| bms/state全零 | BMS板不可达, 无法监控电池 |
| firmware/version部分零 | 内部板固件版本不可获取 |
| 无摄像头 | Jetson Nano不可达, 无camera进程 |
| 无电机控制 | MCU不可达, standUp等命令无法执行 |
| 无IMU数据 | 传感器数据经MCU→Nano→Pi, 链路断开 |

### 可能原因
1. **Pi CM4→内部交换机的以太网线缆松动/断开** (最可能)
2. **内部以太网交换机未通电** (电源问题)
3. **BCM2711 RGMII时钟故障** (dmesg报`failed to get enet clock`)
4. **Pi CM4以太网PHY硬件故障**

### 建议操作
1. **物理检查**: 打开Go1头部外壳, 检查Pi CM4的以太网排线连接
2. **检查内部供电**: 确认机身内部Nano板和交换机LED是否亮起
3. **如果线缆正常**: 可能需要检查CM4的dt-blob.bin以太网配置
4. **临时方案**: 通过USB/串口连接MCU (如果有RS485适配器)

## MQTT主题 (10个)

| 主题 | 频率 | 数据 |
|------|------|------|
| robot/state | ~13Hz | 84B二进制 (全零 — MCU不可达) |
| bms/state | ~0.5Hz | 34B二进制 (全零) |
| firmware/version | ~0.5Hz | 44B二进制 (部分零, 末尾0xa88f) |
| controller/current_action | ~0.5Hz | 空字符串 |
| usys/run | 1次 | "ok" |
| usys/version/app | 1次 | "1.38.0" |
| usys/version/raspi | 1次 | 完整版本字符串 |
| controller/run | 1次 | "ok" |
| programming/run | 1次 | "on" |
| programming/current_action | 1次 | "stop" (发命令后变"run"再变"stop") |

## 正在运行的服务

### 系统服务
mosquitto(MQTT), nginx(Web), dnsmasq(DHCP), ssh, ntp, lightdm(X11)

### ROS Melodic 节点 (7个)
- rosout, roslaunch
- node_lcm (LCM通信, 11.9%CPU, 142MB)
- node_obstacle_traverse (10.1%CPU, 140MB)
- node_obstacle_avoidance (3.5%CPU, 141MB)
- ros2udp_motion_mode_adv (10.5%CPU, 63MB)
- ukd_triple_udp_node + ukd_triple_2_goal (utrack)

### 核心进程
- Legged_sport (sportMode, 1.3%CPU, 31MB) — `[Wait] for check`
- programming.py (MQTT控制入口)
- appTransit (应用程序通信)

## 网络拓扑

```
  [PC笔记本] 192.168.12.251 ──WiFi──→ [Go1 Pi CM4] 192.168.12.1
       │                                    │
  以太网 192.168.31.55                      eth0 (NO-CARRIER!) ──×──→ 内部交换机
       │                                                              │ (不可达)
  [路由器] 192.168.31.1                              ┌────────────────┼────────────┐
       │                                              │                │            │
    Internet                                    [Head Nano]      [Body Nano]    [MCU]
                                              192.168.123.13   192.168.123.14   电机/IMU/BMS
```

## DHCP历史租约
| IP | 设备名 |
|----|--------|
| 192.168.12.28 | (未知) |
| 192.168.12.102 | Tab S7 |
| 192.168.12.104 | Note20 Ultra |
| 192.168.12.79 | zhoumac (历史) |
| 192.168.12.251 | DESKTOP-MASTER (当前) |

## WiFi AP配置 (hostapd)
- interface: wlan1
- hw_mode: a (5GHz)
- 802.11ac + 802.11n
- channel: 165
- VHT bandwidth: 80MHz
- WPA2-PSK, CCMP

## 已知问题清单

| # | 级别 | 问题 | 根因 | 状态 |
|---|------|------|------|------|
| 1 | 🔴 | eth0 NO-CARRIER | 物理连接/硬件 | 需物理检查 |
| 2 | 🔴 | 状态数据全零 | #1导致MCU不可达 | 阻塞于#1 |
| 3 | 🔴 | 无摄像头流 | #1导致Nano不可达 | 阻塞于#1 |
| 4 | 🔴 | 电机控制不可用 | #1导致MCU不可达 | 阻塞于#1 |
| 5 | ✅ | 系统时钟错误(2021年) | RTC电池耗尽+无互联网NTP | **已修复** (2026-03-05 18:07确认正确) |
| 6 | ✅ | rc-local.service失败 | GPIO 18 export冲突 | **已修复** (systemctl --failed = 0) |
| 7 | ✅ | NTP无法解析 | Go1无互联网 | **已修复** 笔记本IP转发+dnsmasq上游DNS(8.8.8.8) |
| 8 | ✅ | WiFi适配器5G优先 | 笔记本Preferred Band=5G | 已通过断开重扫解决 |
| 9 | ✅ | FollowBehavior崩溃 | `ps.yaw` → `ps.yaw_deg` AttributeError | **已修复** (37/37 PASS) |

## 可正常工作的功能

尽管内部以太网断开，以下功能通过WiFi仍可使用:
- ✅ SSH远程访问和文件操作
- ✅ MQTT消息收发 (programming/controller主题)
- ✅ Web UI访问 (端口80和8080)
- ✅ ROS节点运行 (但无传感器数据)
- ✅ Go1文件系统完全访问
- ✅ Go1软件配置和更新

## 最新测试结果 (2026-03-05 19:10)

| 测试套件 | 结果 | 备注 |
|----------|------|------|
| go1_test.py --skip-motor | 5/0/2 PASS | MQTT消息初始化延迟+摄像头UDP |
| _brain_test.py | 37/37 PASS | FollowBehavior修复后全通 |
| go1_rl.py --test | 13/13 PASS | 14参考项目, 46预训练模型 |
| _e2e_dashboard_test.py | 14/14 PASS | GET+POST全API+Dashboard UI |
| go1_test.py --action standUp | ✅已发送 | MCU不可达(无物理响应) |

## eth0全部尝试记录

```
# 尝试1: sudo ip link set eth0 down/up → NO-CARRIER (Session 1)
# 尝试2: 用户重接排线 + sudo ip link set eth0 down/up → NO-CARRIER
# 尝试3: modprobe -r genet → "Module genet is builtin" 无法热重载
# 尝试4: 用户重接排线 + 完全重启Go1 → 启动后仍 NO-CARRIER
# dmesg: [8.139] Link is Down (开机即下) → 硬件故障确认
# 结论: 排线可能损坏或内部交换机/PHY故障
```

## USB-Ethernet替代方案

> **推荐方案**: 买一个USB以太网适配器(RTL8153/AX88179)，插Go1 USB Hub端口4，配置192.168.123.x地址。

```
# Go1 USB拓扑:
# Bus1.Port1: root_hub (dwc2, 480M)
#   └─ Port1: USB 2.0 Hub (4口)
#       └─ Port4: Realtek WiFi (rtl88x2cu)
#       └─ Port1-3: 空闲 ← 插USB-Ethernet适配器
#
# 配置步骤:
# 1. 插入USB-Ethernet适配器，确认出现eth1
# 2. sudo ip addr add 192.168.123.161/24 dev eth1
# 3. sudo ip link set eth1 up
# 4. 连接线插入Go1内部交换机空闲端口
# 5. ping 192.168.123.13 (Nano) / .14 / .15
```

## 数据文件

- `go1_ssh_data.json` — SSH系统信息 (39/41项)
- `go1_mqtt_http_data.json` — MQTT+HTTP+摄像头数据
- `go1_deep_diag.json` — 深度诊断数据
- `_go1_board_scan.json` — Phase 2 三块Nano板SSH深度扫描
- `_go1_hardware_state.json` — Phase 2 MCU原始UDP电机数据

---

## Phase 2: 网线直连内部交换机 (2026-03-06)

> 绕过Pi故障eth0，网线直连Go1内部交换机，PC IP=192.168.123.200/24

### Phase 2 连接概览

| 项目 | 状态 | 详情 |
|------|------|------|
| MCU (.10) | ✅ alive | UDP:8007响应820字节，MAC=00:80:e1:00:00:00 |
| Nano头 (.13) | ✅ SSH | Jetson Nano 4GB, 2摄像头, 超声波, UART, faceLED, wsaudio |
| Nano身 (.14) | ✅ SSH | Jetson Nano 4GB, 2摄像头, mqttControlNode(AI), SDK文件 |
| Nano尾 (.15) | ✅ SSH | Jetson Nano 4GB, 1摄像头, 空闲 |
| Pi (.161) | ❌ dead | 从所有Nano和PC均不可达, ARP=INCOMPLETE |
| Pi WiFi (.12.1) | ❌ dead | 从所有Nano不可达 |

### 内部板子详细信息

| 板子 | IP | OS/内核 | RAM | 磁盘 | 温度 | 负载 | Python |
|------|-----|---------|-----|------|------|------|--------|
| Nano头 | .13 | L4T 4.9.140-tegra aarch64 | 4GB (949M用) | 59G(29%) | 52°C | 1.40 | 3.6.9 |
| Nano身 | .14 | L4T 4.9.140-tegra aarch64 | 4GB (1052M用) | 59G(30%) | 46°C | 0.80 | 3.6.9 |
| Nano尾 | .15 | L4T 4.9.140-tegra aarch64 | 4GB (1311M用) | 59G(30%) | 41°C | 0.07 | 3.6.9 |

### USB设备清单

| 板子 | 设备 |
|------|------|
| .13 | USB Hub + 2×Sunplus摄像头 + C-Media音频 + **CP210x UART**(→MCU串口) |
| .14 | USB Hub + 2×Sunplus摄像头 |
| .15 | 1×Sunplus摄像头 |

### 摄像头映射 (5个)

| 板子 | 设备 | ROS Config | 角色 |
|------|------|-----------|------|
| .13 | video0+video1 | camera1 (stereo_config1) | 头部立体相机 |
| .14 | video0+video1 | camera3+camera4 (stereo_config+config1) | 身体立体相机×2 |
| .15 | video0 | camera5 (stereo_config) | 尾部单目相机 |

### 关键进程

| 板子 | 进程 | CPU | 功能 |
|------|------|-----|------|
| .13 | cameraRosNode (camera1) | - | 头部点云 |
| .13 | **ultrasonic2udp_client** (root) | - | 超声波距离传感器 |
| .13 | **ukd2udp_client** (root) | - | UKD传感器 |
| .13 | **faceLightServer** (root) | - | 人脸LED灯控 |
| .13 | **wsaudio** | **104%** | WebSocket音频流(端口8765) |
| .14 | cameraRosNode (camera3+4) | - | 身体点云×2 |
| .14 | **mqttControlNode** | **57%** | 神经网络AI推理(SNNL) |
| .15 | cameraRosNode (camera5) | - | 尾部点云 |

### 网络服务 (每个Nano)

| 端口 | 服务 |
|------|------|
| 22 | SSH (OpenSSH) |
| 1883 | MQTT (Mosquitto, 本地broker) |
| 111 | RPC |
| 53 | DNS (127.0.0.53, systemd-resolved) |
| 8765 | wsaudio (.13 only) |

### mqttControlNode配置 (.14)

```yaml
mqtt.address: "tcp://192.168.123.161:1883"  # ← Pi! 不可达!
platform: "SecNanoLeft"
MNAddress: "192.168.123.15"  # 与.15通信
camera.calibPath: "../config/"
camera.cWidth: 464, cHeight: 400
version: "1.0.3"
```

> mqttControlNode试图连接Pi的MQTT broker但永远失败 — Pi eth0断开导致AI控制链断裂

### 网络拓扑 (Phase 2 更新)

```text
  [PC笔记本] 192.168.123.200 ──网线──→ [内部交换机] ←──eth0──→ [Pi CM4] .161 (eth0 NO-CARRIER!)
                                            │                         │
                                     ┌──────┼──────┐                 wlan1
                                     │      │      │              Unitree_Go1 WiFi
                                  [Nano头] [Nano身] [Nano尾]      192.168.12.1
                                   .13     .14     .15
                                     │
                                  [MCU STM32] .10 (UDP:8007)
                                  电机×12 + IMU + BMS
```

### ☲离·缺腿诊断 (MCU直读)

> 通过原始UDP发送LowCmd到MCU:8007，接收820字节LowState

| 电机 | 腿 | 角度(°) | 角速度 | 扭矩 | 状态 |
|------|-----|---------|--------|------|------|
| 0 FR_hip | 前右 | 69.4 | -0.003 | 0 | ✅ |
| 1 FR_thigh | 前右 | -160.6 | -0.002 | 0 | ✅ |
| 2 FR_calf | 前右 | -10.1 | 0.006 | 0 | ✅ |
| 3 FL_hip | **前左** | **0.0** | **0.0** | 0 | **❌ 断开** |
| 4 FL_thigh | **前左** | **0.0** | **0.0** | 0 | **❌ 断开** |
| 5 FL_calf | 前左 | -41.4 | 0.0001 | 0 | ⚠️ 残留 |
| 6 RR_hip | 后右 | 84.0 | 0.003 | 0 | ✅ |
| 7 RR_thigh | 后右 | -161.0 | 0.006 | 0 | ✅ |
| 8 RR_calf | 后右 | 43.1 | -0.015 | 0 | ✅ |
| 9 RL_hip | 后左 | 37.1 | -0.008 | 0 | ✅ |
| 10 RL_thigh | 后左 | -161.5 | 0.001 | 0 | ✅ |
| 11 RL_calf | **后左** | **0.0** | **0.0** | 0 | **⚠️ 可能损坏** |

**诊断结论: FL(前左腿)缺失** — hip和thigh电机编码器完全归零(无连接), calf有残留角度(小腿电机可能仍物理连接但上部结构缺失)

> 所有扭矩=0: SportMode未运行(正常，Pi不可达无法启动)
> 足部力传感器: 全部为0 (未着地或需Pi控制链)
> 电池SOC: ≈36%

### Phase 2 问题清单 (更新)

| # | 级别 | 问题 | 根因 | 状态 |
|---|------|------|------|------|
| 1 | 🔴 | Pi eth0 NO-CARRIER | 排线损坏/PHY故障 | 需物理维修 |
| 2 | 🔴 | **FL(前左)腿缺失** | hip+thigh电机断开 | 需物理检查 |
| 3 | 🔴 | SportMode无法启动 | 依赖Pi(不可达) | 阻塞于#1 |
| 4 | 🔴 | WiFi热点不可见 | Pi不可达 | 阻塞于#1 |
| 5 | 🔴 | mqttControlNode连不上Pi MQTT | Pi:1883不可达 | 阻塞于#1 |
| 6 | 🟡 | RL(后左)calf电机归零 | 电机损坏或线缆松 | 需物理检查 |
| 7 | 🟡 | SDK .so不兼容 | 需Python3.7+, Nano为3.6.9 | 用原始UDP绕过 |
| 8 | 🟡 | wsaudio占104% CPU | 可能音频设备异常 | 可kill |
| 9 | 🟡 | 系统时钟2021年 | Nano无RTC+无NTP | 可通过SSH设置 |
| 10 | ℹ️ | IMU标准偏移不匹配 | 固件LowState布局不同 | 需逆向分析 |
| 11 | ℹ️ | BMS数据部分有效 | 偏移量需微调 | SOC≈36%可信 |

### 凭据汇总

| 项目 | 用户名 | 密码 |
|------|--------|------|
| Nano SSH (.13/.14/.15) | unitree | 123 |
| Pi SSH (.161, WiFi) | pi | 123 |
| WiFi AP | - | 00000000 |

### 可执行的软件修复

1. **同步Nano时钟**: `ssh unitree@.13/14/15 "sudo date -s '2026-03-06 17:00:00'"`
2. **Kill wsaudio节省CPU**: `ssh unitree@.13 "kill $(pgrep wsaudio)"`
3. **MQTT本地化**: 修改mqttControlNode配置指向127.0.0.1:1883而非Pi
4. **安装pyserial**: `pip3 install pyserial` on .13 for UART调试

### 需物理干预的修复

1. **检查Pi CM4到内部交换机的排线** — 最可能原因
2. **USB-Ethernet适配器方案** — 给Pi插USB网卡绕过故障eth0
3. **检查FL腿电机连接器** — 确认是拔出还是线缆断
4. **检查RL calf电机** — 确认连接器状态

---

## Phase 3: Pi救援 + PC替代Pi (2026-03-06 01:16)

> Pi WiFi AP消失 → Pi断电/崩溃确认 → PC接管Pi角色

### Phase 3 探测结果 (13项)

| # | 探测 | 结果 |
|---|------|------|
| 1 | PC ping Pi(.161/.1/.12.1) | 全DEAD |
| 2 | Go1 WiFi AP扫描 | 不可见(Phase 1可见) |
| 3 | WiFi直连尝试 | "网络无法用于连接" |
| 4 | Nano→Pi ping | 3板全DEAD |
| 5 | Nano→Pi TCP(22/80/1883/8080) | 全closed |
| 6 | PC→Pi TCP(22/80/1883/8080/9800/9801) | 全closed |
| 7 | 子网扫描(.1-.20/.100-.170/.200-.255) | 仅.13/.14/.15/.200, 无Pi |
| 8 | Nano WiFi模块 | 3板均无WiFi |
| 9 | ARP .161 | INCOMPLETE(无MAC) |
| 10 | UART(CP210x) | →MCU串口,非Pi |
| 11 | Nano网络接口 | 仅eth0+dummy0 |
| 12 | USB设备树 | 无USB-Ethernet |
| 13 | 内部交换机管理口 | .1/.2/.254全无响应 |

**结论: Pi完全失联 — WiFi AP消失证实Pi断电或内核崩溃**

### PC替代Pi方案 (已实施)

#### MQTT重定向 (iptables DNAT)
```bash
# 在每个Nano上执行(已完成):
sudo iptables -t nat -A OUTPUT -d 192.168.123.161 -p tcp --dport 1883 \
  -j DNAT --to-destination 127.0.0.1:1883
```
- .13 ✅ DNAT已添加, 本地Mosquitto运行
- .14 ✅ DNAT已添加, 本地Mosquitto运行
- .15 ✅ DNAT已添加, 本地Mosquitto运行

> mqttControlNode(.14, 53.5%CPU)现在连接本地broker而非Pi

#### PC→MCU直连UDP (已验证)
```
PC(192.168.123.200) → UDP:8007 → MCU(192.168.123.10)
LowCmd(614B) → LowState(820B), <1ms延迟
```

#### IMU数据解析 (offset=10, 首次成功!)

| 数据 | 偏移 | 值 |
|------|------|-----|
| 四元数 | 10-25 | [0.976, -0.015, -0.003, -0.216] \|q\|=1.0000 |
| 角速度 | 26-37 | [-0.012, -0.004, 0.010] rad/s |
| 加速度 | 38-49 | [0.13, -0.29, 9.64] m/s² (≈g) |
| RPY | 50-61 | Roll=-1.6° Pitch=-0.7° Yaw=-24.9° |

#### LowState完整布局 (820字节, Go1固件)

| 偏移 | 大小 | 内容 |
|------|------|------|
| 0-1 | 2B | head: 0xFF 0x1E |
| 2-9 | 8B | levelFlag + SN |
| 10-25 | 16B | quaternion[4] (float×4) |
| 26-37 | 12B | gyroscope[3] (float×3) |
| 38-49 | 12B | accelerometer[3] (float×3) |
| 50-61 | 12B | rpy[3] (float×3) |
| 62-95 | 34B | 温度+保留 |
| 96-479 | 384B | motorState[12] (32B×12) |
| 480-487 | 8B | footForce[4] (int16×4) |
| 488-819 | 332B | BMS+遥控器+保留+CRC |

#### 电池状态
- SOC: 45% (Phase 2时36%, 正在充电)

### Phase 3 问题清单更新

| # | 级别 | 问题 | 状态 |
|---|------|------|------|
| 1 | 🔴 | Pi断电/崩溃(WiFi AP消失) | **需物理检查Pi电源LED** |
| 2 | 🔴 | FL前左腿缺失 | 需物理检查 |
| 3 | ✅ | MQTT断裂 | **已修复(iptables DNAT)** |
| 4 | ✅ | IMU数据解析 | **已修复(offset=10)** |
| 5 | ✅ | PC→MCU通信 | **已建立(直连UDP)** |
| 6 | ✅ | 时钟同步 | **已修复(3板2026年)** |
| 7 | 🟡 | SportMode无法启动 | 需Pi或PC替代 |
| 8 | 🟡 | RL_calf电机归零 | 需物理检查 |

### Pi物理检查清单

1. **Pi CM4 LED** — 红灯=有电, 不亮=断电
2. **Pi→交换机排线** — 两端是否牢固
3. **WiFi dongle** — LED是否亮
4. **电源排线** — 拔插重试(断开5秒)
5. **如有电但eth0不通** — 插USB-Ethernet适配器
