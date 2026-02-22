## 总导航（中文一眼看全）

### 0) 先把“每个模块都有 src”讲明白

这是 **Gradle 多模块** 的正常结构，不是重复拷贝。

- 根目录 `settings.gradle.kts` 里 `include(":app")` / `include(":mjpeg")` 等定义了多个模块。
- 每个模块都是独立子工程，必须有自己的：
  - `src/main/java`（源码）
  - `src/main/res`（资源）
  - `src/main/AndroidManifest.xml`（清单）

因此 `src/` 在每个模块里出现是“正常且必须”的，不能合并成一份。

`.git/` 只应该在仓库根目录；当前仓库未发现模块内嵌套 `.git`（不存在“二次 clone”结构）。

---

## 1) 一级目录：你应该从这里开始看

### 运行时代码（对应 Gradle 模块）

- `01-应用与界面_app`（Gradle：`:app`）
  - 入口：
    - `01-应用与界面_app/src/main/java/info/dvkr/screenstream/BaseApp.kt`
    - `01-应用与界面_app/src/main/java/info/dvkr/screenstream/SingleActivity.kt`
- `02-基础设施_common`（Gradle：`:common`）
  - 总控：`02-基础设施_common/src/main/java/info/dvkr/screenstream/common/module/StreamingModuleManager.kt`
  - 全局设置：`02-基础设施_common/src/main/java/info/dvkr/screenstream/common/settings/AppSettingsImpl.kt`
- `03-投屏输出_MJPEG`（Gradle：`:mjpeg`）
  - 模块入口：`03-投屏输出_MJPEG/src/main/java/info/dvkr/screenstream/mjpeg/MjpegStreamingModule.kt`
  - 服务入口：`03-投屏输出_MJPEG/src/main/java/info/dvkr/screenstream/mjpeg/internal/MjpegStreamingService.kt`
  - HTTP 入口：`03-投屏输出_MJPEG/src/main/java/info/dvkr/screenstream/mjpeg/internal/HttpServer.kt`
- `03-投屏输出_RTSP`（Gradle：`:rtsp`）
  - 模块入口：`03-投屏输出_RTSP/src/main/java/info/dvkr/screenstream/rtsp/RtspStreamingModule.kt`
- `03-投屏输出_WebRTC`（Gradle：`:webrtc`）
  - 模块入口：`03-投屏输出_WebRTC/src/main/java/info/dvkr/screenstream/webrtc/WebRtcStreamingModule.kt`
- `04-反向控制_Input`（Gradle：`:input`）
  - 共享路由（单一权威）：`04-反向控制_Input/src/main/java/info/dvkr/screenstream/input/InputRoutes.kt`
  - 独立 API Server（兼容端口）：`04-反向控制_Input/src/main/java/info/dvkr/screenstream/input/InputHttpServer.kt`
  - Accessibility：`04-反向控制_Input/src/main/java/info/dvkr/screenstream/input/InputService.kt`

### 文档/技能/归档（管理层）

- `文档`
  - 入口：`文档/README.md`
  - 中文项目地图：`文档/PROJECT_MAP_CN.md`
  - ADR：`文档/adr/`
- `06-技能_skills`
  - 入口：`06-技能_skills/README.md`
- `管理/00-归档`
  - 归档噪音文件（analysis、构建输出、运行日志、截图、release 等）

---

## 2) 二级目录：你要找“投屏/反控/入口”最快路径

- 投屏模块选择（总入口）：`StreamingModuleManager` + `AppSettings` + `SingleActivity`。
- Input 入口（推荐理解方式）：
  - **统一入口（同源）**：MJPEG 的 `HttpServer.kt` 挂载 `installInputRoutes()`。
  - **兼容入口（独立端口）**：`InputHttpServer.kt` 也复用同一套路由（`InputRoutes.kt`）。

---

## 3) 重要工程文件（构建/结构的根）

- `settings.gradle.kts`：已用 `projectDir` 映射到中文目录。
- `.gitignore`：已用 `**/src/main/assets/server.p12` 防止证书文件暴露。
