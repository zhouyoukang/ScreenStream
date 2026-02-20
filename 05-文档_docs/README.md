# ScreenStream_v2 文档中心（权威入口）

> 版本：v32+ (AI Brain + 宏系统) | 更新：2026-02-13

## 快速导航

| 文档 | 用途 |
|------|------|
| `STATUS.md` | 状态面板：现在到哪/下一步/风险 |
| `MODULES.md` | 模块清单：代码入口/配置/端口映射 |
| `FEATURES.md` | 功能管理：59 个 API 端点的完整登记 |
| `PROCESS.md` | 标准流程：证据定位→差异→方案→实现→验收→归档 |
| `VISION.md` | 演进路线：5 阶段（投屏→远程→自动化→AI Agent→超级助理）|
| `ARCHITECTURE_v32.md` | v32 三层架构：宿主 + API + AI Brain |
| `USER_GUIDE_v31.md` | 使用指南(v31)：操作方法+API参考+FAQ |
| **`USER_GUIDE_v32plus.md`** | **⭐ 最新综合指南：全功能+一键部署+宏系统+示例** |
| `MERGE_ARCHIVE_CHECKLIST.md` | 合并清单：Quest vs v2 差异对照（9条） |
| `adr/` | 架构决策记录 |

## 项目定位

- **主线**：`ScreenStream_v2` 为唯一主线
- **合并策略**：Quest/上游差异以配置/开关实现，不维护分支
- **端口标准**：Gateway:8080 MJPEG:8081 RTSP:8082 WebRTC:8083 Input:8084

## Gradle 模块映射

| Gradle | 中文目录 | 职责 |
|--------|---------|------|
| `:app` | `010-用户界面与交互_UI/` | 主界面、设置、通知 |
| `:common` | `070-基础设施_Infrastructure/` | DI、设置、通用模型 |
| `:mjpeg` | `020-投屏链路_Streaming/010-MJPEG投屏_MJPEG/` | Web UI + Ktor Server |
| `:rtsp` | `020-投屏链路_Streaming/020-RTSP投屏_RTSP/` | RTSP 输出链路 |
| `:webrtc` | `020-投屏链路_Streaming/030-WebRTC投屏_WebRTC/` | WebRTC 输出链路 |
| `:input` | `040-反向控制_Input/` | 远程控制 + AI Brain |

## ADR 规则

以下变更**必须先写 ADR**（`adr/ADR-YYYYMMDD-<主题>.md`）：
- 端口/入口统一策略
- 对外 API 变更
- Quest/VR 适配取舍
- 鉴权/安全策略

## AI 配置体系

- **规则**：`.windsurf/rules/`（7 个结构化规则）
- **技能**：`.windsurf/skills/`（8 个项目技能）
- **AGENTS.md**：8 个目录级指令
- **工作流**：`.windsurf/workflows/`（9 个标准工作流）
- **部署**：`090-构建与部署_Build/dev-deploy.ps1`（一键编译→安装→启用→验证）
