# ScreenStream_v2 项目深度分析与技术总结

## 1. 项目概览

**ScreenStream** 是一个功能强大的 Android 屏幕共享与远程控制应用。该项目基于 Dmytro Kryvoruchko 的开源项目进行深度定制（即 zhouyoukang 的 Fork 版本），旨在提供低延迟、高清晰度的屏幕镜像，并集成了完善的远程控制功能。

### 核心功能
- **多模式流式传输**：
  - **Local Mode (MJPEG)**: 通过内置 HTTP Server 传输 JPEG 图像序列，延迟极低，无需外网，支持浏览器直接观看与控制。
  - **RTSP Mode**: 将屏幕画面流式推送到外部 RTSP 服务器（如 MediaMTX），支持 H.264/H.265/AV1 编码。
  - **Global Mode (WebRTC)**: (Google Play 版) 通过公网信令服务器实现点对点传输。
- **远程控制 (Input Service)**: 利用 Android `AccessibilityService` 实现点击、滑动、打字、手势等操作，无需 Root 权限（需手动开启无障碍服务）。
- **高级定制 (Fork 特性)**:
  - 针对 FRP 内网穿透优化（`0.0.0.0` 绑定，自定义端口）。
  - PC 端键鼠操作的完美映射（右键返回、滚轮滚动、键盘打字）。
  - 像素级精准的点击映射（解决黑边/比例问题）。
  - VR/Quest 体验优化：默认抑制 VR 键盘弹出、音频解锁提示优化、增强的音频解锁/恢复策略。

---

## 2. 技术栈架构

项目采用现代 Android 开发技术栈，遵循模块化设计原则。

| 类别 | 技术/库 | 说明 |
| :--- | :--- | :--- |
| **语言** | Kotlin | 100% Kotlin 代码，大量使用 Coroutines 和 Flow。 |
| **UI 框架** | Jetpack Compose | 声明式 UI 构建，实现了 Material 3 设计规范。 |
| **架构模式** | MVVM / Clean Arch | 结合 Koin 依赖注入，各模块职责分明。 |
| **依赖注入** | Koin | 轻量级 DI 框架，便于模块化管理。 |
| **网络服务** | Ktor (Server & Client) | 核心组件。用于构建内置 HTTP Server (MJPEG) 和处理网络请求。 |
| **多媒体核心** | MediaProjection API | Android 官方截屏 API。 |
| **编解码** | MediaCodec / Bitmap | H.264/H.265 硬编解码 (RTSP) 及 Bitmap 压缩 (MJPEG)。 |
| **日志** | XLog | 高效的日志系统。 |
| **构建系统** | Gradle Kotlin DSL | 使用 Version Catalog (`libs.versions.toml`) 管理依赖。 |

---

## 3. 模块结构分析

项目工程结构清晰，按功能特性进行了模块拆分：

### 📁 `app` (Application Module)
- **职责**: 应用的主入口，负责整体生命周期管理、全局配置、依赖注入的初始化。
- **关键类**:
  - `ScreenStreamApp`: Application 类，初始化 XLog, Koin 等。
  - `SingleActivity`: 单 Activity 架构，承载 Compose UI 内容。
  - `libs.versions.toml`: 统一管理所有模块的依赖版本。

### 📁 `common` (Common Library)
- **职责**: 存放各模块共用的基础组件、扩展函数、设置接口和 UI 组件。
- **关键组件**:
  - `StreamingModule`: 定义流媒体模块的标准接口（Start, Stop, UI Content）。
  - `AppSettings`: 全局设置管理（DataStore）。
  - `ModuleSettings`: 模块化设置基类。

### 📁 `mjpeg` (MJPEG Streaming Module)
- **核心模块**: 实现基于 HTTP 的 图片流传输。
- **实现原理**:
  - **捕获**: `BitmapCapture` 使用 `ImageReader` 从 `MediaProjection` 获取 Surface 内容，转换为 Bitmap。
  - **压缩**: 将 Bitmap 压缩为 JPEG 字节流。
  - **传输**: `HttpServer` (Ktor CIO) 监听端口，通过 `multipart/x-mixed-replace` 协议向浏览器连续推送 JPEG 帧。
  - **控制集成**: 该模块的 HTTP Server 同时集成了控制 API 路由 (`/tap`, `/swipe` 等)，直接调用 `InputService`。
- **优势**: 兼容性极高（所有浏览器支持），延迟极低，适合局域网或高速网络。

### 📁 `rtsp` (RTSP Streaming Module)
- **核心模块**: 实现标准 RTSP 推流。
- **实现原理**:
  - **编码**: `VideoEncoder` / `H264Encoder` 使用 `MediaCodec` 将屏幕内容编码为 H.264/H.265 NAL 单元。
  - **协议**: 实现了自定义的 RTSP 客户端 (`RtspClient`)，支持 TCP/UDP 传输。
  - **音频**: `AudioCapture` 录制系统内声或麦克风，编码为 AAC/OPUS 并通过 RTSP 发送。

### 📁 `input` (Remote Control Module)
- **职责**: 独立封装的远程控制服务。
- **关键实现**:
  - `InputService`: 继承自 `AccessibilityService`。
    - **手势注入**: `dispatchGesture` 实现点击、长按、滑动。
    - **文本注入**: 通过 Clipboard + Paste 模拟输入，支持中文，规避了直接输入键值的兼容性问题。
    - **按键模拟**: 监听键盘事件，映射 PC 键盘的特殊键（Esc -> Back, Home, Recents）。
  - **坐标映射**: 提供 `tapNormalized(nx, ny)` 接口，接收 0.0~1.0 的相对坐标，自动换算为当前设备分辨率的绝对坐标，确保不同屏幕尺寸下的控制准确性。

### 📁 `webrtc` (WebRTC Module)
- **职责**: P2P 音视频传输（仅 Play Store 版支持完整功能）。
- **实现**: 基于 Google WebRTC 库，实现信令交换和流媒体传输。

---

## 4. 关键技术实现细节

### 4.1 屏幕捕获与 MJPEG 流
代码位于 `mjpeg/.../internal/BitmapCapture.kt` 和 `HttpServer.kt`。
1. **获取画面**: `MediaProjection.createVirtualDisplay` 将屏幕内容投射到 `ImageReader` 的 Surface。
2. **处理帧**: `OnImageAvailableListener` 获取最新的 `Image`，通过 `libjpeg` (Android Bitmap API) 压缩。
3. **并发流**: 使用 Kotlin Flow (`mjpegSharedFlow`) 分发 JPEG 数据。即使有多个浏览器连接，屏幕只截取一次，数据被广播给所有客户端。
4. **防抖与优化**: 如果画面无变化或达到最大 FPS 限制，会控制发帧频率。

### 4.2 远程控制系统 (Input Architecture)
这是一个亮点功能，解决了“只看不控”的痛点。
- **通信**: 修改后的 `HttpServer` 在提供视频流的同时，开放 POST 接口（如 `/tap`）。前端 JS 捕获鼠标点击，计算相对坐标（百分比），发送 JSON 数据。
- **服务端处理**:
  ```kotoln
  // HttpServer.kt
  post("/tap") {
      val json = JSONObject(call.receiveText())
      val nx = json.getDouble("nx").toFloat() // 0.5
      val ny = json.getDouble("ny").toFloat() // 0.5
      InputService.instance?.tapNormalized(nx, ny)
  }
  ```
- **无障碍服务执行**: `InputService` 接收到指令，构建 `GestureDescription`，调用 `dispatchGesture` 系统 API 模拟真实手指触摸。

---

## 6. 使用方法（PC/VR 实战）

### 6.1 PC 浏览器（推荐调试入口）
1. 手机端打开 ScreenStream，选择 **Local(MJPEG)**，点击开始投屏。
2. 在 PC 浏览器打开应用显示的地址。
3. 若要远程控制：在手机系统设置里开启本应用的**无障碍服务**。
4. 文本输入：直接用电脑键盘输入；`Ctrl+V` 会尽可能读取电脑剪贴板并发送到手机。

### 6.2 Quest / VR 浏览器（OculusBrowser）
1. 进入同一局域网/热点，打开网页地址。
2. 若音频未响：浏览器可能因为 autoplay 策略阻止音频。页面会提示：
   - **"VR：请点击底部导航栏（三大金刚键区域）以开启音频"**
   按提示操作一次即可（提示会自动消失）。
3. VR 键盘：默认会抑制网页自动聚焦输入框，避免 VR 键盘频繁弹出；如确实需要可使用 `?vr_kb=1`。

### 6.3 已知限制（Quest 手柄按键）
1. 网页端若要读取更多手柄输入，需要依赖 WebXR 输入（`XRInputSource.gamepad`）。
2. **平台/浏览器保留按键（系统 Home/Meta 等）按标准要求不得暴露给网页**，因此无法作为网页快捷键使用。
3. 业务上建议使用 trigger/squeeze/thumbstick/A/B/X/Y 等可暴露按键进行映射。

### 4.3 解决“黑边”与坐标偏移
在 Web 端显示手机画面时，为了保持比例（Object-fit: contain），往往会出现黑边。
- **前端优化**: `index.html` 中的 JS 逻辑 `getStreamImagePoint` 会计算视频元素在浏览器中的实际显示区域（去处黑边），将鼠标点击位置转换为相对于**画面本身**的归一化坐标。
- 这确保了无论浏览器窗口如何缩放，点击位置始终精准映射到手机屏幕对应的点。

### 4.4 FRP 内网穿透支持 (Fork 特性)
- **Host 绑定**: 原版可能绑定特定的本地 IP，该版本修改为绑定 `0.0.0.0`，允许来自任何网卡（包括虚拟网卡/FRP 隧道）的连接。
- **端口透传**: 增加了 `input_port` 参数支持。在复杂的内网穿透环境中，视频流端口和控制指令端口可能映射不同，该特性允许前端页面灵活指定控制指令的目标端口。

---

## 5. 总结

ScreenStream_v2 是一个架构成熟、代码质量高的开源项目。它不仅展示了 Android 多媒体开发的深厚功底（MediaCodec, MediaProjection），还通过引入 Ktor 和 Jetpack Compose 实现了现代化的应用开发范式。

**特别之处在于其对“实用性”的极致追求**：
通过集成 `AccessibilityService` 并配合前端精心调优的交互逻辑，它将一个简单的“投屏”工具进化为了一个生产力级别的“远程控制”工具，非常适合用于远程调试、演示、协助等场景。
