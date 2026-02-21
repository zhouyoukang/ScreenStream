# Phone Agent Memory 种子

> 这些是 Agent 首次启动时应该创建的初始 Memory。
> 它们提供基础知识，让 Agent 不从零开始。
> 部署方式：Agent 首次对话时，逐条调用 create_memory 创建。

---

## Seed 1: ScreenStream API 连接方式

**Title**: ScreenStream API 连接与端口探测

**Tags**: connection, api, port, adb

**Content**:
```
## ScreenStream API 连接

### 连接方式
1. USB + adb forward: `adb forward tcp:8081 tcp:8081`
2. WiFi 直连: `http://<手机IP>:8081`

### 端口
- 主端口 8081（MJPEG HttpServer，Input 路由挂载于此）
- 备用范围 8080-8099（如 8081 被占用，ScreenStream 会自动选择下一个可用端口）

### 连接检测
- GET /status → {"ok":true} 即正常
- 失败时先检查：USB 连接 → adb devices → adb forward → 手机上 ScreenStream 是否在运行

### 已知问题
- OPPO 手机 HANS 省电机制可能冻结 ScreenStream 进程
- 解决：将 ScreenStream 加入电池优化白名单 + `adb shell settings put global stay_on_while_plugged_in 3`
```

---

## Seed 2: View 树读取最佳实践

**Title**: View 树读取策略与性能权衡

**Tags**: viewtree, perception, performance

**Content**:
```
## View 树读取策略

### 深度选择
- depth=4：轻量级，适合快速定位（首选）
- depth=8：标准深度，大多数元素可见
- depth=12+：深度搜索，仅在浅层找不到时使用

### 性能数据（实测）
- depth=4: ~20-50ms，JSON ~5-15KB
- depth=8: ~50-200ms，JSON ~20-80KB
- depth=12: ~200-500ms，JSON ~50-200KB

### 替代接口
- GET /screen/text：只返回文本+可点击元素，更轻量（~10-30ms）
- GET /windowinfo：只返回包名和节点总数（~5ms）
- 优先用 /screen/text 做初步感知，需要结构信息再用 /viewtree

### 节点 recycle
- View 树是 AccessibilityNodeInfo 的快照，读取后原始节点会被 recycle
- 如果快速连续读取，可能出现部分节点 stale 的情况
- 最佳实践：两次读取间隔 ≥300ms
```

---

## Seed 3: 元素查找多策略降级

**Title**: UI 元素查找的多策略降级体系

**Tags**: element-finding, strategy, degradation

**Content**:
```
## 元素查找策略（按可靠度排序）

### Strategy 1: findByText (最可靠，覆盖面最广)
- POST /findclick {"text": "目标文字"}
- 优点：直观，跨设备通用
- ⚠️ 实践验证（2026-02-21）：Android findAccessibilityNodeInfosByText()
  同时搜索 text 和 contentDescription → 图标按钮（只有 desc 无 text）也能找到
- 成功率：实测 9/9 = 100%（OnePlus NE2210, 桌面+时钟+便签+desc-only元素）
- 注意：View 树中同一元素可能出现两次（容器+子节点），代码已有 clickable 优先选择逻辑

### Strategy 2: findByViewId
- POST /findclick {"id": "com.xxx:id/btn_name"}
- 优点：最精确
- 缺点：需要知道 resource ID，跨 APP/版本可能不同

### Strategy 4: findByClassName + position
- GET /viewtree → 搜索特定 class（如 Switch, Button）→ 按位置匹配
- 优点：不依赖文本
- 缺点：同类控件可能有多个

### Strategy 5: coordinateTap (最后兜底)
- 从 viewtree/findnodes 获取元素 bounds → 计算中心点 → POST /tap
- 优点：总是能执行
- 缺点：不同屏幕分辨率/DPI 下坐标不通用

### 降级记录
每次降级到低优先级策略时记录：{APP, 元素描述, 成功策略, 失败策略}
积累后可以优化优先级顺序
```

---

## Seed 4: 常用 Intent 速查

**Title**: Android Intent 常用动作速查表

**Tags**: intent, app-launch, deep-link

**Content**:
```
## 常用 Intent

### 系统设置
- WiFi: {"action": "android.settings.WIFI_SETTINGS"}
- 蓝牙: {"action": "android.settings.BLUETOOTH_SETTINGS"}
- 显示: {"action": "android.settings.DISPLAY_SETTINGS"}
- 声音: {"action": "android.settings.SOUND_SETTINGS"}
- 电池: {"action": "android.intent.action.POWER_USAGE_SUMMARY"}
- 应用管理: {"action": "android.settings.APPLICATION_SETTINGS"}
- 位置: {"action": "android.settings.LOCATION_SOURCE_SETTINGS"}

### 通用动作
- 拨号: {"action": "android.intent.action.DIAL", "data": "tel:10086"}
- 发短信: {"action": "android.intent.action.SENDTO", "data": "sms:10086"}
- 打开URL: {"action": "android.intent.action.VIEW", "data": "https://..."}
- 拍照: {"action": "android.media.action.IMAGE_CAPTURE"}
- 分享文本: {"action": "android.intent.action.SEND", "type": "text/plain", "extras": {"android.intent.extra.TEXT": "内容"}}

### APP 启动
- 通用: {"action": "android.intent.action.MAIN", "package": "com.xxx.xxx"}
- 带深链: {"action": "android.intent.action.VIEW", "data": "scheme://host/path"}

### 注意
- 不同 OEM 可能重写系统设置的 Intent，导致标准 action 无效
- 失败时回退到：打开设置主页 → 搜索/滚动找到目标项
```

---

## Seed 5: OEM 差异已知经验

**Title**: Android OEM 差异经验（持续更新）

**Tags**: oem, device, compatibility

**Content**:
```
## OEM 差异经验（初始知识，待实测验证）

### OPPO / OnePlus / Realme (ColorOS/OxygenOS)
- 计算器包名: com.coloros.calculator
- 计算器运算符按钮只有 contentDescription，没有 text
- HANS 省电机制可能冻结后台 APP → 需加电池白名单
- 设置页 WiFi Switch: 通常是 CompoundButton 子类

### Samsung (One UI)
- 计算器包名: com.sec.android.app.popupcalculator
- 设置页有独特的搜索入口（顶部搜索栏）
- Switch 控件 ID 通常是 com.android.settings:id/switch_widget

### Xiaomi / Redmi (MIUI/HyperOS)
- 计算器包名: com.miui.calculator
- 系统设置 UI 与原生 Android 差异较大
- 权限弹窗特别多（首次使用各功能都会弹）
- 后台限制严格，需要"自启动"权限

### Google Pixel (原生 Android)
- 计算器包名: com.google.android.calculator
- 最接近标准 Android，兼容性最好
- Switch/Toggle 行为最可预测

### 通用经验
- View 树 class name 含 "Switch" / "Toggle" / "CheckBox" 的控件是开关类
- 不可点击的文本元素，向上最多 5 层 parent 通常能找到可点击的容器
- 列表项通常是 RecyclerView/ListView 的子节点
```

---

## Seed 6: 自然语言命令能力

**Title**: ScreenStream 自然语言命令引擎能力范围

**Tags**: nlp, command, capability

**Content**:
```
## POST /command 自然语言命令

### 已支持的命令模式
- 打开APP: "打开计算器" / "open settings" / "启动微信"
- WiFi切换: "关掉WiFi" / "打开WLAN"
- 点击元素: "点击设置" / "tap OK" / "按确定"
- 输入文本: "输入hello" / "type world"
- 导航: "返回" / "主页" / "最近任务" / "通知栏"
- 截图: "截图" / "截屏"
- 滚动: "上滑" / "下滑" / "scroll down"

### 复合命令（POST /command/stream，SSE 流）
- "打开设置看看WiFi" → 自动拆解为 [打开设置, 看看WiFi]
- "打开计算器按5+3=" → 自动拆解为 [打开计算器, calc:5, calc:+, ...]
- 连接词: "然后" / "接着" / "再" / "and then"

### Agent Path（兜底智能搜索）
- 关键词匹配全部失败后启动
- 读屏幕 → 模糊匹配 → 尝试点击 → 自动滚动搜索
- 最多 8 步，20s 超时

### 限制
- 本质是关键词匹配 + 模糊搜索，不是真正的 NLP
- 无法理解复杂意图（如"帮我看看最近有没有快递"）
- 无状态：不记忆之前的操作上下文
- Agent 应优先直接调用具体 API，/command 作为便捷入口
```

---

## 部署脚本提示

Agent 首次对话时，执行以下操作初始化 Memory：

```
对话开头说：
"我是 Phone Agent，正在初始化。请等待我创建基础 Memory..."

然后依次调用 create_memory 创建上述 6 条种子。

完成后说：
"Memory 初始化完成（6 条基础知识）。请连接手机，我们开始。"
```
