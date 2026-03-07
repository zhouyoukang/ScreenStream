# 主控 ai 子账号·无感全控

> Admin(9904) → PsExec → Session 4 → ai(9905)，两会话并行全控。
> 更新: 2026-02-26 | 蒸馏自能力图谱+_INDEX+所有agent脚本

---

## 👁 视觉 — 架构

```
台式机 192.168.31.141
  Session 1 Console  Administrator → remote_agent :9904 (RemoteAgentAdmin)
  Session 4 RDP-Tcp  ai/Ai@2026!  → remote_agent :9905 (AI_Inject_Session4)
外部: Ghost Shell :8000 | FRP :19903→:9904 | RDP :13389
```

| 项 | Admin :9904 | ai :9905 |
|----|------------|---------|
| Session | Console ID=1 | RDP-Tcp#0 ID=4 |
| 开机 | RemoteAgentAdmin AtLogon | AI_Inject_Session4 AtStartup |
| RDP | mstsc /v:192.168.31.141 | 127.0.0.2 |
| 角色 | 主脑·HA·IDE·MCP | 隔离·VR·CAD·通讯 |

---

## 👂 听觉 — 注入链

```
AtStartup(SYSTEM) → inject_ai_session.ps1
  → 等待 query session ai (最多120s)
  → ai未登录: Start-Process python --port 9905 (Shell可用,GUI不可)
  → ai已登录: PsExec64 -i 4 -d python --port 9905 (全功能)
```

| 组件 | 规范路径 |
|------|---------|
| PsExec64(首选) | C:\Temp\PSTools\PsExec64.exe |
| PsExec64(兜底) | D:\安装的软件\GameViewer\bin\PsExec64.exe |
| remote_agent | E:\道\AI之电脑\agent\remote_agent.py |
| Python | C:\ProgramData\anaconda3\python.exe |

---

## 🖐 触觉 — 控制速查

```powershell
# 感知
python E:\道\AI之电脑\agent\sense_ai_capabilities.py --probe
python E:\道\AI之电脑\agent\sense_ai_capabilities.py
python E:\道\AI之手机\sense_all.py --ai

# 启动软件
python E:\道\AI之电脑\agent\sense_ai_capabilities.py --launch kicad.exe
python E:\道\AI之电脑\agent\sense_ai_capabilities.py --launch freecad.exe

# API直控
Invoke-RestMethod http://localhost:9905/health
Invoke-RestMethod http://localhost:9905/screenshot

# 双控演示
python E:\道\AI之电脑\agent\dual_control.py

# Ghost Shell视觉串流
双击 E:\道\AI之电脑\agent\→Ghost Shell.cmd
```

---

## 👃 嗅觉 — 行动前预检

```powershell
# ai Agent模式确认
(Invoke-RestMethod http://localhost:9905/health).session
# "session-4" = PsExec全功能  "Console" = 非交互模式

# PsExec标准位置
Test-Path "C:\Temp\PSTools\PsExec64.exe"
# False → Copy-Item "D:\安装的软件\GameViewer\bin\PsExec64.exe" "C:\Temp\PSTools\" -Force

# 计划任务
Get-ScheduledTask -TaskName "AI_Inject_Session4" | Select-Object State,LastRunTime

# ai会话
query session ai
netstat -an | findstr ":9905.*LISTENING"
```

---

## 👅 味觉 — ai账号软件域

| 目录 | 软件精华 |
|------|---------|
| AI--3D建模 | FreeCAD 1.0 · SolidWorks 2023 · Bambu Studio |
| AI--PCB | KiCad · 嘉立创EDA 2.2.32 · STM32CubeMX |
| AI--VR | Virtual Desktop Streamer · Sunshine · Oculus |
| AGI | CUDA 12.4/12.6 · Docker · PyCharm |
| homeassistant | HASS.Agent · Mosquitto MQTT |
| AI--摄影 | OBS 31 · Photoshop 2024 · CorelDRAW 2021 |
| 人 | QQ · 微信 · 腾讯会议（ai独立登录） |

> 完整454软件 → E:\道\AI之电脑\ai账号_能力图谱.md

---

## ∞ 无感 — 解惑全表

### 已解（惑1-13 历史）

| # | 惑 | 解 |
|---|-----|-----|
| 1 | ai agent用户显示Administrator | PsExec SYSTEM注入，正常 |
| 2 | 软件安装在哪 | HKLM全局454个 |
| 3 | 延迟2100ms | Python HTTP基础开销，非错误 |
| 4 | ai能连HA | HASS.Agent已装 |
| 5 | ai有GPU | CUDA 12.4/12.6 |
| 6 | VR串流 | Virtual Desktop+Sunshine |
| 7 | ai锁屏 | NoLockScreen永久 |
| 8 | FreeCAD版本 | 1.0（非0.21） |
| 9 | SakuraCat | 网络代理工具 |
| 10 | ai无法登录 | net user ai /active:yes |
| 11 | FreeCAD路径 | D:\安装的软件\FreeCAD 1.0\bin\freecad.exe |
| 12 | 注入任务丢失 | 已重建AI_Inject_Session4 |
| 13 | FRP公网失效 | frpc.exe未安装（见祸A） |

### 新解（惑14-16 本次蒸馏）

| # | 祸 | 根因 | 状态 |
|---|-----|------|------|
| 14 | PsExec路径依赖GameViewer | inject_ai_session.ps1硬编码GameViewer路径，卸载即断链 | ✅ 已修复：多路径探测+自动下载 |
| 15 | AGENT路径用Desktop遗留 | 同文件用Desktop\remote_control非规范路径 | ✅ 已修复：改为E:\道规范路径 |
| 16 | configure与inject路径不一致 | bat用C:\Temp\PSTools，ps1用GameViewer | ✅ 已统一：inject现在首选C:\Temp\PSTools |

### 未解之祸（待处理）

| # | 祸 | 绕过 |
|---|-----|------|
| A | FRP frpc.exe未装 | 下载frp_0.61.1_windows_amd64.zip → 解压frpc.exe → install-frpc.ps1 |
| B | ~~ai会话需手动RDP触发~~ | ✅ **已解 2026-02-27**: rdp_guardian.ps1 自动触发（cmdkey预存凭证 + mstsc静默连接） |
| C | :9905 /processes超时 | sense_ai_capabilities.py已用shell+tasklist绕过 |
| D | X:/Y: SMB已断 | net use X: \\192.168.31.179\C /persistent:yes |

---

## 🛡 守护者体系（2026-02-27 新建）

守护范围：注册表 + TermService + RDP Wrapper + ai会话，每5分钟自愈一次。

```powershell
# 安装守护者（系统首次部署后运行一次即可，永久生效）
.\.\rdp_guardian.ps1 -Install

# 查看守护状态和日志
.\.\rdp_guardian.ps1 -Status

# Windows Update 后 ini 过期时手动触发更新
.\.\install-rdpwrap.ps1 -UpdateIni
```

| 守护功能 | 机制 |
|---------|------|
| termsrv.dll 被替换 | SHA256 哈希监控 → 自动重装 RDP Wrapper |
| TermService 崩溃 | 状态监控 → 自动重启服务 |
| 注册表被 Windows 覆盖 | fSingleSessionPerUser/fDenyTSConnections 监控 → 自动修复 |
| ai 会话掉线 | query session 检测 → cmdkey+mstsc 自动重连 |
| :9905 agent 失效 | REST /health 检测 → 重触发 inject_ai_session.ps1 |

---

## 关联文件

| 文件 | 用途 |
|------|------|
| E:\道\AI之电脑\ai账号_能力图谱.md | 完整454软件+历史惑解 |
| E:\道\AI之电脑\_INDEX.md | 台式机完整档案(15节) |
| E:\道\AI之电脑\install-rdpwrap.ps1 | RDP Wrapper 全自动安装器 |
| E:\道\AI之电脑\rdp_guardian.ps1 | **守护者** — 五感自持，每5分钟自愈 |
| E:\道\AI之电脑\rdp_setup.ps1 | RDP 管理菜单（9选项） |
| E:\道\AI之电脑\→安装RDP多会话.cmd | 一键启动器（含全套部署） |
| E:\道\AI之电脑\rdp连接配置\ | 7个 .rdp 文件（均已改 127.0.0.2 + .\\user） |
| E:\道\AI之电脑\agent\inject_ai_session.ps1 | 注入脚本（已修复） |
| E:\道\AI之电脑\agent\sense_ai_capabilities.py | ai账号五感探针 |
| E:\道\AI之电脑\agent\dual_control.py | 双控演示 |
| E:\道\AI之电脑\agent\ghost_shell五感.md | Ghost Shell详解 |
