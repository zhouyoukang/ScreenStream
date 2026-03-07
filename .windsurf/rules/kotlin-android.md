---
trigger: glob
globs: ["**/*.kt", "**/AndroidManifest.xml", "**/build.gradle.kts"]
---

# Kotlin/Android 开发规则

## 代码风格
- 最少代码实现完整功能
- 语义化命名，必要注释
- 职责单一，合理拆分
- 优先使用 Kotlin 惯用写法（scope functions, extension functions）

## AccessibilityService 注意事项
- `findFocusedNode()` 返回的节点必须 `recycle()`
- `isShowingHintText` 仅 API 26+，需要版本检查
- `ACTION_SET_TEXT` 后设置光标位置
- 检测 hint text 避免与真实文本混淆

## Android 构建
- JAVA_HOME: `C:\Program Files\Android\Android Studio\jbr`
- ANDROID_SDK_ROOT: `090-构建与部署_Build\android-sdk`
- ADB独立路径: `D:\platform-tools\adb.exe`（SDK缺失时回退）
- 构建命令: `gradlew assembleFDroidDebug --no-configuration-cache`
- 包名: `info.dvkr.screenstream.dev`
- 主Activity: `info.dvkr.screenstream.SingleActivity`

## 前台服务
- Android 12+ 必须使用 `ContextCompat.startForegroundService()`
- `onStartCommand` 中必须立即调用 `startForeground()`
