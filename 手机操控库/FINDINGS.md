# 实测发现与经验库

> 设备：OnePlus NE2210, Android 15 (API 35), 1080x2412
> 最后验证：2026-02-22 | 测试结果：46/46 全通过（standalone 36 + agent 5 + complex 5）

## 核心指标

| 指标 | 数值 |
|------|------|
| API平均响应 | 50-100ms |
| observe-act-verify | ~2-3秒/步 |
| findByText 成功率 | 100%（含contentDescription） |
| 零AI自治度 | 86%步骤无需AI |

## Android 平台限制（不可绕过）

| 限制 | 表现 | 应对 |
|------|------|------|
| **微信反无障碍** | `/screen/text` 返回 texts=0 | 用 `/foreground` 包名验证替代文本验证 |
| **剪贴板后台限制** (Android 10+) | `GET /clipboard` 返回 null | API写入时内部缓存；手机手动复制的无法读取 |
| **force-stop 禁用无障碍** | 重启后API返回空 | `dev-deploy.ps1` 已集成重新启用无障碍 |
| **WebView不走accessibility** | 闲鱼/1688等返回DOM ID非文本 | 暂无解，需 `/viewtree?webview=true` |

## 前台APP检测回退机制

微信等反无障碍APP触发时的4层回退：
```
rootInActiveWindow → getWindows()扫描 → UsageStatsManager → event_cache
```
UsageStatsManager 需授权：`adb shell su -c "appops set info.dvkr.screenstream.dev android:get_usage_stats allow"`

## findByText 机制

`findAccessibilityNodeInfosByText()` **同时搜索 text 和 contentDescription**，覆盖面比预期更广。

**元素查找降级策略**：
1. findByText（含desc）→ 最可靠
2. findByViewId → 最精确
3. coordinateTap → 兜底

## OEM 差异（OPPO/ColorOS）

- `com.oplus.securitypermission` 拦截部分APP启动 → `monkey` 命令绕过（走shell权限）
- 抖音持久拦截 → `adb shell appops set <pkg> AUTO_START allow`
- HANS省电冻结后台 → 加电池优化白名单
- APP启动回退链：`/openapp` → Intent MAIN+LAUNCHER → dismiss弹窗 → 记录OEM限制

## APP内搜索经验

- 搜索栏label不统一 → `search_in_app()` 双策略：findclick"搜索栏" → ADB tap顶部
- 底部Tab"搜索"≠顶部搜索框，需区分
- 中文输入：`adb input text`仅ASCII → 用`clipboard_write`+粘贴
- 京东安全验证：检测ADB连接本身（非WiFi/USB），需人工完成验证后继续

## View树性能

| 接口 | 响应 | 适用 |
|------|------|------|
| `/screen/text` | 10-30ms | 首选：文本+可点击元素 |
| `/windowinfo` | ~5ms | 仅包名+节点数 |
| `/viewtree?depth=4` | 20-50ms | 快速定位 |
| `/viewtree?depth=8` | 50-200ms | 标准深度 |

## 通用经验

- `monkey` 是最可靠的APP启动方式
- ADB+API混合模式最优：ADB启动/导航，API感知/读取
- 通知监控是零依赖高价值通道
- View树同一元素可能出现两次（容器+子节点），`/findclick`已有clickable优先逻辑
- 不可点击文本→向上5层parent通常找到可点击容器

## 远程架构发现（2026-02-22）

### InputHttpServer 绑定地址
- `InputHttpServer(8084)`: `embeddedServer(CIO, port=port)` → **默认绑定0.0.0.0** ✅
- `MJPEG HttpServer(8081)`: 根据addressFilter设置监听WiFi/Private/Public接口 ✅
- **结论**: 远程直连在底层已支持，手机WiFi IP:port可直接访问所有90个API

### 纯HTTP模式（无ADB）
- `monkey_open()` → 回退到HTTP `/intent` API（OPPO弹窗拦截时效果稍差）
- `search_in_app()` → 用HTTP `/tap`+`/key`+`/text` 替代ADB `input` 命令
- `discover()` → 无ADB时支持: extra_hosts手动指定 / 局域网网段扫描
- 所有90个API端点均为HTTP，**纯网络即可全功能操控**

### 连接层级实测
| 层 | 方式 | 延迟 | 适用场景 |
|----|------|------|----------|
| L1 | USB `adb forward` | ~1ms | 开发调试 |
| L2 | WiFi直连 | 1-5ms | 家/办公室同网段 |
| L3 | Tailscale | 20-100ms | 外出任何网络 |
| L4 | 公网穿透 | 50-200ms | 极端场景 |

### 负面状态恢复优先级链
多故障叠加时按以下顺序恢复（先恢复致命的，再恢复次要的）：
1. wifi_lost → 重新发现所有链路
2. usb_lost → 切WiFi/Tailscale
3. app_killed → monkey重启+端口重探测
4. screen_off → POST /wake
5. a11y_dead → /a11y/enable 或 ADB
6. doze_mode → ADB unforce + wake
7. battery_low → 告警
