# 阿里云服务器

> **一句话**：阿里云轻量¥38/年，HTTPS统一入口 + FRP穿透 + HA反代，一个域名控制一切。
>
> 本目录是全工作区阿里云相关资源的**唯一真相源**，散落资源已汇于此。

---

## 一、服务器信息

| 项目 | 值 |
|------|-----|
| **类型** | 轻量应用服务器 2核2G 200M带宽 |
| **公网IP** | 60.205.171.100 |
| **系统** | Ubuntu 24.04 LTS |
| **区域** | 华北2-北京 |
| **年费** | ¥38（秒杀价） |
| **SSH** | `ssh aliyun`（已配SSH Key，免密） |
| **域名** | aiotvr.xyz → 60.205.171.100 |
| **SSL** | Let's Encrypt，过期 2026-05-26 |

---

## 二、端口与安全组

> **铁律**：安全组未开放 = 连不上。每个端口必须在阿里云控制台→安全组→入方向添加规则。

| 端口 | 服务 | 方向 | 安全组状态 |
|------|------|------|-----------|
| 22 | SSH | 入 | ✅ 必开 |
| 80 | HTTP→HTTPS重定向 | 入 | ✅ 必开 |
| 443 | HTTPS主站+API+FRP反代 | 入 | ✅ 必开 |
| 8443 | HTTPS Home Assistant反代 | 入 | ✅ 必开 |
| 7000 | FRP 绑定端口 | 入 | ✅ 必开 |
| 7500 | FRP 控制台(内部) | 入 | 已通过/frp/反代 |
| 8123 | HA Docker(内部) | — | 已通过8443反代 |
| 19903 | FRP→remote_agent:9903 | 入 | ✅ 必开 |
| 13389 | FRP→Windows RDP:3389 | 入 | ✅ 必开 |
| 16528 | 宝塔面板 | 入 | ✅ |
| 3389 | xrdp（Linux桌面） | 入 | 可选 |

**安全组配置路径**：阿里云控制台 → 轻量应用服务器 → 安全 → 防火墙 → 添加规则

---

## 三、统一入口地图（无感网络架构）

| 服务 | URL | 说明 |
|------|-----|------|
| **主站** | https://aiotvr.xyz | 静态展示网站 |
| **Home Assistant** | https://aiotvr.xyz:8443 | SSL+WebSocket反代 |
| **FRP控制台** | https://aiotvr.xyz/frp/ | Basic Auth(admin) |
| **API健康检查** | https://aiotvr.xyz/api/status | JSON状态 |
| **远程桌面** | `mstsc → 60.205.171.100:13389` | FRP→家里RDP |
| **remote_agent** | http://60.205.171.100:19903 | FRP→家里API |
| **宝塔面板** | https://60.205.171.100:16528/ef35182f | 服务器管理 |

```
浏览器/手机
    │
    ├── https://aiotvr.xyz ──────────────── Nginx(:443) → 静态站
    ├── https://aiotvr.xyz:8443 ─────────── Nginx(:8443) → HA(:8123)
    ├── https://aiotvr.xyz/frp/ ─────────── Nginx(:443) → FRP控制台(:7500)
    ├── https://aiotvr.xyz/api/status ───── Nginx(:443) → JSON
    ├── 60.205.171.100:19903 ────────────── FRP → 家里 remote_agent(:9903)
    └── 60.205.171.100:13389 ────────────── FRP → 家里 RDP(:3389)

┌─────────────────────────────────────────────────────┐
│  阿里云 60.205.171.100 (aiotvr.xyz)                  │
│  ┌────────────────┐  ┌────────┐  ┌───────────────┐  │
│  │ Nginx          │  │ frps   │  │ HA (Docker)   │  │
│  │ :80/:443/:8443 │  │ :7000  │  │ :8123         │  │
│  │ SSL+反代       │  │ :7500  │  │ onboarding    │  │
│  └────────────────┘  └────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────┘
         │ FRP隧道
┌────────▼────────────────────────────────────────────┐
│  家里的电脑                                           │
│  ┌──────────────┐  ┌─────┐  ┌─────────────────┐    │
│  │remote_agent  │  │ RDP │  │ frpc            │    │
│  │:9903 (45+API)│  │:3389│  │ (开机自启)      │    │
│  └──────────────┘  └─────┘  └─────────────────┘    │
└────────────────────────────────────────────────────┘
```

---

## 四、快速操作手册

### 4.1 首次部署服务器端（30分钟，只做一次）

```bash
# 1. SSH登录
ssh root@60.205.171.100

# 2. 上传并执行FRP安装脚本
# （或直接在ECS网页终端粘贴 frps-setup.sh 内容）
bash frps-setup.sh

# 3. 验证
curl http://localhost:7500  # FRP控制台
systemctl status frps       # 服务状态
```

### 4.2 首次配置本地端（15分钟，只做一次）

```powershell
# 1. 下载FRP客户端
# https://github.com/fatedier/frp/releases → frp_0.61.1_windows_amd64.zip
# 解压到 阿里云服务器\frp\ 目录

# 2. 复制配置（先编辑 secrets.toml 填入真实密码）
# frpc.toml 已配置好，确认 secrets.toml 中的 token 正确

# 3. 安装为开机自启
powershell -ExecutionPolicy Bypass -File 阿里云服务器\install-frpc.ps1

# 4. 启动 remote_agent
python 远程桌面\remote_agent.py --token 你的密码
```

### 4.3 日常使用

```
# 主站（HTTPS）
https://aiotvr.xyz

# Home Assistant（HTTPS反代）
https://aiotvr.xyz:8443

# FRP控制台（HTTPS反代，需Basic Auth）
https://aiotvr.xyz/frp/

# API健康检查
https://aiotvr.xyz/api/status

# 手机浏览器（认知/管控/触觉）
http://60.205.171.100:19903/?token=你的密码

# Windows远程桌面（视觉/听觉）
mstsc → 60.205.171.100:13389
```

### 4.4 可选：部署Linux桌面（xrdp + XFCE）

```powershell
# 从Windows一键部署到阿里云
.\阿里云服务器\deploy-xrdp.ps1 -HostIP 60.205.171.100 -User root

# 部署完成后，Windows RDP直连
mstsc → 60.205.171.100:3389
```

---

## 五、三档穿透方案

| 档位 | 方案 | 成本 | 延迟 | 手机体验 | 视觉体验 |
|------|------|------|------|---------|---------|
| **零成本** | Cloudflare Quick Tunnel | ¥0 | 50-150ms | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **推荐** | **FRP + 阿里云轻量** | **¥38/年** | **20-40ms** | **⭐⭐⭐⭐⭐** | **⭐⭐⭐⭐⭐** |
| 极致 | Tailscale + 阿里云DERP | ¥38/年 | 5ms(P2P) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

**当前方案**：档位二（FRP + 阿里云），已部署运行。

**Cloudflare应急**（随时可用，无需配置）：
```powershell
cloudflared tunnel --url http://localhost:9903
# 输出 https://xxx.trycloudflare.com → 手机打开即用
```

---

## 六、安全体系

### 已实施
- ✅ Let's Encrypt SSL证书（aiotvr.xyz，过期2026-05-26）
- ✅ Nginx HTTPS + HTTP→HTTPS强制重定向
- ✅ HA反向代理（端口8443，含WebSocket支持）
- ✅ FRP Dashboard反向代理（/frp/，Basic Auth）
- ✅ Agent API网关（/api/status 健康检查）
- ✅ remote_agent Bearer Token 认证
- ✅ FRP auth.token 认证
- ✅ SSH Key 免密登录（ed25519，ssh aliyun）
- ✅ frpc `loginFailExit = false` 自动重连
- ✅ TLS 1.2/1.3 + HTTP/2

### 待实施
- ⚠️ SSL自动续期（certbot renew cron）
- ⚠️ FRP TLS加密（`transport.tls.force = true`）
- ⚠️ 安全组限制源IP（宝塔16528尤其重要）
- ⚠️ remote_agent Token 定期更换

### 敏感信息管理
- **`secrets.toml`** 存放真实密码（已gitignore，不提交）
- **`frpc.example.toml`** 是配置模板（占位符，安全提交）
- **`frps-setup.sh`** 从 `secrets.toml` 读取或用命令行参数

---

## 七、故障排查

| 症状 | 诊断 | 修复 |
|------|------|------|
| frpc连不上 | `curl http://60.205.171.100:7000` | 检查安全组+frps状态 |
| 外网访问不通 | `curl http://60.205.171.100:19903` | 检查安全组+frpc映射 |
| FRP控制台打不开 | 浏览器打开 `:7500` | 安全组开放7500 |
| SSH连不上 | `ssh -v root@60.205.171.100` | 安全组开放22+检查Key |
| xrdp黑屏 | `journalctl -u xrdp -n 50` | 重启xrdp+检查.xsession |
| remote_agent无响应 | 本地 `curl localhost:9903` | 重启agent+检查端口 |

**Guardian自愈**：frpc断线自动重连，remote_agent可配置计划任务自启。

---

## 八、文件说明

| 文件 | 运行位置 | 用途 |
|------|---------|------|
| `frps-setup.sh` | **阿里云ECS** | FRP Server一键安装 |
| `aliyun-full-setup.ps1` | **本地Windows** | 一键全量部署(SSH+FRP+验证) |
| `frpc.example.toml` | 本地参考 | FRP Client配置模板 |
| `install-frpc.ps1` | **本地Windows** | FRP Client开机自启 |
| `xrdp-setup.sh` | **阿里云ECS** | xrdp+XFCE桌面一键安装（可选） |
| `deploy-xrdp.ps1` | **本地Windows** | 远程SSH部署xrdp到ECS（可选） |
| `secrets.toml` | 本地 | 敏感信息（gitignored，不提交） |
| `AGENTS.md` | — | AI Agent目录级指令 |

---

## 九、与其他目录的关系

| 目录 | 关系 | 说明 |
|------|------|------|
| `远程桌面/` | **被控端代码** | remote_agent.py + Web前端（不在本目录） |
| `远程桌面/阿里云远控全景方案.md` | **参考保留** | 完整方案分析，精华已融入本README |
| `双电脑互联/` | **知识中枢** | 双电脑全景，含阿里云部分 |

---

## 十、演进路线

| 优先级 | 方向 | 状态 | 下一步 |
|--------|------|------|--------|
| P0 | HTTPS统一入口 | ✅ 已完成 | SSL续期cron |
| P0 | FRP穿透 | ✅ 已部署 | 维护 |
| P0 | HA反向代理 | ✅ 端口8443 | 完成HA初始化 |
| P1 | 安全加固 | ⚠️ 部分 | TLS+安全组限IP |
| P2 | xrdp桌面 | ✅ 脚本就绪 | 需要时部署 |
| P3 | 子域名(ha.aiotvr.xyz) | ❌ 未做 | DNS+通配符证书 |
| P4 | 监控告警 | ❌ 未做 | UptimeRobot/自建 |
