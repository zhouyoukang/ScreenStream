# Agent操作电脑 · 统一中枢

> 汇总所有"Agent操控电脑/手机/智能家居/网络"的资源。统一入口、统一探测、统一管理。

## 快速命令

```bash
# 启动统一中枢 (Web UI :9000)
python hub.py

# 探测所有系统状态
python probe.py

# 详细模式
python probe.py --verbose
```

## 双电脑架构

| 机器 | 主机名 | IP | 角色 | Agent端口 |
|------|--------|-----|------|----------|
| **台式机** | DESKTOP-MASTER | 本机 | 主控+中枢 | :9000 (hub.py) |
| **笔记本** | zhoumac | 192.168.31.179 | 远程被控(55+ API) | :9903 (remote_agent) |

## 15个Agent系统全景

### 🖥️ 电脑控制（核心）

| # | 系统 | 位置 | 端口 | 启动方式 | 说明 |
|---|------|------|------|---------|------|
| 1 | **笔记本Agent(LAN)** | `远程桌面/` | 9903 | `start_agent.bat` | 55+端点全能控制(截屏/键鼠/Shell/文件/UIA/Guardian), FRP公网:19903 |
| 2 | **远程桌面Agent(台式机)** | `远程桌面/` | 9903 | `start_agent.bat` | 台式机增强版(111KB), 含视频录制/RDP扩展 |
| 3 | **远程中枢(Node.js)** | `远程桌面/remote-hub/` | 3002 | `start_all.bat` | WebSocket三体架构(Sense↔Brain↔Agent), 17步自动诊断, 公网 aiotvr.xyz/agent/ |
| 4 | **AGI仪表盘** | `AGI/` | 9090 | `start.bat` | 系统健康/凭据/Skills/Observatory统一仪表盘 (localhost) |
| 5 | **桌面守护(Guardian)** | `远程桌面/` | — | 按需 | 防误操作/自动恢复/RDP保护 (`desktop_guardian.ps1`) |
| 6 | **跨账号控制** | `构建部署/三界隔离/` | — | `enter.ps1` | Administrator↔ai↔zhou 跨Windows账号无缝切换 |
| 7 | **双电脑互联** | `远程桌面/rdp/` | — | RDP文件 | 台式机↔笔记本 RDP连接/Shadow控制/恢复脚本 |
| 8 | **电脑公网投屏手机** | `电脑公网投屏手机/` | 9802 | `start-relay.bat` + `start.bat` | PC屏幕→手机浏览器(WebSocket JPEG流+反向触控), 替代Ghost Shell |

### 📱 手机控制

| # | 系统 | 位置 | 端口 | 说明 |
|---|------|------|------|------|
| 9 | **手机操控库** | `手机操控库/` | — | phone_lib.py(ADB/五感/循环采集) + five_senses.py + remote_assist.py |
| 10 | **公网投屏控制台** | `公网投屏/cast/` | — | ADB Bridge + 配置中心 + 直连手机, 公网 aiotvr.xyz/cast/setup.html |

### 🌐 网络与基础设施

| # | 系统 | 位置 | 端口 | 启动方式 | 说明 |
|---|------|------|------|---------|------|
| 11 | **Clash VPN管理** | `clash-agent/` | 9098 | `start.bat` | 代理引擎(7890)+Web UI(9098): 6分类应用路由/实时连接/节点管理 |
| 12 | **二手书系统** | E盘 ModularSystem | 8088 | — | 190路由, 3校区对接 |

### 🏠 智能家居与AI

| # | 系统 | 位置 | 端口 | 启动方式 | 说明 |
|---|------|------|------|---------|------|
| 13 | **智能家居网关** | `智能家居/网关服务/` | 8900 | `start.bat` | HA代理+涂鸦+eWeLink+微信推送 |
| 14 | **认知代理** | `认知代理/` | 9070 | — | 五维感知(文件/输入/窗口/剪贴板/网络)+意图提炼 |
| 15 | **Voxta AI对话** | `VAM-agent/voxta/` | 5384 | — | SignalR协议/角色管理/聊天引擎/动作推理 |

## 公网入口

| 入口 | URL | 说明 |
|------|-----|------|
| 健康检查 | `https://aiotvr.xyz/api/health` | 阿里云全服务状态JSON |
| 远程中枢 | `https://aiotvr.xyz/agent/` | 登录→诊断→终端→Windsurf配置 |
| 投屏控制 | `https://aiotvr.xyz/cast/` | CloudRelay/P2P投屏viewer |
| 配置中心 | `https://aiotvr.xyz/cast/setup.html` | ADB Bridge+五感仪表盘+远程控制面板 |

## 端口分配（固定）

| 端口 | 服务 | 监听 |
|------|------|------|
| **9000** | **统一中枢 hub.py** | **localhost** |
| 3002 | 远程中枢 Node.js | 0.0.0.0 |
| 5384 | Voxta Server | localhost |
| 7890 | Clash Meta 代理 | localhost |
| 8088 | 二手书系统 | 0.0.0.0 |
| 8900 | 智能家居网关 | localhost |
| 9070 | 认知代理 | localhost |
| 9090 | AGI仪表盘 | localhost |
| 9097 | Clash API | localhost |
| 9098 | VPN Web UI | localhost |
| 9802 | 电脑公网投屏手机 | 0.0.0.0 |
| 9903 | 远程桌面Agent | 0.0.0.0 (笔记本) |

## 通道优先级

```
文件工具(无状态) ≫ HTTP API ≫ WebSocket ≫ WinRM ≫ SSH ≫ RDP
```

## 阿里云 FRP 隧道

| 隧道 | 本地→远程 | 状态 |
|------|----------|------|
| agent | 9903→19903 | 笔记本在线时开 |
| rdp | 3389→13389 | 笔记本在线时开 |
| remote-agent | 3002→13002 | ✅ 常驻 |
| bookshop | 8088→18088 | ✅ 常驻 |
| windsurf | 443→18443 | ✅ 常驻 |
| ss/input/gateway | 各端口 | 手机/服务启动时开 |

## 文件结构

```
agent操作电脑/
├── hub.py             ← 统一中枢 v2.0 :9000 (Web UI + 本地操作 + 远程代理 + 笔记本资源感知)
├── probe.py           ← 独立探测脚本 (14系统 + 公网SSL + 重复检测)
├── probe_report.json  ← 最近一次探测报告
├── AGENTS.md          ← Agent行为指令
├── README.md          ← 本文件（全景索引）
└── REPORT.md          ← 历史审计报告
```

### hub.py v2.0 能力

- **本地操作**: 截屏/键鼠/滚轮/拖拽/移动/OCR/进程/Shell/剪贴板/窗口/文件浏览
- **远程代理**: GET+POST透传到14个子系统的API (含笔记本LAN直连)
- **笔记本资源感知**: 自动扫描笔记本5个散落agent目录(电脑管理/AI-操控手机/AI-浏览器自动化等)
- **Web UI**: 暗色主题仪表盘，系统状态/本地操作/远程API/Shell
- **零必需依赖**: 纯stdlib运行，psutil/PIL/pyautogui增强

### 笔记本散落资源目录 (已索引但未迁移)

| 目录 | 描述 | 数量 |
|------|------|------|
| `E:\道\电脑管理` | 桌面自动化POC(B站/豆包/混元/UIA/MCP) | 187+项 |
| `E:\道\AI-操控手机` | 24个手机Agent框架研究 | 52+项 |
| `E:\道\AI-浏览器自动化` | UFO-3.0/PaddleOCR/Playwright MCP | 39项 |
| `E:\道\AI-助手开发实验` | Agent助手开发实验 | — |
| `E:\道\AI-初恋测试` | AI人格对话测试 | — |

> 各系统保留在各自目录中（避免重复），本目录作为**统一入口**。
