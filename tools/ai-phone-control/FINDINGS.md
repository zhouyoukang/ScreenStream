# 实测发现与经验库

> 浓缩自 10 个实践场景、36 项独立测试、43 步复杂联动、15 个APP深度操控测试。
> 设备：OnePlus NE2210, Android 15 (API 35), 1080x2412, 端口 8086

## 核心数据

| 指标 | 数值 | 日期 |
|------|------|------|
| L0 原子API测试 | 29/29 = 100% | 2026-02-21 |
| L1 组合序列测试 | 6/6 = 100% | 2026-02-21 |
| L2 AI命令测试 | 1/1 = 100% | 2026-02-21 |
| Agent多步任务 | 5/5 = 100% | 2026-02-21 (修复后) |
| 复杂联动场景 | 5/5 = 100%（43步，86%零AI） | 2026-02-21 |
| findByText 成功率 | 12/12 = 100% | 2026-02-21 |
| APP深度操控 | 12/15 = 80%（3失败均为OPPO OEM拦截） | 2026-02-21 |
| API平均响应 | 50-100ms（改善自100-300ms） | 2026-02-21 |
| 完整 observe-act-verify | ~2-3秒/步 | 2026-02-21 |

## 关键发现（P1-P20）

### 已验证通过（10项）
| ID | 发现 | 影响 |
|----|------|------|
| P3 | 信任模型有效：T0全量感知确实捕获了设置恢复位置问题 | 设计可靠 |
| P6 | 探索模式有效：Phase 1-4 渐进探索流程自然流畅 | 设计可靠 |
| P8 | 文本列表差异对比是低成本高可靠的操作验证方式 | 推荐方法 |
| P9 | 探索模式~1.5秒/步，执行模式可压到~0.5秒/步 | 速度可接受 |
| P12 | 弹窗是最常见的首次打开障碍（Tasker电池优化弹窗） | 需预处理 |
| P14 | 循环密度变化由信任自然驱动，不需要显式切换 | 设计可靠 |
| P16 | **通知监控是极高价值零依赖通道**，可被动感知手机事件 | 核心能力 |
| P18 | "最大化可达性，最小化依赖"在实践中成立 | 设计原则验证 |
| P19 | ADB `--activity-clear-task` 是通用"干净启动"方案 | 绕过P2 |
| P20 | ADB+API混合模式验证通过：ADB启动/导航，API感知/读取 | 推荐模式 |

### 需注意（5项）
| ID | 发现 | 解决方案 |
|----|------|---------|
| P1 | 端口不固定（默认8081实际可能是8086） | 扫描8080-8099找`GET /status`响应 |
| P2 | APP打开恢复上次位置（设置→显示子页面） | 用`--activity-clear-task` Intent |
| P7 | class多样性高（按钮可能是ImageView/FrameLayout/TextView） | 不依赖class判断可交互性，依赖clickable属性 |
| P10 | sendIntent曾缺少flags参数 | 已修复：支持`FLAG_ACTIVITY_CLEAR_TASK` |
| P13 | `/dismiss`预设12种关闭文字，不覆盖所有弹窗 | 用`/findclick`精确处理非预设弹窗 |

### P21: 微信三重阻止 AccessibilityService（2026-02-21 发现并修复）

**现象**：微信在前台时，`/foreground` 和 `/screen/text` 都返回空。

**根因**：微信同时阻止了 AccessibilityService 的三个通道：
1. `rootInActiveWindow` → null
2. `getWindows()` → 无法获取微信窗口 root
3. `TYPE_WINDOW_STATE_CHANGED` 事件 → 不发送给 AccessibilityService

**修复**：`getForegroundApp()` 和 `extractScreenText()` 新增三层回退机制：
```
rootInActiveWindow（主路径）
  → getWindows() 扫描（回退1：扫描所有可见窗口）
    → UsageStatsManager（回退2：查询系统级使用统计，最准确）
      → event_cache（回退3：缓存的最后窗口事件，可能过时）
```

**UsageStatsManager 权限授权**（需 Magisk root）：
```bash
adb shell su -c "appops set info.dvkr.screenstream.dev android:get_usage_stats allow"
```

**验证结果**：
- 修复前：`/foreground` → `{}` | `/screen/text` → `pkg="" texts=0`
- 修复后：`/foreground` → `{packageName: "com.tencent.mm", source: "usage_stats"}` | `/screen/text` → `pkg="com.tencent.mm" texts=0 source=usage_stats`
- 注意：微信的文本仍然读不到（texts=0），但包名正确返回，足够用于前台APP检测

### P22: 剪贴板读取 Android 10+ 后台限制（2026-02-21 发现并修复）

**现象**：`POST /clipboard` 写入成功（`ok:true, length:10`），但 `GET /clipboard` 返回 `{"text": null}`。

**根因**：Android 10+ 限制后台服务读取剪贴板。AccessibilityService 是后台服务，可以写入 `ClipboardManager` 但无法读取 `primaryClip`。

**修复**：`setClipboard()` 写入时同步缓存到 `cachedClipboardText` 字段，`getClipboardText()` 在系统读取返回 null 时返回缓存值。

**限制**：只能读回通过 API 写入的内容。用户在手机上手动复制的文本仍然无法通过 API 读取（Android 系统限制）。

### P23: force-stop 会禁用 AccessibilityService（2026-02-21 发现）

**现象**：`am force-stop info.dvkr.screenstream.dev` 后重启应用，所有API返回空数据。

**根因**：Android 系统在 force-stop 时会自动从 `enabled_accessibility_services` 列表中移除该应用的服务。

**修复**：部署脚本中重启应用后需要重新启用无障碍服务：
```bash
# 获取当前列表并追加
current=$(adb shell settings get secure enabled_accessibility_services)
adb shell settings put secure enabled_accessibility_services "$current:info.dvkr.screenstream.dev/info.dvkr.screenstream.input.InputService"
```

**注意**：这个操作应该集成到 `dev-deploy.ps1` 部署脚本中，避免每次手动执行。（已集成）

### P24-P26: 购物APP启动与OEM拦截

**结论**：
- `monkey` 命令是最可靠的APP启动方式——走shell权限，不受OEM弹窗拦截
- 命令：`adb shell monkey -p <pkg> -c android.intent.category.LAUNCHER 1`
- OPPO/ColorOS 会拦截部分APP的Scheme深链（`com.oplus.securitypermission`），用APP内搜索替代
- `open_app` 内部已有重试+`_dismiss_oppo()`回退机制

## findByText 重大发现

Android `findAccessibilityNodeInfosByText()` **同时搜索 text 和 contentDescription**。

这意味着：
- 图标按钮（只有 desc 无 text）也能被 `/findclick` 找到
- 不需要单独的 "findByContentDescription" 策略
- findByText 覆盖面比预期更广
- 实测 9/9 = 100%（包含1个 desc-only 元素"必应壁纸"）

**元素查找降级策略（4级）**：
```
Strategy 1: findByText (含desc)        → 最可靠，首选
Strategy 2: findByViewId               → 最精确，需知ID
Strategy 3: findByClassName + position  → 不可靠（P7发现）
Strategy 4: coordinateTap (bounds中心)  → 最后兜底
```

## OEM 差异经验

### OPPO/OnePlus/Realme (ColorOS)
- `com.oplus.securitypermission` 弹窗拦截部分APP启动
- **淘宝**：用 Intent MAIN+LAUNCHER 回退可绕过
- **抖音**：持久拦截，需手动授权或 `adb shell appops set <pkg> AUTO_START allow`
- HANS省电机制可能冻结后台APP → 加电池优化白名单
- 计算器运算符按钮只有contentDescription没有text → findByText仍可找到

### 微信
- AccessibilityService读不到文本（texts=0）→ 微信有反无障碍保护
- 解决方案：用foreground包名验证替代文本验证

### 通用经验
- `monkey` 命令不受OPPO弹窗拦截（走shell权限）
- APP启动回退链：`/openapp` → 失败 → Intent MAIN+LAUNCHER → 失败 → dismiss弹窗 → 失败 → 记录为OEM限制
- View树中同一元素可能出现两次（容器+子节点），`/findclick`已有clickable优先选择逻辑
- 不可点击的文本元素，向上最多5层parent通常能找到可点击容器

## 中国用户高频需求覆盖

### 日均5+次（全部L0可解决）
查消息(`/notifications/read`) · 查时间(ADB date) · 查天气(`/command`) · 打开微信(monkey) · 返回桌面(KEYCODE_HOME) · 查电量(dumpsys battery) · 截图(screencap)

### 日均1-5次（L0-L1）
WiFi开关(`/quicksettings`+findclick) · 蓝牙(Intent) · 音量(`/volume`) · 亮度(`/brightness`) · 手电筒(`/flashlight`) · 打电话(Intent DIAL) · 播放音乐(`/media/playpause`) · 打开APP(monkey/`/command`)

### 周几次（L0-L1）
文件管理(ADB ls/`/files/*`) · 导航(Intent VIEW geo:) · 扫码(`/command`) · 找手机(`/vibrate`+volume max) · 勿扰(`/dnd`)

### 需要L2-L3的（~10%）
多步操作 · 内容理解 · 决策类 · 创造类

## 可编排子系统（手机上已安装）

| 系统 | Agent调用方式 | 状态 |
|------|-------------|------|
| ScreenStream | HTTP API (70+端点) | ✅ |
| Tasker | Intent广播 | 部分（广播送达，任务执行待验证） |
| MacroDroid | HTTP Server(未启用) | ❌ 需手动启用 |
| Home Assistant | 通知监控 | ✅ |

## 连接方式

| 方式 | 命令 | 状态 |
|------|------|------|
| USB ADB | `adb forward tcp:PORT tcp:PORT` | ✅ |
| WiFi ADB | `adb connect 192.168.x.x:5555` | ✅ |
| 端口转发 | `adb forward tcp:8087 tcp:8086` | ✅ |

## View树性能数据

| 深度 | 响应时间 | JSON大小 | 适用场景 |
|------|---------|---------|---------|
| depth=4 | ~20-50ms | ~5-15KB | 快速定位（首选） |
| depth=8 | ~50-200ms | ~20-80KB | 标准深度 |
| depth=12+ | ~200-500ms | ~50-200KB | 深度搜索 |

替代接口：
- `GET /screen/text`：~10-30ms，只返回文本+可点击元素
- `GET /windowinfo`：~5ms，只返回包名和节点总数
- **推荐优先用 `/screen/text` 做初步感知，需要结构信息再用 `/viewtree`**

### P27: APP内搜索通用经验

- 各APP搜索栏的accessibility label不统一（"搜索栏"/"搜索京东商品"等），`findclick` 不可靠
- `search_in_app` 采用双策略：findclick"搜索栏" → ADB tap屏幕顶部搜索区域
- 底部Tab"搜索"按钮与顶部搜索框功能不同，需精确区分
- **京东安全验证绕过**：`search_in_app` 可能触发验证页 → `back()` 回到搜索建议页 → `findclick("搜索")` 点击搜索按钮 → 正常返回结果（不再触发验证）
- **淘宝**：findclick"搜索栏"直接命中，最顺畅
- **拼多多**：ADB tap(570,170) 策略有效

## 架构级差距（未来方向）

| 差距 | 描述 | 影响 |
|------|------|------|
| LLM集成 | Agent缺少"think"能力，/command只有关键词匹配 | L2-L3能力受限 |
| 持久化工作流 | 只有前端localStorage，无服务端持久化 | 宏系统重启后丢失 |
| 多设备支持 | 当前只能操控一台手机 | 无法同时管理多设备 |
| 公网远程 | WiFi ADB仅限局域网 | 需FRP/Tailscale穿透 |
