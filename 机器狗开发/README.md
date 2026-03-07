# 宇树 Go1 机器狗开发

> 宇树科技 Go1 四足机器人的电机控制、逆运动学、MQTT通信、网络诊断资源汇总。

## 项目结构

```
机器狗开发/
├── gooddawg/                    # 核心：Go1电机直接控制库 (RS485)
│   ├── build_a_packet.py        # 通信协议实现（CRC32+数据包构建+串口）
│   ├── example_dead_simple.py   # 单电机正弦波测试
│   ├── example_cartesian_arm.py # 2关节笛卡尔空间控制（逆运动学+雅可比）
│   ├── example_square.py        # G-code路径跟踪（五角星/爱心/方形）
│   ├── test_motor_com5.py       # Windows COM5端口电机测试
│   ├── calibration/             # 电机角度标定工具
│   │   ├── 1_calibrate_angle.py
│   │   ├── 2_calibrate_motor.py
│   │   └── 3_linear_fit_from_LUT.py
│   └── unitree_crc/             # CRC校验C++参考实现 (Go1/Go2/G1)
├── 电机测试/                     # Windows环境下的电机通信调试脚本集
│   ├── scan_all_ports.py        # 扫描所有串口+波特率+电机ID
│   ├── check_com_windows.py     # Windows串口诊断
│   ├── debug_motor.py           # 电机通信调试
│   └── ...                      # 30+调试脚本
├── YushuTech参考/                # YushuTechUnitreeGo1 社区参考资料
│   ├── README.md                # 75KB Go1逆向工程百科(硬件/固件/网络/漏洞)
│   ├── paho_mqtt_example.py     # MQTT控制Go1行走
│   ├── programming.py           # Go1编程接口
│   ├── unitree_tunnel_manager.py # Go1隧道管理器
│   └── ...                      # 固件更新/摄像头/启动管理
├── go1_test.py                  # 一键全功能诊断 (T1-T7: Ping/SSH/MQTT/摄像头/电机)
├── go1_control.py               # 统一控制入口 (MQTT双模式+交互式控制台)
├── go1_sim.py                   # MuJoCo仿真v2.1 (7步态+IMU+Gym RL+地形+--json/--quiet)
├── go1_brain.py                 # Agent中枢大脑v2.0 (五感→情感→决策→执行+HTTP API)
├── go1_rl.py                    # RL集成模块 (Gymnasium环境+PPO训练+策略推理, 13/13 PASS)
├── tools/
│   └── setup_ethernet.ps1       # 以太网连接配置 (WiFi不断连)
├── docs/
│   └── WiFi开发全流程.md         # 双网络开发完整指南
├── refs/                        # GitHub开源资源整合 (详见 refs/README.md)
│   ├── free-dog-sdk/            # 纯Python UDP SDK (218★, 替代C++ SDK)
│   ├── go1pylib/                # MQTT高层控制库 (async运动/LED/模式)
│   ├── setup-guide/             # Go1内部网络架构+SSH配置
│   ├── mujoco-menagerie/        # Go1 MuJoCo官方模型 (DeepMind, URDF+STL)
│   ├── unitree-ros2-sim/        # Go1 Gazebo ROS2仿真 (46★)
│   ├── maestro-mujoco/          # MuJoCo四足滑面控制 (17★)
│   ├── go1-voice-control/       # Go1语音控制SDK (16★)
│   ├── legged-mpc/              # MPC四足控制器 (64★)
│   ├── quadruped-rl-locomotion/ # Go1 RL Gymnasium环境+28个预训练PPO模型 (123★)
│   ├── rl_sar/                  # 多机器人RL sim2sim部署+策略权重 (1161★)
│   ├── unitree-go2-mjx-rl/      # MuJoCo XLA GPU加速RL训练 (19★)
│   ├── unitree-mujoco/          # 官方Unitree MuJoCo仿真器 (Go2/G1/H1)
│   ├── GenLoco/                 # 多机器人泛化步态控制含Go1 (HybridRobotics)
│   └── DRLoco/                  # DeepMimic+MuJoCo+SB3运动模仿
└── requirements.txt             # Python依赖: pyserial, paho-mqtt, opencv, numpy, mujoco, gymnasium, sb3, torch
```

## AI大脑 v2.0 架构

```
五感输入              情感引擎              行为决策              后端执行
┌──────┐         ┌───────┐         ┌────────┐         ┌──────┐
│ 视/听  │─────→│ calm  │─────→│ 11行为  │─────→│ Sim  │
│ 触/嗅  │         │ happy │         │ 安全优先 │         │ Real │
│ 味/IMU│         │ alert │         │ 强制可断 │         │ MQTT │
└──────┘         └───────┘         └────────┘         └──────┘
     │                  │                  │
     └─────────────────┴─────────────────┘
           空间地图  ·  健康监测  ·  持久记忆  ·  HTTP API(:8085)
```

**v2.0 新特性**:
- **五感感知**: 视觉(障碍物+地形) / 听觉(声音事件) / 触觉(IMU+足力) / 嗅觉(电量) / 味觉(健康)
- **情感引擎**: 8种情绪(calm/happy/curious/alert/tired/scared/excited/lonely) + LED颜色映射
- **11行为**: stand/patrol/dance/explore/play/greet/guard/follow/rest/recover/balance
- **安全行为可中断**: recover/balance/rest 可中断任何强制行为
- **空间地图**: 10m×10m栅格地图 + 覆盖率跟踪 + 障碍物标记
- **健康监测**: 电量/温度/里程/故障诊断
- **持久记忆**: JSON文件存储 + 地点记忆 + 统计数据
- **人机交互**: 自然语言命令 + 语音回应 + 情感反馈
- **HTTP API**: REST接口 GET/POST 远程控制

```bash
# 基础命令
python go1_brain.py                          # sim站立
python go1_brain.py -b patrol -d 30          # sim巡逻30s
python go1_brain.py -b play -d 15            # 互动玩耍
python go1_brain.py --cmd "say 你好"          # 语音交互
python go1_brain.py --cmd emotion             # 查看情感状态
python go1_brain.py --cmd health              # 健康诊断
python go1_brain.py --cmd "remember home"     # 记住当前位置
python go1_brain.py --api -d 300              # 启动HTTP API服务器

# HTTP API (启动后)
curl http://localhost:8085/status             # 感知状态
curl http://localhost:8085/emotion            # 情感状态
curl http://localhost:8085/health             # 健康报告
curl -X POST http://localhost:8085/cmd -d "dance"   # 执行命令
curl -X POST http://localhost:8085/say -d "过来"  # 自然语言
```

## 外部资源索引（未拷贝，体积大）

| 位置 | 内容 | 大小 |
|------|------|------|
| `E:\unitree\unitree_legged_sdk-3.4.2` | 官方C++ SDK (Go1 UDP通信) | ~2MB |
| `E:\unitree\unitree_legged_sdk-3.8.0` | 官方C++/Python SDK (含Python绑定) | ~1MB |
| `E:\unitree\GO-M8010-6 资料包` | 电机3D模型+尺寸图+数据手册 | ~13MB |
| `E:\unitree\GO-M8010-6电机使用教程` | 教程视频(Linux/STM32/Windows) | ~670MB |
| 笔记本 `E:\道\轮毂电机` | ZLTECH轮毂电机调试软件 | ~23MB |

## 硬件需求

- **Go1机器人** — IP: `192.168.12.1`, SSH: `pi@192.168.12.1`
- **USB-RS485适配器** — 推荐 Robotis U2D2，必须支持 **5Mbps** 波特率
- **电源** — 23-25V（低电压会导致brownout）
- **串口** — Windows: COM5 (CH343), Linux: /dev/ttyUSB0

## 网络连接

Go1有两种网络连接方式：

**WiFi连接** (推荐调试用):
- Go1开机后自动广播WiFi热点，SSID: `Unitree_Go1XXXXX`
- 密码: `00000000`
- 连接后Go1 IP: `192.168.12.1`

**有线连接** (推荐高带宽用):
- 网线插入Go1头部网口
- **直连模式**: 电脑配IP `192.168.12.100/24`, Go1 IP: `192.168.12.1`
- **Mesh模式**: 电脑配IP `192.168.123.162/24`, Go1 IP: `192.168.123.161` (go1_control.py默认)

**Go1内部网络架构**:
- `192.168.12.1` — 主控Nano (MQTT Broker + SSH), WiFi和直连共用
- `192.168.123.161` — 外部Mesh网络 (以太网专用, UDP高层通信)
- MQTT端口: `1883` (TCP), `80` (WebSocket)
- SSH: `pi@192.168.12.1`

## 一键诊断

```bash
python go1_test.py              # 全功能诊断 (自动检测T1-T7)
python go1_test.py --skip-motor  # 跳过RS485电机测试
python go1_test.py --action standUp  # 发送站立命令
```

## 快速开始

```bash
pip install -r requirements.txt

# 单电机正弦波测试 (motor_id=0, 自动检测端口)
cd gooddawg
python example_dead_simple.py 0

# 指定端口
python example_dead_simple.py 0 COM5

# 2关节笛卡尔空间控制（需连接2个电机）
python example_cartesian_arm.py

# G-code路径跟踪（五角星）
python example_square.py
```

## 通信协议

Go1电机使用RS485总线，5Mbps波特率，自定义协议：

```
包结构: [Header:FEEE] [MotorID:1B] [Reserved:9B] [Torque:2B] [Velocity:2B] [Position:4B] [Kp:1B] [Reserved:1B] [Kd:2B] [Reserved:6B] [CRC32:4B]
总长度: 32 bytes
```

**控制模式**（通过参数组合切换）：
- **位置控制**: 设置 `q`(目标角度) + `Kp`>0 + `Kd`>0
- **速度控制**: 设置 `Kp=0` + `dq`(目标速度) + `Kd`>0
- **力矩控制**: 设置 `Kp=0, Kd=0` + `tau`(力矩)

## 已知问题与解决方案

| 问题 | 根因 | 解决 |
|------|------|------|
| COM5/COM7 "拒绝访问" | 串口被其他程序占用 | 重启电脑或在设备管理器禁用再启用 |
| COM1无电机响应 | 标准串口非RS485，波特率上限115200 | 必须使用USB-RS485适配器(COM5/COM7) |
| 所有电机ID无响应 | 电机未供电或RS485接线错误 | 确认23-25V供电 + A+/B-/GND接线 |
| 波特率不支持5Mbps | 适配器芯片限制(CH340仅1Mbps) | 使用CH343或U2D2适配器 |
| 以太网Disconnected | Go1未开机或网线松动 | 确认Go1开机(30秒)且网线两端插好 |
| Ping 192.168.12.1超时 | 电脑不在12.x子网 | 配置以太网IP为192.168.12.100/24或连WiFi |
| Go1 WiFi AP不可见 | Go1未开机或WiFi模块故障 | 等待Go1完全启动(约30-60秒) |
| MQTT连接失败 | 网络不通或Broker未运行 | 先确认ping通，再检查1883端口 |

## 凭据

见 `secrets.env`：`GO1_IP`, `GO1_USER`, `GO1_SSH_KEY`

## 致谢

- [gooddawg](https://github.com/imcnanie/gooddawg) — Go1电机直接控制
- [unitree_crc](https://github.com/aatb-ch/unitree_crc) — CRC逆向
- [YushuTechUnitreeGo1](https://github.com/YushuTech/UnitreeGo1) — Go1逆向百科
- [free-dog-sdk](https://github.com/Bin4ry/free-dog-sdk) — 开源Go1 SDK
- [unitree_legged_sdk](https://github.com/unitreerobotics/unitree_legged_sdk) — 官方SDK
