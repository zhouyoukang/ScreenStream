# 智能家居控制中心

> 通过 ScreenStream 浏览器面板(Alt+Shift+H)统一控制所有智能设备。
> Gateway: 8900 | ScreenStream: 8080+

## 架构

```
浏览器 → ScreenStream /smarthome/* → Gateway :8900 → {MiCloud | eWeLink | Tuya | HA} → 设备
```

**核心洞察**: 一台在线音箱 > 十个平台API。音箱在家庭WiFi内代理执行语音指令，不依赖设备云端在线。

## 快速启动

```bash
cd 100-智能家居_SmartHome/07-网关服务_Gateway
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
100-智能家居_SmartHome/
├── README.md                  ← 本文件
└── 07-网关服务_Gateway/
    ├── gateway.py             ← 主网关 FastAPI多后端聚合
    ├── micloud_backend.py     ← 小米云直连 MIoT RPC + 音箱回退
    ├── ewelink_backend.py     ← 易微联直连 CoolKit v2
    ├── wechat_handler.py      ← ★ 微信公众号消息处理模块
    ├── config.example.json    ← 配置模板(提交到仓库)
    ├── config.json            ← 实际配置(gitignored)
    ├── requirements.txt       ← Python依赖
    ├── verify_platforms.py    ← 平台连通性验证
    ├── test_wechat.py         ← ★ 微信模块本地测试
    ├── test_mina.py           ← Mina API(音箱)连通测试
    └── start.bat              ← 一键启动
```

### ScreenStream 集成点
- **路由**: `040-反向控制_Input/010-输入路由_Routes/InputRoutes.kt`
- **前端**: `020-投屏链路_Streaming/010-MJPEG投屏_MJPEG/assets/index.html`
- **快捷键**: Alt+Shift+H

### 已验证路径 (2026-02-21)
| 路径 | 验证 | 核心价值 |
|------|------|---------|
| MiCloud MIoT | 13/13 | 24设备属性读写 |
| 音箱语音代理 | 17/17 | 控制离线设备(最强) |
| Mina API | TTS成功 | 音箱大脑直接调度 |
| eWeLink/Tuya | 代码就绪 | 待注册凭据 |
