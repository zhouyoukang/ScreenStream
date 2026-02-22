# 投屏链路模块 (Streaming)

包含三种投屏协议实现，平级隔离，互不依赖。

## 子模块
- `MJPEG投屏/` — MJPEG over HTTP，主力协议，InputRoutes 共享挂载于此
- `RTSP投屏/` — RTSP 实时传输协议
- `WebRTC投屏/` — WebRTC 浏览器直连

## 关键约束
- 三个子模块平级隔离，禁止互相依赖
- 都依赖 `:common`（070-基础设施）
- 前台服务必须 ContextCompat.startForegroundService() + 立即 startForeground()
- 修改任一子模块时，评估是否需要同步修改其他两个

## 对话结束选项

> 任务完成后，AI 必须调用 `ask_user_question` 从以下选项中选取 4 个最相关的：

| label | description |
|-------|-------------|
| 编译部署测试 | Gradle构建→推送→安装→启动投屏验证 |
| 同步其他协议 | 检查MJPEG/RTSP/WebRTC三模块是否需要同步修改 |
| 优化投屏性能 | 继续改进帧率/延迟/编码质量 |
| 更新文档提交 | 更新FEATURES.md/ARCHITECTURE + git commit |
