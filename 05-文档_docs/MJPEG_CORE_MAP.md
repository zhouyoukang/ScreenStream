# MJPEG 投屏模块 — 核心文件地图

> 生成时间：2026-02-21 | Gradle 模块名：`:mjpeg`
>
> 本文档是 MJPEG 投屏模块的**唯一权威索引**，覆盖散布在整个项目中的所有核心文件。

## 一、核心目的

**Android 屏幕实时投屏 HTTP 服务**

```
屏幕采集(MediaProjection) → 编码(MJPEG/H264/H265) → HTTP/WebSocket服务(Ktor) → 浏览器查看+远程控制
```

## 二、Gradle 模块定义

| 项目 | 值 |
|------|-----|
| 模块名 | `:mjpeg` |
| 目录 | `020-投屏链路_Streaming/010-MJPEG投屏_MJPEG/` |
| namespace | `info.dvkr.screenstream.mjpeg` |
| 依赖 | `:common` (基础设施), `:input` (反向控制) |
| 源码目录 | `mjpeg/` (非标准 `src/main/java/`) |
| assets 目录 | `assets/` + `mjpeg/assets/` |
| 资源目录 | `res/` + `mjpeg/res/` |

定义位置：`settings.gradle.kts` 第 27-28 行

## 三、核心源码文件清单

### 3.1 模块入口（3 个 Kotlin 文件）

| 文件 | 大小 | 职责 |
|------|------|------|
| `mjpeg/MjpegKoinModule.kt` | 1.3KB | Koin DI 模块注册 |
| `mjpeg/MjpegModuleService.kt` | 5.3KB | Android 前台服务（启停/通知/错误） |
| `mjpeg/MjpegStreamingModule.kt` | 5.5KB | 模块生命周期管理（状态机） |

### 3.2 核心实现（`mjpeg/internal/`，10 个文件）

| 文件 | 大小 | 职责 |
|------|------|------|
| `MjpegStreamingService.kt` | 34KB | **核心编排器**：MediaProjection→BitmapCapture→编码→HttpServer |
| `HttpServer.kt` | 22.7KB | **Ktor HTTP 服务器**：路由/MJPEG流/H264 WS/H265 WS/音频 WS |
| `HttpServerData.kt` | 11.7KB | 客户端管理、PIN 认证、流量统计 |
| `BitmapCapture.kt` | 27.6KB | 屏幕截图（ImageReader + OpenGL ES fallback for VR） |
| `H264Encoder.kt` | 6.8KB | MediaCodec 硬件编码（H264/H265） |
| `AudioStreamer.kt` | 4.5KB | AudioPlaybackCapture 音频采集 (Android 10+) |
| `NetworkHelper.kt` | 13.6KB | 网络接口发现（WiFi/移动/以太网/VPN） |
| `MjpegEvent.kt` | 1.8KB | 事件定义（启停/投屏权限/PIN） |
| `MjpegNetInterface.kt` | 0.4KB | 网络接口数据类 |
| `extentions.kt` | 4.9KB | 扩展函数（资产加载/网络监听/颜色转换） |

### 3.3 OpenGL ES 辅助（`mjpeg/com/android/grafika/gles/`，7 个 Java 文件）

来源：Google Grafika 项目，用于 VR 模式和 OpenGL 回退渲染。

| 文件 | 大小 |
|------|------|
| `EglCore.java` | 13.3KB |
| `Texture2dProgram.java` | 14.5KB |
| `GlUtil.java` | 7KB |
| `Drawable2d.java` | 6.5KB |
| `EglSurfaceBase.java` | 6.5KB |
| `FullFrameRect.java` | 3.1KB |
| `OffscreenSurface.java` | 1.2KB |

### 3.4 设置（`mjpeg/settings/`，3 个文件）

| 文件 | 大小 | 职责 |
|------|------|------|
| `MjpegSettings.kt` | 179行 | 设置接口（Key/Default/Values/Data） |
| `MjpegSettingsImpl.kt` | 203行 | DataStore 实现 |
| `MjpegSettingsMigrations.kt` | 54行 | 旧版数据迁移 |

### 3.5 UI（`mjpeg/ui/`，共 39 个文件）

| 目录/文件 | 职责 |
|-----------|------|
| `MjpegMainScreenUI.kt` | Compose 主界面 |
| `MjpegModuleSettings.kt` | 设置模块入口 |
| `models.kt` | UI 数据模型（MjpegState/MjpegError） |
| `main/` (5 files) | 主屏幕卡片：Clients/Error/Interfaces/Pin/Traffic |
| `settings/` (31 files) | 设置页面 UI：General/Image/Security/Advanced |

## 四、前端文件

### 4.1 运行时资产（`assets/`）

| 文件 | 大小 | 职责 | 打包 |
|------|------|------|------|
| `index.html` | 352KB (6417行) | **主投屏页面**：投屏画面+6模式导航+远程控制+AI工具 | ✅ |
| `voice.html` | 20.9KB (772行) | **Command Center**：仪表盘+功能面板+宏管理 | ✅ |
| `voice.js` | 19KB (248行) | Command Center JS 逻辑 | ✅ |
| `jmuxer.min.js` | 41KB | H264 解码库（第三方） | ✅ |
| `favicon.ico` | 9.7KB | 网站图标 | ✅ |
| `logo.png` | 3.3KB | Logo 位图 | ✅ |
| `logo.svg` | 1.5KB | Logo 矢量 | ✅ |
| `server.p12` | 2.6KB | SSL 证书 | ✅ |

### 4.2 开发工具（`assets/dev/`）— 不打包入 APK

| 文件 | 职责 |
|------|------|
| `script.js` | index.html 的 JS 开发源码（Babel 编译前） |
| `package.json` | Babel 依赖 |
| `babel.config.json` | Babel 配置 |

### 4.3 文档（`assets/`）— 不打包入 APK

| 文件 | 职责 |
|------|------|
| `COMMAND_CENTER.md` | Command Center 架构索引 |

## 五、构建和清单

| 文件 | 职责 |
|------|------|
| `build.gradle.kts` | 模块构建配置 |
| `src/main/AndroidManifest.xml` | 服务声明（MjpegModuleService + MediaProjection 权限） |

## 六、多语言资源（`res/`）

23 个语言目录的字符串翻译：
af, am, ar, bn, de, es, eu, fr, hi, in, it, ja, jv, ka, nl, pl, pt, ru, uk, uz, zh, zh-rTW + 默认 values/

## 七、跨模块依赖文件

### 7.1 直接依赖：`:input` 模块（反向控制）

| 文件 | 关系 |
|------|------|
| `040-反向控制_Input/010-输入路由_Routes/InputRoutes.kt` | 在 HttpServer 中通过 `installInputRoutes()` 挂载 |
| `040-反向控制_Input/020-输入服务_Service/InputService.kt` | 提供触控/键盘/导航等所有控制能力 |
| `040-反向控制_Input/030-HTTP服务器_HttpServer/` | Input 独立 HTTP 服务（端口 8084） |
| `040-反向控制_Input/040-宏系统_Macro/MacroEngine.kt` | 宏录制/回放引擎 |

### 7.2 直接依赖：`:common` 模块（基础设施）

| 文件 | 关系 |
|------|------|
| `070-基础设施_Infrastructure/010-模块管理_ModuleManager/` | StreamingModule 基类/StreamingModuleService |
| `070-基础设施_Infrastructure/020-依赖注入_DI/` | CommonKoinModule |
| `070-基础设施_Infrastructure/030-通用工具_Utils/` | 扩展函数/ModuleSettings |
| `070-基础设施_Infrastructure/040-日志系统_Logging/` | XLog 封装 |

### 7.3 上游宿主：`:app` 模块

`010-用户界面与交互_UI/` — 应用主入口，加载并展示 MJPEG 模块 UI

## 八、参考/伴侣文件（非编译依赖）

| 文件 | 性质 | 说明 |
|------|------|------|
| `090-构建与部署_Build/030-MJPEG构建_MjpegBuild` | 上游参考 | 原始 build.gradle.kts 参考版本 |
| `api-services/mjpeg-server/` | 伴侣项目 | 独立 API 服务器（用于无 APK 测试） |

## 九、已识别的冗余/垃圾文件

| 文件 | 问题 | 处置 |
|------|------|------|
| `080-配置管理_Settings/020-MJPEG配置_MjpegSettings/settings/` (3 files) | ❌ 与 `mjpeg/settings/` 100% 重复（已验证 byte-identical） | 应删除，避免维护漏改 |
| `080-配置管理_Settings/030-RTSP配置_RtspSettings/settings/` (2 files) | ❌ 与 RTSP 模块内 settings/ 重复 | 同上 |
| `080-配置管理_Settings/040-WebRTC配置_WebRtcSettings/settings/` (2 files) | ❌ 与 WebRTC 模块内 settings/ 重复 | 同上 |
| `管理/00-归档/backups/v4_stable/mjpeg/src/` | ❌ 空目录，无效备份 | 应删除 |
| `管理/00-归档/根目录-logcat/logcat_mjpeg_filtered.txt` | ⚠️ 旧日志 | 可删除 |

> **080-配置管理_Settings/ 清理结果**：
> - ✅ 已删除 MJPEG/RTSP/WebRTC 的 7 个冗余副本（与各自模块内 settings/ 100% 重复）
> - ✅ 保留 `010-全局配置_GlobalSettings/`（被 `:common` 的 build.gradle.kts 引用为源码目录）
> - ✅ 保留 `040-反向控制配置_InputSettings/`（被 `:input` 的 build.gradle.kts 引用为源码目录）

## 十、已修复的问题

| 问题 | 修复 |
|------|------|
| `assets/dev/` 被打包入 APK | `build.gradle.kts` 添加 `ignoreAssetsPattern = "!dev:!*.md"` |
| `assets/COMMAND_CENTER.md` 被打包入 APK | 同上，`!*.md` 排除所有 .md 文件 |
| 上游参考有 `ignoreAssetsPattern` 但当前缺失 | 已补齐，与 `030-MJPEG构建_MjpegBuild` 保持一致 |

## 十一、核心数据流

```
┌─────────────────── Android 端 ───────────────────┐
│                                                    │
│  MediaProjection ──→ BitmapCapture ──→ MJPEG流     │
│        │                   │                       │
│        │                   └──→ H264Encoder ──→ H264/H265流  │
│        │                                           │
│        └──→ AudioStreamer ──→ PCM音频流              │
│                                                    │
│  MjpegStreamingService (编排器)                     │
│        │                                           │
│        └──→ HttpServer (Ktor)                      │
│              ├── GET /           → index.html       │
│              ├── GET /voice.html → Command Center   │
│              ├── WS  /socket    → 控制信道          │
│              ├── WS  /stream/h264 → H264视频流      │
│              ├── WS  /stream/h265 → H265视频流      │
│              ├── WS  /stream/audio → 音频流         │
│              ├── GET /{stream}   → MJPEG流          │
│              └── installInputRoutes() → 全部控制API  │
│                                                    │
└────────────────────────────────────────────────────┘
         │                    ▲
         ▼                    │
┌─────── 浏览器端 ────────────┘
│
│  index.html (主投屏页)
│  ├── MJPEG: <img> 直接显示
│  ├── H264/H265: jmuxer.min.js → <video>
│  ├── 音频: WebSocket → AudioContext
│  ├── 触控: pointer events → /tap, /swipe API
│  ├── 键盘: keydown → /key API
│  └── 6模式导航: 导航/控制/系统/远程/宏/AI工具
│
│  voice.html (Command Center)
│  ├── 实时仪表盘 (5s 轮询)
│  ├── 30+ 功能按钮
│  └── 宏管理面板
│
└───────────────────────────────────────────────
```

## 十二、关键配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 端口 | 8080 | `MjpegSettings.Default.SERVER_PORT` |
| 编码格式 | MJPEG(0) | 可选 H264(1)/H265(2) |
| JPEG 质量 | 80 | 1-100 |
| 最大 FPS | 90 | 为 VR 模式提升（原 30） |
| 缩放因子 | 50% | 100=不缩放 |
| VR 模式 | 关闭(0) | 左眼(1)/右眼(2)/立体(3) |
| PIN 保护 | 关闭 | 5次错误自动封禁IP |
