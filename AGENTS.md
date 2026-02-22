# ScreenStream_v2 项目指令

**核心目的**：通过PC浏览器远程操控Android手机的一切功能。
150+ 功能 · 70+ API · AI Brain · 宏系统 · 10个平台面板。

## 项目结构（整合后）

| 目录 | 模块 | 职责 |
|------|------|------|
| `010-用户界面与交互_UI/` | `:app` | Android主APP |
| `020-投屏链路_Streaming/` | `:mjpeg` `:rtsp` `:webrtc` | 投屏引擎 + HTTP服务器 + 前端 |
| `040-反向控制_Input/` | `:input` | **核心**：70+ API路由 + AccessibilityService |
| `070-基础设施_Infrastructure/` | `:common` | 模块管理/DI/工具/日志 |
| `080-配置管理_Settings/` | — | 全局+模块配置 |
| `090-构建与部署_Build/` | — | Gradle构建 + 部署脚本 |
| `100-智能家居_SmartHome/` | — | 智能家居网关：MiCloud直连+eWeLink+涂鸦+HA |
| `tools/ai-phone-control/` | — | AI操控手机：phone_lib.py + 3测试 + 实测发现 |
| `05-文档_docs/` | — | 12个核心文档 + adr/ |
| `管理/` | — | 归档（非核心项目/过时文档/历史产物） |

## 核心原则
- 修改前先确认关联模块（前后端必须同步）
- InputRoutes.kt 由 MJPEG HttpServer 共享挂载
- 端口固定：Gateway:8080 MJPEG:8081 RTSP:8082 WebRTC:8083 Input:8084

## 关键文件
- **路由**: `040-反向控制_Input/010-输入路由_Routes/InputRoutes.kt`
- **服务**: `040-反向控制_Input/020-输入服务_Service/InputService.kt`
- **前端**: `020-投屏链路_Streaming/010-MJPEG投屏_MJPEG/assets/index.html`
- **HTTP**: `020-投屏链路_Streaming/010-MJPEG投屏_MJPEG/mjpeg/internal/HttpServer.kt`
- **部署**: `090-构建与部署_Build/dev-deploy.ps1`
- **架构**: `CORE.md`（底层逻辑/数据流/API分类/面板索引）

## 文档入口
`CORE.md` → `05-文档_docs/FEATURES.md` → `STATUS.md` → `MODULES.md`

## 硬约束
- **构建串行**: 同时只有1个Agent执行Gradle构建
- **设备独占**: 同一Android设备同时只有1个Agent操作ADB
- **Zone 0冻结**: 禁止修改 ~/.codeium/windsurf/ 下任何文件
