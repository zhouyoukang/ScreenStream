---
trigger: glob
glob_pattern: "*.kt"
---

# Kotlin/Android 项目认知

> 此文件为"术"层——项目特定知识。当编辑 `*.kt` 文件时自动加载。

## 模块映射

| 模块 | 路径 | 说明 |
|------|------|------|
| 投屏链路 | `mjpeg/` | MJPEG流+HttpServer+前端 |
| RTSP投屏 | `rtsp/` | RTSP流 |
| WebRTC投屏 | `webrtc/` | WebRTC P2P |
| 输入控制 | `input/` | Input API + AccessibilityService |
| 用户界面 | `app/src/main/java/...` | Android UI + Compose |
| 基础设施 | `lib/` | 公共组件/DI/工具/日志 |
| 配置管理 | `settings/` | Settings接口+实现 |

## 关键端口

| 端口 | 服务 |
|------|------|
| 9537 | MJPEG HTTP Server |
| 9555 | ADB Server |
| 8080 | 开发服务器 |

## 构建命令

```bash
./gradlew assembleDebug   # 调试构建
./gradlew assembleRelease # 发布构建
./gradlew installDebug    # 安装到设备
```

## Android调试

```bash
adb devices              # 查看设备
adb logcat              # 查看日志
adb shell dumpsys activity top # 查看当前Activity
```

## 注意事项

- 使用标准Android SDK路径（`$env:ANDROID_SDK_ROOT`）
- 禁止在 Junction 目录内进行 PowerShell 写入操作
- Gradle 构建串行执行，避免并发冲突

---

*此文件仅在编辑 Kotlin/Android 文件时加载。*
