# Agent操作电脑 · Agent操作指令

> Agent操作此目录时的行为指令。

## 目录职责

**统一中枢** — 整合14个Agent系统(含笔记本远程)的入口、探测、控制面板。

## 核心文件

| 文件 | 用途 | 启动方式 |
|------|------|----------|
| `hub.py` | 统一中枢 v2.0 :9000 (Web UI + 本地操作 + 远程代理转发 + 笔记本资源感知) | `python hub.py` |
| `probe.py` | 独立探测脚本 (14系统 + 公网SSL + 重复检测) | `python probe.py` |
| `README.md` | 全景索引文档 | — |
| `REPORT.md` | 审计报告(含双机深度测试结果) | — |

## 双电脑架构

| 机器 | IP | Agent端口 | FRP公网 | 角色 |
|------|-----|-----------|---------|------|
| 台式机 DESKTOP-MASTER | 本机 | :9000(hub) | — | 主控+中枢 |
| 笔记本 zhoumac | 192.168.31.179 | :9903 | 60.205.171.100:19903 | 远程被控 |

### 笔记本四通道(优先级排序)
1. **HTTP API**: `http://192.168.31.179:9903` (主通道, <1s)
2. **FRP公网**: `http://60.205.171.100:19903` (外网, ~2s)
3. **Hub代理**: `http://127.0.0.1:9000/api/proxy/laptop_agent/` (统一入口)
4. **SMB**: `\\192.168.31.179\E$` (文件传输)

## 端口分配

| 端口 | 系统 | 说明 |
|------|------|------|
| **9000** | hub.py (本目录) | 统一中枢 Web UI + ThreadingHTTPServer |
| 3002 | 远程中枢 Node.js | WebSocket三体架构 |
| 5384 | Voxta Server | SignalR对话 |
| 7890 | Clash Meta 代理 | SOCKS/HTTP代理 |
| 8088 | 二手书系统 | ModularSystem |
| 8900 | 智能家居网关 | HA+涂鸦+微信 |
| 9070 | 认知代理 | 五维感知 |
| 9090 | AGI仪表盘 | 系统健康 |
| 9098 | Clash Web UI | VPN管理 |
| 9903 | 远程桌面Agent | HTTP全能控制 (笔记本LAN / 台式机本机) |

## Agent行为规则

### 必须
- 操作前先 `python probe.py` 或访问 `/api/probe` 了解当前状态
- 修改任何子系统前，读取该系统的 `_AGENT_GUIDE.md`
- 新增系统时同步更新 `hub.py` 的 `SYSTEMS` 列表和 `probe.py` 的 `SYSTEMS` 列表

### 禁止
- 禁止在此目录创建大型重复文件（各系统代码保持在原目录）
- 禁止删除 `probe_report.json`（它是探测历史记录）
- 禁止修改子系统端口（固定分配，见上表）

### 子系统引用路径

| 系统 | 位置 | _AGENT_GUIDE.md |
|------|------|-----------|
| 远程桌面Agent | `远程桌面/` | `远程桌面/_AGENT_GUIDE.md` |
| 远程中枢 | `远程桌面/remote-hub/` | `远程桌面/_AGENT_GUIDE.md` |
| AGI仪表盘 | `AGI/` | `AGI/_AGENT_GUIDE.md` |
| VPN管理 | `clash-agent/` | `clash-agent/_AGENT_GUIDE.md` |
| 智能家居 | `智能家居/` | `智能家居/AGENT_GUIDE.md` |
| 认知代理 | `认知代理/` | `认知代理/_AGENT_GUIDE.md` |
| 手机操控 | `手机操控库/` | `手机操控库/_AGENT_GUIDE.md` |
| 公网投屏 | `公网投屏/cast/` | — |
| 三界隔离 | `构建部署/三界隔离/` | `构建部署/三界隔离/_AGENT_GUIDE.md` |
| 桌面守护 | `远程桌面/` | `远程桌面/_AGENT_GUIDE.md` |
| 双电脑互联 | `远程桌面/rdp/` | `文档/双电脑连接卡.md` |
| Voxta对话 | `VAM-agent/voxta/` | `VAM-agent/_AGENT_GUIDE.md` |

## Hub API 速查

### 本地操作 (直接在本机执行)
```
GET  /api/local/sysinfo       # 系统信息(RAM/CPU/磁盘)
GET  /api/local/screenshot    # 截屏(base64 JPEG)
GET  /api/local/processes     # 进程列表(Top20)
GET  /api/local/ports         # 端口扫描(所有系统)
GET  /api/local/clipboard     # 读剪贴板
GET  /api/local/windows       # 活动窗口
GET  /api/local/ocr           # 屏幕OCR
GET  /api/local/files?path=X  # 文件浏览
GET  /api/local/shell?cmd=X   # 执行Shell命令
POST /api/local/click         # {"x":100,"y":200}
POST /api/local/key           # {"key":"enter"}
POST /api/local/type          # {"text":"hello"}
POST /api/local/scroll        # {"x":0,"y":0,"clicks":3}
POST /api/local/move          # {"x":100,"y":200}
POST /api/local/drag          # {"x1":0,"y1":0,"x2":100,"y2":100}
POST /api/local/shell         # {"cmd":"dir","timeout":15}
```

### 远程代理转发 (GET+POST透传)
```
GET  /api/proxy/{system_id}/{path}  # GET转发到目标系统
POST /api/proxy/{system_id}/{path}  # POST转发(带body)
# 例: GET  /api/proxy/laptop_agent/health
# 例: POST /api/proxy/laptop_agent/key {"key":"enter"}
```

### 笔记本资源感知
```
GET /api/laptop/resources     # 笔记本散落资源目录列表
```

### 全局
```
GET /api/probe     # 全系统探测(14系统+公网+笔记本资源)
GET /api/systems   # 系统列表
GET /             # Web Dashboard
```
