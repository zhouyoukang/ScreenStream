# 智能家居设备清单与场景配置

> 最后更新: 2026-02-21

## 一、设备清单

### Sonoff WiFi智能开关系列 (×5)

| # | 名称 | Entity ID | 协议 | 控制方式 | 日常用途 |
|---|------|-----------|------|----------|----------|
| 1 | 四号开关 | `switch.sonoff_10022dede9_1` | WiFi/eWeLink | HA/n8n/语音 | 主照明 |
| 2 | 五号开关 | `switch.sonoff_10022dedc7_1` | WiFi/eWeLink | HA/n8n/语音 | 备用(与4互斥) |
| 3 | 中央插头 | `switch.sonoff_10022cf71d` | WiFi/eWeLink | HA/n8n/语音 | 中央电源 |
| 4 | 户外插头 | `switch.sonoff_100235142b_1` | WiFi/eWeLink | HA/n8n/语音 | 户外设备 |
| 5 | 床插头 | `switch.sonoff_10022cf6a2` | WiFi/eWeLink | HA/n8n/语音 | 床头电源 |

### 照明系统 (×3)

| # | 名称 | Entity ID | 能力 | 场景 |
|---|------|-----------|------|------|
| 1 | 飞利浦灯带 | `light.philips_strip3_12ad_light` | RGB+亮度+色温+呼吸效果 | 聚会/浪漫/阅读 |
| 2 | 技嘉RGB | `light.b650m_aorus_elite_ax_0` | RGB灯效 | 桌面氛围 |
| 3 | 床底灯 | (Node-RED定时控制) | 开/关 | 晚间照明 |

### 环境控制 (×2)

| # | 名称 | Entity ID | 能力 |
|---|------|-----------|------|
| 1 | 小米风扇P221 | `fan.dmaker_p221_5b47_fan` | 多档风速(低/中/高) |
| 2 | 小米开关 | `switch.xiaomi_miio_switch` | 开/关 |

### AI语音设备

| # | 名称 | 接入方式 | 功能 |
|---|------|----------|------|
| 1 | 小爱音箱Pro | MIGPT-Easy(Python) | 语音→AI→设备控制 |
| 2 | 豆包/Kimi系统 | API调用 | AI语音对话 |
| 3 | 网易云音乐 | 三星手机控制 | 音乐播放 |

---

## 二、场景配置

### 已实现场景

| 场景 | 触发 | 灯光 | 风扇 | 音频 | 其他 |
|------|------|------|------|------|------|
| **睡眠模式** | 语音/定时 | 暖光低亮度 | 低速 | 关音乐 | 关豆包通话 |
| **聚会模式** | 语音 | 彩色灯光 | 高速 | 播放音乐 | - |
| **阅读模式** | 语音 | 白光 | 低速 | - | - |
| **浪漫模式** | 语音 | 暖光+呼吸 | - | - | - |
| **专注模式** | 语音 | 冷白光 | 中速 | - | - |
| **定时开灯** | 21:00 | 开床底灯 | - | - | 自动 |
| **定时关灯** | 07:00 | 关床底灯 | - | - | 自动 |

### 互斥逻辑

- 开4号开关 → 自动关5号开关
- 开5号开关 → 自动关4号开关
- 播放音乐 → 自动停止豆包通话

### 能耗监控

- 实时功率监控
- 每日能耗计算
- 月度费用预估
- 过载保护

---

## 三、网络拓扑

```
路由器 (192.168.31.1)
├── Home Assistant 服务器 (:8123)
│   ├── Sonoff开关 ×5 (eWeLink/WiFi)
│   ├── 飞利浦灯带 (米家WiFi)
│   ├── 技嘉RGB (WiFi)
│   └── 小米设备 ×2 (米家WiFi)
├── Node-RED (:1880)
├── n8n (:5678)
├── PC (192.168.31.xxx)
│   └── MIGPT-Easy运行
├── 小爱音箱Pro (192.168.31.xxx)
└── 手机 (192.168.31.228)
    └── ScreenStream (:8080+)
```

---

## 四、API快速参考

### Home Assistant
```bash
# 查询所有设备状态
curl -H "Authorization: Bearer TOKEN" http://localhost:8123/api/states

# 控制开关
curl -X POST -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "switch.sonoff_10022dede9_1"}' \
  http://localhost:8123/api/services/switch/turn_on

# 控制灯光
curl -X POST -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "light.philips_strip3_12ad_light", "brightness": 128, "rgb_color": [255,0,0]}' \
  http://localhost:8123/api/services/light/turn_on
```

### n8n Webhooks
```bash
# 设备状态
curl -X POST http://localhost:5678/webhook/smart-home \
  -d '{"action": "status"}'

# 场景控制
curl -X POST http://localhost:5678/webhook/unified-scene \
  -d '{"scene": "sleep_mode"}'

# AI场景调节
curl -X POST http://localhost:5678/webhook/ai-scene-adjust \
  -d '{"ai_analysis": "用户正在工作", "auto_adjust": true}'
```

### MIGPT-Easy
```bash
# 通过API服务器控制HA设备
curl -X POST http://localhost:5001/v1/chat/completions \
  -d '{"messages": [{"role": "user", "content": "打开客厅灯"}]}'
```
