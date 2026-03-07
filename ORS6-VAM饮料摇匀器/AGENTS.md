# AGENTS.md — OSR6-VAM饮料摇匀器

## 目录用途
OSR6/SR6 六轴开源机器人 × VaM(Virt-A-Mate) 实时联动项目。
包含TCode通信库、VaM桥接、Funscript播放器、工具脚本。

## 技术栈
- **语言**: Python 3.10+
- **通信**: pyserial (USB), socket (UDP/WiFi), bleak (BLE)
- **协议**: TCode v0.3 (L/R/V/A轴命令)
- **硬件**: ESP32 + 6x舵机 (MG996R/DS3218)

## 模块结构
| 模块 | 用途 |
|------|------|
| `tcode/` | TCode协议编解码 + Serial/WiFi/BLE连接 |
| `vam_bridge/` | VaM AgentBridge API → TCode实时桥接 |
| `funscript/` | .funscript解析 + 多轴同步播放 |
| `tools/` | 舵机测试/固件烧写/轴校准 |

## 关键约束
- TCode位置范围: 0-9999 (5000=中位)
- ESP32 串口: 115200bps
- WiFi UDP: 默认端口8000
- BLE: Nordic UART Service (NUS)
- VaM AgentBridge: HTTP API端口8084

## 操作规范
- 修改tcode/前先运行: `python -m pytest tests/ -v`
- 连接设备前先: `python tools/servo_test.py --list-ports`
- 新增轴支持: 修改 `tcode/protocol.py` AXES_SR6
