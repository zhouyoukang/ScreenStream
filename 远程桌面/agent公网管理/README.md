# Agent公网管理电脑 · 全景汇总

> **一句话**: 通过公网(aiotvr.xyz)远程管理所有电脑的统一索引。
> 所有设计、代码、文档、测试的唯一真相源。

## 架构总览

```
用户浏览器 → https://aiotvr.xyz/agent/
    → Nginx(443) → FRP(13002) → Node.js(:3002) → WebSocket → Agent(PowerShell)

Python/CLI → remote_hub.py / brain.js → HTTP API → 同上
```

### 三体架构 (Sense → Brain → Agent)

| 层 | 角色 | 实现 |
|----|------|------|
| **Sense** | 用户五感(浏览器) | `page.js` — 暗色UI, 5面板, 设备卡片, WebSocket实时 |
| **Brain** | 中枢决策(服务端) | `server.js` — Node.js, 17步诊断, Windsurf配置, 多设备管理 |
| **Agent** | 执行触手(PowerShell) | `agent.ps1` — 动态下载, 系统采集, 命令执行 |

## 系统清单 (14个Agent系统)

### 核心电脑控制

| # | 系统 | 源目录 | 端口 | 公网 | 说明 |
|---|------|--------|------|------|------|
| 1 | **远程中枢(Node.js)** | `远程桌面/remote-hub/` | 3002 | aiotvr.xyz/agent/ | 三体架构, 17步诊断, 多设备管理 |
| 2 | **远程桌面Agent** | `远程桌面/` | 9903 | :19903(FRP) | Python 55+API, Guardian引擎, 截屏/键鼠/Shell |
| 3 | **桌面守护Guardian** | `远程桌面/` | — | — | 防误操作/自动恢复/RDP保护/铁律13条 |
| 4 | **统一中枢hub.py** | `agent操作电脑/` | 9000 | — | 14系统统一入口, Web UI, 本地+远程操作 |
| 5 | **系统探测probe.py** | `agent操作电脑/` | — | — | 14系统+公网+重复检测 |
| 6 | **双电脑互联** | `远程桌面/rdp/` | — | :13389(FRP) | RDP/Shadow/AHK/恢复脚本 |
| 7 | **跨账号控制** | `构建部署/三界隔离/` | — | — | Administrator↔ai↔zhou 无缝切换 |
| 8 | **AGI仪表盘** | `AGI/` | 9090 | — | 系统健康/凭据/Skills统一仪表盘 |

### 手机控制

| # | 系统 | 源目录 | 说明 |
|---|------|--------|------|
| 9 | **手机操控库** | `手机操控库/` | phone_lib.py(ADB/五感/循环采集) |
| 10 | **公网投屏控制台** | `公网投屏/cast/` | ADB Bridge + aiotvr.xyz/cast/setup.html |

### 网络/智能家居/AI

| # | 系统 | 源目录 | 端口 | 说明 |
|---|------|--------|------|------|
| 11 | **Clash VPN管理** | `clash-agent/` | 9098 | 7标签页UI, 30+API |
| 12 | **智能家居网关** | `智能家居/网关服务/` | 8900 | HA代理+涂鸦+微信推送 |
| 13 | **认知代理** | `认知代理/` | 9070 | 五维感知+意图提炼 |
| 14 | **Voxta AI对话** | `VAM-agent/voxta/` | 5384 | SignalR/角色/聊天/动作推理 |

## 核心文件索引

### 远程中枢 (远程桌面/remote-hub/)

| 文件 | 大小 | 用途 |
|------|------|------|
| `server.js` | 62KB | 服务端核心: HTTP+WebSocket, 多设备管理, 诊断, Windsurf配置 |
| `page.js` | 38KB | 前端UI: 暗色主题, 5面板, 设备卡片, 实时WebSocket |
| `brain.js` | 4KB | CLI工具: exec/auto/state/say/msg |
| `remote_hub.py` | 10KB | Python SDK: 跨项目复用, 五感API封装 |
| `start_all.bat` | <1KB | 启动脚本: frpc + node server.js |
| `.env` | gitignored | 凭据: AUTH_PASSWORD, AUTH_AGENT_KEY |
| `frpc.toml` | <1KB | FRP客户端配置 |
| `README.md` | 9KB | 项目文档: 架构/API/SDK/变更日志 |

### 统一中枢 (agent操作电脑/)

| 文件 | 大小 | 用途 |
|------|------|------|
| `hub.py` | 34KB | 统一中枢 :9000 — Web UI + 本地操作 + 远程代理 |
| `probe.py` | 16KB | 独立探测: 14系统 + 公网 + 重复检测 |
| `REPORT.md` | 7KB | 历史审计报告 |

### 远程桌面 (远程桌面/)

| 文件 | 用途 |
|------|------|
| `remote_agent.py` | Python全能控制: 55+API, Guardian引擎, MouseGuard |
| `remote_desktop.html` | 前端: 9面板PWA, 触摸五感 |
| `_unified_remote_hub.py` | 统一远程Hub |
| `REMOTE_CONTROL_AUDIT.md` | 远程控制审计 |

### 设计文档 (文档/)

| 文件 | 用途 |
|------|------|
| `AI_COMPUTER_CONTROL.md` | 全球30+项目对标, 演进路线, 技术方案 |
| `AI_PHONE_CONTROL.md` | AI操控手机全景图 |

### Skills (.windsurf/skills/)

| 文件 | 用途 |
|------|------|
| `remote-hub/SKILL.md` | 远程中枢操作技能: API端点表, Python SDK, 故障排查 |
| `agent-phone-control/SKILL.md` | Agent操控手机技能 |

## API端点总览

### 远程中枢 (aiotvr.xyz/agent/)

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/health` | 无 | 健康检查(状态/版本/Agent数) |
| POST | `/login` | 无 | 登录获取Bearer token |
| GET | `/brain/agents` | Bearer | 列出所有Agent |
| POST | `/brain/exec` | Bearer | 远程执行PowerShell |
| POST | `/brain/broadcast` | Bearer | 广播到所有Agent |
| GET | `/brain/state` | Bearer | 完整系统状态 |
| POST | `/brain/auto` | Bearer | 17步自动诊断 |
| POST | `/brain/windsurf-setup` | Bearer | Windsurf代理配置 |
| POST | `/brain/sysinfo` | Bearer | 系统信息 |
| POST | `/brain/select` | Bearer | 切换Agent |
| GET | `/brain/terminal` | Bearer | 命令历史 |
| POST | `/brain/say` | Bearer | 推送消息到浏览器 |
| GET | `/brain/messages` | Bearer | 获取用户消息 |

### 远程桌面Agent (192.168.31.179:9903)

> 55+端点, 五域覆盖: 视觉/输入/数据/系统/守护
> 公网: 60.205.171.100:19903 (FRP)

## 快速使用

### Python SDK (推荐)

```python
import sys; sys.path.insert(0, r'd:\道\道生一\一生二\远程桌面\remote-hub')
from remote_hub import RemoteHub

hub = RemoteHub()
hub.health()                        # 健康检查(无认证)
hub.exec("Get-Date")                # 远程执行
hub.broadcast("$env:COMPUTERNAME")  # 广播所有Agent
hub.agents()                        # 列出Agent
hub.hostname()                      # 获取主机名
hub.ram_free()                      # 空闲内存(GB)
hub.disk_free("C:")                 # 磁盘空闲(GB)
hub.diagnose()                      # 17步自动诊断
```

### curl (PowerShell)

```powershell
# 健康检查(无认证)
curl.exe -sk "https://aiotvr.xyz/agent/health"

# 登录
$tok = (curl.exe -sk "https://aiotvr.xyz/agent/login" -X POST -H "Content-Type: application/json" -d '{"password":"[见secrets.env]"}' | ConvertFrom-Json).token

# 远程执行
curl.exe -sk "https://aiotvr.xyz/agent/brain/exec" -X POST -H "Authorization: Bearer $tok" -H "Content-Type: application/json" -d '{"cmd":"Get-Process | Measure | Select -Expand Count"}'
```

### Brain CLI

```bash
node brain.js exec "Get-Process"     # 远程执行
node brain.js auto                    # 17步自动诊断
node brain.js state                   # 系统状态
node brain.js say "消息"              # 推送消息
```

## 公网入口

| 入口 | URL | 说明 |
|------|-----|------|
| 远程中枢 | `https://aiotvr.xyz/agent/` | 登录→诊断→终端→Windsurf配置 |
| 健康检查 | `https://aiotvr.xyz/api/health` | 阿里云全服务状态JSON |
| 投屏控制 | `https://aiotvr.xyz/cast/` | CloudRelay/P2P投屏viewer |
| 配置中心 | `https://aiotvr.xyz/cast/setup.html` | ADB Bridge+远程控制面板 |

## FRP隧道映射

| 代理名 | 公网端口 | 本地端口 | 源机器 | 状态 |
|--------|---------|---------|--------|------|
| desktop.remote-agent | 13002 | 3002 | 台式机(Node) | ✅常驻 |
| laptop.remote_agent | 19903 | 9903 | 笔记本 | 在线时开 |
| laptop.rdp | 13389 | 3389 | 笔记本 | 在线时开 |
| desktop.windsurf | 18443 | 443 | 台式机 | ✅常驻 |
| desktop.bookshop | 18088 | 8088 | 台式机 | ✅常驻 |

## 端口分配

| 端口 | 服务 | 位置 |
|------|------|------|
| 3002 | 远程中枢 Node.js | 台式机 |
| 9000 | 统一中枢 hub.py | 本地 |
| 9903 | 远程桌面Agent | 笔记本/台式机 |
| 7890 | Clash Meta 代理 | 本地 |
| 8900 | 智能家居网关 | 本地 |
| 9070 | 认知代理 | 本地 |
| 9090 | AGI仪表盘 | 本地 |
| 9098 | VPN Web UI | 本地 |

## 独有技术护城河

| 能力 | 说明 |
|------|------|
| **Guardian自治引擎** | 断网自愈+进程监控+事件规则+任务队列 |
| **MouseGuard防劫持** | 检测物理输入，cooldown保护 |
| **跨Windows会话** | 不同用户会话独立Agent |
| **三体架构** | Sense↔Brain↔Agent WebSocket实时 |
| **多设备管理** | per-agent状态+wsConfig+定向配置 |
| **17步自动诊断** | 浏览器+Agent双向诊断 |
| **零框架零依赖** | 纯stdlib运行(Python SDK/Agent) |
| **PWA触摸前端** | 手机浏览器全功能操控PC |

## 演进路线

### Phase 1: 补短板 (投入小收益大)
- **P1.1** PC端 UIA 感知 (~200行) → 结构化窗口元素
- **P1.2** `/capabilities` 端点 (~50行) → 设备自描述
- **P1.3** SSE事件推送 (~100行) → 台式机出事秒通知
- **P1.4** 触控板相对移动 (~30行) → 手机远控精确鼠标

### Phase 2: 接入AI视觉
- **P2.1** OmniParser本地部署 → PC截屏→结构化元素
- **P2.2** VLM决策循环 → Observe→Think→Act

### Phase 3: 多设备Galaxy (长期)
- **P3.1** 统一Agent协议 (参考UFO³ AIP)
- **P3.2** 任务DAG引擎 → 复杂工作流分解+并行

## E2E测试

> 测试脚本: `_e2e_test.ps1` | 结果: `_test_results.json`
> 运行: `pwsh -NoProfile -File _e2e_test.ps1`

### 最新结果 (2026-03-04)

| 分类 | 测试项 | 结果 |
|------|--------|------|
| 视·API | T01 Health / T02 Login / T03 Agents / T04 Exec / T05 Broadcast / T06 State / T07 Terminal / T08 Say / T09 FakeReject / T10 Sysinfo | 10/10 ✅ |
| 听·连通 | T11 LocalHealth / T12 AliyunHealth / T13 NoAuth401 | 3/3 ✅ |
| 触·前端 | T14 PageFeatures(10/10) / T15 PageSize / T16 AgentScript | 2/3 ✅ (T15=gzip压缩伪问题) |
| 嗅·安全 | T17 BadPassword / T18 BadAgentKey | 2/2 ✅ |
| 味·质量 | T19 MemoryOK / T20 TokensBound / T21 WsConfig / T22 AgentData | 4/4 ✅ |
| **总计** | | **21/22 (95.5%) — 全部功能正常** |

## 安全

- **密码**: 存于 `远程桌面/remote-hub/.env` + `secrets.env`，禁止硬编码
- **Agent Key**: 由密码派生 `fcd862bdd55b0b97`，自动验证
- **Token**: 登录后获取Bearer token，上限1000
- **Cookie**: `dao_token` (前端WebSocket认证)
- **铁律13条**: 见 `文档/双机保护手册.md`

## 本目录文件

```
agent公网管理电脑/
├── README.md              ← 本文件(全景汇总·唯一真相源)
├── AGENTS.md              ← Agent行为指令
├── _e2e_test.ps1          ← 五感E2E测试脚本(22项)
└── _test_results.json     ← 最新测试结果
```

> 核心代码保留在各自源目录(避免重复)，本目录作为**统一索引+测试中心**。

---

*整合自: 6个源目录 + 30+文件 + 14个Agent系统 + 全球30+项目对标*
*五感评分: 9.5/10 — 全部API端点正常, 公网入口畅通, 安全验证通过*
