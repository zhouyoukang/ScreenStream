# ADR-20260210-输入链路收敛（MJPEG HttpServer vs InputHttpServer）

## 背景

当前 `ScreenStream_v2` 同时存在两条 HTTP 服务链路：

- **MJPEG Web UI / Streaming**：`mjpeg/.../internal/HttpServer.kt`（Ktor embedded server）
- **Input API Server**：`input/.../InputHttpServer.kt`（Ktor embedded server）+ `input/.../InputKoinModule.kt`（自动启动）

补充一手现状：

- `mjpeg/.../internal/HttpServer.kt` 已内置输入路由（例如：`/tap`、`/swipe`、`/pointer`、`/key`、`/text`、`/home`、`/back`、`/recents`、`/status`、`start-stop`）。
- `mjpeg/src/main/assets/index.html` 的输入调用默认走 `window.location.origin`（同源），意味着 **Web UI 侧已经实现“单入口”**。
- 目前需要收敛的核心点变成：是否仍要 **默认自动启动** `InputHttpServer` 的独立端口（兼容端口），以及最终是否合并为单 server/单 port。

问题：

- **双入口/双端口**导致：
  - Web UI 与输入 API 的访问地址需要分别配置（FRP/反向代理场景更复杂）。
  - 鉴权/Pin/跨域策略容易分裂。
  - 用户理解成本高（“为什么视频是 8080/8081，而输入是 8084？”）。
- **模块职责不清**：Input 的 API 路由与 MJPEG 的 Web UI 路由在不同 server，后续扩展（键盘/剪贴板/权限提示/状态）会反复遇到“入口到底在哪”。

## 现状证据（入口）

- Input server 启动入口：
  - `ScreenStream_v2/input/src/main/java/info/dvkr/screenstream/input/InputKoinModule.kt`
  - `InputHttpServer(settings.data.value.apiPort)` + `autoStartHttp` 控制是否启动
- Input server 实现：
  - `ScreenStream_v2/input/src/main/java/info/dvkr/screenstream/input/InputHttpServer.kt`
  - 典型路由：`/status`、`/tap`、`/swipe`、`/key`、`/text`...
- MJPEG server 实现：
  - `ScreenStream_v2/mjpeg/src/main/java/info/dvkr/screenstream/mjpeg/internal/HttpServer.kt`

## 目标

- 对外表现为 **单入口/单端口**：
  - 同一个 base URL 能同时访问视频/页面/输入 API（或至少由同一入口统一转发/映射）。
- 保持模块化可维护：
  - Input 仍然是独立模块（业务逻辑与权限/Accessibility 不被 mjpeg 绑死）。
- 迁移风险可控：
  - 允许短期兼容旧端口/旧 URL。

## 决策

采用“分阶段收敛”的策略：

- **Phase 0（本 ADR）**：只做决策与执行步骤。
- **Phase 1（最小可落地，推荐优先）**：
  - 保留 `InputHttpServer` 实现不大改，但对外暴露“统一入口”能力。
  - 目标：用户只需要记一个入口；旧端口仍可用但被标注为“兼容”。
- **Phase 2（最终态）**：
  - Input API 路由与 MJPEG server 统一在同一个 Ktor server 上（单 server、单 port）。
  - Input 模块只提供路由注册能力（例如：`fun Route.installInputRoutes(...)` 或类似形式），由 MJPEG server 负责挂载。

## 备选方案

### 方案 A：继续维持双 server（现状延续）

- 优点：改动最小。
- 缺点：入口/端口/鉴权/FRP 配置长期分裂；后续持续返工。

### 方案 B：只做文档/参数层面的“软统一”

- 例如：Web UI 强制携带 `input_port` 参数，或者在 UI 中提示另一个端口。
- 优点：几乎不改代码。
- 缺点：仍然双入口；只是把复杂度推给用户。

### 方案 C：完全合并为单 Ktor server（推荐最终态）

- 优点：真正的单入口/单端口；维护成本最低。
- 缺点：需要处理模块依赖方向、路由挂载、权限生命周期等。

## 后果与影响面

- 需要明确：
  - Input API 是否需要 Pin/鉴权与 MJPEG 的 Pin 共用。
  - CORS 策略与跨域来源（本地/FRP）是否统一。
  - 输入相关的状态（connected/enabled/scaling/screenOffMode）是否应通过同一状态端点呈现。

## 执行步骤（可验收）

### Phase 1（建议先做）

1. 在 docs 中明确“统一入口”的推荐访问方式（只记一个 base URL）。
2. 统一对外文档参数：
   - 约定：如果存在 `input_port` / `input_base_url`，其默认值应与 MJPEG server 同源（或可推导）。
3. 加入验收：
   - 通过同一 base URL 能完成“看画面 + 点击/滑动/按键”。

### Phase 2（最终态）

1. 抽出 Input routes 的“可挂载”形态（由 MJPEG server 统一挂载）。
2. 移除/关闭独立的 `InputHttpServer` 自动启动（保留兼容开关）。
3. 将输入相关状态端点合并到统一 server。

## 落地结果（Phase-2 实现状态）

已落地 Phase-2 的“路由单一权威”实现：

- Input 模块新增共享路由：`ScreenStream_v2/input/.../InputRoutes.kt`（`installInputRoutes()`）。
- MJPEG server 挂载共享路由：`ScreenStream_v2/mjpeg/.../internal/HttpServer.kt`（在同源 server 上调用 `installInputRoutes()`）。
- `InputHttpServer` 改为复用同一共享路由：`ScreenStream_v2/input/.../InputHttpServer.kt`（作为可选兼容端口时也不会出现第二套路由实现）。

当前仍保留兼容端口的开关与端口配置：

- `InputSettings.Data.autoStartHttp/apiPort`

## 验收标准

- 文档层：
  - docs/README/STATUS/ADR 指向一致，没有“入口冲突”的描述。
- 功能层：
  - 用户使用时只需要一个入口地址；输入与视频在同一入口下可用。
- 兼容层：
  - 旧端口仍可用（或有明确迁移说明）。
