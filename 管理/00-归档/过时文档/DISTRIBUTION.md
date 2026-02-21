# ScreenStream 分发与适配方案

> 版本：v32 | 日期：2026-02-13

## 一、分发渠道

| 渠道 | 优先级 | 说明 |
|------|--------|------|
| **GitHub Releases** | ⭐⭐⭐⭐⭐ | 主渠道，APK 直接下载 |
| **F-Droid** | ⭐⭐⭐⭐ | 开源应用商店，自动构建 |
| **网盘链接** | ⭐⭐⭐ | 国内用户备用（百度网盘/阿里云盘） |
| Google Play | ❌ 不使用 | 审核严格，AccessibilityService 可能被拒 |

## 二、非 Root 用户体验设计

### 2.1 首次安装流程（目标：3步完成）

```
1. 下载安装 APK
2. 打开 APP → 自动弹出引导页
3. 跟随引导开启 AccessibilityService → 完成
```

### 2.2 AccessibilityService 自动引导

**问题**：不同品牌手机的无障碍设置路径不同。

**方案**：APP 内置品牌适配引导

```kotlin
// 检测品牌并生成对应的引导步骤
fun getAccessibilityGuide(): List<String> {
    return when (Build.MANUFACTURER.lowercase()) {
        "xiaomi", "redmi" -> listOf(
            "设置 → 更多设置 → 无障碍",
            "已下载的应用 → ScreenStream",
            "开启服务 → 确定"
        )
        "huawei", "honor" -> listOf(
            "设置 → 辅助功能 → 无障碍",
            "已安装的服务 → ScreenStream",
            "开启 → 确定"
        )
        "oppo", "oneplus", "realme" -> listOf(
            "设置 → 系统设置 → 无障碍",
            "已下载的应用 → ScreenStream",
            "开启 → 允许"
        )
        "vivo", "iqoo" -> listOf(
            "设置 → 更多设置 → 无障碍",
            "已下载的服务 → ScreenStream",
            "开启 → 确定"
        )
        "samsung" -> listOf(
            "设置 → 辅助功能 → 已安装的应用",
            "ScreenStream → 开启",
            "确定"
        )
        else -> listOf(
            "设置 → 无障碍/辅助功能",
            "找到 ScreenStream",
            "开启服务"
        )
    }
}
```

**一键跳转**：
```kotlin
// 直接跳转到无障碍设置页
startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
```

### 2.3 品牌特殊处理

| 品牌 | 特殊限制 | 处理方案 |
|------|---------|---------|
| 小米/MIUI | 后台限制严格 | 引导用户关闭电池优化 + 自启动 |
| 华为/EMUI | 后台杀进程 | 引导锁定最近任务 + 关闭省电 |
| OPPO/ColorOS | 自启动管理 | 引导添加自启动白名单 |
| vivo/OriginOS | 后台限制 | 引导关闭后台清理 |
| Samsung/OneUI | 设备管理 | 相对宽松，标准引导即可 |

## 三、Google API 限制应对

### 3.1 当前使用的 API 合规性分析

| API | SDK 级别 | 隐藏 API? | 风险 |
|-----|---------|----------|------|
| `AccessibilityService` | 公开 API | ❌ 否 | 🟢 安全 |
| `performGlobalAction()` | 公开 API | ❌ 否 | 🟢 安全 |
| `getRootInActiveWindow()` | 公开 API | ❌ 否 | 🟢 安全 |
| `findAccessibilityNodeInfosByText()` | 公开 API | ❌ 否 | 🟢 安全 |
| `GestureDescription` | 公开 API (API 24+) | ❌ 否 | 🟢 安全 |
| `dispatchGesture()` | 公开 API (API 24+) | ❌ 否 | 🟢 安全 |
| `AudioManager.adjustVolume()` | 公开 API | ❌ 否 | 🟢 安全 |
| `PowerManager.WakeLock` | 公开 API | ❌ 否 | 🟢 安全 |
| `Settings.System.putInt()` | 公开 API | ❌ 否 | 🟢 安全（需 WRITE_SETTINGS） |

### 3.2 结论

**我们当前使用的所有 API 都是 Android 公开 SDK API，不涉及隐藏 API 或反射调用。**

Google 封杀的是：
- `@hide` 注解的内部 API（通过反射调用）
- `android.internal.*` 包下的类
- 绕过 SELinux 的系统调用

我们的方案完全基于：
- `AccessibilityService`（官方无障碍服务框架）
- `Ktor`（HTTP/WebSocket 服务器）
- 标准 Android SDK API

**不需要任何静态修补或反射绕过。**

### 3.3 未来可能的风险

| 风险 | 可能性 | 影响 | 应对 |
|------|--------|------|------|
| Google 限制 AccessibilityService 能力 | 低 | 高 | AccessibilityService 是无障碍核心，大量应用依赖，Google 不太可能大幅限制 |
| 品牌 ROM 限制后台服务 | 中 | 中 | 已有品牌适配方案 |
| Android 版本升级 API 变动 | 中 | 低 | `targetSdk` 适配 + 版本判断 |

## 四、开发环境 vs 分发环境

| 维度 | 开发环境（当前） | 分发环境（目标） |
|------|----------------|----------------|
| Root | ✅ 已 Root | ❌ 不需要 |
| ADB | ✅ USB 连接 | ❌ 不需要 |
| AccessibilityService | 自动启用（`settings put`） | 引导用户手动开启 |
| 端口转发 | ADB forward | 局域网直连 |
| 调试 | logcat + curl | 用户反馈 |

## 五、最小可用版本清单

用户下载安装后，不需要任何额外配置即可使用的功能：

- [x] 屏幕投屏（MJPEG/H264/H265）
- [x] 任意设备浏览器查看
- [x] 触控操作（点击/滑动/长按/双击/捏合）
- [x] 导航操作（Home/Back/最近任务/通知栏）
- [x] 键盘输入
- [ ] AccessibilityService 自动引导开启（待实现）
- [ ] 品牌适配后台保活（待实现）
- [ ] 首次使用教程/引导页（待实现）
