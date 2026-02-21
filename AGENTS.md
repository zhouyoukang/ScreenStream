# ScreenStream_v2 项目指令

Android 屏幕投屏+远程控制+AI Brain+宏系统+AI工具箱 应用。当前版本 **v32+**，72 个功能点。

## 核心原则
- 修改任何文件前，先确认影响的关联模块（前后端必须同步）
- 输入路由（InputRoutes.kt）由 MJPEG HttpServer 共享挂载
- 端口固定：Gateway:8080 MJPEG:8081 RTSP:8082 WebRTC:8083 Input:8084
- 端口/入口/鉴权变更 → 先写 ADR (`05-文档_docs/adr/`)

## 技术栈
- **语言**: Kotlin (Android) + HTML/JS (前端)
- **框架**: Ktor (HTTP), AccessibilityService (输入控制), WebSocket (实时触控)
- **构建**: Gradle, FDroid flavor, `dev-deploy.ps1` 一键部署
- **投屏**: MJPEG / H264 / H265 over HTTP/WebSocket, RTSP, WebRTC

## 能力矩阵（v32）
- **投屏**：MJPEG/H264/H265 + 音频流
- **基础控制**：触控/滑动/键盘/导航/文本输入
- **系统控制**（v30）：音量/锁屏/通知栏/快捷设置
- **远程协助**（v31）：唤醒/截屏/电源/亮度/长按/双击/滚动/捏合/打开APP/设备信息/剪贴板
- **AI Brain**（v32）：View树分析/语义化点击/节点搜索/智能关闭弹窗/WebSocket实时触控

## 关键文件
- **路由**: `040-反向控制_Input/010-输入路由_Routes/InputRoutes.kt`
- **服务**: `040-反向控制_Input/020-输入服务_Service/InputService.kt`
- **前端**: `020-投屏链路_Streaming/010-MJPEG投屏_MJPEG/assets/index.html`
- **HTTP**: `020-投屏链路_Streaming/010-MJPEG投屏_MJPEG/mjpeg/internal/HttpServer.kt`
- **部署**: `090-构建与部署_Build/dev-deploy.ps1`

## 文档入口
`05-文档_docs/README.md` → `STATUS.md` → `MODULES.md` → `FEATURES.md` → `VISION.md`

## 多Agent并行（Worktree 架构）

**并行开发使用 Windsurf Worktree 模式**：每个 Cascade 在独立 git worktree 中工作，物理隔离。

### 操作
1. 新开 Cascade 对话 → 底部右下角切换 **Worktree 模式** → 发任务
2. Agent 在隔离副本中工作，不影响主工作区
3. 完成后点 **Merge** 合并回主分支

### 仍需遵守
- **构建串行**: 同时只有1个Agent执行Gradle构建
- **设备独占**: 同一Android设备同时只有1个Agent操作ADB
- **Zone 0冻结**: 禁止修改 ~/.codeium/windsurf/ 下任何文件
