# MJPEG 投屏模块 — v32

## 核心文件
- `mjpeg/MjpegModuleService.kt` — 服务生命周期，前台通知
- `mjpeg/MjpegStreamingService.kt` — 流媒体核心：网络发现→启动HTTP服务器→推送MJPEG帧
- `mjpeg/internal/HttpServer.kt` — Ktor 服务器，挂载投屏流 + InputRoutes
- `assets/index.html` — v32 前端：画面显示、4模式导航、WebSocket触控、手机沉浸模式

## 投屏流
- `/stream/mjpeg` — MJPEG over HTTP
- `/stream/h264` — H264 over WebSocket
- `/stream/h265` — H265 over WebSocket
- `/stream/audio` — 音频流 over WebSocket

## 前端能力（v32）
- **4模式导航栏**：导航→控制→系统控制→远程协助
- **WebSocket 实时触控**：/ws/touch（自动降级到 HTTP POST）
- **手机端沉浸模式**：自动检测移动浏览器→全屏+浮动☰按钮
- **设备信息面板**：电量/网络/存储/型号/音量/亮度/分辨率
- **VR 适配**：Quest 浏览器特殊处理（禁止自动聚焦输入框）

## 关键约束
- InputRoutes 共享路由挂载在此模块的 HttpServer 上（端口 8081）
- 前端键盘事件必须附带 shift/ctrl 修饰键状态
- `ContextCompat.startForegroundService()` + 立即 `startForeground()`

## 修改此模块时
- 改 index.html 的输入/触控逻辑 → 同步检查 InputRoutes 和 InputService
- 改 HttpServer 路由 → 确认不影响 InputRoutes 的共享挂载
- 新增前端模式/按钮 → 同步更新 `文档/USER_GUIDE_v31.md`

## 对话结束选项

> 任务完成后调用 `ask_user_question`，从下表选 4 个最贴合的：

| label | description |
|-------|-------------|
| 打开浏览器看看 | 编译安装，浏览器打开确认前端效果 |
| 继续打磨前端 | 优化界面交互/面板/快捷键 |
| 确保前后端一致 | 确认前端变更与后端API匹配 |
| 优化画面流畅度 | 改进投屏流的性能和质量 |
| 收工提交 | 记录成果 + git commit |
