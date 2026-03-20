# 本地投屏 · Agent操作指令 v2.0

> **从源码构建 → 部署 → 投屏 → 验证 完整管线已通**
> ScreenStream手机端内置HTTP Server + H264/H265 WebSocket流 + 70+ REST API + AI Brain

## 核心成就 (v2.0)

| 里程碑 | 状态 | 详情 |
|--------|------|------|
| 源码构建 | ✅ | `assembleFDroidDebug` 1m24s, 17MB APK |
| 部署到手机 | ✅ | OnePlus NE2210, AccessibilityService自动启用 |
| Input API | ✅ | 11/11端点响应 (8084端口) |
| H264视频流 | ✅ | WebSocket `/stream/h264` NAL帧已验证 |
| 音频流 | ✅ | WebSocket `/stream/audio` 已连接 |
| 触控反操控 | ✅ | WebSocket TouchWS已连接 |
| 浏览器前端 | ✅ | 469KB index.html + Command Center全面板 |

## 构建管线

```powershell
# 全链路: 构建→部署→验证→E2E
.\build_pipeline.ps1

# 分阶段
.\build_pipeline.ps1 -Phase build       # 仅构建
.\build_pipeline.ps1 -Phase deploy      # 仅部署
.\build_pipeline.ps1 -Phase verify      # 仅API验证
.\build_pipeline.ps1 -Phase e2e         # 端到端测试
.\build_pipeline.ps1 -Clean             # 清理重建
.\build_pipeline.ps1 -Device OnePlus    # 指定设备

# E2E验证(轻量)
.\e2e_build_test.ps1 -Verbose
```

## 构建环境

| 组件 | 路径/版本 |
|------|----------|
| JDK | `E:\CacheMigration\.gradle\jdks\eclipse_adoptium-17-amd64-windows.2` (OpenJDK 17.0.17) |
| Android SDK | `E:\Android\Sdk` |
| Gradle | 8.14.3 (wrapper) |
| AGP | 8.12.0 |
| Kotlin | 2.2.0 |
| ADB | `D:\platform-tools\adb.exe` |
| Debug Key | `gradle/debug-key.jks` |
| APK输出 | `010-用户界面与交互_UI/build/outputs/apk/FDroid/debug/app-FDroid-debug.apk` |

## 端口

| 端口 | 服务 | 位置 | 协议 |
|------|------|------|------|
| **8080** | SS Gateway | 手机端 | HTTP + WebSocket |
| **8084** | SS Input API | 手机端 | HTTP REST |
| **9871** | 本地投屏 Hub | PC端 | HTTP |

## 流架构 (WebSocket)

```
浏览器 ──WS /socket──→ 获取streamAddress + 设置协商
浏览器 ──WS /stream/h264──→ H264 NAL帧 (二进制)
浏览器 ──WS /stream/h265──→ H265 NAL帧 (二进制)
浏览器 ──WS /stream/audio──→ 音频PCM流
浏览器 ──WS TouchWS──→ 触控事件双向
```

## Input API (端口8084)

| 类别 | 端点 | 已验证 |
|------|------|--------|
| 基础 | `/status` `/deviceinfo` `/apps` `/foreground` `/clipboard` `/windowinfo` | ✅ 全通 |
| AI Brain | `/viewtree` `/screen/text` `/findclick` `/command` | ✅ |
| 宏系统 | `/macro/list` `/macro/running` `/macro/create` `/macro/run/{id}` | ✅ |
| 文件 | `/files/list` `/files/upload` `/files/download` | ✅ |
| 导航 | `/home` `/back` `/recents` `/notifications` `/quicksettings` | ✅ |
| 触控 | `/tap` `/swipe` `/longpress` `/doubletap` `/scroll` `/pinch` | ✅ |
| 系统 | `/volume` `/brightness` `/lock` `/wake` `/screenshot` `/flashlight` | ✅ |
| Auth | `/auth/info` `/auth/verify` `/auth/generate` `/auth/revoke` | ✅ |

## 关键文件

| 文件 | 用途 | 修改风险 |
|------|------|---------|
| `build_pipeline.ps1` | 完整构建管线(build→deploy→verify→e2e) | 🟡中 |
| `e2e_build_test.ps1` | 轻量E2E验证(18项测试) | 🟢低 |
| `lan_cast.py` | Hub中枢(设备发现+ADB+API) | 🟡中 |
| `dashboard.html` | Dashboard前端 | 🟢低 |
| `→本地投屏.cmd` | 一键启动Hub | 🟢低 |
| `e2e_results.json` | E2E测试结果(自动生成) | 🟢低 |

## 源码模块映射

| Gradle模块 | 目录 | 核心职责 |
|-----------|------|---------|
| `:app` | `010-用户界面与交互_UI/` | Android主APP (SingleActivity) |
| `:common` | `070-基础设施_Infrastructure/` | 模块管理/DI/工具/日志 |
| `:mjpeg` | `020-投屏链路_Streaming/010-MJPEG投屏_MJPEG/` | HTTP Server + 流引擎 + 前端 |
| `:rtsp` | `020-投屏链路_Streaming/020-RTSP投屏_RTSP/` | RTSP投屏 (PlayStore only) |
| `:webrtc` | `020-投屏链路_Streaming/030-WebRTC投屏_WebRTC/` | WebRTC投屏 (PlayStore only) |
| `:input` | `040-反向控制_Input/` | 70+ API + AccessibilityService |

## Agent操作规则

- **构建**: `.\build_pipeline.ps1` 或手动 `gradlew assembleFDroidDebug --no-configuration-cache`
- **部署**: 需设 `$env:JAVA_HOME` 和 `$env:ANDROID_SDK_ROOT`
- **WiFi投屏**: 浏览器直连 `http://手机IP:8080`
- **USB投屏**: 先 `adb forward tcp:8080 tcp:8080` 再访问 `http://127.0.0.1:8080`
- **MediaProjection**: 需用户在手机上点击"开始流"并授权录屏
- **ADB**: `D:\platform-tools\adb.exe`
- **验证**: `.\e2e_build_test.ps1 -Verbose`

## 与其他项目关系

| 项目 | 关系 | 路径 |
|------|------|------|
| **ScreenStream源码** | 上游: 手机端投屏引擎 | `../010-用户界面与交互_UI/` 等 |
| **GitHub** | 远程: `zhouyoukang/ScreenStream` | `origin/main` |
| **scrcpy** | 集成: USB备选投屏 | `../scrcpy/` |
| **亲情远程** | 衍生: 公网P2P投屏 | `../亲情远程/` |
| **公网投屏** | 衍生: H264 Relay公网投屏 | `../公网投屏/` |
