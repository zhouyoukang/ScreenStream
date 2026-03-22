# VP99 华强北智能手表

## 设备

| 项目 | 值 |
|------|-----|
| 型号 | VP99 |
| 系统 | **Android 8.1 Oreo** (非Wear OS) |
| 平台 | **K15** · Unisoc展锐 4核 · 3GB RAM |
| 固件 | K15_V11B_DWQ_VP99_EN_ZX_HSC_4.4V700_20241127 |
| 屏幕 | 480×576 (VNC: 336×401) |
| 存储 | 24.4GB总 / 12.1GB可用 |
| 网络 | WiFi 192.168.31.41 · 4G LTE · BLE |
| OEM | HSC · DWQ方案商 · 佰佑通配套 |
| 序列号 | 10109530162925 · IMEI: 860123401266076 |

## 当前状态

| 通道 | 状态 | 说明 |
|------|------|------|
| MacroDroid HTTP | ✅ :8080 | 8个远程命令可用 |
| USB MTP | ✅ VID:1782 PID:4001 | 文件传输 |
| VNC | ⏳ 需手动启动 | DroidVNC-NG已安装, 端口5900 |
| ADB | ❌ 被HSC固件屏蔽 | 开发者模式锁定, 需突破 |

## 快速开始

```powershell
# 启动Hub中枢
python watch_hub.py          # → http://localhost:8841

# ADB突破 (探测+指南+监控)
python watch_breakthrough.py           # 自动探测所有通道
python watch_breakthrough.py --guide   # 完整物理操作指南
python watch_breakthrough.py --monitor # 持续监控, ADB一开即自动配置
```

## 目录

```
watch_hub.py              ★ Hub中枢 :8841 (MacroDroid+VNC+端口扫描+API)
watch_dashboard.html      ★ 八卦Dashboard 8页SPA
watch_breakthrough.py     ★ ADB突破引擎 (探测/指南/监控/自动配置)
→手表中枢.cmd             快捷启动器
docs/
  VP99_REVERSE_ENGINEERING.md  逆向报告 (VNC确认/固件解码/MTP分析)
  VP99_BREAKTHROUGH.md         6条突破路径 + 佰佑通APK逆向
  ADB_COMMANDS.md              VP99 ADB命令参考
tools/
  watch_bridge.py              VNC统一控制接口
  watch_connect.ps1            WiFi ADB连接助手
  watch_data_collector.py      全量数据采集
  watch_monitor.py             实时监控
  vnc_adb_enabler.py           VNC远程开ADB
  vnc_connect.py               VNC连接工具
  analyze_apks.py              APK分析
  _e2e_test.py                 端到端测试
data/                          采集数据存储
```

## ADB突破路径 (优先级)

1. **Activity Launcher** — Play商店安装→直接打开DevelopmentSettings (3分钟)
2. **拨号码** — `*#*#592411#*#*` 展锐工程码 (30秒, 需确认是否生效)
3. **佰佑通APP** — BLE配对→工具箱→开ADB (5分钟)
4. **DroidVNC-NG** — 手表启动VNC→PC远程操作 (需手动启动)
5. **SPD深刷** — spd_dump进入FDL2→修改build.prop (高级, 10分钟)

详见 `watch_breakthrough.py --guide` 或 `docs/VP99_BREAKTHROUGH.md`