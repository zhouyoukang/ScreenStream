# 智能家居控制中心

> **971设备** | Gateway :8900 (MiCloud + HA桥接) | 95自动化 | 28 AI Agent | 7场景
> 笔记本Python网关 ↔ 台式机Home Assistant Docker，合二为一

## 架构

```
用户入口
  ├─ 📱 微信公众号 ─── POST /wx → Gateway:8900 → 设备
  ├─ 🌐 浏览器仪表盘 ── Gateway:8900/dashboard → 设备+场景+TTS
  ├─ 🔊 语音 ────── 小爱音箱 → execute-text-directive → 全屋WiFi设备
  └─ 💻 ScreenStream ─ /smarthome/* → Gateway:8900

控制路径（从快到慢）
  1️⃣ MiCloud RPC直控 ── 200ms ── 在线WiFi设备(24台)
  2️⃣ HA API ────── ~100ms ── 1416 entities(含Sonoff/OpenRGB)
  3️⃣ 音箱语音代理 ──── 2s ─── 任何设备(含离线)
```

**核心洞察**: 一台在线音箱 > 十个平台API。`execute-text-directive` 是万物互联的塑码密钥。

## 快速启动

```bash
cd 智能家居/网关服务
pip install -r requirements.txt
python gateway.py           # MiCloud直连模式(默认)
adb reverse tcp:8900 tcp:8900
# → ScreenStream Alt+Shift+H 打开面板
```

## 硬件设备

| 名称 | ID | 类型 |
|------|-----------|------|
| 四号开关 | `switch.sonoff_10022dede9_1` | Sonoff(eWeLink) |
| 五号开关 | `switch.sonoff_10022dedc7_1` | Sonoff(eWeLink) |
| 中央插头 | `switch.sonoff_10022cf71d` | Sonoff(eWeLink) |
| 户外插头 | `switch.sonoff_100235142b_1` | Sonoff(eWeLink) |
| 床插头 | `switch.sonoff_10022cf6a2` | Sonoff(eWeLink) |
| 飞利浦灯带 | `light.philips_strip3_12ad_light` | MiCloud(RGB+亮度+色温) |
| 技嘉RGB | `light.b650m_aorus_elite_ax_0` | MiCloud |
| 小米风扇P221 | `fan.dmaker_p221_5b47_fan` | MiCloud(多档) |
| 小爱音箱Pro | MiCloud TTS | 语音+AI+设备控制 |

## Gateway API (port 8900)

### 核心
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 网关状态 |
| GET | `/devices` | 设备列表(聚合全部后端) |
| GET | `/devices/{id}` | 单设备详情 |
| POST | `/devices/{id}/control` | 控制 `{"action":"turn_on"}` |
| POST | `/quick/{action}` | all_off / lights_off / fans_off |
| POST | `/batch` | 批量控制 |

### MiCloud
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/micloud/status` | 连接状态 |
| GET | `/micloud/diagnose` | 深度诊断(云端/session/在线) |
| POST | `/micloud/rpc` | MIoT RPC 原始调用 |
| POST | `/micloud/tts` | TTS `{"text":"你好"}` |
| POST | `/micloud/relogin` | 重新登录(token过期时) |
| POST | `/micloud/refresh` | 刷新设备列表 |

### 音箱代理（最强远程路径）
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/proxy/voice` | 语音代理 `{"command":"打开灯带","silent":true}` |
| GET | `/tts/{text}` | TTS快捷(浏览器地址栏即可) |
| GET | `/speakers` | 音箱列表+在线状态 |
| GET | `/scenes/macros` | 场景宏(home/away/sleep/movie/work) |
| POST | `/scenes/macros/{name}` | 执行场景宏 |

### eWeLink / Tuya / HA (按需启用)
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/ewelink/devices` | eWeLink设备列表 |
| POST | `/ewelink/refresh` | 刷新eWeLink设备 |
| GET | `/tuya/devices` | 涂鸦设备 |
| POST | `/tuya/devices/{id}/cmd` | 涂鸦控制 |
| GET | `/scenes` | HA场景列表 |
| POST | `/scenes/{id}/activate` | 触发HA场景 |

## 配置 (config.json)

```jsonc
{
  "gateway": {"host": "0.0.0.0", "port": 8900, "mode": "direct"},
  "micloud": {
    "enabled": true,
    "_comment": "三级凭据链: L1 config直填token → L2 自缓存 → L3 ha_config_path回退HA",
    "user_id": "", "service_token": "", "ssecurity": "",
    "username": "", "password": "", "server": "cn",
    "ha_config_path": ""
  },
  "ewelink": {"enabled": true, "app_id": "", "app_secret": "", "email": "", "password": ""},
  "tuya":    {"enabled": false, "client_id": "", "secret": ""},
  "ha":      {"enabled": false, "url": "http://192.168.31.228:8123", "token": ""}
}
```

## 故障排查

| 诊断 | 命令 |
|------|------|
| 网关状态 | `curl http://127.0.0.1:8900/` |
| MiCloud诊断 | `curl http://127.0.0.1:8900/micloud/diagnose` |
| 重新登录 | `curl -X POST http://127.0.0.1:8900/micloud/relogin` |
| 刷新设备 | `curl -X POST http://127.0.0.1:8900/micloud/refresh` |

| MiCloud错误码 | 含义 | 解决 |
|--------|------|------|
| -704042011 | 设备离线 | 检查电源/WiFi |
| -704220043 | Token过期 | `/micloud/relogin` |
| -704010000 | 未授权 | 检查凭据 |

## 文件结构

```
智能家居/
├── README.md                  ← 本文件
└── 网关服务/
    ├── gateway.py             ← 主网关 FastAPI 多后端聚合(路由+编排)
    ├── micloud_backend.py     ← 小米云直连 MIoT RPC + 音箱回退
    ├── ewelink_backend.py     ← 易微联直连 CoolKit v2
    ├── ha_backend.py          ← Home Assistant REST API 客户端
    ├── mina_backend.py        ← 小米音箱 Mina API 客户端(TTS+对话)
    ├── tuya_backend.py        ← 涂鸦 Cloud API 客户端
    ├── wechat_handler.py      ← ★ 微信公众号消息处理模块
    ├── config.example.json    ← 配置模板(提交到仓库)
    ├── config.json            ← 实际配置(gitignored, 含敏感凭据)
    ├── .xiaomi_token_cache.json ← MiCloud token 缓存(gitignored)
    ├── mina_token.json        ← Mina speaker token(gitignored)
    ├── requirements.txt       ← Python依赖
    ├── verify_platforms.py    ← 平台连通性验证(含微信路由)
    ├── test_wechat.py         ← 微信模块离线单元测试
    ├── test_wx_live.py        ← 微信在线测试(本地/公网URL均支持)
    ├── start.bat              ← Gateway一键启动
    └── start_wechat.bat       ← Gateway + Cloudflare隧道一键启动
```

### 模块化架构
gateway.py 只负责路由和编排，后端逻辑拆分到独立模块:
- `micloud_backend.py` → MiCloudDirect 类(设备/属性/RPC)
- `ewelink_backend.py` → EWeLinkClient 类(CoolKit v2 API)
- `ha_backend.py` → HAClient 类(场景/历史/模板)
- `mina_backend.py` → MinaClient 类(音箱TTS/对话历史)
- `tuya_backend.py` → TuyaClient 类(涂鸦Cloud API)
- `wechat_handler.py` → WeChatCommandRouter 类(微信命令解析)

### ScreenStream 集成点
- **路由**: `反向控制/输入路由/InputRoutes.kt`
- **前端**: `投屏链路/MJPEG投屏/assets/index.html`
- **快捷键**: Alt+Shift+H

## 微信公众号控制 (NEW)

通过微信公众号发送文字/语音消息远程控制智能家居。

### 架构
```
微信用户 → 微信服务器 → POST /wx (XML) → Gateway → MiCloud/eWeLink/音箱 → 设备
```

### 支持的命令

| 类型 | 示例 |
|------|------|
| 设备控制 | 打开灯带 / 关闭风扇 / 关闭床插头 |
| 状态查询 | 状态 / 设备列表 |
| 场景模式 | 回家模式 / 睡眠模式 / 工作模式 |
| 快捷操作 | 全部关闭 / 关灯 / 开灯 |
| 音箱播报 | 说 你好世界 |
| 自然语言 | 任意文字→自动转发给小爱音箱 |
| 语音消息 | 微信语音→自动识别→执行命令 |

### 部署步骤

#### 1. 申请微信测试号 (免费，无需企业资质)
1. 访问 https://mp.weixin.qq.com/debug/cgi-bin/sandbox
2. 用微信扫码登录
3. 记录页面上的 `appID` 和 `appsecret`

#### 2. 配置 config.json
```json
"wechat": {
    "enabled": true,
    "token": "smarthome2026",
    "appid": "从测试号页面复制",
    "appsecret": "从测试号页面复制"
}
```

#### 3. 公网暴露 (cloudflared，免费无账号)
```bash
# 安装: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
cloudflared tunnel --url http://localhost:8900
# 获得公网URL，如: https://xxxx.trycloudflare.com
# 或一键启动: start_wechat.bat (自动启动Gateway + Tunnel)
```

#### 4. 配置测试号回调
- 在测试号页面「接口配置信息」填入:
  - URL: `https://xxxx.trycloudflare.com/wx`
  - Token: `smarthome2026` (与config.json一致)
- 点击「提交」，验证通过即完成

#### 5. 扫码关注测试号
- 测试号页面底部二维码 → 微信扫码关注
- 发送「帮助」测试

### 微信公众号 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/wx` | 微信Token验证 |
| POST | `/wx` | 消息接收与回复 |
| GET | `/wx/status` | 模块状态 |

### 已验证路径 (2026-02-21)
| 路径 | 验证 | 核心价值 |
|------|------|---------|
| MiCloud MIoT | 13/13 | 24设备属性读写 |
| 音箱语音代理 | 17/17 | 控制离线设备(最强) |
| Mina API | TTS成功 | 音箱大脑直接调度 |
| eWeLink/Tuya | 代码就绪 | 待注册凭据 |
