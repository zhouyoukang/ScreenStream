# 道 · 远程中枢

> 道生一，一生二，二生三，三生万物。
> AGI = 人 + AI。五感连接远方，大脑分析万象。

一个极简的远程诊断与修复系统，基于 WebSocket 实现浏览器（五感）+ PowerShell Agent（手）+ 分析引擎（脑）三位一体架构。

## 哲学

```
人(Ren) — 洞察需求，感知无感
术(Shu) — 落地实现，执行万法
哲(Zhe) — 反思提升，回归于道
```

## 架构：五感 → 大脑 → 手

```
┌─────────────────────────────────────────────────┐
│                  道 · 远程中枢                     │
│                   server.js                      │
│                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │  五感     │    │   大脑    │    │    手     │   │
│  │  Sense   │◄──►│  Brain   │◄──►│  Agent   │   │
│  │ (浏览器)  │    │ (分析)    │    │(PowerShell)│  │
│  └──────────┘    └──────────┘    └──────────┘   │
│                                                  │
│  视·听·触·嗅·味     分析·决策·记忆     执行·感知·反馈  │
└─────────────────────────────────────────────────┘
```

### 用户之五感 (Sense · 浏览器)

| 感 | 能力 | 实现 |
|----|------|------|
| **视** (Vision) | 看见远程机器的状态 | 系统信息面板、诊断结果 |
| **听** (Hearing) | 听见系统的声音 | 实时日志、通知消息 |
| **触** (Touch) | 触及远程机器 | 终端命令输入、消息面板 |
| **嗅** (Smell) | 嗅到问题的气味 | 网络诊断、Code Smell 检测 |
| **味** (Taste) | 品味修复的效果 | 验证结果、一键修复 |

### 用户之无感 (Unconscious)

未说出的习惯、隐含的需求、沉默中的意图。系统主动感知：
- 自动检测 Clash/VPN 环境（198.18.0.x fake-IP / DoH 拦截）
- 自动识别 hosts 劫持、DNS 污染、代理异常
- 自动生成定制修复方案

### Agent 之五感 (Agent · PowerShell)

| 感 | 能力 | 实现 |
|----|------|------|
| **目** (Eyes) | 读取系统状态 | Get-Content, Get-Process, Resolve-DnsName |
| **耳** (Ears) | 监听运行日志 | 命令输出、事件日志 |
| **手** (Hands) | 执行修复操作 | Set-Content, Remove-Item, netsh |
| **脉** (Pulse) | 感知机体状态 | CPU/RAM/Disk, 网络适配器 |
| **网** (Network) | 连接外部世界 | Test-NetConnection, DNS 查询 |

### Agent 之无感 (Unconscious)

- 17 步自动诊断（hostname → firewall，全链路扫描）
- Clash/VPN 环境智能识别（不误报代理为污染）
- 根因分析 + 自动修复建议

## 快速开始

### 1. 启动服务器

```bash
npm install
node server.js
```

### 2. 通过 FRP 暴露到公网（可选）

```bash
# 复制并编辑 FRP 配置
cp frpc.example.toml frpc.toml
# 编辑 frpc.toml 填入你的 FRP 服务器信息

# 启动 FRP 客户端
frpc -c frpc.toml

# 设置公网 URL 并重启服务器
PUBLIC_URL=your-server:port node server.js
```

### 3. 连接 Agent（在目标电脑）

在目标电脑打开浏览器访问页面，然后在管理员 PowerShell 中运行页面上显示的安装命令。

### 4. 使用 Brain CLI

```bash
node brain.js exec "Get-Process"        # 远程执行命令
node brain.js auto                       # 17步自动诊断
node brain.js state                      # 查看系统状态
node brain.js say "消息"                 # 推送消息到页面
node brain.js msg                        # 读取用户从页面发送的消息
node brain.js terminal                   # 查看命令历史
node brain.js sysinfo                    # 获取系统信息
```

## 分析引擎

### 浏览器诊断 (Sense → Brain)

浏览器自动执行 11 项检查：
- DNS 解析（windsurf.com, auth, unleash, marketplace）
- HTTPS 连通性
- IP 直连测试
- GitHub 参考基线

### Agent 诊断 (Agent → Brain)

17 步全链路扫描：
- 系统信息（hostname, OS, CPU, RAM, Disk）
- 网络配置（适配器, DNS 服务器, 代理）
- hosts 文件检查
- DNS 解析验证
- TCP 连通性测试
- 防火墙规则检查
- 进程状态检查

### 智能环境识别

```
Clash/VPN 检测模式:
  Pattern 1: DNS 返回 198.18.0.x → Clash fake-IP 模式
  Pattern 2: DNS 全失败 + HTTPS 全通过 → Clash DoH 拦截模式
  
关键区分:
  ✅ 198.18.0.x = Clash 正常代理（不报错）
  ❌ hosts 127.0.0.1 绕过 Clash = 真正的问题（报错）
```

## API

| 方法 | 路径 | 认证 | 说明 |
|------|------|------|------|
| GET | `/health` | 无 | ☰乾: 健康自检（Agent/内存/连接） |
| GET | `/` | Cookie | 五感页面 |
| GET | `/agent.ps1` | AgentKey | Agent 安装脚本 |
| GET | `/brain/state` | Bearer | 系统状态 |
| GET | `/brain/agents` | Bearer | Agent 列表 |
| GET | `/brain/terminal` | Bearer | 命令历史 |
| GET | `/brain/messages` | Bearer | 用户消息 |
| POST | `/brain/exec` | Bearer | ☳震: 远程执行命令 |
| POST | `/brain/broadcast` | Bearer | ☱兑: 所有Agent同时执行 |
| POST | `/brain/select` | Bearer | 切换当前Agent |
| POST | `/brain/say` | Bearer | 推送消息到页面 |
| POST | `/brain/command` | Bearer | 推送修复命令到页面 |
| POST | `/brain/sysinfo` | Bearer | 获取系统信息 |
| POST | `/brain/auto` | Bearer | ☵坎: 17步自动诊断 |
| POST | `/brain/windsurf-setup` | Bearer | ☲离: 9步Windsurf代理配置 |
| WS | `/ws/sense` | Token | 浏览器 WebSocket |
| WS | `/ws/agent` | AgentKey | Agent WebSocket |

## Python SDK (跨项目复用)

```python
from remote_hub import RemoteHub
hub = RemoteHub()                        # 自动读取.env
hub.exec("Get-Date")                     # 执行命令
hub.broadcast("$env:COMPUTERNAME")       # 广播所有Agent
hub.health()                             # 健康检查(无认证)
hub.agents()                             # 列出Agent
hub.select("ZHOUMAC")                    # 切换Agent
hub.sysinfo()                            # 系统信息
hub.diagnose()                           # 17步自动诊断
hub.say("消息")                          # 发送到浏览器
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | `3002` | 服务器端口 |
| `PUBLIC_URL` | `localhost:3002` | 公网访问地址 |

## 技术栈

- **Node.js** — 服务器 + CLI
- **WebSocket (ws)** — 实时双向通信
- **PowerShell** — Agent 执行引擎
- **原生 HTML/CSS/JS** — 零依赖前端

## 变更日志

### 2026-03-04 — v3.1 八卦升维

**新增能力（填补5个缺失卦位）：**

| 卦 | 能力 | 说明 |
|---|------|------|
| ☰乾 | `/health` 端点 | 公开健康自检（Agent/内存/连接/uptime） |
| ☱兑 | `/brain/broadcast` | 所有Agent同时执行命令 |
| ☷坤 | 僵尸Agent清理 | 每60秒扫描，5分钟无响应自动移除 |
| ☶艮 | 内存保护 | validTokens≤1000, commandHistory≤500, userMessages≤200 |
| ☲离 | Python SDK | `remote_hub.py` — 跨项目一行代码调用远程中枢 |

**修复4个Bug：**

| # | 问题 | 修复 |
|---|------|------|
| 1 | `validTokens` Set无限增长（内存泄漏） | 超1000个自动清理最旧token |
| 2 | `commandHistory` 数组无限增长 | 限制500条 |
| 3 | `user_exec` 超时不通知用户 | 正确调用reject回调 |
| 4 | `global.userMessages` 无限增长 | 限制200条 |

### 2026-03-04 — 端到端测试与修复

**发现并修复 5 个 Bug：**

| # | 问题 | 根因 | 修复 |
|---|------|------|------|
| 1 | 自动诊断 `hostname` 命令失败 | CMD 命令，PowerShell 不识别 | → `$env:COMPUTERNAME` |
| 2 | 自动诊断 `proxy_check` 命令失败 | `netsh` 未用全路径 | → `& "$env:SystemRoot\System32\netsh.exe"` |
| 3 | JS 字符串 `\S` `\n` 被转义 | 单引号字符串中反斜杠被解释 | → 双重转义 `\\` |
| 4 | 代理分析误报 | `netsh` 失败时错误信息被当作"代理已配置" | → 先检查 `ok()` 再分析输出 |
| 5 | `buildFixCommand` 使用裸 CMD 命令 | `netsh`/`ipconfig`/`taskkill` 在 PS 中可能不可用 | → 全路径 + `Stop-Process` |

**验证结果：** 17/17 自动诊断项全部通过，0 误报。

## 许可证

MIT

---

*道可道，非常道。名可名，非常名。*
