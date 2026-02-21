# AI 操作手机 — 完整指南

> 通过 ScreenStream HTTP API + ADB，从PC端完全控制Android手机。
> 70+ API端点 | 零AI即可覆盖90%日常需求 | Python一行代码操控

## 架构（四层金字塔）

```
┌─────────────────────────────────────────────┐
│  L3: 自主Agent (监控循环+决策+自愈)         │  可选，需LLM
├─────────────────────────────────────────────┤
│  L2: LLM推理 (自然语言→操作序列)            │  可选，需LLM
├─────────────────────────────────────────────┤
│  L1: 组合序列 (多步确定性流程)              │  零AI，脚本/规则
├─────────────────────────────────────────────┤
│  L0: 原子API (单个HTTP调用)                 │  零AI，curl即可
└─────────────────────────────────────────────┘
```

**核心设计原则：AI是可选加速层，不是必要依赖。**
- L0+L1 覆盖90%日常需求（零成本）
- L2 覆盖8%（小模型，低成本）
- L3 覆盖2%（大模型，高成本）
- 35/36项核心功能脱离AI后完全可用

## 快速开始

```bash
# 1. 连接手机
adb devices
adb forward tcp:8086 tcp:8086

# 2. 验证连接
curl -s http://127.0.0.1:8086/status
# → {"connected":true,"inputEnabled":true}

# 3. Python操控
python -c "from phone_lib import Phone; p=Phone(); print(p.device())"
```

端口范围 8080-8099，实际端口取决于 ScreenStream 启动时分配。

## phone_lib.py 用法

```python
from phone_lib import Phone
p = Phone(port=8086)

# 感知（零屏幕依赖）
p.status()                          # 连接状态
p.device()                          # 设备信息（电池/内存/存储/WiFi）
p.foreground()                      # 前台APP包名
p.notifications(10)                 # 最近通知
texts, pkg = p.read()               # 屏幕文本列表

# 操控
p.click("设置")                     # 语义查找并点击（100%成功率）
p.tap(0.5, 0.5)                     # 归一化坐标点击
p.home()                            # 返回桌面
p.back()                            # 返回上一页

# APP启动（自动处理OPPO弹窗）
p.open_app("com.tencent.mm")        # 打开微信
p.open_app("com.eg.android.AlipayGphone")  # 打开支付宝

# Scheme深链直跳
p.alipay("10000007")                # 支付宝扫一扫
p.alipay("20000056")                # 支付宝付款码
p.amap_search("星巴克")              # 高德搜索POI
p.bili("search?keyword=AI")         # B站搜视频

# 系统控制
p.volume(8)                         # 音量
p.brightness(128)                   # 亮度
p.wake()                            # 唤醒屏幕
p.screenshot()                      # 截屏

# 剪贴板同步
p.clipboard_write("从PC发送的文本")
text = p.clipboard_read()

# 高级组合
status = p.collect_status()         # 一键采集全状态
p.daily_check()                     # 每日巡检（设备+通知+快递）
notifs = p.check_notifications_smart()  # 智能通知分类
p.quick_pay_scan()                  # 一键扫码
p.quick_navigate("公司")            # 一键导航

# 验证
p.is_app("tencent")                 # 当前是否在微信
p.has_text("设置", "WiFi")          # 屏幕是否有文字
```

## API 速查

### 感知（只读）
| 端点 | 方法 | 说明 |
|------|------|------|
| `/status` | GET | 连接状态 |
| `/deviceinfo` | GET | 设备完整信息（电池/内存/存储/WiFi/运行时间） |
| `/foreground` | GET | 前台APP包名+Activity |
| `/screen/text` | GET | 屏幕文本+可点击元素（推荐首选感知接口） |
| `/viewtree?depth=N` | GET | View树结构（depth=4轻量，8标准，12+深度） |
| `/windowinfo` | GET | 窗口包名+节点数（最轻量） |
| `/notifications/read?limit=N` | GET | 通知列表（零屏幕依赖，高价值） |
| `/apps` | GET | 已安装APP列表 |
| `/clipboard` | GET | 剪贴板内容 |
| `/wait?text=X&timeout=T` | GET | 等待文本出现 |
| `/findnodes` | POST | 节点搜索 `{"text":"X"}` |

### 操控
| 端点 | 方法 | 说明 |
|------|------|------|
| `/findclick` | POST | 语义查找并点击 `{"text":"X"}` |
| `/tap` | POST | 归一化坐标点击 `{"nx":0.5,"ny":0.5}` |
| `/text` | POST | 输入文本 `{"text":"X"}` |
| `/settext` | POST | 设置输入框 `{"search":"X","value":"Y"}` |
| `/intent` | POST | 发送Intent `{"action":"X","data":"Y","package":"Z","flags":[...]}` |
| `/command` | POST | 自然语言命令 `{"command":"X"}` |
| `/dismiss` | POST | 关闭弹窗（12种预设关闭文字） |
| `/openapp` | POST | 打开APP `{"packageName":"X"}` |

### 导航
`POST /home` · `POST /back` · `POST /recents` · `POST /notifications`

### 系统控制
| 端点 | 方法 | 说明 |
|------|------|------|
| `/volume` | POST | 音量控制 `{"stream":"music","level":N}` |
| `/brightness/N` | POST | 亮度 (0-255) |
| `/wake` | POST | 唤醒屏幕 |
| `/screenshot` | POST | 截屏 |
| `/flashlight/bool` | POST | 手电筒 |
| `/stayawake/bool` | POST | 保持唤醒 |
| `/dnd/bool` | POST | 勿扰模式 |
| `/rotate` | POST | 旋转屏幕 |

### 文件管理（12端点）
| 端点 | 方法 | 说明 |
|------|------|------|
| `/files/storage` | GET | 存储信息 |
| `/files/list?path=X` | GET | 目录列表 |
| `/files/info?path=X` | GET | 文件详情 |
| `/files/read?path=X` | GET | 读文本文件(≤512KB) |
| `/files/download?path=X` | GET | 下载文件 |
| `/files/search?path=X&query=Y` | GET | 搜索文件 |
| `/files/mkdir` | POST | 创建目录 |
| `/files/delete` | POST | 删除文件 |
| `/files/rename` | POST | 重命名 |
| `/files/move` | POST | 移动 |
| `/files/copy` | POST | 复制 |
| `/files/upload` | POST | 上传 |

### 宏系统（11端点）
`GET /macro/list` · `POST /macro/create` · `POST /macro/run` · `POST /macro/stop` 等

## 后端源码

| 文件 | 说明 |
|------|------|
| `040-反向控制_Input/010-输入路由_Routes/InputRoutes.kt` | 70+个API路由定义 |
| `040-反向控制_Input/020-输入服务_Service/InputService.kt` | AccessibilityService核心实现 |
| `040-反向控制_Input/040-宏系统_Macro/MacroEngine.kt` | 宏引擎 |

## 测试

```bash
# 零AI独立测试（36项，验证所有L0/L1能力）
python tests/standalone_test.py --port 8086

# Agent Demo（5个多步任务，含L2 /command）
python tests/agent_demo.py

# 复杂多级联动（5场景，43步，证明86%步骤零AI）
python tests/complex_scenarios.py
```

## 依赖度分层（实测验证）

### 零依赖（人机完全共存，Agent不干扰用户）
通知监控 · 设备信息 · APP列表 · 电池状态 · 前台APP · 系统属性 · 截图到PC · 进程列表 · 存储占用 · 网络路由 · CPU温度 · 内存状态 · 系统设置读取（共13种）

### 低依赖（一瞬间影响前台，然后交还）
启动APP · 按键注入 · 触控注入 · 通知推送 · 通知栏控制 · 干净启动(clear-task)（共6种）

### 中依赖（需要ScreenStream运行，只读不操控）
屏幕文本 · View树 · 窗口信息 · 剪贴板（共4种）

### 高依赖（占用前台，人机互斥）
语义点击 · 文本输入 · 智能关弹窗 · Intent发送 · 自然语言命令 · 节点搜索 · 文本设置（共7种）

**默认模式应该是"零依赖感知+低依赖操控"，只在需要精确UI交互时才用"高依赖"。**

## 常用Intent速查

| 目标 | Intent Action |
|------|---------------|
| WiFi设置 | `android.settings.WIFI_SETTINGS` |
| 蓝牙设置 | `android.settings.BLUETOOTH_SETTINGS` |
| 关于手机 | `android.settings.DEVICE_INFO_SETTINGS` |
| 显示设置 | `android.settings.DISPLAY_SETTINGS` |
| 电池设置 | `android.intent.action.POWER_USAGE_SUMMARY` |
| 应用管理 | `android.settings.APPLICATION_SETTINGS` |
| 位置设置 | `android.settings.LOCATION_SOURCE_SETTINGS` |
| 打开URL | `android.intent.action.VIEW` + data=URL |
| 拨号 | `android.intent.action.DIAL` + data=tel:NUMBER |
| 发短信 | `android.intent.action.SENDTO` + data=sms:NUMBER |

## 常用APP Scheme

| APP | Scheme | 功能 |
|-----|--------|------|
| 支付宝扫码 | `alipays://platformapi/startapp?appId=10000007` | 扫一扫 |
| 支付宝付款 | `alipays://platformapi/startapp?appId=20000056` | 付款码 |
| 支付宝账单 | `alipays://platformapi/startapp?appId=20000003` | 账单 |
| 支付宝快递 | `alipays://platformapi/startapp?appId=20000754` | 查快递 |
| 高德导航 | `androidamap://navi?lat=X&lon=Y&dev=0&style=2` | 导航 |
| 高德搜索 | `androidamap://poi?keywords=X&dev=0` | POI搜索 |
| B站搜索 | `bilibili://search?keyword=X` | 视频搜索 |

## 零AI可复用自动化模式

### 模式1：Intent直跳+读屏 → 信息提取
```
POST /intent {action, flags} → wait → GET /screen/text → 文本过滤
```

### 模式2：状态采集+规则引擎 → 自动调优
```
GET /deviceinfo → if(电量<30) POST /stayawake/false → if(亮度<50) POST /brightness/10
```

### 模式3：通知轮询+分类+动作
```
GET /notifications/read → 包名匹配分类 → 触发对应动作(Intent/宏)
```

### 模式4：APP启动+OEM回退
```
POST /openapp {pkg} → 检查foreground → 失败则 POST /intent MAIN+LAUNCHER
```

### 模式5：Scheme深链直跳
```
POST /intent {action:VIEW, data:"alipays://...|androidamap://..."}
```

## 目录结构

```
tools/ai-phone-control/
├── README.md              ← 本文件（完整指南）
├── phone_lib.py           ← 核心Python库（Phone类，零外部依赖）
├── FINDINGS.md            ← 实测发现（P1-P27 + OEM差异 + 用户需求）
└── tests/
    ├── standalone_test.py ← 36项L0/L1独立测试（零AI依赖）
    ├── agent_demo.py      ← 5个多步Agent任务
    └── complex_scenarios.py ← 5个复杂联动场景（43步，86%零AI）
```

## 相关文件（项目内其他位置）

| 文件 | 位置 | 说明 |
|------|------|------|
| Cascade Skill | `.windsurf/skills/agent-phone-control/SKILL.md` | Cascade Agent操控手机的技能定义 |
| 路由代码 | `040-反向控制_Input/010-输入路由_Routes/InputRoutes.kt` | 后端路由 |
| 服务代码 | `040-反向控制_Input/020-输入服务_Service/InputService.kt` | 后端实现 |
| 前端 | `020-投屏链路_Streaming/010-MJPEG投屏_MJPEG/assets/index.html` | Web前端 |
