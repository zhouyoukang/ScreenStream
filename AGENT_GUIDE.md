# 道生一 · DaoOne — Agent操作指令 v2.0

> **万物归一核心** — 单文件/零依赖/全设备/任何Agent
> `dao_one.py` = 唯一入口 (E2E 15/15 PASS)

## 快速启动

```bash
# HTTP Hub :8880
python dao_one.py serve

# Agent感知 (~30 tokens)
python dao_one.py sense

# 设备列表
python dao_one.py devices

# 执行操作
python dao_one.py action Quest3 home
python dao_one.py action Quest3 shell '{"command":"echo hello"}'

# 健康检查
python dao_one.py health --json
```

## 端口: 8880

## Agent API (HTTP)

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | `/api/health` | 系统健康 (version/devices/online/hubs/uptime) |
| GET | `/api/sense` | Agent感知摘要 (~30 tokens) |
| GET | `/api/devices` | 全部设备详情+状态 |
| GET | `/api/hubs` | 已发现的Hub服务列表 |
| GET | `/api/capabilities` | 全能力清单 (Agent发现用) |
| GET | `/api/probe` | 重新探测所有设备 |
| GET | `/api/discover` | 全量发现 (ADB+Hub扫描) |
| GET | `/api/device/{name}` | 单设备详情 |
| GET | `/api/gua` | 八卦全景报告 |
| GET | `/api/log?n=50` | 事件日志 |
| GET | `/api/hub/{hub}/{path}` | Hub API代理 (透传) |
| POST | `/api/action` | 执行操作: `{device, cmd, ...params}` |
| POST | `/api/sequence` | 多步自动化: `{steps: [{device, cmd, delay}]}` |
| POST | `/api/hub/{hub}/{path}` | Hub API代理 POST |

## 设备矩阵

| 卦 | 设备 | 类型 | 操作 |
|----|------|------|------|
| ☷坤 | OnePlus | phone | home/back/wake/screenshot/tap/swipe/text/launch/shell/battery/list_packages/ss_* |
| ☷坤 | Samsung | phone | 同上 |
| ☷坤 | OPPO-SE | phone | 同上 |
| ☵坎 | Quest3 | vr | 同上 + **cdp_list/browse** |
| ☰乾 | RayNeo-V3 | glasses | 同上 |
| ☲离 | Desktop-141 | pc | processes/services/screenshot/ahk |
| ☲离 | LocalPC | pc | processes/services/screenshot/ahk |
| ☶艮 | VP99-Watch | watch | status |
| ☴巽 | Aliyun | server | health/deploy/ssh |
| ☴巽 | Server | server | health/deploy/ssh |
| ☳震 | HomeAssistant | iot | service/states/entity/toggle |

## 操作参数

### 手机/VR (ADB设备)
```json
{"device":"Quest3", "cmd":"shell", "command":"echo hello"}
{"device":"Quest3", "cmd":"tap", "x":540, "y":1200}
{"device":"Quest3", "cmd":"swipe", "x1":540, "y1":1500, "x2":540, "y2":500}
{"device":"Quest3", "cmd":"text", "text":"hello world"}
{"device":"Quest3", "cmd":"launch", "pkg":"com.oculus.browser"}
{"device":"Quest3", "cmd":"screenshot", "wake":true}
{"device":"Quest3", "cmd":"cdp_list"}
{"device":"Quest3", "cmd":"browse", "url":"https://aiotvr.xyz/quest/"}
```

### PC
```json
{"device":"LocalPC", "cmd":"processes"}
{"device":"LocalPC", "cmd":"ahk", "script":"MsgBox 'Hello'"}
```

### HA
```json
{"device":"HomeAssistant", "cmd":"toggle", "entity":"light.bedroom"}
{"device":"HomeAssistant", "cmd":"service", "domain":"light", "service":"turn_on", "entity":"light.bedroom"}
{"device":"HomeAssistant", "cmd":"states"}
```

### Server
```json
{"device":"Aliyun", "cmd":"ssh", "cmd":"uptime"}
{"device":"Aliyun", "cmd":"deploy", "local":"index.html", "remote":"/var/www/quest/"}
```

### Hub代理
```
GET  /api/hub/ors6/api/health       → 透传到 ORS6 Hub :41927
POST /api/hub/ors6/api/endpoint     → 透传POST到 ORS6 Hub
```

## 多步自动化 (Sequence)

```json
POST /api/sequence
{
  "steps": [
    {"device":"Quest3", "cmd":"wake"},
    {"device":"Quest3", "cmd":"home", "delay":0.5},
    {"device":"Quest3", "cmd":"browse", "url":"https://aiotvr.xyz", "delay":1}
  ]
}
```

## 配置

- `dao_config.json` — 设备配置 (serial/IP/端口)
- `secrets.env` — HA Token等凭据 (自动读取)
- 环境变量: `DAO_PORT`/`DAO_ADB`/`DAO_HA_URL`/`DAO_HA_TOKEN`

## 已知Hub服务 (自动发现)

| 名称 | 端口 | 说明 |
|------|------|------|
| ors6 | 41927 | ORS6饮料摇匀器 |
| wan-wu | 8808 | 万物中枢 |
| dual-pc | 8809 | 双电脑互联 |
| ui-control | 8819 | UI操控 |
| arsenal | 8840 | Agent军火库 |
| cognitive | 8850 | 认知系统 |
| quest3 | 8863 | Quest3 Unified |
| quest3-ops | 8864 | Quest3 Ops |
| bambu | 8870 | 拓竹3D打印 |
| family-remote | 9860 | 亲情远程 |
| sim-platform | 9500 | 虚拟仿真 |
| windsurf-mgr | 9999 | Windsurf管理 |
| openclaw | 18880 | OpenClaw |

## v2.0.0 变更 (v1.0.0 → v2.0.0)

| 变更 | 详情 |
|------|------|
| P0修复 | shell/list_packages: _adb_shell_ex检测ADB断连,正确报错(不再假ok:true) |
| P1修复 | screenshot: +wake参数 / stale-probe: 120s后重验设备在线 |
| CDP集成 | Quest3 VR: cdp_list列出浏览器页面, browse打开URL |
| Hub代理 | GET/POST /api/hub/{name}/{path} 透传到专业Hub |
| battery | 新增battery命令 |
| HA改进 | 始终添加HA设备,probe自动检测可用性 |
| favicon | SVG ☯ favicon,消除console error |
| 背景刷新 | 60s周期更新设备status(不只是probe) |

## E2E验证 (v2.0.0)

| 测试 | 结果 |
|------|------|
| health | ✅ v2.0.0 |
| sense | ✅ 170ch |
| devices | ✅ 11个 |
| capabilities | ✅ 12个 |
| Quest3:home | ✅ |
| Quest3:shell | ✅ output='dao_v2' |
| Samsung:shell(offline) | ✅ ok=false,error正确 |
| Quest3:list_packages | ✅ 271包 |
| Quest3:battery | ✅ 100% |
| Quest3:cdp_list | ✅ 3页 |
| hub_proxy:ors6 | ✅ |
| HA exists | ✅ online=false(Docker未运行) |
| dashboard | ✅ 13732B |
| gua | ✅ 271ch |
| log | ✅ |

## 文件清单

| 文件 | 说明 |
|------|------|
| `dao_one.py` | ★核心 (单文件归一) |
| `dao_config.json` | 设备配置 (8设备) |
| `→道生一.cmd` | 一键启动器 |
| `AGENT_GUIDE.md` | 本文件 |
