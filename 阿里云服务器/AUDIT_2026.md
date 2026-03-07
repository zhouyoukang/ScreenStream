# 阿里云服务器全景审计报告 v6

> **审计时间**: 2026-07-15
> **审计方法**: 全盘文件扫描 + 内容分析 + 实时连通性测试
> **服务器**: 60.205.171.100 (aiotvr.xyz) — 阿里云轻量应用服务器

---

## 〇、紧急状态：服务器应用层全部不可达

### 实时测试结果

| 测试项 | 结果 | 说明 |
|--------|------|------|
| **Ping** | ✅ 50ms, 0%丢失 | 网络可达，服务器在线 |
| **DNS** | ✅ aiotvr.xyz → 60.205.171.100 | 解析正确 |
| **TCP:22 (SSH)** | ⚠️ TCP握手成功，但banner交换超时 | sshd可能hung |
| **TCP:80 (HTTP)** | ⚠️ TCP握手成功，HTTP请求超时 | nginx可能hung |
| **TCP:443 (HTTPS)** | ⚠️ TCP握手成功，HTTPS请求超时 | nginx可能hung |
| **TCP:7000 (FRP)** | ❌ 连接拒绝 | frps未运行 |
| **TCP:18443 (CFW隧道)** | ❌ 连接拒绝 | FRP隧道未建立 |
| **TCP:18800 (Auth Hub)** | ❌ 连接拒绝 | windsurf-hub未运行 |
| **TCP:9100 (Relay)** | ❌ 连接拒绝 | ss-relay未运行 |
| **TCP:9101 (信令)** | ❌ 连接拒绝 | family-signaling未运行 |
| **TCP:9800 (CloudRelay)** | ❌ 连接拒绝 | 未运行 |
| **TCP:18086 (SS投屏)** | ❌ 连接拒绝 | FRP隧道未建立 |
| **TCP:18084 (SS反控)** | ❌ 连接拒绝 | FRP隧道未建立 |
| **TCP:18088 (二手书)** | ❌ 连接拒绝 | FRP隧道未建立 |
| **TCP:13389 (RDP)** | ❌ 连接拒绝 | FRP隧道未建立 |
| **TCP:19903 (Agent)** | ❌ 连接拒绝 | FRP隧道未建立 |

### 诊断

- **ICMP可达 + TCP握手成功 + 应用层超时** → 服务器OS在运行，但应用进程（sshd/nginx）处于hung状态
- **可能原因**: 内存耗尽(OOM) / 磁盘满 / 僵尸进程 / 安全组策略变更
- **frps未运行** → 所有FRP隧道端口(18xxx/13xxx/19xxx)均不可达

### 建议修复步骤

1. **登录阿里云控制台** → 使用VNC远程连接（绕过SSH）
2. 检查: `dmesg | tail -50`, `journalctl -b --no-pager | tail -100`
3. 检查内存: `free -h`, 磁盘: `df -h`
4. 重启关键服务: `systemctl restart sshd nginx frps`
5. 如果无法恢复: 在控制台重启实例
6. 恢复后执行: `bash aliyun_recover.sh`（全量恢复脚本）

---

## 一、服务器基础设施

### 1.1 服务器信息

| 项目 | 值 |
|------|-----|
| **云厂商** | 阿里云轻量应用服务器 |
| **IP** | 60.205.171.100 |
| **域名** | aiotvr.xyz |
| **SSH用户** | root |
| **SSH密钥** | `~/.ssh/aliyun_ed25519` |
| **SSH别名** | `aliyun` (在~/.ssh/config中配置) |

### 1.2 服务器端运行服务

| 服务 | 端口 | 进程 | systemd | 说明 |
|------|------|------|---------|------|
| **frps** | 7000 | /opt/frp/frps | frps.service | FRP服务端，所有隧道的入口 |
| **nginx** | 80/443 | nginx | nginx.service | 反向代理 + SSL终止 + 静态文件 |
| **windsurf-hub** | 18800 | python3 auth_hub.py | windsurf-hub.service | Windsurf授权中枢 |
| **ss-relay** | 9100 | node server.js | ss-relay.service | ScreenStream WebRTC信令 |
| **family-signaling** | 9101 | node server.js | — (nohup) | 亲情远程信令 |
| **desktop-cast** | 9802/9803 | node server.js | desktop-cast.service | 电脑公网投屏 |
| **HA Docker** | 8123 | docker | — | Home Assistant (Docker容器) |
| **watchdog** | — | bash | cron | 服务监控 + 自愈 + health.json |

### 1.3 FRP服务端配置

```toml
bindPort = 7000
auth.method = "token"
auth.token = "NKLQyCrSavf1MmYOGtkFzbh0"
webServer.addr = "127.0.0.1"
webServer.port = 7500
webServer.user = "admin"
webServer.password = "frp_admin_2026"
allowPorts = [
  { start = 13000, end = 13999 },
  { start = 18000, end = 19999 }
]
```

### 1.4 Nginx路由表

| Location | 后端 | 功能 |
|----------|------|------|
| `/` | 静态文件 | 主站 |
| `/cast/` | 127.0.0.1:9100 | ScreenStream WebRTC客户端 |
| `/app/socket` | 127.0.0.1:9100 (WebSocket) | Socket.IO信令通道 |
| `/app/` | 127.0.0.1:9100 | Nonce/Ping API |
| `/screen/` | 127.0.0.1:18086 (FRP) | ScreenStream MJPEG投屏 (Basic Auth) |
| `/input/` | 127.0.0.1:18084 (FRP) | ScreenStream反向控制 (Basic Auth) |
| `/signal/` | 127.0.0.1:9101 | 亲情远程P2P信令 |
| `/hub/` | 127.0.0.1:18800 | Windsurf授权中枢面板 |
| `/agent/` | /opt/windsurf-hub/static/ | 部署包分发 |
| `/desktop/` | 127.0.0.1:9802 | 电脑公网投屏 |
| `/wx` | 127.0.0.1:18900 (FRP) | 微信公众号网关 |
| `/frp/` | 127.0.0.1:7500 | FRP Dashboard (Basic Auth) |
| `/api/relay-status` | 127.0.0.1:9100 | Relay状态API |
| `/api/health` | 静态JSON | 健康检查 |
| `/book/` | 127.0.0.1:18088 (FRP) | 二手书API |
| `/quest/` | 静态文件 | Quest3 WebXR Portal |

---

## 二、FRP隧道体系

### 2.1 FRP客户端配置对比

项目中存在 **2个frpc.toml**，分别用于不同设备：

#### 台式机/笔记本 FRP客户端 (`远程桌面/frp/frpc.toml`)

| 隧道名 | 本地端口 | 远程端口 | 用途 |
|--------|---------|---------|------|
| remote_agent | 9903 | 19903 | 远程Agent API |
| rdp | 3389 | 13389 | Windows远程桌面 |
| ss | 18080 | 18086 | ScreenStream MJPEG投屏 |
| input | 18084 | 18084 | ScreenStream反向控制 |
| cfw_proxy | 443 | 18443 | CFW代理隧道(Windsurf) |

#### 独立FRP客户端 (`阿里云服务器/frpc.toml`)

| 隧道名 | 本地端口 | 远程端口 | 用途 |
|--------|---------|---------|------|
| remote_agent | 9903 | 19903 | 远程Agent API |
| rdp | 3389 | 13389 | Windows远程桌面 |
| bookshop_api | 8088 | 18088 | 二手书API |
| screenstream | 18080 | 18086 | ScreenStream投屏 |
| screenstream_input | 18084 | 18084 | ScreenStream反控 |
| gateway | 8900 | 18900 | 微信/智能家居网关 |
| relay | 9800 | 19800 | CloudRelay服务 |
| heal | 8085 | 18085 | Brain健康检查 |

### 2.2 FRP配置差异分析

| 差异项 | `远程桌面/frp/frpc.toml` | `阿里云服务器/frpc.toml` |
|--------|--------------------------|--------------------------|
| **user** | `laptop` | 无(默认) |
| **cfw_proxy** | ✅ 有(443→18443) | ❌ 无 |
| **bookshop_api** | ❌ 无 | ✅ 有(8088→18088) |
| **gateway** | ❌ 无 | ✅ 有(8900→18900) |
| **relay** | ❌ 无 | ✅ 有(9800→19800) |
| **heal** | ❌ 无 | ✅ 有(8085→18085) |

**结论**: `远程桌面/frp/frpc.toml` 是台式机当前实际使用的配置（含CFW隧道），`阿里云服务器/frpc.toml` 是更完整的参考配置但缺少CFW隧道。两份配置需要合并统一。

---

## 三、散落文件清单

### 3.1 部署脚本（涉及阿里云的）

| 文件 | 目标服务 | 部署方式 | 状态 |
|------|---------|---------|------|
| `阿里云服务器/deploy-screenstream.sh` | ScreenStream Nginx反代 | SSH + Nginx配置 | ⚠️ Nginx注入过时 |
| `阿里云服务器/deploy-relay.sh` | WebRTC Relay | SSH + Node + Nginx | ⚠️ Nginx注入过时 |
| `阿里云服务器/deploy-wechat-nginx.sh` | 微信公众号Nginx | SSH + Nginx配置 | ⚠️ Nginx注入过时 |
| `阿里云服务器/server-watchdog.sh` | 服务监控+自愈 | cron定时 | ✅ 有效 |
| `阿里云服务器/patch_watchdog.py` | 增强watchdog HTTP探针 | Python补丁 | ✅ 有效 |
| `阿里云服务器/aliyun-health.ps1` | 本地健康检查 | PowerShell | ✅ 有效 |
| `Windsurf无限额度/aliyun_recover.sh` | 全量恢复(frps+hub+nginx) | SSH | ✅ 恢复用 |
| `Windsurf无限额度/deploy_hub.sh` | Windsurf授权中枢部署 | SSH | ✅ 有效 |
| `Windsurf无限额度/auth_hub.py` | 授权中枢服务(v2.0) | systemd | ✅ 有效 |
| `亲情远程/deploy-signaling.sh` | 亲情信令服务器 | SSH + Node | ✅ 有效 |
| `电脑公网投屏手机/deploy.sh` | Desktop Cast Relay | SSH + systemd | ✅ 有效 |
| `公网投屏/投屏链路-公网投屏/deploy/deploy-relay.sh` | WebRTC Relay | SSH + Node + systemd | ⚠️ Nginx注入过时 |
| `公网投屏/投屏链路-公网投屏/deploy/deploy.sh` | WebRTC Relay (PM2版) | SSH + PM2 | ⚠️ 与systemd版冲突 |
| `100-智能家居_SmartHome/HA核心配置/scripts/install_mosquitto_aliyun.sh` | MQTT Broker | SSH + apt | ⚠️ 目标IP不同(8.138.177.6) |
| `微信公众号/deploy-wechat-nginx.sh` | 微信Nginx | SSH | ⚠️ 与阿里云服务器/下的重复 |

### 3.2 FRP配置文件

| 文件 | 设备 | 用途 |
|------|------|------|
| `阿里云服务器/frpc.toml` | 参考配置 | 完整隧道列表(8条) |
| `阿里云服务器/frpc.exe` | Windows FRP客户端 | v0.61.1二进制 |
| `远程桌面/frp/frpc.toml` | 台式机/笔记本实际使用 | 5条隧道(含CFW) |
| `远程桌面/frp/frpc.toml.bak` | 备份 | — |
| `远程桌面/remote-hub/frpc.example.toml` | 模板 | remote-hub用 |
| `Windsurf无限额度/start_frpc.cmd` | FRP启动脚本 | Windows CMD |

### 3.3 凭证文件

| 文件 | 内容 | 安全风险 |
|------|------|---------|
| `阿里云服务器/secrets.toml` | FRP token, Dashboard密码, SSH公钥 | 🟡 应gitignore |

---

## 四、发现的问题

### 4.1 紧急问题 (P0)

| # | 问题 | 影响 | 修复 |
|---|------|------|------|
| P0-1 | **服务器应用层全部不可达** | 所有公网服务瘫痪 | 阿里云控制台VNC登录诊断 |
| P0-2 | **frps未运行** | 所有FRP隧道断开 | `systemctl restart frps` |

### 4.2 高优先级问题 (P1)

| # | 问题 | 影响 | 修复 |
|---|------|------|------|
| P1-1 | **2份frpc.toml不一致** | 部署时容易用错配置 | 合并为统一配置 |
| P1-2 | **3个deploy脚本Nginx注入过时** | 重新部署会覆盖现有配置 | 标记过时或更新 |
| P1-3 | **2个Relay部署脚本冲突(PM2 vs systemd)** | 进程管理混乱 | 统一为systemd |
| P1-4 | **deploy-wechat-nginx.sh存在2份副本** | 维护歧义 | 删除重复 |

### 4.3 中优先级问题 (P2)

| # | 问题 | 影响 | 修复 |
|---|------|------|------|
| P2-1 | **install_mosquitto_aliyun.sh目标IP不同(8.138.177.6)** | 可能是另一台服务器 | 确认是否过时 |
| P2-2 | **secrets.toml明文存储凭证** | 安全风险 | 确保gitignore覆盖 |
| P2-3 | **亲情信令用nohup非systemd** | 重启后不自动恢复 | 创建systemd service |
| P2-4 | **watchdog未集成auth_hub监控** | 授权中枢崩溃无告警 | 扩展watchdog |

---

## 五、服务依赖拓扑

```
                    ┌─────────────────────────────────────┐
                    │  阿里云 60.205.171.100 (aiotvr.xyz)  │
                    │                                      │
                    │  frps(:7000) ◄── 所有FRP隧道入口      │
                    │      │                               │
                    │  nginx(:80/:443) ── 反代+SSL+静态     │
                    │      │                               │
                    │  ┌───┼───────────────────────┐       │
                    │  │   ├→ :9100  ss-relay      │       │
                    │  │   ├→ :9101  family-signal  │       │
                    │  │   ├→ :18800 auth_hub      │       │
                    │  │   ├→ :7500  frp-dashboard │       │
                    │  │   ├→ :18086 → FRP → SS投屏 │       │
                    │  │   ├→ :18084 → FRP → SS反控 │       │
                    │  │   ├→ :18900 → FRP → 微信   │       │
                    │  │   └→ :18088 → FRP → 二手书 │       │
                    │  └───────────────────────────┘       │
                    │                                      │
                    │  watchdog(cron) → health.json         │
                    │  HA Docker(:8123)                     │
                    └──────────────────────────────────────┘
                                    ▲
                                    │ FRP隧道
                    ┌───────────────┴───────────────┐
                    │  台式机 (192.168.31.141)        │
                    │                                │
                    │  frpc → 5条隧道                 │
                    │  CFW(:443) → Windsurf授权       │
                    │  remote_agent(:9903)            │
                    │  ScreenStream ADB转发(:18080)   │
                    └────────────────────────────────┘
```

---

## 六、恢复操作手册

### 6.1 紧急恢复（当前状态适用）

```bash
# 1. 阿里云控制台 → 实例管理 → 远程连接(VNC)
# 2. 检查系统状态
dmesg | tail -50
free -h
df -h
journalctl -b --no-pager | tail -100

# 3. 重启关键服务
systemctl restart sshd
systemctl restart nginx
systemctl restart frps

# 4. 验证
ss -tlnp | grep -E ':(22|80|443|7000) '
```

### 6.2 全量恢复（使用恢复脚本）

```bash
# SSH恢复后，从本地执行：
ssh aliyun 'bash -s' < "Windsurf无限额度/aliyun_recover.sh"
```

### 6.3 FRP客户端启动（台式机）

```powershell
# 在台式机执行
cd 远程桌面\frp
.\frpc.exe -c frpc.toml
```

---

## 七、文件索引

### 阿里云服务器/ 目录

| 文件 | 大小 | 用途 |
|------|------|------|
| `aliyun-health.ps1` | 6.6KB | PowerShell本地健康检查脚本 |
| `deploy-relay.sh` | 8.2KB | WebRTC Relay部署 |
| `deploy-screenstream.sh` | 11.5KB | ScreenStream投屏部署 |
| `deploy-wechat-nginx.sh` | 3.2KB | 微信Nginx部署 |
| `frp_status.py` | 1.2KB | FRP状态查询(Python) |
| `frpc.exe` | 14.9MB | FRP客户端Windows二进制 |
| `frpc.toml` | 1.7KB | FRP客户端参考配置 |
| `patch_watchdog.py` | 3.2KB | Watchdog HTTP探针补丁 |
| `secrets.toml` | 477B | 凭证文件(应gitignore) |
| `server-watchdog.sh` | 6.7KB | 服务监控+自愈脚本 |
| `公网资源审计报告.md` | 16.8KB | v5审计报告(历史) |

### 散落在其他项目中的阿里云相关文件

| 文件 | 用途 |
|------|------|
| `Windsurf无限额度/aliyun_recover.sh` | 全量恢复脚本(frps+hub+nginx) |
| `Windsurf无限额度/deploy_hub.sh` | 授权中枢部署 |
| `Windsurf无限额度/auth_hub.py` | 授权中枢服务v2.0(688行) |
| `Windsurf无限额度/start_frpc.cmd` | FRP客户端启动 |
| `远程桌面/frp/frpc.toml` | 台式机FRP客户端配置(实际使用) |
| `亲情远程/deploy-signaling.sh` | 亲情信令部署 |
| `电脑公网投屏手机/deploy.sh` | Desktop Cast部署 |
| `公网投屏/投屏链路-公网投屏/deploy/deploy-relay.sh` | Relay部署(另一版本) |
| `公网投屏/投屏链路-公网投屏/deploy/deploy.sh` | Relay部署(PM2版) |
| `微信公众号/deploy-wechat-nginx.sh` | 微信Nginx(重复) |
| `100-智能家居_SmartHome/HA核心配置/scripts/install_mosquitto_aliyun.sh` | MQTT安装(另一台服务器?) |

---

## 八、凭证汇总（⚠️ 敏感信息）

| 凭证 | 值 | 用途 |
|------|-----|------|
| FRP Token | `NKLQyCrSavf1MmYOGtkFzbh0` | FRP客户端认证 |
| FRP Dashboard | `admin / frp_admin_2026` | FRP管理面板 |
| SS Basic Auth | `screen / stream2026` | ScreenStream投屏页面保护 |
| MQTT | `ha_mqtt / ha_mqtt_password` | Home Assistant MQTT |

> ⚠️ 建议：将所有凭证集中到 `secrets.toml`，确保 `.gitignore` 覆盖

---

*审计完成。核心发现：服务器应用层全部不可达，需通过阿里云控制台VNC紧急修复。*
