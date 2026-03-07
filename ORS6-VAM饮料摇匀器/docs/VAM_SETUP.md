# VaM × OSR6 配置指南

## 方案概览

| 方案 | 工具 | 连接方式 | 适用场景 |
|------|------|---------|---------|
| A | ToySerialController | VaM插件→Serial/UDP | VaM实时场景联动 |
| B | MultiFunPlayer | 外部播放器→Serial | 视频+Funscript同步 |
| C | AgentBridge | HTTP API→Python→Serial | 自定义集成 |
| D | Buttplug.io | 通用协议→多设备 | 多设备场景 |

## 方案A: ToySerialController (推荐)

### 安装
1. 下载: [VaM Hub #19853](https://hub.virtamate.com/resources/toyserialcontroller.19853/)
2. 解压到 VaM 的 `Custom/Scripts/` 目录
3. VaM中: 添加到Person原子 → Plugin → 搜索 ToySerialController

### 配置
1. **Serial模式**: 选择ESP32串口 (如COM5)
2. **UDP模式**: 输入ESP32 IP和端口 (如 192.168.1.100:8000)
3. **Motion Source**: 选择角色的运动部件 (通常是hipControl)
4. **轴映射**: ToySerialController自动映射6轴

### 测试
1. 加载一个动画场景
2. 观察设备是否跟随角色运动
3. 调整参数: 灵敏度、平滑度、行程范围

## 方案B: MultiFunPlayer

### 安装
1. 下载: [GitHub/Yoooi0/MultiFunPlayer](https://github.com/Yoooi0/MultiFunPlayer)
2. 运行 MultiFunPlayer.exe

### 配置
1. **设备**: 添加Serial Device → 选择COM口
2. **输入源**: 添加VaM WebSocket或视频播放器
3. **脚本**: 加载.funscript文件
4. **轴映射**: L0-L2, R0-R2 全部映射

### Funscript获取
- [ScriptAxis](https://scriptaxis.com) — 脚本库搜索
- [EroScripts论坛](https://discuss.eroscripts.com) — 社区脚本
- [FapTap](https://faptap.net) — 在线播放

## 方案C: AgentBridge (本项目)

### 前提
- VaM运行中，AgentBridge插件加载 (端口8084)
- ESP32通过USB连接

### 使用

```python
from vam_bridge import VaMTCodeBridge, BridgeConfig

config = BridgeConfig(
    vam_host="127.0.0.1",
    vam_port=8084,
    tcode_mode="serial",       # serial / wifi
    tcode_serial_port="COM5",
    vam_poll_hz=30,
    smoothing=0.3,
)

bridge = VaMTCodeBridge(config=config)

# 模式1: AgentBridge HTTP轮询
bridge.start(atom_name="Person", mode="agent_bridge")

# 模式2: 监听ToySerialController UDP输出
# bridge.start(mode="tsc")

input("按Enter停止...")
bridge.stop()
```

### 自定义轴映射

```python
config = BridgeConfig(
    axis_mapping={
        "hip_position_y": "L0",    # 骨盆Y → 行程
        "hip_position_z": "L1",    # 骨盆Z → 推进
        "chest_rotation_x": "R1",  # 胸部旋转X → 横滚
    },
    invert_axes=["L1"],  # 反转推进轴
    position_scale=1.5,  # 放大运动幅度
)
```

## 方案D: Buttplug.io

### 概述
[Buttplug.io](https://buttplug.io) 是通用设备控制协议。
通过 [Intiface Central](https://intiface.com/central/) 桥接。

### 配置
1. 安装 Intiface Central
2. 添加Serial设备 (ESP32)
3. VaM安装 Buttplug 插件
4. 连接 VaM → Intiface → ESP32

## 百度贴吧教程汇总

来源: [tieba.baidu.com/p/9218988520](https://tieba.baidu.com/p/9218988520)

### VaM连接OSR的方法:
1. **ToySerialController** — 直接Serial/UDP，最简单
2. **MultiFunPlayer** — 外部播放器中转
3. **Buttplug/Intiface** — 通用设备协议

## 常见问题

### Q: VaM检测不到串口？
- 确认ESP32 USB线是数据线(非充电线)
- 安装CP210x/CH340驱动
- 设备管理器检查COM口

### Q: 动作不同步/延迟大？
- 使用USB Serial (延迟最低)
- 降低VaM物理精度
- 增加ToySerialController平滑值
- WiFi模式确认在同一局域网

### Q: 行程太大/太小？
- ToySerialController: 调整Range参数
- 本项目: 调整 `position_scale` 和轴校准

### Q: 只有部分轴工作？
- 检查固件是否支持6轴 (部分固件默认2-3轴)
- 确认TCode命令格式正确 (D2查询设备支持)
