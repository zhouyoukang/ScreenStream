---
name: smart-home-hub
description: AI中枢模式：Windsurf作为用户智能家居+手机+桌面的统一感知与控制中枢。当需要查看用户状态、主动响应环境变化、跨系统联动、或构建高维感知体验时自动触发。
triggers:
  - 查看用户当前活动/状态/位置
  - 智能家居与手机联动控制
  - 主动感知引擎操作(ProactiveAgent)
  - 高维度用户状态推断
  - 跨系统(手机+家居+桌面)编排
---

# AI 中枢 — Smart Home Hub

## 架构总览

```
Windsurf (AI大脑)
    ↕
AGI Dashboard :9090      — 观: 全系统配置+用户状态总览
    ├── 用户全感知面板      — 感: 手机+家居+活动推断实时显示
    └── 服务全景面板        — 枢: 所有服务在线状态

SmartHome Gateway :8900  — 控: 多后端设备控制
    ├── ProactiveAgent     — 主动感知守护(30s手机+60s家居)
    │   ├── PhoneSensor    — 手机五感(battery/screen/notif/app)
    │   ├── HomeSensor     — 家居(temp/presence/lights/fans)
    │   ├── ContextInference — 活动推断(sleeping/working/away/home)
    │   └── RulesEngine    — 9条规则: 低电/高温/晨起/回家/睡眠/etc
    ├── MiCloud 24设备      — 小米云直连
    ├── eWeLink/Sonoff      — 易微联设备
    ├── Mina TTS           — 小爱音箱播报
    └── 微信公众号          — 远程入口

Phone API :8084          — 手: 手机五感直控
RemoteDesktop :9903      — 桌: 台式机全功能控制
```

## 快速状态读取

### 1. 用户上下文（最常用）
```powershell
# 完整用户上下文（手机+家居+活动）
Invoke-RestMethod http://127.0.0.1:8900/proactive/context
# → {inferred_activity, at_home, likely_sleeping, phone:{battery,screen_off,...}, home:{temperature,lights_on,...}}

# 人类可读摘要
Invoke-RestMethod http://127.0.0.1:8900/proactive/summary
# → {summary: "活动=working | 手机电量=85% | 室温=22.3°C"}

# AGI仪表盘（浏览器可视化）
Start-Process "http://localhost:9090"
```

### 2. 手机状态
```powershell
Invoke-RestMethod http://127.0.0.1:8084/status        # 屏幕/无障碍状态
Invoke-RestMethod http://127.0.0.1:8084/deviceinfo    # 电量/网络/存储
Invoke-RestMethod http://127.0.0.1:8084/notifications/read?limit=10  # 通知
Invoke-RestMethod http://127.0.0.1:8084/screen/text   # 前台APP+屏幕文字
```

### 3. 家居状态
```powershell
Invoke-RestMethod http://127.0.0.1:8900/devices       # 所有设备
Invoke-RestMethod http://127.0.0.1:8900/speakers      # 音箱在线状态
Invoke-RestMethod http://127.0.0.1:8900/micloud/diagnose  # MiCloud诊断
```

## ProactiveAgent 操作

### 强制立即感知（调试）
```powershell
# 单次采集+规则检查
Invoke-RestMethod -Method POST http://127.0.0.1:8900/proactive/force-check

# 仅检查特定规则
Invoke-RestMethod -Method POST "http://127.0.0.1:8900/proactive/force-check?rule_id=battery_low"

# 立即采集手机状态
Invoke-RestMethod -Method POST http://127.0.0.1:8900/proactive/phone/poll

# 立即采集家居状态
Invoke-RestMethod -Method POST http://127.0.0.1:8900/proactive/home/poll
```

### 规则管理
```powershell
# 查看所有规则状态
Invoke-RestMethod http://127.0.0.1:8900/proactive/rules

# 开关规则
Invoke-RestMethod -Method POST http://127.0.0.1:8900/proactive/rules/notification_spike `
  -Body '{"enabled":true}' -ContentType 'application/json'

# 历史事件
Invoke-RestMethod "http://127.0.0.1:8900/proactive/history?limit=20"
```

## 9条主动规则速查

| rule_id | 触发条件 | 动作 | 冷却 |
|---------|---------|------|------|
| `battery_low` | 电量20-8%且不充电 | TTS提醒 | 10min |
| `battery_critical` | 电量<8%且不充电 | TTS警报 | 3min |
| `high_temp_fan` | 室温>28°C且在家 | 开风扇+TTS | 30min |
| `low_temp_alert` | 室温<14°C且醒着 | TTS提醒 | 60min |
| `morning_greeting` | 6-9点+手机亮屏 | TTS问候 | 12h |
| `sleep_auto_off` | 23点+屏关+有灯亮 | sleep场景+TTS | 8h |
| `welcome_home` | 手机从不可达→可达 | home场景+TTS | 30min |
| `notification_spike` | 新通知≥3条 | TTS播报(默认关) | 2min |
| `evening_relax` | 19-23点+在家+无灯 | TTS提醒开灯 | 24h |

## 智能家居控制速查

```powershell
# 场景宏
Invoke-RestMethod -Method POST http://127.0.0.1:8900/scenes/macros/home   # 回家
Invoke-RestMethod -Method POST http://127.0.0.1:8900/scenes/macros/sleep  # 睡觉
Invoke-RestMethod -Method POST http://127.0.0.1:8900/scenes/macros/away   # 离家
Invoke-RestMethod -Method POST http://127.0.0.1:8900/scenes/macros/work   # 工作

# TTS播报
Invoke-RestMethod -Method POST http://127.0.0.1:8900/micloud/tts -Body '{"text":"你好"}' -ContentType 'application/json'

# 音箱语音代理（最强路径）
Invoke-RestMethod -Method POST http://127.0.0.1:8900/proxy/voice -Body '{"command":"打开灯带","silent":false}' -ContentType 'application/json'

# 快捷操作
Invoke-RestMethod -Method POST http://127.0.0.1:8900/quick/all_off
Invoke-RestMethod -Method POST http://127.0.0.1:8900/quick/lights_off
```

## 服务启动顺序

```powershell
# 1. 智能家居网关（含ProactiveAgent）
cd 智能家居/网关服务
python gateway.py
# → :8900 + ProactiveAgent自动启动

# 2. AGI仪表盘
python AGI/dashboard-server.py
# → :9090 托盘图标

# 3. 远程桌面Agent（已在运行 :9903）
python 远程桌面/remote_agent.py

# 4. ADB转发（手机API）
adb forward tcp:8084 tcp:8084
# → :8084
```

## config.json ProactiveAgent配置

在 `智能家居/网关服务/config.json` 中添加：
```json
"proactive": {
  "enabled": true,
  "phone_url": "http://127.0.0.1:8084",
  "gateway_url": "http://127.0.0.1:8900",
  "phone_interval_sec": 30,
  "home_interval_sec": 60,
  "rules_interval_sec": 15,
  "home_ssid_keywords": ["家", "Home"],
  "rules": {
    "notification_spike": {"enabled": true},
    "sleep_auto_off": {"enabled": true, "cooldown_sec": 28800}
  }
}
```

## Agent循环示例（高维感知）

```python
# 读取用户完整状态
import urllib.request, json

def get_user_state():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8900/proactive/context", timeout=3) as r:
            return json.loads(r.read())
    except:
        return {}

ctx = get_user_state()
activity = ctx.get("inferred_activity", "unknown")
phone_bat = ctx.get("phone", {}).get("battery", -1)
home_temp = ctx.get("home", {}).get("temperature", -1)

print(f"用户活动: {activity}")
print(f"手机电量: {phone_bat}%")
print(f"室温: {home_temp}°C")
```

## 全景文档
- `智能家居/README.md` — 网关架构+API+设备列表
- `智能家居/NEEDS_ANALYSIS.md` — 用户需求层次分析
- `智能家居/深度探索报告.md` — 完整技术深度报告
- `手机操控库/README.md` — PhoneLib使用指南
- `远程桌面/README.md` — 远程桌面Agent API
