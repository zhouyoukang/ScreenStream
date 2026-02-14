# ScreenStream_v2 项目地图（中文索引：模块 / 功能 / 入口 / 配置 / ADR / Skill）

> 目标：解决“英文理解弱 + 工程入口分散”的问题。
>
> 原则：**不靠重命名代码/目录**来中文化（那是高风险）；先用“中文索引 + 权威入口映射”把项目管理做扎实。

Refs：

- 权威入口：`docs/README.md`
- 模块索引：`docs/MODULES.md`
- 功能索引：`docs/FEATURES.md`
- 流程：`docs/PROCESS.md`
- Skills：`docs/SKILLS.md`、`skills/README.md`

## 1) 模块地图（中文）

> 说明：模块名保持代码一致（英文/目录名不动），这里给中文职责与“入口定位法”。

| 模块（目录） | 中文职责 | 代码入口（示例/定位点） | 配置入口（示例/定位点） | ADR | Skills |
|---|---|---|---|---|---|
| `app/` | App UI、设置页、用户入口 | `app/src/...`（Compose UI/入口 Activity） | UI 绑定的 settings | （按需） | `skill-ssv2-release-checklist` |
| `common/` | 共享基础设施（日志/DI/模型/DataStore） | `common/src/...` | 共享 settings/工具 |  |  |
| `mjpeg/` | Web UI + MJPEG 输出 + Ktor HTTP 主入口 | `mjpeg/.../internal/HttpServer.kt`；`mjpeg/src/main/assets/index.html` | `MjpegSettings`（模块内） | `ADR-20260210-input-http-entrypoints` | `skill-ssv2-input-unify` |
| `input/` | 远程输入控制（Accessibility + 注入 + API） | `input/.../InputService.kt`；`InputHttpServer.kt`；`InputRoutes.kt` | `input/.../settings/InputSettings.kt`（端口/开关/PIN） | `ADR-20260210-input-http-entrypoints` | `skill-ssv2-input-unify` |
| `webrtc/` | WebRTC 输出链路 | `webrtc/src/...` | 模块 settings（如有） |  |  |
| `rtsp/` | RTSP 输出链路 | `rtsp/src/...` | 模块 settings（如有） |  |  |
| `Quest/VR 适配` | Quest/VR 浏览器兼容与交互策略（优先开关化） | 多分布于 Web UI / 输出链路 | URL 参数/设置项 |（按需新建）| `skill-ssv2-merge-plan` |

## 2) 端口 / 入口地图（中文）

| 入口类型 | 中文说明 | 实现入口 | 约束 |
|---|---|---|---|
| MJPEG Server（主入口） | 主 HTTP 入口：Web UI + MJPEG 流 +（同源）输入路由 | `mjpeg/.../internal/HttpServer.kt` | 端口/入口变更必须先 ADR |
| Web UI | 浏览器端控制台/交互层 | `mjpeg/src/main/assets/index.html` | 输入 API 默认同源调用 |
| InputHttpServer（兼容入口） | 可选的独立输入 API 端口（兼容/旧场景） | `input/.../InputHttpServer.kt`；`InputKoinModule.kt` 控制自启 | 必须复用同一套 routes，避免漂移 |

## 3) 功能地图（中文）

> 当前 `docs/FEATURES.md` 还是“骨架”，这里补一个中文优先的映射表（先覆盖最核心路径，后续迭代补全）。

| 功能（中文） | 用户可见入口 | 代码入口（定位点） | 配置入口 | 验收（最小） | ADR | Skill |
|---|---|---|---|---|---|---|
| 远程输入控制（tap/swipe/key/text） | Web UI | `mjpeg/.../HttpServer.kt` + `input/.../InputRoutes.kt` + `InputService.kt` | `input/.../settings/InputSettings.kt`（enable/scaling/port/pin） | Web UI 点击/滑动/按键可用 | `ADR-20260210-input-http-entrypoints` | `skill-ssv2-input-unify` |
| 终端证据收集/命令分组 | 终端/IDE | `docs/TERMINAL_RUNBOOK.md` |（无）| 一次性拿到可复查证据包 |（无）| `skill-ssv2-terminal-runbook` |
| 合并/归档清单维护 | docs | `docs/MERGE_ARCHIVE_CHECKLIST.md` |（无）| 每条差异都有入口/计划/验收 |（按需）| `skill-ssv2-merge-plan` |
| 构建/发布/验收清单 | docs/终端 |（以 Gradle 为主） |（无）| 产物可构建、验收步骤可复现 |（按需）| `skill-ssv2-release-checklist` |

## 4) 中文化策略（重要：避免高风险“全量重命名”）

你提到“把以前名字都改中文/把整个项目文件夹重构”。这里给一个**效率最高且风险最低**的中文化路线（从低风险到高风险）：

1. **文档中文索引（推荐）**
   - 目录/类名不动
   - 用本文件 + `docs/MODULES.md` / `docs/FEATURES.md` 提供中文别名与入口定位
2. **UI 文案中文化（中风险，可控）**
   - 只改可见字符串（不改包名/类名）
3. **代码符号/目录重命名（高风险，不建议默认做）**
   - 需要全局重命名、Gradle/Manifest/引用迁移、测试与回归
   - 一次重命名会让 `git blame`、diff、合并成本显著上升

结论：为了“最高效率推进开发 + 不混乱”，优先采用 **第 1 层（文档索引）**，在你确实需要“对外展示/团队协作”时，再按模块逐个评估第 2/3 层。

## 5) 后续迭代方式（你只要持续给我需求，我负责把表补齐）

- 新增/调整功能：
  - 同步更新：`docs/FEATURES.md` + 本文件对应行
- 新发现入口/端口重复：
  - 先写 ADR，再更新：`docs/MODULES.md` + 本文件
- 新出现高频重复推进：
  - 新建 skill，并在：`docs/SKILLS.md` + `skills/README.md` + 本文件挂上链接
