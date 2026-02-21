# 国内智能家居平台 API 接入深度研究

> 版本：v1.0 | 日期：2026-02-21
> 核心问题：**如何用 API 调用的形式介入国内各大智能家居平台，调用其核心功能？**

---

## 总览：可行性矩阵

| 平台 | API开放度 | 个人开发者 | 免费额度 | 本地控制 | 推荐接入方式 |
|------|----------|-----------|---------|---------|-------------|
| **涂鸦智能 (Tuya)** | ⭐⭐⭐⭐⭐ | ✅ 体验版免费 | 有限(500次/月API) | ✅ LocalTuya | **直接Cloud API** |
| **Home Assistant** | ⭐⭐⭐⭐⭐ | ✅ 完全开源 | 无限(本地) | ✅ 核心能力 | **本地REST API** |
| **小米/米家** | ⭐⭐⭐ | ⚠️ 非官方 | N/A | ✅ python-miio | **HA官方集成 + python-miio** |
| **易微联 (eWeLink)** | ⭐⭐⭐⭐ | ✅ 开发者中心 | 有限 | ✅ SonoffLAN | **eWeLink API + 本地LAN** |
| **Aqara (绿米)** | ⭐⭐⭐⭐ | ✅ 开放平台 | 有限 | ✅ HomeKit/Zigbee | **Aqara Open API** |
| **美的美居** | ⭐⭐⭐ | ⚠️ 企业为主 | 需申请 | ⚠️ midea-ac-lan | **HA集成(midea_ac_lan)** |
| **天猫精灵** | ⭐⭐ | ✅ 技能平台 | 免费 | ❌ | **AliGenie技能 + HA桥接** |
| **小度 (DuerOS)** | ⭐⭐ | ✅ 技能平台 | 免费 | ❌ | **DuerOS技能 + HA桥接** |
| **华为鸿蒙智联** | ⭐ | ❌ 极封闭 | N/A | ❌ | **仅ScreenStream APP控制** |
| **海尔智家** | ⭐⭐ | ⚠️ 抓包方式 | N/A | ⚠️ | **HA集成(haier)** |

### 关键结论

> **能直接用 REST API 控制设备的只有 3 个平台：涂鸦、Home Assistant、易微联。**
> 其余平台要么需要通过 HA 桥接，要么需要逆向工程（python-miio），要么完全封闭。
> **最优策略：以 Home Assistant 为中枢，统一接管所有平台设备，对外暴露标准 REST API。**

---

## 一、涂鸦智能 (Tuya) — 最开放的商业平台

### 1.1 平台概况
- **官网**: https://developer.tuya.com
- **设备覆盖**: 全球最大 IoT 平台之一，国内大量白牌设备底层都是涂鸦方案
- **品类**: 开关/插座/灯具/传感器/摄像头/家电/门锁 等几乎所有品类
- **个人开发者**: 支持，体验版免费

### 1.2 Cloud API（云端控制）

**注册流程**:
1. 注册涂鸦开发者账号 → https://iot.tuya.com
2. 创建云项目 → 选择"智能家居"
3. 获取 `client_id` + `client_secret`
4. 关联涂鸦智能APP中的设备

**核心 API 端点**:

```
基础URL: https://openapi.tuyacn.com (中国区)

# 1. 获取Token
POST /v1.0/token?grant_type=1
→ 返回 access_token（有效期2小时）

# 2. 获取设备列表
GET /v1.0/users/{uid}/devices

# 3. 获取设备状态
GET /v1.0/devices/{device_id}/status
→ 返回: [{"code":"switch_led","value":true}, {"code":"bright_value","value":255}]

# 4. 控制设备（核心！）
POST /v1.0/devices/{device_id}/commands
Body: {
  "commands": [
    {"code": "switch_led", "value": true},
    {"code": "bright_value", "value": 128}
  ]
}

# 5. 获取设备支持的指令集
GET /v1.0/devices/{device_id}/functions

# 6. 批量控制
POST /v1.0/devices/{device_id}/commands  (可一次下发多条)

# 7. 设备规格查询（含所有可用属性）
GET /v1.0/devices/{device_id}/specifications
```

**签名机制**（HMAC-SHA256）:
```python
import hmac, hashlib, time, requests

client_id = "YOUR_CLIENT_ID"
secret = "YOUR_SECRET"
base_url = "https://openapi.tuyacn.com"

# Step 1: 获取Token
t = str(int(time.time() * 1000))
sign_str = client_id + t
sign = hmac.new(secret.encode(), sign_str.encode(), hashlib.sha256).hexdigest().upper()

headers = {
    "client_id": client_id,
    "sign": sign,
    "t": t,
    "sign_method": "HMAC-SHA256"
}
resp = requests.get(f"{base_url}/v1.0/token?grant_type=1", headers=headers)
access_token = resp.json()["result"]["access_token"]

# Step 2: 控制设备
t = str(int(time.time() * 1000))
sign_str = client_id + access_token + t
sign = hmac.new(secret.encode(), sign_str.encode(), hashlib.sha256).hexdigest().upper()

headers = {
    "client_id": client_id,
    "access_token": access_token,
    "sign": sign,
    "t": t,
    "sign_method": "HMAC-SHA256",
    "Content-Type": "application/json"
}
data = {"commands": [{"code": "switch_1", "value": True}]}
resp = requests.post(f"{base_url}/v1.0/devices/DEVICE_ID/commands", 
                     json=data, headers=headers)
```

**常用设备指令码**:
| 品类 | code | value类型 | 说明 |
|------|------|----------|------|
| 开关 | `switch_1` | bool | 开/关 |
| 灯 | `switch_led` | bool | 开/关 |
| 灯 | `bright_value` | 10-1000 | 亮度 |
| 灯 | `temp_value` | 0-1000 | 色温 |
| 灯 | `colour_data` | JSON | RGB颜色 |
| 插座 | `switch` | bool | 开/关 |
| 插座 | `cur_power` | int | 当前功率(只读) |
| 风扇 | `switch` | bool | 开/关 |
| 风扇 | `fan_speed_enum` | enum | 档位 |
| 窗帘 | `control` | open/stop/close | 控制 |
| 窗帘 | `percent_control` | 0-100 | 开合度 |

### 1.3 Local API（本地控制，无需云端）

通过 **LocalTuya** 方案可实现纯局域网控制：

```
前提: 获取设备的 local_key（需从涂鸦云API获取一次）

# 设备在局域网通过 UDP 6666/6667 端口广播
# 使用 tinytuya 库直接控制

pip install tinytuya

import tinytuya

d = tinytuya.OutletDevice('DEVICE_ID', '192.168.1.100', 'LOCAL_KEY')
d.set_version(3.3)

# 开关
d.turn_on()
d.turn_off()

# 读取状态
data = d.status()
print(data)  # {'dps': {'1': True, '2': 0, ...}}

# 设置DPS值
d.set_value(1, True)   # DPS 1 = 开关
d.set_value(2, 128)    # DPS 2 = 亮度
```

### 1.4 费用
| 版本 | 价格 | API调用 | 设备数 |
|------|------|---------|-------|
| 体验版 | 免费 | 500次/月 | 20台 |
| 基础版 | ¥3980/年 | 5万次/月 | 5000台 |
| 旗舰版 | ¥19800/年 | 50万次/月 | 7.5万台 |

> **个人用户策略**: 体验版 + LocalTuya 本地控制 = 完全免费且无限制

---

## 二、Home Assistant — 开源中枢（最推荐的统一层）

### 2.1 为什么 HA 是最佳中枢？

```
┌─────────────────────────────────────────────────────┐
│              Home Assistant REST API                  │
│         http://HA_IP:8123/api/                        │
│    一个API入口 → 控制所有已接入的设备                   │
└────────────────────┬────────────────────────────────┘
                     │
    ┌────────────────┼────────────────────┐
    │                │                    │
┌───┴───┐      ┌────┴────┐         ┌────┴────┐
│ 米家   │      │  涂鸦   │         │ 易微联  │
│ 官方集成│      │ 官方集成 │         │SonoffLAN│
│ 6亿设备 │      │全品类设备│         │开关插座  │
└───────┘      └─────────┘         └─────────┘
    │                │                    │
┌───┴───┐      ┌────┴────┐         ┌────┴────┐
│ Aqara │      │  HomeKit │         │ 海尔    │
│ 传感器 │      │苹果生态  │         │ 家电    │
└───────┘      └─────────┘         └─────────┘
```

**核心优势**: 一次接入HA，所有设备统一暴露为标准REST API

### 2.2 REST API 完整参考

**认证**: 长期访问令牌 (Long-Lived Access Token)
- 在 HA 界面 → 个人资料 → 页面底部 → 创建长期令牌

```bash
# 基础请求格式
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     http://192.168.31.228:8123/api/ENDPOINT
```

**核心 API 端点**:

```bash
# 1. 检查API状态
GET /api/
→ {"message": "API running."}

# 2. 获取所有实体状态
GET /api/states
→ [{"entity_id": "switch.sonoff_xxx", "state": "on", "attributes": {...}}, ...]

# 3. 获取单个实体状态
GET /api/states/{entity_id}
→ {"entity_id": "light.philips_strip", "state": "on", 
   "attributes": {"brightness": 255, "color_temp": 370, "friendly_name": "飞利浦灯带"}}

# 4. 更新/设置实体状态
POST /api/states/{entity_id}
Body: {"state": "on", "attributes": {"brightness": 200}}

# 5. 调用服务（核心控制方法！）
POST /api/services/{domain}/{service}
Body: {"entity_id": "switch.sonoff_10022dede9_1"}

# 6. 触发事件
POST /api/events/{event_type}
Body: {"key": "value"}

# 7. 获取可用服务列表
GET /api/services
→ [{"domain": "light", "services": ["turn_on", "turn_off", "toggle"]}, ...]

# 8. 获取配置
GET /api/config

# 9. 历史记录
GET /api/history/period/{timestamp}?filter_entity_id=sensor.temperature

# 10. 日志
GET /api/logbook/{timestamp}

# 11. 获取错误日志
GET /api/error_log

# 12. 渲染模板
POST /api/template
Body: {"template": "{{ states('sensor.temperature') }}"}
```

### 2.3 实用控制示例

```python
import requests

HA_URL = "http://192.168.31.228:8123"
TOKEN = "YOUR_LONG_LIVED_TOKEN"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# ===== 开关控制 =====
# 打开Sonoff开关
requests.post(f"{HA_URL}/api/services/switch/turn_on",
    json={"entity_id": "switch.sonoff_10022dede9_1"}, headers=HEADERS)

# 关闭
requests.post(f"{HA_URL}/api/services/switch/turn_off",
    json={"entity_id": "switch.sonoff_10022dede9_1"}, headers=HEADERS)

# ===== 灯光控制 =====
# 开灯 + 设置亮度 + 颜色
requests.post(f"{HA_URL}/api/services/light/turn_on",
    json={
        "entity_id": "light.philips_strip3_12ad_light",
        "brightness": 200,
        "rgb_color": [255, 100, 50]
    }, headers=HEADERS)

# 设置色温
requests.post(f"{HA_URL}/api/services/light/turn_on",
    json={
        "entity_id": "light.philips_strip3_12ad_light",
        "color_temp": 370  # 暖白
    }, headers=HEADERS)

# ===== 风扇控制 =====
requests.post(f"{HA_URL}/api/services/fan/turn_on",
    json={"entity_id": "fan.dmaker_p221_5b47_fan"}, headers=HEADERS)

# 设置风速
requests.post(f"{HA_URL}/api/services/fan/set_percentage",
    json={"entity_id": "fan.dmaker_p221_5b47_fan", "percentage": 50}, headers=HEADERS)

# ===== 场景触发 =====
requests.post(f"{HA_URL}/api/services/scene/turn_on",
    json={"entity_id": "scene.sleep_mode"}, headers=HEADERS)

# ===== 自动化触发 =====
requests.post(f"{HA_URL}/api/services/automation/trigger",
    json={"entity_id": "automation.party_mode"}, headers=HEADERS)

# ===== 批量查询所有设备状态 =====
resp = requests.get(f"{HA_URL}/api/states", headers=HEADERS)
for entity in resp.json():
    if entity["entity_id"].startswith(("switch.", "light.", "fan.")):
        print(f"{entity['attributes'].get('friendly_name', entity['entity_id'])}: {entity['state']}")
```

### 2.4 WebSocket API（实时推送）

```python
import websockets, json, asyncio

async def listen_ha():
    uri = "ws://192.168.31.228:8123/api/websocket"
    async with websockets.connect(uri) as ws:
        # 认证
        await ws.recv()  # auth_required
        await ws.send(json.dumps({"type": "auth", "access_token": "YOUR_TOKEN"}))
        await ws.recv()  # auth_ok
        
        # 订阅状态变更
        await ws.send(json.dumps({
            "id": 1, 
            "type": "subscribe_events", 
            "event_type": "state_changed"
        }))
        
        # 实时接收设备状态变化
        while True:
            msg = json.loads(await ws.recv())
            if msg.get("type") == "event":
                data = msg["event"]["data"]
                entity = data["entity_id"]
                new_state = data["new_state"]["state"]
                print(f"[变化] {entity}: {new_state}")
```

### 2.5 HA 集成各平台的方式

| 平台 | HA集成名称 | 安装方式 | 控制方式 |
|------|-----------|---------|---------|
| 小米/米家 | `Xiaomi Home` (官方) | HA内置 | 云端+本地 |
| 小米/米家 | `Xiaomi Miot Auto` (第三方) | HACS | 本地优先 |
| 涂鸦 | `Tuya` (官方) | HA内置 | 云端 |
| 涂鸦 | `LocalTuya` (第三方) | HACS | 纯本地 |
| 易微联 | `SonoffLAN` | HACS | 本地优先 |
| Aqara | `Aqara` (官方) | HA内置 | 云端 |
| 美的 | `Midea AC LAN` | HACS | 本地 |
| 海尔 | `Haier` | HACS | 云端(抓包) |
| HomeKit | `HomeKit Controller` | HA内置 | 本地 |

---

## 三、小米/米家 — 国内最大 IoT 生态

### 3.1 现状分析
- **设备数**: 6亿+ 连接设备，国内市占率第一
- **官方API**: **不对个人开发者开放**（iot.mi.com 面向设备厂商）
- **突破口**: python-miio（逆向工程）+ HA官方集成（2024年底发布）

### 3.2 python-miio（本地直接控制）

```bash
pip install python-miio
```

**获取设备Token（关键步骤）**:
```bash
# 方法1: 通过小米云端获取
miiocli cloud --username YOUR_XIAOMI_ID --password YOUR_PASSWORD

# 方法2: 从米家APP数据库提取（需root或备份）
# 数据库: miio2.db → select token from devicerecord where localIP='192.168.x.x'

# 方法3: 通过HA Xiaomi Home集成自动获取
```

**MIoT-Spec 协议控制**:
```python
from miio import Device

# 通用 MIoT 设备控制
dev = Device("192.168.31.100", "YOUR_TOKEN")

# 读取属性 (SIID=2, PIID=1 = 开关状态)
result = dev.get_properties([{"siid": 2, "piid": 1}])
print(result)  # [{'siid': 2, 'piid': 1, 'value': True}]

# 设置属性（控制设备）
dev.set_property(siid=2, piid=1, value=True)   # 开
dev.set_property(siid=2, piid=1, value=False)  # 关

# 执行动作
dev.call_action(siid=2, aiid=1, params=[])
```

**常用设备 SIID/PIID 查询**: https://home.miot-spec.com
- 在此网站搜索设备型号，可查到所有可控制的属性和动作
- 例如: `dmaker.fan.p221` → SIID=2(风扇), PIID=1(开关), PIID=2(模式), PIID=6(风速)

**专用设备库**:
```python
# 空气净化器
from miio import AirPurifier
ap = AirPurifier("192.168.31.101", "TOKEN")
ap.on()
ap.set_mode("auto")
ap.set_favorite_level(10)

# 扫地机器人
from miio import RoborockVacuum
vac = RoborockVacuum("192.168.31.102", "TOKEN")
vac.start()
vac.home()
vac.find()

# 小米网关（Zigbee子设备）
from miio import Gateway
gw = Gateway("192.168.31.103", "TOKEN")
gw.discover_devices()

# 智能插座
from miio import ChuangmiPlug
plug = ChuangmiPlug("192.168.31.104", "TOKEN")
plug.on()
plug.off()
print(plug.status())  # 功率、温度等
```

### 3.3 HA Xiaomi Home 官方集成（2024年底发布）

```
# 最新最推荐的方式
# HA → 设置 → 设备与服务 → 添加集成 → 搜索 "Xiaomi Home"
# 登录小米账号 → 自动发现所有米家设备 → 暴露为HA实体

# 然后通过HA REST API统一控制
POST /api/services/switch/turn_on
{"entity_id": "switch.xiaomi_miio_switch"}
```

### 3.4 小爱音箱特殊API（MIGPT使用的）

```python
# 这些是小米独有的未公开API，MIGPT-Easy的核心

# 1. 对话轮询（获取用户对小爱说了什么）
GET https://userprofile.mina.mi.com/device_profile/v2/conversation
Headers: Cookie: serviceToken=xxx; userId=xxx

# 2. TTS注入（让小爱说话）
POST https://api2.mina.mi.com/remote/ubus
Body: {
    "deviceId": "xxx",
    "message": '{"text":"你好","is_force_action":1}',
    "method": "text_to_speech",
    "path": "mibrain"
}

# 3. 执行语音命令（模拟用户说话）
POST https://api2.mina.mi.com/remote/ubus
Body: {
    "deviceId": "xxx",  
    "message": '{"text":"打开客厅灯","is_force_action":1}',
    "method": "text_to_speech",
    "path": "mibrain"
}
```

---

## 四、易微联 (eWeLink/SONOFF) — 开关插座之王

### 4.1 eWeLink Developer API

**开发者中心**: https://dev.ewelink.cc

```bash
# 1. 获取Token
POST https://cn-apia.coolkit.cn/v2/user/login
Body: {
    "email": "your@email.com",
    "password": "your_password",
    "countryCode": "+86"
}
→ 返回 {"at": "access_token", "rt": "refresh_token"}

# 2. 获取设备列表
GET https://cn-apia.coolkit.cn/v2/device/thing
Headers: Authorization: Bearer {at}

# 3. 设备控制
POST https://cn-apia.coolkit.cn/v2/device/thing/status
Body: {
    "type": 1,
    "id": "DEVICE_ID",
    "params": {"switch": "on"}
}

# 4. 多通道设备控制
POST /v2/device/thing/status
Body: {
    "type": 1,
    "id": "DEVICE_ID",
    "params": {
        "switches": [
            {"switch": "on", "outlet": 0},
            {"switch": "off", "outlet": 1}
        ]
    }
}
```

### 4.2 本地 LAN 控制

SONOFF 设备支持 mDNS 局域网发现 + 本地加密控制：
```python
# 通过 SonoffLAN (Home Assistant 集成) 或直接 HTTP

# 设备在局域网通过 mDNS 广播 _ewelink._tcp.local
# 发现后可直接发送加密控制命令

# 最简方式: HA + SonoffLAN 集成，自动本地控制
# HA → HACS → 搜索 SonoffLAN → 安装 → 添加 eWeLink 账号
# 优先局域网控制，断网也能用
```

---

## 五、Aqara (绿米) — 传感器生态之王

### 5.1 Aqara Open API

**开放平台**: https://developer.aqara.com

```bash
# 1. 获取Token (OAuth 2.0)
POST https://open-cn.aqara.com/v3.0/open/authorize/token
Body: {
    "client_id": "YOUR_APP_ID",
    "client_secret": "YOUR_APP_SECRET",
    "grant_type": "authorization_code",
    "code": "AUTH_CODE"
}

# 2. 查询设备列表
POST https://open-cn.aqara.com/v3.0/open/device/query
Headers: Accesstoken: xxx
Body: {"pageNum": 1, "pageSize": 50}

# 3. 查询设备属性（状态）
POST https://open-cn.aqara.com/v3.0/open/resource/query  
Body: {
    "resources": [
        {"subjectId": "DEVICE_ID", "resourceId": "4.1.85"}  // 开关状态
    ]
}

# 4. 控制设备
POST https://open-cn.aqara.com/v3.0/open/resource/write
Body: {
    "resources": [
        {"subjectId": "DEVICE_ID", "resourceId": "4.1.85", "value": "1"}
    ]
}

# 5. 触发场景
POST https://open-cn.aqara.com/v3.0/open/scene/run
Body: {"sceneId": "SCENE_ID"}
```

**Aqara 常用 ResourceID**:
| ResourceID | 说明 | 值 |
|-----------|------|-----|
| 4.1.85 | 墙壁开关(左) | "0"=关, "1"=开 |
| 4.2.85 | 墙壁开关(右) | "0"=关, "1"=开 |
| 0.1.85 | 温度 | 浮点数 |
| 0.2.85 | 湿度 | 浮点数 |
| 0.3.85 | 气压 | 浮点数 |
| 3.1.85 | 人体存在 | "0"=无人, "1"=有人 |
| 13.1.85 | 门窗状态 | "0"=关, "1"=开 |
| 14.1.85 | 窗帘位置 | 0-100 |

---

## 六、天猫精灵 (AliGenie) — 技能开发路径

### 6.1 现状
- **不提供设备控制REST API** — 无法直接API调控天猫精灵控制的设备
- **唯一路径**: 开发 AliGenie 技能（类似Alexa Skill）
- **或**: 通过 HA + HassLife 桥接（设备控制）

### 6.2 AliGenie 技能开发

**技能平台**: https://iap.aligenie.com

```
开发流程:
1. 注册阿里云 + AliGenie开发者
2. 创建自定义技能
3. 配置意图(Intent) + 话术(Utterance)
4. 部署后端Webhook

# 天猫精灵调用流程:
用户说话 → AliGenie NLU → 匹配技能 → 调用你的Webhook → 返回响应文本

# Webhook请求格式 (AliGenie → 你的服务器):
POST https://your-server.com/aligenie
Body: {
    "header": {"namespace": "AliGenie.Skill", "name": "SkillExecute"},
    "payload": {
        "intentId": "xxx",
        "intentName": "控制设备",
        "slotEntities": [
            {"intentParameterName": "device", "standardValue": "客厅灯"}
        ],
        "utterance": "打开客厅灯"
    }
}

# 你的服务器响应:
{
    "returnCode": "0",
    "returnValue": {
        "reply": "已为您打开客厅灯",
        "resultType": "RESULT",
        "executeCode": "SUCCESS"
    }
}
```

### 6.3 IoT 云云对接（设备厂商路径）

天猫精灵IoT平台支持"云云对接"，但面向设备厂商：
```
你的云服务器 ←OAuth→ AliGenie云 ←→ 天猫精灵设备

需要实现的接口:
- /discovery    设备发现
- /control      设备控制
- /query        状态查询

这个路径适合把你的HA设备暴露给天猫精灵控制，
但反过来（你控制天猫精灵的设备）仍然不行。
```

---

## 七、小度 (DuerOS) — 百度系

### 7.1 与天猫精灵类似
- **不提供设备控制REST API**
- **路径**: DuerOS 技能开发 或 HA 桥接

### 7.2 DuerOS 智能家居技能

**开发者平台**: https://dueros.baidu.com/open

```
# 两种接入方式:
# 1. 云云对接: 你的服务器 ←→ DuerOS云 ←→ 小度设备
# 2. 直连: WiFi/蓝牙Mesh直连（面向设备厂商）

# 技能开发Webhook格式:
POST https://your-server.com/dueros
Body: {
    "version": "2.0",
    "session": {...},
    "request": {
        "type": "IntentRequest",
        "intent": {
            "name": "控制设备",
            "slots": {
                "device": {"value": "客厅灯"},
                "action": {"value": "打开"}
            }
        }
    }
}

# 响应:
{
    "version": "2.0",
    "response": {
        "outputSpeech": {"type": "PlainText", "text": "客厅灯已打开"},
        "shouldEndSession": true
    }
}
```

---

## 八、美的美居 — 云云对接

### 8.1 官方 IoT 平台

**开发者平台**: https://iot.midea.com

```
# 面向控端厂商（APP/小程序/车机等）
# 需要企业资质申请

# 对接方式:
# 1. 美居用户名密码授权
# 2. 手机验证码授权  
# 3. 扫码授权

# 设备控制流程:
# Step 1: OAuth获取token
# Step 2: 获取用户设备列表
# Step 3: 下发控制指令

# 个人开发者替代方案:
# → HA + midea_ac_lan 集成（HACS安装）
# → 本地局域网直接控制美的空调/热水器等
# → 不需要走美的云
```

### 8.2 midea_ac_lan（推荐，本地控制）

```
# Home Assistant HACS 安装 Midea AC LAN
# 支持品类: 空调/除湿机/热水器/洗碗机/...
# 控制方式: 纯局域网，不依赖云端

# 安装后设备暴露为HA实体，通过HA REST API控制
POST /api/services/climate/set_temperature
{"entity_id": "climate.midea_ac_living_room", "temperature": 26}

POST /api/services/climate/set_hvac_mode  
{"entity_id": "climate.midea_ac_living_room", "hvac_mode": "cool"}
```

---

## 九、海尔智家 — 抓包接入

### 9.1 现状
- 官方U+平台已转型，不再公开面向个人开发者
- 国内社区通过抓包微信小程序获取Token接入HA

### 9.2 HA集成方法

```
# 方法: 微信PC端抓包海尔智家小程序 → 获取RefreshToken → 添加到HA

# 步骤:
# 1. PC微信打开"海尔智家"小程序
# 2. Fiddler/Charles抓包获取RefreshToken
# 3. HA → 添加集成 → Haier → 输入Token
# 4. 设备自动发现

# 控制（通过HA REST API）:
POST /api/services/climate/set_temperature
{"entity_id": "climate.haier_ac_xxx", "temperature": 25}
```

---

## 十、华为鸿蒙智联 — 最封闭

### 10.1 现状
- **完全不开放**第三方API
- HiLink 已升级为 HarmonyOS Connect
- 面向设备厂商认证接入，不面向个人开发者
- HA社区无成熟集成方案

### 10.2 唯一控制方式

```
# 1. ScreenStream + AccessibilityService
#    通过模拟操作"华为智慧生活"APP控制设备
#    这是目前唯一可行的程序化控制方式

# 2. 如果设备同时支持 Matter 协议
#    可通过 HA Matter 集成接入（但华为在国内未开放Matter）

# 3. 部分华为设备（如路由器）有本地API
#    但智能家居设备（灯/开关/传感器）完全封闭
```

---

## 十一、Matter 协议 — 未来的统一标准

### 11.1 现状（2026年）
- Matter 1.3 已发布，支持品类持续扩展
- **国内支持情况**:
  - 涂鸦: ✅ 已支持 Matter
  - Aqara: ✅ 部分网关支持 Matter
  - 小米: ⚠️ 海外支持，国内尚未开放
  - 天猫精灵: ⚠️ 宣布支持但进展缓慢
  - 华为: ❌ 未支持
  - 易微联: ⚠️ 部分设备

### 11.2 Matter + HA

```
# Matter 设备可直接接入 HA（内置 Matter 集成）
# HA → 设置 → 设备与服务 → 添加集成 → Matter
# 设备通过 WiFi/Thread 本地连接

# 优势: 真正的本地控制，无需云端，无平台限制
# 劣势: 国内设备支持缓慢
```

---

## 十二、n8n 集成层 — 智能编排

### 12.1 n8n + Home Assistant

n8n 原生支持 HA 节点，可实现复杂的跨平台自动化：

```
# n8n HA节点配置:
# Host: http://192.168.31.228:8123
# Access Token: YOUR_HA_TOKEN

# 支持的操作:
# - 获取实体状态
# - 调用服务（开关/灯光/...）
# - 触发事件
# - 获取相机截图
# - 获取日志/历史

# 示例工作流: 天气自适应
# Cron(每小时) → 获取天气API → 
#   温度>30°C → HA: 开空调+关窗帘
#   温度<15°C → HA: 开暖气+开灯
#   PM2.5>100 → HA: 开净化器
```

### 12.2 n8n + 涂鸦 API

```
# n8n HTTP Request 节点直接调用涂鸦API
# 可实现: 涂鸦设备 ↔ 其他服务 的复杂联动
# 例如: 门锁开门 → 涂鸦Webhook → n8n → 开灯+关窗帘+播报欢迎词
```

---

## 十三、统一架构建议

### 13.1 三层架构

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 3: 应用层                                              │
│  ScreenStream · n8n · MIGPT-Easy · 自定义脚本                  │
│  统一调用 HA REST API                                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Home Assistant 统一中枢                              │
│  REST API: http://HA_IP:8123/api/                             │
│  WebSocket: ws://HA_IP:8123/api/websocket                     │
│  所有设备统一为 entity_id → state + attributes                  │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: 平台适配层                                           │
│  ┌─────────┬──────────┬──────────┬─────────┬──────────┐     │
│  │ 小米     │ 涂鸦     │ 易微联   │ Aqara   │ 美的     │     │
│  │ Xiaomi   │ LocalTuya│ SonoffLAN│ Aqara   │ midea_ac │     │
│  │ Home集成 │ 集成     │ 集成     │ 集成    │ _lan集成  │     │
│  └─────────┴──────────┴──────────┴─────────┴──────────┘     │
│  ┌─────────┬──────────┬──────────┐                           │
│  │ 海尔     │ 天猫精灵  │ 小度    │                           │
│  │ 抓包集成 │ HassLife │ HassLife│                           │
│  └─────────┴──────────┴──────────┘                           │
└─────────────────────────────────────────────────────────────┘
```

### 13.2 实施优先级

| 优先级 | 平台 | 方法 | 耗时 | 效果 |
|--------|------|------|------|------|
| P0 | HA REST API | 已有，直接用 | 0 | 控制已接入的所有设备 |
| P1 | 涂鸦 LocalTuya | HACS安装 | 1小时 | 所有涂鸦设备本地控制 |
| P1 | 小米 Xiaomi Home | HA内置集成 | 30分钟 | 所有米家设备 |
| P2 | 易微联 SonoffLAN | HACS安装 | 30分钟 | 所有Sonoff本地控制 |
| P2 | Aqara | HA内置集成 | 30分钟 | 所有Aqara设备 |
| P3 | 美的 midea_ac_lan | HACS安装 | 1小时 | 美的空调等 |
| P3 | 海尔 Haier | HACS+抓包 | 2小时 | 海尔家电 |
| P4 | 天猫精灵/小度 | HassLife | 2小时 | 反向: 让音箱控制HA设备 |
| P5 | 涂鸦 Cloud API | 直接REST | 2小时 | 需要绕过HA时的备选 |

### 13.3 与 ScreenStream 的集成方案

```
ScreenStream 已有的能力:
- /intent POST → 启动任意APP
- /screen/text GET → 读取屏幕文字
- /ai/click POST → AI语义点击
- 宏系统 → 自动化序列

新增(建议):
- /smarthome/devices GET → 从HA获取设备列表
- /smarthome/control POST → 通过HA控制设备
- /smarthome/scenes GET → 获取HA场景列表
- /smarthome/scene/{id} POST → 触发场景

实现: 在InputService.kt中转发请求到HA REST API
```

---

## 附录A: 快速验证脚本

```python
#!/usr/bin/env python3
"""快速验证各平台API可达性"""
import requests

# ============ Home Assistant ============
HA_URL = "http://192.168.31.228:8123"
HA_TOKEN = "YOUR_TOKEN"

def test_ha():
    resp = requests.get(f"{HA_URL}/api/", 
        headers={"Authorization": f"Bearer {HA_TOKEN}"})
    print(f"HA: {resp.status_code} - {resp.json()}")
    
    # 列出所有设备
    resp = requests.get(f"{HA_URL}/api/states",
        headers={"Authorization": f"Bearer {HA_TOKEN}"})
    entities = [e for e in resp.json() 
                if e["entity_id"].startswith(("switch.", "light.", "fan."))]
    print(f"HA 设备数: {len(entities)}")
    for e in entities:
        print(f"  {e['entity_id']}: {e['state']}")

# ============ Tuya Cloud ============
def test_tuya():
    """需要先配置 client_id 和 secret"""
    # 参考上面的涂鸦API部分
    pass

# ============ 执行 ============
if __name__ == "__main__":
    test_ha()
```

## 附录B: 参考链接汇总

| 平台 | 开发者文档 | 关键工具/库 |
|------|-----------|------------|
| 涂鸦 | https://developer.tuya.com/cn/docs/cloud | tinytuya, LocalTuya |
| Home Assistant | https://developers.home-assistant.io/docs/api/rest/ | 内置REST API |
| 小米 | https://home.miot-spec.com (设备规格) | python-miio |
| 易微联 | https://dev.ewelink.cc | SonoffLAN |
| Aqara | https://developer.aqara.com | HA Aqara集成 |
| 天猫精灵 | https://iap.aligenie.com | AliGenie SDK |
| 小度 | https://dueros.baidu.com/open | DuerOS SDK |
| 美的 | https://iot.midea.com | midea_ac_lan |
| Matter | https://csa-iot.org/all-solutions/matter/ | HA Matter集成 |
