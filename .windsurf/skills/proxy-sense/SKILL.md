---
description: Agent代理感知与自动修复。当网络请求失败、需要访问国外资源(GitHub/npm/PyPI/Docker)、或需要诊断代理状态时自动触发。
---

# Proxy Sense — Agent 代理五感

> 让Agent无感穿越GFW，自动感知/使用/修复Clash代理。

## 快速命令

```powershell
# 1. 快速状态 (JSON一行，<100ms)
python clash-agent/proxy_sense.py

# 2. 深度检查 (连通性+延迟+规则+节点数)
python clash-agent/proxy_sense.py --check

# 3. 自动修复 (代理挂了自动重启)
python clash-agent/proxy_sense.py --fix

# 4. 设置代理环境变量 (当前终端)
python clash-agent/proxy_sense.py --env | Invoke-Expression
```

## Agent网络请求模式

### 访问国外资源时 (GitHub/npm/PyPI/Docker)

```powershell
# 方式1: IWR/IRM 加 -Proxy 参数 (推荐，单次请求)
Invoke-WebRequest -Uri "<URL>" -Proxy "http://127.0.0.1:7890" -UseBasicParsing -TimeoutSec 15

# 方式2: 批量操作前设环境变量
python clash-agent/proxy_sense.py --env | Invoke-Expression
# 之后所有 pip/npm/git/curl 自动走代理
```

### 访问国内资源时
```powershell
# 不加 -Proxy，直连更快
Invoke-WebRequest -Uri "<URL>" -UseBasicParsing -TimeoutSec 15
```

### 降级链 (网络请求失败时)
1. **直连尝试** → 国内资源通常直连即可
2. **加代理重试** → `-Proxy "http://127.0.0.1:7890"`
3. **检查代理状态** → `python clash-agent/proxy_sense.py`
4. **自动修复** → `python clash-agent/proxy_sense.py --fix`
5. **告知用户** → "代理引擎无法启动，请检查clash-agent"

## 端口分配 (固定)
- **7890**: Mixed (HTTP+SOCKS5) 代理
- **9097**: Clash RESTful API
- **9098**: VPN Manager Web UI

## 核心文件
- `clash-agent/proxy_sense.py` — 代理感知模块
- `clash-agent/clash-meta.exe` — Mihomo 引擎
- `clash-agent/clash-config.yaml` — 完整配置
- `clash-agent/node_aggregator.py` — 免费节点聚合器
- `clash-agent/vpn-manager.py` — Flask Web UI 后端
- `clash-agent/vpn-app.pyw` — 系统托盘应用

## 判断是否需要代理的规则
| 目标 | 需要代理 | 说明 |
|------|---------|------|
| `github.com` / `raw.githubusercontent.com` | ✅ | GitHub |
| `npmjs.org` / `registry.npmjs.org` | ✅ | npm |
| `pypi.org` / `files.pythonhosted.org` | ⚠️ | 有时可直连 |
| `hub.docker.com` / `gcr.io` | ✅ | Docker |
| `api.openai.com` | ✅ | OpenAI |
| `*.google.com` / `*.googleapis.com` | ✅ | Google |
| `aiotvr.xyz` | ❌ | 自有服务器 |
| `127.0.0.1` / `localhost` | ❌ | 本地 |
| `192.168.*.*` | ❌ | 局域网 |
