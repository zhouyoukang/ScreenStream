# ScreenStream_v2 模块清单（MODULES）

> 目的：把“功能在哪里 / 入口在哪里 / 配置在哪里 / 风险在哪里”固定成可检索的权威索引。

## 0) 使用约定

- 只要你在项目里看到“同一能力有多个入口/多个端口/多个页面”，就必须：
  - 先在 `docs/adr/` 写 ADR
  - 再在本文件更新权威入口

## 1) 模块索引（主线）

| 模块 | 责任边界 | 代码入口（例） | 配置入口（例） | 相关 ADR | 相关 Skills |
|---|---|---|---|---|---|
| `app/` | UI、设置页面、用户交互入口 | `app/src/...` | UI 绑定的 Settings |  |  |
| `common/` | 日志、DI、通用模型、DataStore 等基础设施 | `common/src/...` | 共享 Settings / 工具 |  |  |
| `mjpeg/` | Web UI + MJPEG 输出、Ktor Server（对外入口之一） | `mjpeg/.../internal/HttpServer.kt` | `MjpegSettings`（模块内） | `adr/ADR-20260210-input-http-entrypoints.md` | |
| `input/` | 远程控制：Accessibility + 输入注入 + API + AI Brain + 宏系统 | `input/.../InputRoutes.kt`、`input/.../InputService.kt`、`input/.../MacroEngine.kt` | `input/.../settings/InputSettings.kt`（端口/开关） | `adr/ADR-20260210-input-http-entrypoints.md` | |
| `webrtc/` | WebRTC 输出链路 | `webrtc/src/...` | 模块 settings |  |  |
| `rtsp/` | RTSP 输出链路 | `rtsp/src/...` | 模块 settings |  |  |
| `Quest/VR 适配` | Quest/VR 浏览器兼容、裁切/交互策略（优先开关化） | 多分布于 `mjpeg/assets/index.html`、渲染链路 | URL 参数/设置项 |（必要时新建）| |

## 2) 端口与入口（必须唯一可解释）

> 这里不做“完整端口表”，只固定一个原则：任何端口/入口变更必须先 ADR。

- **MJPEG Server（主入口）**：
  - 实现：`mjpeg/.../internal/HttpServer.kt`
  - Web UI：`mjpeg/src/main/assets/index.html`
  - 已内置输入路由（70+ 端点）：
    - 基础控制：`/tap /swipe /pointer /key /text /home /back /recents /status /notifications`
    - 系统控制：`/volume /lock /quicksettings /wake /screenshot /power /brightness /rotate /stayawake /showtouches /media /findphone /vibrate /flashlight /dnd /autorotate`
    - 远程协助：`/splitscreen /longpress /doubletap /scroll /pinch /openapp /openurl /deviceinfo /apps /clipboard /foreground /killapp /upload`
    - AI Brain：`/viewtree /windowinfo /findclick /dismiss /findnodes /settext /command /ws/touch`
    - 宏系统：`/macro/list /macro/create /macro/run/{id} /macro/run-inline /macro/stop/{id} /macro/{id} /macro/update/{id} /macro/delete/{id} /macro/running /macro/log/{id} /macro/triggers /macro/trigger/{id}`
    - 文件管理：`/files/list /files/info /files/read /files/download /files/search /files/storage /files/mkdir /files/delete /files/rename /files/move /files/copy /files/upload`
    - 平台层：`/intent /screen/text /wait /notifications/read`
    - 智能家居：`/smarthome/status /smarthome/devices /smarthome/control /smarthome/scenes`
- **InputHttpServer（兼容入口）**：
  - 实现：`input/.../InputHttpServer.kt`
  - 启动：`input/.../InputKoinModule.kt`（由设置控制是否 autoStart）

## 3) 交付物与证据入口

- 文档权威入口：`05-文档_docs/README.md`
- 状态面板：`05-文档_docs/STATUS.md`
- 架构决策：`05-文档_docs/adr/`
- 愿景路线：`05-文档_docs/VISION.md`
- Windsurf Skills：`.windsurf/skills/`（9个项目技能）
- Windsurf Rules：`.windsurf/rules/`（6个结构化规则）
- AGENTS.md：8个目录级指令文件
