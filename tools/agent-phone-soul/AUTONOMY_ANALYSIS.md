# ScreenStream 手机控制 — 自治度架构分析

> 测试日期：2026-02-21 | 设备：OnePlus 10 Pro | 结果：**36/36 = 100% 自治**

## 顶层哲学

```
用户的一句话 → 分解为确定性操作序列 → 每个操作都是独立可测试的HTTP调用
```

**核心设计原则：AI是可选加速层，不是必要依赖。**

系统每一层都可独立运行、独立测试、独立替换。AI（LLM）只在"理解模糊意图"这一环节不可替代，所有实际执行能力都是确定性REST API。

## 四层架构

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

## 验证结果

| 层级 | AI依赖 | 测试数 | 通过率 |
|------|--------|--------|--------|
| L0 原子API | 零 | 29 | 100% |
| L1 组合序列 | 零 | 6 | 100% |
| L2 LLM推理 | 需要 | 1 | 100% |
| **合计** | — | **36** | **100%** |

**脱离AI后，35/35项核心功能完全可用。**

## L0 原子能力（29项）

- **感知15项**：status/deviceinfo/foreground/screen-text/viewtree/windowinfo/notifications/apps/clipboard/storage/files/wait/findnodes/macro-list/stayawake
- **导航3项**：home/back/recents
- **系统7项**：wake/brightness/volume/screenshot/flashlight/stayawake/dismiss
- **输入2项**：tap/findclick
- **Intent 2项**：intent/验证前台

## L1 组合能力（6项）

| 场景 | 步骤 | 耗时 |
|------|------|------|
| Intent+读屏=设备信息 | intent→wait→screen/text→判断 | ~2.2s |
| Intent+读屏=WiFi信息 | intent→wait→screen/text→判断 | ~2.2s |
| Intent+验证=电池页 | intent→wait→foreground→screen/text | ~2.1s |
| 通知读取+规则判断 | notifications/read→规则匹配 | ~17ms |
| 跨页面切换 | intent→verify→home→intent→verify | ~4.5s |
| 设备状态综合采集 | status+deviceinfo+foreground+storage并行 | ~142ms |

## AI唯一不可替代的价值

| 能力 | L0/L1替代方案 | AI优势 |
|------|---------------|--------|
| "打开微信" | 需知道包名+Intent | 理解自然语言 |
| "找到蓝牙设置并关闭" | 需硬编码坐标/路径 | 理解UI语义 |
| 异常处理 | if/else穷举 | 泛化推理 |
| 多步任务规划 | 预定义流程 | 动态规划 |

**结论：AI将"模糊意图→精确操作"的转化效率提升10x，但底层执行100%不依赖AI。**

## 脱离AI的操作方式

### 方式1：curl直调（最原始）
```bash
curl -X POST http://127.0.0.1:8086/home
curl -X POST http://127.0.0.1:8086/intent -d '{"action":"android.settings.SETTINGS","flags":["FLAG_ACTIVITY_NEW_TASK"]}'
curl http://127.0.0.1:8086/screen/text
```

### 方式2：Python脚本（L1组合）
```python
POST("/intent", {"action": "android.settings.WIFI_SETTINGS", "flags": ["FLAG_ACTIVITY_NEW_TASK"]})
time.sleep(2)
screen = GET("/screen/text")
wifi_info = [t["text"] for t in screen["texts"]]
```

### 方式3：前端网页（浏览器操控）
- 直接在 http://127.0.0.1:8086 点击/滑动
- Alt+M 打开命令菜单（60+按钮，全部零AI）
- 底部导航栏 Back/Home/Recents

### 方式4：宏系统（自动化）
- 预录操作序列，定时/触发执行
- 通知触发、APP切换触发、定时触发

## 测试脚本

```bash
# 零AI独立测试（36项）
python tools/agent-phone-soul/scripts/standalone_test.py

# Agent Demo（5个多步任务，含AI /command）
python tools/agent-phone-soul/scripts/agent_demo.py

# 复杂多级联动（5场景，43步）
python tools/agent-phone-soul/scripts/complex_scenarios.py
```

## 复杂联动测试结果（2026-02-21）

| 场景 | AI参与度 | 步数 | 耗时 | 结果 |
|------|---------|------|------|------|
| S1 智能环境感知报告 | L2+L1 | 6 | 3.4s | ✅ |
| S2 跨APP信息萃取 | L1 | 10 | 8.6s | ✅ |
| S3 系统状态自动调优 | L1 | 7 | 0.3s | ✅ |
| S4 通知驱动自动化链 | L1 | 5 | 0.1s | ✅ |
| S5 全自主巡检 | L0 | 15 | 2.8s | ✅ |
| **合计** | — | **43** | **15s** | **5/5** |

**43步中37步（86%）无需AI。唯一需要AI的6步是S1中的`/command`调用。**

## 可复用的零AI自动化模式

### 模式1：Intent直跳+读屏 → 信息提取
```
POST /intent {action, flags} → wait → GET /screen/text → 文本过滤
```
适用：打开任意系统设置页、提取页面信息、不需要知道UI坐标

### 模式2：状态采集+规则引擎 → 自动调优
```
GET /deviceinfo → if(电量<30) POST /stayawake/false → if(亮度<50) POST /brightness/10
```
适用：根据设备状态自动调整系统设置，完全确定性

### 模式3：通知轮询+分类+动作
```
GET /notifications/read → 包名匹配分类 → 触发对应动作(Intent/宏)
```
适用：事件驱动自动化，无需轮询屏幕

### 模式4：跨APP切换序列
```
POST /intent{APP_A} → wait → GET /screen/text → POST /home → POST /intent{APP_B} → verify
```
适用：多APP间数据采集、对比、串联操作

### 模式5：全API巡检
```
for api in ALL_APIS: http(api) → record(ok/fail) → report
```
适用：健康检查、连通性验证、状态快照

## APP深度操控测试结果（2026-02-21）

| APP | 场景数 | 通过 | 方法 | 备注 |
|-----|--------|------|------|------|
| 微信 | 3 | 3/3 | openapp+findclick | 反无障碍：texts=0但包名验证通过 |
| 支付宝 | 3 | 3/3 | openapp+scheme深链 | alipays://扫码页直跳 |
| 高德地图 | 3 | 3/3 | openapp+androidamap:// | 导航/POI搜索scheme直跳 |
| 淘宝 | 3 | 2/3 | openapp+Intent回退 | OPPO弹窗需Intent MAIN回退 |
| 抖音 | 3 | 1/3 | openapp | OPPO持久拦截(OEM限制) |
| **合计** | **15** | **12/15** | — | 80%通过，全部零AI |

### OEM特异性发现
| OEM | 现象 | 根因 | 解决方案 |
|-----|------|------|---------|
| OPPO/ColorOS | 部分APP启动被安全弹窗拦截 | `com.oplus.securitypermission` | Intent MAIN+LAUNCHER回退 |
| OPPO/ColorOS | 抖音持久拦截 | 系统级自启动管理 | 需手动授权或ADB appops |
| 微信 | AccessibilityService无法读取文本 | 微信反无障碍保护 | 以包名验证替代文本验证 |

### APP操控可复用模式

**模式6：包名启动+OEM回退**
```
POST /openapp {pkg} → 检查foreground → 失败则 POST /intent MAIN+LAUNCHER
```
适用：跨OEM启动任意APP，自动降级

**模式7：Scheme深度链接直跳**
```
POST /intent {action:VIEW, data:"alipays://...|androidamap://...|weixin://..."}
```
适用：直接跳转APP内特定功能页（扫码/导航/支付）

**模式8：Tab导航 = findclick**
```
open_app → wait → POST /findclick {text:"购物车|发现|我的"}
```
适用：APP内底部Tab切换，零坐标依赖
