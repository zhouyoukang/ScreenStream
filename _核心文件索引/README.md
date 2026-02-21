# ScreenStream_v2 核心文件索引

> 生成时间：2026-02-21 | 分析范围：全项目
> 本文件夹不包含源代码副本，仅提供**结构化索引**，避免破坏 Gradle 构建体系。

## 项目核心目的

**Android 屏幕投屏 + 远程控制 + AI Brain + 宏系统**

用户在手机上运行 ScreenStream，PC 浏览器打开投屏页面即可：
1. 实时观看手机屏幕（MJPEG/H264/H265 + 音频）
2. 鼠标/键盘远程控制手机（触控/滑动/打字/导航）
3. 通过 Command Center 执行 30+ 设备管理操作
4. 使用宏系统编排自动化任务
5. AI Brain 语义化操作（View 树分析/智能点击/自然语言命令）

---

## Gradle 模块映射（6 个模块）

| Gradle 模块 | 目录 | 核心职责 |
|-------------|------|----------|
| `:app` | `010-用户界面与交互_UI/` | Android 主界面、设置、通知、瓦片 |
| `:common` | `070-基础设施_Infrastructure/` | 模块管理、DI、工具、日志 |
| `:mjpeg` | `020-投屏链路_Streaming/010-MJPEG投屏_MJPEG/` | MJPEG/H264/H265 投屏 + HTTP 服务器 + 前端 |
| `:rtsp` | `020-投屏链路_Streaming/020-RTSP投屏_RTSP/` | RTSP 投屏 |
| `:webrtc` | `020-投屏链路_Streaming/030-WebRTC投屏_WebRTC/` | WebRTC 投屏 |
| `:input` | `040-反向控制_Input/` | 输入控制、API 路由、宏引擎 |

---

## 一、核心源码文件（按功能分组）

### 1.1 HTTP 服务器 + 投屏引擎（`:mjpeg` 模块）

| 文件 | 行数 | 职责 |
|------|------|------|
| `mjpeg/internal/HttpServer.kt` | 487 | Ktor HTTP/WebSocket 服务器，挂载所有路由 |
| `mjpeg/internal/BitmapCapture.kt` | — | 屏幕截图捕获（MediaProjection） |
| `mjpeg/internal/H264Encoder.kt` | — | H264/H265 硬件编码器 |
| `mjpeg/internal/AudioStreamer.kt` | — | 音频流采集与传输 |
| `mjpeg/internal/HttpServerData.kt` | — | 连接管理、PIN 验证、客户端追踪 |
| `mjpeg/internal/MjpegStreamingService.kt` | — | 投屏服务生命周期管理 |
| `mjpeg/internal/MjpegEvent.kt` | — | 事件定义 |
| `mjpeg/internal/MjpegNetInterface.kt` | — | 网络接口抽象 |
| `mjpeg/internal/NetworkHelper.kt` | — | 网络工具 |
| `mjpeg/internal/extentions.kt` | — | 扩展函数 |
| `mjpeg/MjpegKoinModule.kt` | — | Koin DI 模块 |
| `mjpeg/MjpegModuleService.kt` | — | 模块服务 |
| `mjpeg/MjpegStreamingModule.kt` | — | 模块定义 |

### 1.2 反向控制（`:input` 模块）— 项目核心价值

| 文件 | 行数 | 职责 |
|------|------|------|
| `InputRoutes.kt` | 784 | **全部 API 路由**（70+ 端点：触控/键盘/导航/系统控制/AI/宏/文件/平台） |
| `InputService.kt` | 3626 | **AccessibilityService 核心**（手势注入/键盘映射/View 树/设备管理/通知捕获） |
| `MacroEngine.kt` | 519 | 宏引擎（CRUD/执行/触发器/定时/持久化） |
| `InputHttpServer.kt` | — | 独立 HTTP 服务器（端口 8084） |
| `InputKoinModule.kt` | — | DI 模块 |

### 1.3 Web 前端（assets 目录）

| 文件 | 行数 | 职责 |
|------|------|------|
| `assets/index.html` | 6417 | **主投屏页面**（6 模式导航/触控/键盘/系统控制/远程/宏/AI 工具箱/10 平台面板） |
| `assets/voice.html` | 150 | **Command Center**（30+ 设备管理磁贴/语音输入/自然语言命令） |
| `assets/voice.js` | 186 | Command Center 全部交互逻辑（5s 仪表盘刷新/API 调用/语音识别） |
| `assets/dev/script.js` | 433 | 投屏页面 JS 逻辑（WebSocket 连接/PIN/PiP/全屏/SHA256） |
| `assets/jmuxer.min.js` | — | H264 解码库（第三方） |
| `assets/favicon.ico` | — | 图标 |
| `assets/logo.svg` / `logo.png` | — | Logo |
| `assets/server.p12` | — | HTTPS 证书 |

### 1.4 基础设施（`:common` 模块）

| 文件 | 职责 |
|------|------|
| `module/StreamingModule.kt` | 投屏模块抽象接口 |
| `module/StreamingModuleManager.kt` | 模块生命周期管理 |
| `module/StreamingModuleService.kt` | 前台服务基类 |
| `CommonKoinModule.kt` | 全局 DI |
| `ModuleSettings.kt` | 设置抽象 |
| `extensions.kt` | 通用扩展 |
| `logger/AppLogger.kt` | 日志系统 |
| `logger/CollectingLogsUi.kt` | 日志 UI |

### 1.5 配置管理（`080-配置管理_Settings/`）

| 文件 | 职责 |
|------|------|
| `AppSettings.kt` / `AppSettingsImpl.kt` | 全局配置 |
| `MjpegSettings.kt` / `MjpegSettingsImpl.kt` | MJPEG 配置 |
| `RtspSettings.kt` / `RtspSettingsImpl.kt` | RTSP 配置 |
| `WebRtcSettings.kt` / `WebRtcSettingsImpl.kt` | WebRTC 配置 |
| `InputSettings.kt` / `InputSettingsImpl.kt` | 输入控制配置 |

### 1.6 构建系统

| 文件 | 职责 |
|------|------|
| `settings.gradle.kts` | 模块注册（6 个模块） |
| `build.gradle.kts`（根） | 顶层构建配置 |
| `gradle/libs.versions.toml` | 依赖版本目录 |
| `gradle.properties` | Gradle 属性 |
| `090-构建与部署_Build/dev-deploy.ps1` | 一键部署脚本 |

---

## 二、非核心但有价值的辅助文件

| 目录/文件 | 说明 | 建议 |
|-----------|------|------|
| `05-文档_docs/` | 项目文档（FEATURES/STATUS/VISION 等） | 保留，知识资产 |
| `api-services/` | 独立 API 服务伴侣项目 | 保留，测试用 |
| `050-音频处理_Audio/` | 音频中心子项目 | 保留，独立发展 |
| `100-智能家居_SmartHome/` | 智能家居集成文档 | 保留，未来方向 |
| `tools/agent-phone-soul/` | Agent 手机控制工具 | 保留，理论有价值 |
| `.windsurf/` | AI 规则/技能/工作流 | 保留，开发基础设施 |

---

## 三、已识别的垃圾/无效产出

| 项目 | 大小 | 状态 |
|------|------|------|
| 根目录 `$null` 文件（0 bytes） | 0 | ✅ 已删除 |
| `.gitignore` 14 条中文路径乱码 | — | ✅ 已修复 |
| `voice.html` 3 个路由 Bug | — | ✅ 已修复 |
| 根目录视频文件（~8.1 GB） | 8.1 GB | ⚠️ 建议移出仓库 |
| `管理/` 旧 APK（129 MB） | 129 MB | ⚠️ 建议清理 |
| Gradle build/ 缓存（~155 MB） | 155 MB | ⚠️ 可 gradlew clean |
| `050-音频/.../references/`（158 MB） | 158 MB | ⚠️ 参考项目克隆 |

---

## 四、发现并修复的问题

### 问题 1：`.gitignore` 编码腐败 🔴 严重
- **现象**：14 条含中文的 gitignore 规则全是乱码（mojibake）
- **影响**：android-sdk（1GB）、管理/、06-技能_skills/ 等未被正确忽略
- **根因**：Agent 写入时编码处理错误（UTF-8 内容被 Latin-1 方式处理）
- **修复**：重写所有中文路径为正确 UTF-8

### 问题 2：`voice.html` 路由 Bug 🟡
- `/flashlight/toggle` → 路由不存在，修复为 `/flashlight/true` toggle 逻辑
- `/rotate` → 缺少 degrees 参数，修复为 `/rotate/90`（每次旋转 90°）
- `voice.js` 音量 `adjust` 参数 → InputRoutes 期望 `level`，修复为 up/down 路由

### 问题 3：`$null` 垃圾文件 🟢
- 根目录 0 字节 `$null` 文件，PowerShell 重定向产物，已删除

---

## 五、API 端点全览（70+ 个）

### 基础控制
`POST /tap` · `/swipe` · `/key` · `/text` · `/pointer`

### 导航
`POST /home` · `/back` · `/recents` · `/notifications` · `/quicksettings`

### 系统控制
`POST /volume/up` · `/volume/down` · `/lock` · `/wake` · `/power` · `/screenshot` · `/splitscreen`
`POST /brightness/{level}` · `GET /brightness`

### 增强手势
`POST /longpress` · `/doubletap` · `/scroll` · `/pinch`

### 设备管理
`POST /openapp` · `/openurl` · `/upload` · `/killapp`
`GET /deviceinfo` · `/apps` · `/clipboard` · `/foreground`
`POST /media/{action}` · `/findphone/{enabled}` · `/vibrate` · `/flashlight/{enabled}`
`POST /dnd/{enabled}` · `/volume` · `/autorotate/{enabled}`
`POST /stayawake/{enabled}` · `/showtouches/{enabled}` · `/rotate/{degrees}`

### AI Brain
`GET /viewtree` · `/windowinfo` · `/screen/text`
`POST /findclick` · `/dismiss` · `/findnodes` · `/settext`
`POST /command` · `/command/stream`

### 宏系统
`GET /macro/list` · `/macro/{id}` · `/macro/running` · `/macro/log/{id}` · `/macro/triggers`
`POST /macro/create` · `/macro/run/{id}` · `/macro/run-inline` · `/macro/stop/{id}`
`POST /macro/update/{id}` · `/macro/delete/{id}` · `/macro/trigger/{id}`

### 文件管理
`GET /files/storage` · `/files/list` · `/files/info` · `/files/read` · `/files/download` · `/files/search`
`POST /files/mkdir` · `/files/delete` · `/files/rename` · `/files/move` · `/files/copy` · `/files/upload`

### 平台层
`POST /intent` · `GET /screen/text` · `GET /wait` · `GET /notifications/read`

### 演示
`POST /demo/semantic` · `/demo/wifi`
