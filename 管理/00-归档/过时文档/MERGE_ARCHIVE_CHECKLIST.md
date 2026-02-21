# ScreenStream_v2 合并 / 归档清单（以 v2 为主线）

> 目的：把 `ScreenStream_Quest` / 上游差异吸收为“可开关/配置”，并避免出现第二条代码线。

## 0) 基本原则

- 主线只认：`ScreenStream_v2`
- 合并方式：
  - 能配置就不分叉
  - 能开关就不复制
  - 能设备判定就不维护第二套 UI/逻辑
- 每条差异必须绑定：
  - **代码入口**（文件/类/函数）
  - **配置入口**（Setting/参数/默认值）
  - **文档入口**（docs/README + ADR）

## 1) 需要对照的工程

- `ScreenStream_v2/`（主线）
- `ScreenStream_Quest/`（差异来源之一）
- （可选）上游 GitHub repo（如存在，按目录对照）

## 2) 文件级差异清单模板（逐条登记）

> 使用方式：每发现一条差异，就新增一条记录；不要把差异“藏在脑子里”。

| # | 来源 | 类型 | 差异点描述 | v2 入口 | Quest/上游入口 | 计划吸收方式（开关/配置/设备判定） | 风险 | 验收 |
|---:|---|---|---|---|---|---|---|---|
| 1 | Quest | 功能 | 例：VR 裁切策略不同 | `mjpeg/...` | `...` | 设备判定 + 开关 | 中 | Quest 浏览器验收 |

| 2 | Quest | 入口/端口 | Web UI 输入 API 依赖 `input_port` + 独立输入端口（默认 8085），通过 `protocol//hostname:input_port` 访问 | `ScreenStream_v2/mjpeg/src/main/assets/index.html`（`getInputApiBase()` 默认 `window.location.origin`；`input_port` 目前不再作为主路径） | `ScreenStream_Quest/mjpeg/src/main/assets/index.html`（`input_port` 默认 8085；`getInputApiBase()` 拼接独立端口） | 主线采用同源单入口；保留 `InputHttpServer` 作为可选兼容端口（由设置控制） | 中 | Quest/手机浏览器：同一 base URL 下输入可用；FRP 场景不再要求额外配置 input_port |

| 3 | Quest | 行为/配置 | InputHttpServer 启动策略：Quest 强制启动用于验证；v2 受 `autoStartHttp` 控制 | `ScreenStream_v2/input/.../InputKoinModule.kt`（`autoStartHttp` 控制是否启动）+ `InputSettings.Default.API_PORT=8084` | `ScreenStream_Quest/input/.../InputKoinModule.kt`（强制 `server.start()`）+ `InputSettings.Default.API_PORT=8085` | v2 保持“兼容端口可控”，并将路由定义收敛为单一权威（共享 routes） | 中 | 打开/关闭 autoStartHttp 后，兼容端口行为符合预期；同源入口始终可用 |

| 4 | Quest | 架构 | MJPEG server 是否内置输入路由：v2 内置且可同源调用；Quest MJPEG server 未发现输入路由（输入走独立 server） | `ScreenStream_v2/mjpeg/.../internal/HttpServer.kt`（已挂载 input routes） | `ScreenStream_Quest/mjpeg/.../internal/HttpServer.kt`（未检出 `/tap` 等路由） + `ScreenStream_Quest/input/InputHttpServer.kt` | 以 v2 为主线：输入 routes 统一在 input 模块定义，并由 MJPEG server 挂载；独立输入 server 仅做兼容 | 中 | 同源入口输入正常；兼容端口仍可选启用；两端行为一致 |

| 5 | Quest | 一致性 | `common/src`：Quest vs v2 无差异（`git diff --no-index --name-status -- ScreenStream_Quest/common/src ScreenStream_v2/common/src` 输出为空） | `ScreenStream_v2/common/src` | `ScreenStream_Quest/common/src` | 无需吸收；后续仅在 v2 主线改动 | 低 | 再次对比仍为空；构建不受影响 |

| 6 | Quest | 一致性 | `webrtc/src`：Quest vs v2 无差异（`git diff --no-index --name-status -- ScreenStream_Quest/webrtc/src ScreenStream_v2/webrtc/src` 输出为空） | `ScreenStream_v2/webrtc/src` | `ScreenStream_Quest/webrtc/src` | 无需吸收；后续仅在 v2 主线改动 | 低 | 再次对比仍为空；构建不受影响 |

| 7 | Quest | 一致性 | `rtsp/src`：Quest vs v2 无差异（`git diff --no-index --name-status -- ScreenStream_Quest/rtsp/src ScreenStream_v2/rtsp/src` 输出为空） | `ScreenStream_v2/rtsp/src` | `ScreenStream_Quest/rtsp/src` | 无需吸收；后续仅在 v2 主线改动 | 低 | 再次对比仍为空；构建不受影响 |

| 8 | Quest | 一致性+差异 | `app/src`：Quest 34个.kt vs V2 38个.kt。**Quest 独有2个**：`AppLogger.kt`（日志收集UI）、`CollectingLogsUi.kt`（日志显示）。**V2 独有10个**：`FakeScreenOffActivity.kt` `AdaptiveBanner.kt` `InputModuleSettings.kt` `InputSettingsUI.kt` `InputGeneralGroup.kt` `NotificationHelper.kt` `composeExtenstions.kt` `DoubleClickProtection.kt` `ExpandableCard.kt` `MediaProjectionPermission.kt` | `ScreenStream_v2/010-用户界面与交互_UI/` | `ScreenStream_Quest/app/src/` | Quest 独有的日志功能可按需吸收为开关；V2 新增的 Input 设置 UI、通用组件是主线新增不需吸收 | 低 | 日志功能如需要，从 Quest 提取并适配到 V2 目录结构 |

| 9 | Quest | 结构 | `app/src` 目录结构：Quest 使用标准 `src/main/java/...` 扁平结构；V2 重组为中文子目录（`010-主界面_MainUI/` `020-设置界面_SettingsUI/` `030-通知系统_Notifications/` `040-瓦片服务_Tiles/` `050-通用组件_CommonUI/`）| `ScreenStream_v2/010-用户界面与交互_UI/` 各子目录 | `ScreenStream_Quest/app/src/` | 无需吸收，V2 结构更清晰 | 低 | 编译通过即可 |

## 3) 推荐优先对照的目录（按收益排序）

- `ScreenStream_v2/app/`
  - UI 入口、设置项呈现、功能开关位置
- `ScreenStream_v2/common/`
  - 日志、DI、设置模型、跨模块共享工具
- `ScreenStream_v2/mjpeg/`
  - Web UI、Ktor server、VR 适配参数
- `ScreenStream_v2/input/`
  - 输入注入、HTTP API、鉴权/Pin
- `ScreenStream_v2/webrtc/` / `rtsp/`
  - 输出链路差异（编解码/参数/兼容）

## 4) 归档策略（不删，只收敛）

- 任何从 Quest/上游“吸收完成”的旧实现：
  - 优先：变成 **配置/开关**（保留在 v2）
  - 次选：移动到 `archive/`（仅当你明确允许）
- 禁止：
  - 直接删除历史文件（除非你明确要求）

## 5) 输出与验收

- 输出文件：
  - 本清单持续追加
  - 每个架构级取舍必须补 ADR（`docs/adr/ADR-*.md`）
- 验收：
  - 能从 docs/README 快速定位到每条差异的入口与状态
  - 合并后仍保持单主线可构建、可运行
