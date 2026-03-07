# VaM × ORS6 生态资源索引

> 统一索引本项目及相关VaM/ORS6资源，三位一体。

## 核心项目: ORS6-VAM饮料摇匀器 (本目录)

| 模块 | 路径 | 功能 |
|------|------|------|
| **Hub中枢** | `ors6_hub.py` + `hub.html` | HTTP+WS服务器, Three.js 3D可视化, 42种运动模式, 20项测试 |
| **TCode协议** | `tcode/protocol.py` | TCode v0.3编解码, 11轴(L0-L2,R0-R2,V0-V1,A0-A2) |
| **虚拟设备** | `tcode/virtual_device.py` | 120Hz模拟SR6, 9轴伺服+IK |
| **串口连接** | `tcode/serial_conn.py` | USB串口115200bps |
| **WiFi连接** | `tcode/wifi_conn.py` | UDP无线控制 |
| **BLE连接** | `tcode/ble_conn.py` | 蓝牙低功耗控制 |
| **TempestStroke** | `tcode/tempest_stroke.py` | 42种运动模式(orbit-tease, long-stroke等) |
| **VaM桥接** | `vam_bridge/bridge.py` | AgentBridge HTTP轮询 + TSC UDP监听两种模式 |
| **Funscript** | `funscript/parser.py` + `player.py` | 脚本解析+多轴同步播放 |
| **视频同步** | `video_sync/pipeline.py` | 抖音/Bilibili下载→节拍检测→Funscript生成 |
| **Hip追踪** | `hip_sync.html` | MediaPipe姿态→ORS6实时同步 |
| **工具** | `tools/` | 固件烧录, 舵机测试, 校准 |

## 关联项目: VAM-agent

| 路径 | 功能 | 集成方式 |
|------|------|---------|
| `../VAM-agent/vam/` | VaM 3D引擎自动化(场景/资源/插件管理) | Python import |
| `../VAM-agent/voxta/` | Voxta AI对话引擎(TTS/STT/LLM) | HTTP API |
| `../VAM-agent/browser_bridge/` | 桌面应用浏览器化 | WebSocket |
| `../VAM-agent/master.py` | VaM+Voxta统一编排 | CLI调用 |

**集成点**: VAM-agent的VaM自动化可用于自动加载场景并配置角色控制器，然后由本项目的VaM Bridge实时桥接角色动作到ORS6设备。

## 关联项目: YAVAM

| 路径 | 功能 | 集成方式 |
|------|------|---------|
| `../YAVAM/` | Go+React桌面应用, .var包管理器 | 独立运行 |

**集成点**: YAVAM管理VaM的.var资源包(场景/服装/插件等)，确保VaM运行时所需依赖完整。

## 通信架构

```
                    ┌─────────────┐
                    │  VaM 3D引擎  │
                    └──────┬──────┘
                           │ AgentBridge HTTP / TSC UDP
                    ┌──────┴──────┐
                    │  VaM Bridge  │  vam_bridge/bridge.py
                    └──────┬──────┘
                           │ TCode命令
              ┌────────────┼────────────┐
              │            │            │
        ┌─────┴─────┐ ┌───┴───┐ ┌─────┴─────┐
        │ USB Serial │ │ WiFi  │ │   BLE     │
        │  115200bps │ │  UDP  │ │  GATT     │
        └─────┬─────┘ └───┬───┘ └─────┬─────┘
              └────────────┼────────────┘
                    ┌──────┴──────┐
                    │  ORS6/SR6   │
                    │  6轴机器人   │
                    └─────────────┘
```

## 端口分配

| 服务 | 端口 | 协议 |
|------|------|------|
| ORS6 Hub | 8086 (默认) | HTTP+WS |
| VaM AgentBridge | 8084 | HTTP |
| TSC UDP | 20777 | UDP |
| Go1 UDP | 8086 (冲突!用8096) | UDP |

## 启动命令

```bash
# Hub中枢 (虚拟设备)
python ors6_hub.py --port 8096 --no-browser

# Hub中枢 (真实设备)
python ors6_hub.py --serial COM6 --baud 115200

# VaM桥接 (AgentBridge模式)
python -m vam_bridge.bridge --mode agent --host localhost --port 8084

# VaM桥接 (TSC UDP模式)
python -m vam_bridge.bridge --mode tsc --udp-port 20777
```

## E2E测试结果 (2026-03-06)

| 测试项 | 结果 |
|--------|------|
| 协议测试 (8项) | 8/8 PASS |
| 设备测试 (8项) | 8/8 PASS |
| TempestStroke测试 (4项) | 4/4 PASS |
| API端点 (health/state/patterns/send/play/stop/history/test) | 全部200 OK |
| WebSocket连接 | 稳定 (B1超时修复已应用) |
| Hip Sync页面 | 200 OK |
| 3D可视化 | Three.js SR6模型+IK正常 |
