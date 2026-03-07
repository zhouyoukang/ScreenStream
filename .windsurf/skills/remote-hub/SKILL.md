---
name: remote-hub
description: 通过远程中枢管理和操作远程电脑。当需要在远程机器上执行命令、查看状态、批量操作、诊断网络、配置Windsurf代理时自动触发。
triggers:
  - 远程电脑/远程机器/远程执行/远程管理
  - 在台式机/在DESKTOP上执行
  - 广播命令到所有机器
  - 远程诊断/远程修复
  - Windsurf代理配置/共享代理
  - 查看Agent状态/Agent连接
---

# 远程中枢操作 Skill

> 道·远程中枢 v3.1 — 五感延伸到任意远程电脑
> 八卦能力完整：☰乾(健康) ☷坤(清理) ☵坎(诊断) ☲离(配置) ☳震(执行) ☴巽(增量) ☶艮(保护) ☱兑(广播)

> ⚠️ **守卫**: 此Skill仅在用户**明确要求**远程操作时使用。禁止在本地开发/构建/Bug修复任务中自动调用远程中枢或检查aiotvr.xyz。

## 架构速查

```
浏览器 → https://aiotvr.xyz/agent/ → Nginx(443) → FRP(13002) → Node.js(:3002) → WebSocket → Agent(PowerShell)
```

## 资源位置

| 文件 | 用途 |
|------|------|
| `远程桌面/remote-hub/server.js` | 服务端 (~830行) |
| `远程桌面/remote-hub/page.js` | 前端UI |
| `远程桌面/remote-hub/brain.js` | CLI工具 |
| `远程桌面/remote-hub/remote_hub.py` | Python SDK (跨项目复用) |
| `远程桌面/remote-hub/.env` | 凭据 (gitignored) |

## 方式一：Python SDK（推荐，跨项目复用）

```python
import sys; sys.path.insert(0, r'd:\道\道生一\一生二\远程桌面\remote-hub')
from remote_hub import RemoteHub

hub = RemoteHub()                        # 自动读取.env
hub.health()                             # 健康检查(无认证)
hub.exec("Get-Date")                     # 远程执行
hub.broadcast("$env:COMPUTERNAME")       # 广播所有Agent
hub.agents()                             # 列出Agent
hub.select("ZHOUMAC")                    # 切换Agent
hub.sysinfo()                            # 系统信息
hub.diagnose()                           # 17步自动诊断
hub.say("消息")                          # 发到浏览器
hub.ram_free()                           # 便捷：空闲内存(GB)
hub.disk_free("C:")                      # 便捷：磁盘空闲(GB)
```

## 方式二：HTTP API（curl/Invoke-WebRequest）

### 公开端点（无需认证）
```powershell
# 健康检查
curl.exe -sk "https://aiotvr.xyz/agent/health"
```

### 认证端点
```powershell
# 登录获取token
$token = (curl.exe -sk "https://aiotvr.xyz/agent/login" -X POST -H "Content-Type: application/json" -d '{"password":"[见secrets.env]"}' | ConvertFrom-Json).token

# 远程执行
curl.exe -sk "https://aiotvr.xyz/agent/brain/exec" -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $token" -d '{"cmd":"Get-Process | Measure | Select -Expand Count"}'

# 广播执行（所有Agent）
curl.exe -sk "https://aiotvr.xyz/agent/brain/broadcast" -X POST -H "Content-Type: application/json" -H "Authorization: Bearer $token" -d '{"cmd":"Get-Date -Format o"}'
```

## 方式三：Brain CLI

```bash
node brain.js exec "Get-Process"        # 远程执行
node brain.js auto                       # 17步自动诊断
node brain.js state                      # 系统状态
node brain.js say "消息"                 # 推送消息
node brain.js msg                        # 读取用户消息
```

## API 完整端点表

| 方法 | 路径 | 认证 | 卦 |
|------|------|------|---|
| GET | `/health` | 无 | ☰乾 |
| POST | `/brain/exec` | Bearer | ☳震 |
| POST | `/brain/broadcast` | Bearer | ☱兑 |
| POST | `/brain/auto` | Bearer | ☵坎 |
| POST | `/brain/windsurf-setup` | Bearer | ☲离 |
| POST | `/brain/sysinfo` | Bearer | - |
| POST | `/brain/select` | Bearer | - |
| GET | `/brain/agents` | Bearer | - |
| GET | `/brain/state` | Bearer | - |
| GET | `/brain/terminal` | Bearer | - |
| POST | `/brain/say` | Bearer | - |

## 故障排查

| 症状 | 诊断 | 修复 |
|------|------|------|
| Agent未连接 | `curl /health` 查agents.connected | 检查FRP隧道 + Agent脚本运行 |
| API返回401 | token过期或错误 | 重新POST `/login` |
| 命令超时 | Agent侧PowerShell阻塞 | 加 `-EA SilentlyContinue`，避免交互式命令 |
| 广播部分失败 | 某Agent断开 | `/health` 确认连接，reconnect |
| 内存高 | 长时间运行 | 重启server.js（已有自动清理机制） |

## 安全注意

- **密码**: 存于 `远程桌面/remote-hub/.env`，禁止硬编码
- **Agent Key**: 由密码派生，自动验证
- **Token**: 登录后获取，有效期无限但数量上限1000
- **远程执行**: 任何PowerShell命令均可执行，务必谨慎
