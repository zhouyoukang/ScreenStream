# 三电脑服务器 — 道生万物·三机韧性架构

> **道生一**(资源注册表:9000) → **一生二**(24个Hub+20个Dashboard) → **二生三**(三机协同) → **三生万物**(40+服务·11台设备·全覆盖)
>
> 伏羲八卦 · 老子道德经 · 释迦牟尼 — 万物负阴而抱阳，冲气以为和

## 三机总览

```text
              ☰ 阿里云 (60.205.171.100, aiotvr.xyz)
             /  Nginx + frps + SSL · 2C/1.6GB · 永驻
            /         ↑                          \
     FRP×9 ↗    FRP×2 (caddy+rdp)         ↘ 公网用户
          /           |                      \
   ☷ 台式机141    ☲ 笔记本179           三路径可达:
   R7-9700X/62GB   R7-7840HS/15GB       ① LAN → 179
   RTX 4070S       24h在线               ② FRP → /laptop/*
   白天8-23点      Caddy统一入口          ③ FRP → 各路由
   9条FRP隧道      2条FRP隧道
   动态服务引擎 ←── LAN代理 ←── Caddy
```

## 运维模式（核心约束）

| 机器 | 卦 | 在线时间 | 角色 | 核心限制 |
|------|-----|---------|------|---------|
| 阿里云 | ☰乾·天 | **永驻** | 公网门户·SSL·frps | 1.6GB内存极紧 |
| 台式机141 | ☷坤·地 | 白天8-23点 | 服务引擎·最强算力 | 晚上断电 |
| 笔记本179 | ☲离·火 | **24h** | Caddy代理·静态serve | 15GB内存·偶尔重启 |

## 硬件资源矩阵

| | 台式机141 | 笔记本179 | 阿里云 |
|--|----------|----------|--------|
| CPU | R7-9700X 8C16T | R7-7840HS 8C16T | Xeon 2C |
| RAM | **62GB** | 15GB | 1.6GB |
| GPU | **RTX 4070 SUPER** | Radeon 780M集显 | 无 |
| 磁盘 | C:300G D:653G E:1TB | C:300G D:653G E:954G | 40G |
| 网络 | LAN 1Gbps | LAN 1Gbps | 200Mbps公网 |
| OS | Win11 Education | Win11 Pro | Ubuntu 24.04 |

## 公网访问路径

| 路径 | URL | 延迟 | 可靠性 |
|------|-----|------|--------|
| ① LAN直连 | `http://192.168.31.179/` | 最低 | 179在线即可 |
| ② FRP笔记本 | `https://aiotvr.xyz/laptop/*` | 中 | 179+阿里云 |
| ③ FRP各路由 | `https://aiotvr.xyz/*` | 中 | 141+阿里云 |

## FRP隧道分工

### 笔记本179 (user=laptop, 2条)

| 名称 | 本地 | 远程 | 服务 |
|------|------|------|------|
| caddy | 80 | 10080 | **Caddy统一入口** |
| rdp | 3389 | 23389 | 笔记本远程桌面 |

### 台式机141 (user=desktop, 9条)

| 名称 | 本地 | 远程 | 服务 | 状态 |
|------|------|------|------|------|
| rdp | 3389 | 13389 | 台式机远程桌面 | 常驻 |
| relay | 9800 | 19800 | 公网投屏中继 | 常驻 |
| cfw_proxy | 443 | 18443 | CFW代理隧道 | 常驻 |
| ss | 18080 | 18086 | ScreenStream投屏 | 需手机 |
| input | 18084 | 18084 | 反向控制API | 需手机 |
| remote_agent | 9903 | 19903 | 远程Agent | 按需 |
| remote_hub | 3002 | 13002 | 远程修复中枢 | 按需 |
| bookshop_api | 8088 | 18088 | 二手书API | 按需 |
| gateway | 8900 | 18900 | 智能家居网关 | 需凭据 |

## 五种故障场景（释迦·四谛·苦集灭道）

| 场景 | 频率 | 苦(影响) | 道(可用) |
|------|------|---------|---------|
| **S1:141夜间断电** | 每天 | 141代理路由不可用 | 179静态7路由+阿里云本地 |
| **S2:179重启** | 偶尔 | /laptop/*暂时不可用 | 141直达FRP+阿里云本地 |
| **S3:双机同断** | 罕见 | 全FRP隧道离线 | 仅阿里云本地服务 |
| **S4:阿里云故障** | 极罕见 | 公网完全不可达 | 仅LAN http://179/ |
| **S5:全恢复** | 每天早晨 | 无 | 全部路由恢复 |

## 自愈机制（道德经·上善若水）

### 笔记本179计划任务

| 任务名 | 触发器 | 功能 |
|--------|--------|------|
| LaptopServer-Caddy | 登录时 | 启动Caddy反向代理 |
| LaptopServer-FrpcClient | 登录时 | 启动FRP隧道客户端 |
| LaptopServer-Watchdog | 每分钟 | 健康检查+自愈+三机矩阵 |

### Watchdog自愈链

```
每分钟 → 检查Caddy进程 → 崩溃?→重启
       → 检查frpc进程  → 崩溃?→重启
       → 探测141可达性  → ping+6端口
       → 生成health.json → 三机健康矩阵
```

### Caddy韧性配置

- **dial_timeout 3s**: 所有reverse_proxy，离线时快速失败
- **handle_errors**: 503维护页(道德经·☲卦)
- **路径**: 所有默认使用E:盘(笔记本)

## Caddy路由架构（笔记本179）

### 静态本地serve (24h可用)

| 路由 | 内容 |
|------|------|
| `/` | 静态主站 |
| `/api/status` | 状态JSON |
| `/api/health` | 健康矩阵(watchdog) |
| `/app/` | APP下载页 |
| `/book/` | 校园书市PWA |
| `/cast/` | WebRTC投屏套件 |
| `/quest/` | Quest3 WebXR门户 |

### 动态代理→台式机141 (白天可用)

| 路由 | 目标端口 | 服务 |
|------|---------|------|
| `/screen/` | 18080 | ScreenStream投屏 |
| `/input/` | 18084 | 反向控制API |
| `/gw/` `/wx` | 8900 | 智能家居网关 |
| `/agent/` `/heal/` | 3002 | 远程修复中枢 |
| `/signal/` | 9100 | P2P信令 |
| `/relay/` | 9800 | WebSocket中继 |
| `/remote/` | 9903 | remote_agent |
| `/desktop/` | 9802 | 电脑投屏 |
| `/hub/` | 18800 | Hub管理 |
| `/frp/` | 7500 | FRP控制台 |

## 阿里云组件对应

| 阿里云 | 笔记本 | 备注 |
|--------|--------|------|
| Nginx | Caddy v2.9 | 功能等价 |
| frps | frpc连回 | 保持架构 |
| systemd | 计划任务 | Windows版 |
| cron(每分钟) | 计划任务(每分钟) | 功能等价 |
| server-watchdog.sh | watchdog.ps1 | Windows版+三机矩阵 |
| Let's Encrypt | FRP隧道自带SSL | 无需证书 |

## E2E验证结果 (2026-03-08)

```
17/17 全通 ✅

LAN(179):  / /api/status /api/health /app/ /book/ /cast/ /quest/  → 7/7 ✅
FRP笔记本: /laptop/ /laptop/api/status /laptop/api/health          → 3/3 ✅
公网阿里云: / /api/health /app/ /book/ /cast/ /agent/ /frp/        → 7/7 ✅
```

## 文件清单

```
三电脑服务器/
├── README.md                     # 本文档(唯一真相源)
├── resource_registry.py          # ★全景资源注册表+探测+API(:9000)
├── portal.html                   # ★统一Portal八卦Dashboard
├── AGENTS.md                     # Agent指令
├── 笔记本179/
│   ├── Caddyfile                 # Caddy配置(E:盘路径)
│   ├── watchdog.ps1              # 健康检查+自愈+三机矩阵
│   ├── frpc-laptop.toml          # 笔记本FRP(user=laptop)
│   └── maintenance.html          # 503维护页
├── 台式机141/
│   ├── frpc-desktop.toml         # 台式机FRP(user=desktop)
│   └── start_all_hubs.ps1       # ★一键启动所有Hub服务
└── 阿里云/
    └── nginx-routes.md           # Nginx路由参考(只读)
```

## 全景资源注册表 (resource_registry.py :9000)

统一入口 — 中枢的中枢。注册全部40+服务、11台设备、20个Dashboard。

```powershell
# 启动Portal
python 三电脑服务器/resource_registry.py
# → http://localhost:9000/          (Portal八卦Dashboard)
# → http://localhost:9000/api/probe  (全量探测JSON)
# → http://localhost:9000/api/health (健康检查)

# CLI探测
python 三电脑服务器/resource_registry.py --probe
```

## 一键启动Hub服务 (start_all_hubs.ps1)

```powershell
# 列出所有Hub状态
.\台式机141\start_all_hubs.ps1 -List

# 启动全部Hub
.\台式机141\start_all_hubs.ps1 -All

# 按分类启动
.\台式机141\start_all_hubs.ps1 -Category 设备

# 停止全部Hub
.\台式机141\start_all_hubs.ps1 -Stop
```

## 伏羲八卦 · 全景服务注册表

### ☰乾 · 创造/算力
| 服务 | 端口 | 位置 | 分类 |
|------|------|------|------|
| Ollama LLM | 11434 | 台式机141 | AI |
| OpenWebUI | 18880 | 台式机141 | AI |
| MaxKB | 18881 | 台式机141 | AI |
| AGI Dashboard | 9090 | 台式机141 | AI |

### ☷坤 · 基础设施
| 服务 | 端口 | 位置 | 分类 |
|------|------|------|------|
| HomeAssistant | 8123 | 台式机141 | IoT |
| MQTT | 1883 | 台式机141 | IoT |
| NodeRED | 1880 | 台式机141 | IoT |
| Grafana | 3000 | 台式机141 | 监控 |
| PostgreSQL | 5432 | 台式机141 | 数据库 |
| Redis | 6379 | 台式机141 | 数据库 |

### ☲离 · 投屏/可视
| 服务 | 端口 | 位置 | 分类 |
|------|------|------|------|
| 电脑投屏 | 9802 | 台式机141 | 投屏 |
| ScreenStream投屏 | 18080 | 台式机141 | 投屏 |
| ScreenStream控制 | 18084 | 台式机141 | 投屏 |
| P2P信令 | 9100 | 台式机141 | 投屏 |
| WebSocket中继 | 9800 | 台式机141 | 投屏 |

### ☳震 · 控制/操控
| 服务 | 端口 | 位置 | 分类 |
|------|------|------|------|
| 远程Agent | 9903 | 台式机141 | 远程 |
| 远程修复中枢 | 3002 | 台式机141 | 远程 |
| 万物中枢 | 8808 | 台式机141 | 中枢 |
| RayNeo管理 | 8800 | 台式机141 | AR |
| RayNeo仿真 | 8768 | 台式机141 | AR |

### ☴巽 · 网络/代理
| 服务 | 端口 | 位置 | 分类 |
|------|------|------|------|
| Clash代理 | 7890 | 台式机141 | 代理 |
| CFW授权 | 443 | 台式机141 | 代理 |
| 公网CFW Hub | 443 | 阿里云 | 公网 |
| FRP控制台 | 7500 | 台式机141 | 隧道 |

### ☵坎 · 数据/凭据
| 服务 | 端口 | 位置 | 分类 |
|------|------|------|------|
| 密码中枢 | 9877 | 台式机141 | 凭据 |
| 手机数据中枢 | 9878 | 台式机141 | 凭据 |
| 二手书API | 8088 | 台式机141 | 业务 |

### ☶艮 · 设备Hub
| 服务 | 端口 | 设备 | 分类 |
|------|------|------|------|
| 拓竹3D打印 | 8870 | Bambu A1 | 硬件 |
| EcoFlow电源 | 8871 | Delta 2 | 硬件 |
| Insta360相机 | 8860 | X3 | 硬件 |
| ORS6设备 | 41927 | ESP32 | 硬件 |
| Go1机器狗 | 8087 | Unitree Go1 | 硬件 |

### ☱兑 · 智能家居
| 服务 | 端口 | 位置 | 分类 |
|------|------|------|------|
| 米家中枢 | 8873 | 台式机141 | 智能家居 |
| 米家摄像头 | 8874 | 台式机141 | 智能家居 |
| 智能家居网关 | 8900 | 台式机141 | 智能家居 |

## 设备矩阵 (11台)

| 设备 | IP | 类型 | 接口 |
|------|-----|------|------|
| OnePlus NE2210 | 192.168.31.40 | 手机 | SS API :8084 |
| Samsung S23U | 192.168.31.123 | 手机 | ADB WiFi TLS |
| OPPO Reno4 SE | 192.168.31.95 | 手机 | SS API :8084 |
| Quest 3 | 192.168.31.136 | VR | ADB |
| RayNeo V3 | 192.168.31.116 | AR | WiFi ADB :5555 |
| VP99手表 | 192.168.31.41 | 手表 | VNC :5900 |
| Go1机器狗 | 192.168.12.1 | 机器人 | SSH/MQTT |
| Bambu A1 | 192.168.31.134 | 3D打印 | MQTTS :8883 |
| EcoFlow Delta 2 | 192.168.31.134 | 电源 | TCP :3000 |
| 小米路由器 | 192.168.31.1 | 路由器 | HTTP :80 |
| 米家中枢网关 | 192.168.31.53 | 网关 | WS/MQTT |

## Dashboard索引 (20个)

| Dashboard | 端口 | 来源项目 |
|-----------|------|---------|
| 拓竹3D打印 | 8870 | 拓竹AI 3D打印机/ |
| EcoFlow电源 | 8871 | 正浩德2户外电源/ |
| Insta360相机 | 8860 | 影石360 x3/ |
| ORS6设备 | 41927 | ORS6-VAM饮料摇匀器/ |
| Go1机器狗 | 8087 | 机器狗开发/ |
| Go1仿真 | 46173 | 虚拟仿真平台/go1/ |
| 米家全景 | 8873 | 米家系统全整合/ |
| 米家摄像头 | 8874 | 米家系统全整合/ |
| RayNeo AR | 8800 | 雷鸟v3开发/ |
| 万物中枢 | 8808 | 雷鸟v3开发/ |
| Quest 3 VR | 47387 | quest3开发/ |
| AGI仪表盘 | 9090 | AGI/ |
| 手机逆向 | 8096 | 手机现成app库/ |
| PC软件全景 | 8098 | 电脑现成项目app/ |
| 虚拟仿真门户 | 48000 | 虚拟仿真平台/ |
| 远程桌面 | 9903 | 远程桌面/ |
| 二手书手机端 | 8099 | 二手书手机端/ |
| DJI Neo | — | 大疆所有体系整合/ |
| 智能家居 | — | 100-智能家居_SmartHome/ |
| 小米路由器 | — | 米家系统全整合/ |

## 凭据引用

> 实际值见 `secrets.env`，此处仅列键名。**frpc toml中的token为部署必需，无法环境变量替代。**

| 凭据 | secrets.env键名 | 用途 |
|------|------|------|
| FRP认证Token | `FRP_TOKEN` | frpc↔frps通信 |
| FRP控制台用户 | `FRP_DASH_USER` | 7500 Dashboard |
| FRP控制台密码 | `FRP_DASH_PASSWORD` | 7500 Dashboard |
| 台式机密码 | `DESKTOP_PASSWORD` | RDP/WinRM |
| 笔记本密码 | `LAPTOP_MAIN_PASSWORD` | RDP |
| 阿里云SSH | `ALIYUN_SSH_ALIAS` | `ssh aliyun` |
| 密码Hub | `PORT_PASSWORD_HUB` (9877) | 凭据API |
| 手机Hub | `PORT_PHONE_HUB` (9878) | 手机数据API |

## 密码管理体系整合

> 三电脑服务器通过密码管理中枢实现凭据统一管理。

| 服务 | 端口 | 位置 | 功能 |
|------|------|------|------|
| password_hub | 9877 | 台式机141 | secrets.env凭据API(132键) |
| phone_hub | 9878 | 台式机141 | OnePlus手机数据API |
| service_hub | 9999 | 台式机141 | 端口服务管理 |

**Agent获取凭据方式**(三机均可):
- LAN: `curl http://192.168.31.141:9877/api/get?key=FRP_TOKEN`
- 本机: `curl http://127.0.0.1:9877/api/get?key=KEY`
- 备选: `Get-Content secrets.env` (文件直读)

## 哲学映射

```
☰乾(阿里云) — 天行健，自强不息    永驻公网，SSL+frps
☷坤(台式机) — 地势坤，厚德载物    最强算力，承载万服务
☲离(笔记本) — 离为火，照万物      24h照亮，统一入口
☵坎(网络)   — 坎为水，上善若水    FRP隧道如水贯通三机
☳震(启动)   — 震为雷，一触即发    计划任务+自愈机制
☴巽(渐进)   — 巽为风，无孔不入    渐进降级+服务探测
☶艮(知止)   — 艮为山，知止不殆    故障时优雅降级
☱兑(交流)   — 兑为泽，万物交通    health.json三机矩阵
```

> 释迦·中道：不过度冗余也不脆弱，三机各司其职，如水流向可用路径。
